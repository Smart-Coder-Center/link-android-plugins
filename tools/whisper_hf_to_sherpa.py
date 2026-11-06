#!/usr/bin/env python3
"""Convert a Hugging Face fine-tuned Whisper checkpoint to Sherpa-ONNX files.

This is an experimental, fail-closed conversion tool for Link. It:
  1. pins the Hugging Face source to an immutable commit,
  2. maps every HF Whisper tensor into OpenAI Whisper's model structure,
  3. checks tokenizer probes and special-token IDs,
  4. compares HF and OpenAI forward logits before exporting,
  5. invokes the matching Sherpa-ONNX exporter and records hashes.

It does not publish a Link catalog entry. Run it in a dedicated environment with
enough RAM/VRAM and disk space; large-v3 checkpoints require substantial memory.
"""

from __future__ import annotations

import argparse
import gc
import hashlib
import importlib.util
import json
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

SUPPORTED = {
    "givia/whisper-large-v3-turbo-persian": {
        "base": "turbo",
        "prefix": "large-v3-turbo-persian",
        "license": "CC-BY-4.0",
        "feature_dim": 128,
    },
    "areffarhadi/Taraneh-WMedium": {
        "base": "medium",
        "prefix": "taraneh-wmedium",
        "license": "MIT",
        "feature_dim": 80,
    },
    "nezamisafa/whisper-persian-v4": {
        "base": "large-v3",
        "prefix": "whisper-persian-v4",
        "license": "Apache-2.0",
        "feature_dim": 128,
    },
}

HF_ALLOW_PATTERNS = [
    "config.json",
    "model.safetensors",
    "model.safetensors.index.json",
    "model-*.safetensors",
    "generation_config.json",
    "tokenizer.json",
    "vocab.json",
    "merges.txt",
    "added_tokens.json",
    "special_tokens_map.json",
    "tokenizer_config.json",
    "preprocessor_config.json",
    "processor_config.json",
    "normalizer.json",
]

EXPECTED_CONFIGS = {
    "givia/whisper-large-v3-turbo-persian": {
        "num_mel_bins": 128, "d_model": 1280, "encoder_layers": 32,
        "encoder_attention_heads": 20, "decoder_layers": 4,
        "decoder_attention_heads": 20, "max_source_positions": 1500,
        "max_target_positions": 448, "vocab_size": 51866,
    },
    "areffarhadi/Taraneh-WMedium": {
        "num_mel_bins": 80, "d_model": 1024, "encoder_layers": 24,
        "encoder_attention_heads": 16, "decoder_layers": 24,
        "decoder_attention_heads": 16, "max_source_positions": 1500,
        "max_target_positions": 448, "vocab_size": 51866,
    },
    "nezamisafa/whisper-persian-v4": {
        "num_mel_bins": 128, "d_model": 1280, "encoder_layers": 32,
        "encoder_attention_heads": 20, "decoder_layers": 32,
        "decoder_attention_heads": 20, "max_source_positions": 1500,
        "max_target_positions": 448, "vocab_size": 51866,
    },
}


PROBES = [
    "سلام، حال شما چطوره؟",
    "امروز می‌خواهم یک پیام صوتی کوتاه بفرستم.",
    "نمی‌دونم، شاید فردا ساعت ۱۲:۳۰ تماس بگیریم.",
    "لینک؛ تبدیل گفتار به نوشتار فارسی.",
    "این یک آزمایش برای کلمات کوتاه است: بله، نه، خوب.",
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_model_config(config: dict[str, Any], model_id: str) -> None:
    if config.get("model_type") != "whisper":
        raise RuntimeError(f"Expected Whisper config, got {config.get('model_type')}")
    expected = EXPECTED_CONFIGS[model_id]
    mismatches = {
        key: (value, config.get(key))
        for key, value in expected.items()
        if config.get(key) != value
    }
    if mismatches:
        raise RuntimeError(
            f"{model_id} checkpoint does not match its declared Whisper architecture: {mismatches}"
        )


def dimensions_from_config(config: Any):
    from whisper.model import ModelDimensions

    mel = int(config.num_mel_bins)
    if mel not in (80, 128):
        raise RuntimeError(f"Unsupported HF mel dimension: {mel}")
    dims = ModelDimensions(
        n_mels=mel,
        n_audio_ctx=int(config.max_source_positions),
        n_audio_state=int(config.d_model),
        n_audio_head=int(config.encoder_attention_heads),
        n_audio_layer=int(config.encoder_layers),
        n_vocab=int(config.vocab_size),
        n_text_ctx=int(config.max_target_positions),
        n_text_state=int(config.d_model),
        n_text_head=int(config.decoder_attention_heads),
        n_text_layer=int(config.decoder_layers),
    )
    return dims


def map_key(key: str) -> str | None:
    """Map one HF Transformers Whisper state-dict key to OpenAI Whisper."""
    direct = {
        "model.encoder.conv1.weight": "encoder.conv1.weight",
        "model.encoder.conv1.bias": "encoder.conv1.bias",
        "model.encoder.conv2.weight": "encoder.conv2.weight",
        "model.encoder.conv2.bias": "encoder.conv2.bias",
        "model.encoder.embed_positions.weight": "encoder.positional_embedding",
        "model.encoder.layer_norm.weight": "encoder.ln_post.weight",
        "model.encoder.layer_norm.bias": "encoder.ln_post.bias",
        "model.decoder.embed_tokens.weight": "decoder.token_embedding.weight",
        "model.decoder.embed_positions.weight": "decoder.positional_embedding",
        "model.decoder.layer_norm.weight": "decoder.ln.weight",
        "model.decoder.layer_norm.bias": "decoder.ln.bias",
    }
    if key in direct:
        return direct[key]

    match = re.fullmatch(
        r"model\.(encoder|decoder)\.layers\.(\d+)\."
        r"(self_attn|encoder_attn)\.(q_proj|k_proj|v_proj|out_proj)\.(weight|bias)",
        key,
    )
    if match:
        stack, layer, attention, projection, parameter = match.groups()
        if stack == "encoder" and attention == "encoder_attn":
            return None
        block = "attn" if attention == "self_attn" else "cross_attn"
        projection_name = {
            "q_proj": "query",
            "k_proj": "key",
            "v_proj": "value",
            "out_proj": "out",
        }[projection]
        return f"{stack}.blocks.{layer}.{block}.{projection_name}.{parameter}"

    match = re.fullmatch(
        r"model\.(encoder|decoder)\.layers\.(\d+)\."
        r"(self_attn_layer_norm|encoder_attn_layer_norm|final_layer_norm)\.(weight|bias)",
        key,
    )
    if match:
        stack, layer, norm, parameter = match.groups()
        if norm == "encoder_attn_layer_norm":
            if stack != "decoder":
                return None
            target = "cross_attn_ln"
        elif norm == "self_attn_layer_norm":
            target = "attn_ln"
        else:
            target = "mlp_ln"
        return f"{stack}.blocks.{layer}.{target}.{parameter}"

    match = re.fullmatch(
        r"model\.(encoder|decoder)\.layers\.(\d+)\.(fc1|fc2)\.(weight|bias)",
        key,
    )
    if match:
        stack, layer, linear, parameter = match.groups()
        index = "0" if linear == "fc1" else "2"
        return f"{stack}.blocks.{layer}.mlp.{index}.{parameter}"

    # WhisperForConditionalGeneration exposes a tied output projection. The
    # target OpenAI Whisper model computes logits from token_embedding directly.
    if key == "proj_out.weight":
        return None
    return None


def strict_map_weights(hf_model: Any, openai_model: Any) -> list[dict[str, Any]]:
    import torch

    source = hf_model.state_dict()
    target = openai_model.state_dict()
    mapped: dict[str, Any] = {}
    report: list[dict[str, Any]] = []
    ignored: list[str] = []

    for source_key, tensor in source.items():
        target_key = map_key(source_key)
        if target_key is None:
            if source_key == "proj_out.weight":
                tied = source.get("model.decoder.embed_tokens.weight")
                if tied is None or not torch.equal(tensor.cpu(), tied.cpu()):
                    raise RuntimeError("HF proj_out.weight is not tied to decoder token embeddings")
            else:
                ignored.append(source_key)
            continue
        if target_key in mapped:
            raise RuntimeError(f"Duplicate destination tensor: {target_key}")
        if target_key not in target:
            raise RuntimeError(f"Destination tensor does not exist: {target_key}")
        if tuple(tensor.shape) != tuple(target[target_key].shape):
            raise RuntimeError(
                f"Shape mismatch {source_key} -> {target_key}: "
                f"{tuple(tensor.shape)} != {tuple(target[target_key].shape)}"
            )
        mapped[target_key] = tensor
        report.append({
            "source": source_key,
            "destination": target_key,
            "source_shape": list(tensor.shape),
            "destination_shape": list(target[target_key].shape),
            "max_abs_difference_after_mapping": 0.0,
        })

    missing = sorted(set(target) - set(mapped))
    if missing:
        raise RuntimeError("Unmapped OpenAI Whisper tensors: " + ", ".join(missing[:30]))
    # No unrecognized trainable model tensors may be silently ignored.
    unexpected = [key for key in ignored if not key.endswith("num_batches_tracked")]
    if unexpected:
        raise RuntimeError("Unrecognized HF tensors: " + ", ".join(unexpected[:30]))

    try:
        openai_model.load_state_dict(mapped, strict=True, assign=True)
    except TypeError:
        openai_model.load_state_dict(mapped, strict=True)

    loaded = openai_model.state_dict()
    for entry in report:
        source_tensor = source[entry["source"]].detach().cpu()
        target_tensor = loaded[entry["destination"]].detach().cpu()
        if not torch.equal(source_tensor, target_tensor):
            difference = float((source_tensor.float() - target_tensor.float()).abs().max().item())
            raise RuntimeError(
                f"Tensor changed during assignment: {entry['source']} -> "
                f"{entry['destination']} (max_abs={difference})"
            )
        entry["max_abs_difference_after_mapping"] = 0.0
    return report


def verify_special_token_inventory(hf_tokenizer: Any, openai_tokenizer: Any) -> dict[str, Any]:
    """Require the HF added-token inventory to match OpenAI Whisper exactly."""
    encoding = getattr(openai_tokenizer, "encoding", None)
    expected_special = getattr(encoding, "_special_tokens", None)
    if not isinstance(expected_special, dict) or not expected_special:
        raise RuntimeError("Cannot inspect OpenAI Whisper special-token inventory")

    hf_vocab_size = len(hf_tokenizer)
    openai_vocab_size = int(encoding.n_vocab)
    if hf_vocab_size != openai_vocab_size:
        raise RuntimeError(
            f"Tokenizer vocabulary size mismatch: HF={hf_vocab_size}, "
            f"OpenAI={openai_vocab_size}"
        )

    hf_added = hf_tokenizer.get_added_vocab()
    mismatches = []
    for token, expected_id in expected_special.items():
        actual_id = hf_tokenizer.convert_tokens_to_ids(token)
        if actual_id != expected_id:
            mismatches.append((token, expected_id, actual_id))
    unknown_added = [
        (token, token_id) for token, token_id in hf_added.items()
        if token not in expected_special or expected_special[token] != token_id
    ]
    if mismatches or unknown_added:
        raise RuntimeError(
            "Whisper special-token inventory mismatch: "
            f"wrong_ids={mismatches[:12]}, unexpected_hf_added_tokens={unknown_added[:12]}"
        )
    return {
        "hf_vocabulary_size": hf_vocab_size,
        "openai_vocabulary_size": openai_vocab_size,
        "special_token_count": len(expected_special),
        "hf_added_token_count": len(hf_added),
        "all_special_token_ids_match": True,
    }


def verify_tokenizer(processor: Any, base_model: str) -> dict[str, Any]:
    from whisper.tokenizer import get_tokenizer

    hf_tokenizer = processor.tokenizer
    openai_tokenizer = get_tokenizer(multilingual=True, num_languages=99)
    inventory_report = verify_special_token_inventory(hf_tokenizer, openai_tokenizer)
    comparisons = []
    for text in PROBES:
        hf_ids = hf_tokenizer.encode(text, add_special_tokens=False)
        openai_ids = openai_tokenizer.encode(text)
        if hf_ids != openai_ids:
            raise RuntimeError(
                "Tokenizer mismatch for probe "
                + repr(text)
                + f": HF={hf_ids[:20]} OpenAI={openai_ids[:20]}"
            )
        comparisons.append({"text": text, "token_count": len(hf_ids), "ids_match": True})

    hf_fa = hf_tokenizer.convert_tokens_to_ids("<|fa|>")
    openai_fa = openai_tokenizer.to_language_token("fa")
    special = {
        "fa": [int(hf_fa), int(openai_fa)],
        "transcribe": [
            int(hf_tokenizer.convert_tokens_to_ids("<|transcribe|>")),
            int(openai_tokenizer.transcribe),
        ],
        "no_timestamps": [
            int(hf_tokenizer.convert_tokens_to_ids("<|notimestamps|>")),
            int(openai_tokenizer.no_timestamps),
        ],
    }
    for name, ids in special.items():
        if ids[0] != ids[1]:
            raise RuntimeError(f"Tokenizer special-token mismatch ({name}): {ids}")
    return {
        "base_model": base_model,
        "probes": comparisons,
        "special_token_ids": special,
        "inventory": inventory_report,
    }


def verify_forward_parity(hf_model: Any, openai_model: Any, feature_dim: int, device: str):
    import torch
    from whisper.tokenizer import get_tokenizer

    torch.manual_seed(20261106)
    mel = torch.randn(1, feature_dim, 3000, dtype=torch.float32)
    tok = get_tokenizer(multilingual=True, num_languages=99)
    tokens = torch.tensor(
        [[tok.sot, tok.to_language_token("fa"), tok.transcribe, tok.no_timestamps]],
        dtype=torch.long,
    )

    hf_model.eval()
    hf_model.to(device)
    with torch.inference_mode():
        hf_logits = hf_model(
            input_features=mel.to(device),
            decoder_input_ids=tokens.to(device),
            use_cache=False,
            return_dict=True,
        ).logits.float().cpu()
    # Move the HF model back off the accelerator before moving the OpenAI
    # model there. This keeps peak VRAM to one full checkpoint, not two.
    hf_model.cpu()
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()

    openai_model.eval()
    openai_model.to(device)
    with torch.inference_mode():
        openai_logits = openai_model(mel.to(device), tokens.to(device)).float().cpu()
    openai_model.cpu()
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()

    if hf_logits.shape != openai_logits.shape:
        raise RuntimeError(
            f"Forward output shape mismatch: HF={tuple(hf_logits.shape)} "
            f"OpenAI={tuple(openai_logits.shape)}"
        )
    max_abs = float((hf_logits - openai_logits).abs().max().item())
    mean_abs = float((hf_logits - openai_logits).abs().mean().item())
    if not torch.allclose(hf_logits, openai_logits, rtol=5e-3, atol=5e-3):
        raise RuntimeError(
            f"HF/OpenAI forward parity failed: max_abs={max_abs:.6g}, "
            f"mean_abs={mean_abs:.6g}"
        )
    return {
        "input": "seeded 30-second synthetic log-mel tensor",
        "decoder_tokens": tokens.tolist(),
        "max_abs_difference": max_abs,
        "mean_abs_difference": mean_abs,
        "rtol": 5e-3,
        "atol": 5e-3,
        "passed": True,
    }


def load_sherpa_exporter(exporter_path: Path):
    spec = importlib.util.spec_from_file_location("link_sherpa_whisper_exporter", exporter_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import Sherpa exporter: {exporter_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_exporter(exporter_path: Path, base_model: str, openai_model: Any, output: Path):
    exporter = load_sherpa_exporter(exporter_path)
    original_loader = exporter.whisper.load_model
    old_argv = sys.argv[:]
    old_cwd = Path.cwd()
    try:
        # The official exporter then uses its own v1.13.8 graph and quantization
        # code, but receives our verified fine-tuned OpenAI-compatible weights.
        exporter.whisper.load_model = lambda _name: openai_model
        os.chdir(output)
        sys.argv = [str(exporter_path), "--model", base_model]
        # The pinned exporter applies this workaround only when executed as a
        # script. We import it as a module to inject the verified HF weights,
        # so reproduce the exact v1.13.8 entry-point context explicitly.
        from whisper.model import disable_sdpa

        with disable_sdpa():
            exporter.main()
    finally:
        exporter.whisper.load_model = original_loader
        sys.argv = old_argv
        os.chdir(old_cwd)


def rename_exported_files(output: Path, exporter_prefix: str, package_prefix: str) -> list[dict[str, str]]:
    """Rename every exporter-named graph, token, and external-data file as a set."""
    renamed = []
    for path in sorted(output.iterdir()):
        if not path.is_file() or not path.name.startswith(exporter_prefix + "-"):
            continue
        destination = path.with_name(package_prefix + path.name[len(exporter_prefix):])
        if destination.exists():
            raise RuntimeError(f"Refusing to overwrite package output: {destination.name}")
        path.rename(destination)
        renamed.append({"from": path.name, "to": destination.name})
    if not renamed:
        raise RuntimeError(f"No files found with Sherpa exporter prefix {exporter_prefix!r}")
    return renamed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-id", required=True, choices=sorted(SUPPORTED))
    parser.add_argument("--revision", required=True, help="HF branch, tag, or commit; resolved SHA is recorded")
    parser.add_argument("--sherpa-exporter", required=True, type=Path,
                        help="Path to scripts/whisper/export-onnx.py from Sherpa-ONNX v1.13.8")
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--device", default="auto", choices=("auto", "cpu", "cuda"))
    args = parser.parse_args()

    import torch
    from huggingface_hub import HfApi, snapshot_download
    from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor

    if not args.sherpa_exporter.is_file():
        raise FileNotFoundError(args.sherpa_exporter)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    if any(args.output_dir.iterdir()):
        raise RuntimeError("Output directory must be empty")

    metadata = SUPPORTED[args.model_id]
    info = HfApi().model_info(args.model_id, revision=args.revision)
    source_sha = info.sha
    # Download only files needed for Transformers inference. In particular,
    # exclude the upstream 1.62 GB GGML model because this conversion path uses
    # the 3.24 GB safetensors checkpoint and Sherpa-ONNX exporter.
    snapshot = Path(snapshot_download(
        repo_id=args.model_id,
        revision=source_sha,
        allow_patterns=HF_ALLOW_PATTERNS,
    ))
    snapshot_files = sorted(path.name for path in snapshot.iterdir() if path.is_file())
    has_single_checkpoint = "model.safetensors" in snapshot_files
    has_sharded_checkpoint = (
        "model.safetensors.index.json" in snapshot_files
        and any(re.fullmatch(r"model-\\d+-of-\\d+\\.safetensors", name) for name in snapshot_files)
    )
    if (not has_single_checkpoint and not has_sharded_checkpoint) or "config.json" not in snapshot_files:
        raise RuntimeError("HF snapshot is missing config.json or a complete safetensors checkpoint")
    if any(name.lower().endswith((".ggml", ".gguf", ".bin")) for name in snapshot_files):
        raise RuntimeError("Unexpected GGML/binary model file downloaded; refusing duplicate model storage")

    config_path = snapshot / "config.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    validate_model_config(config, args.model_id)
    if int(config.get("num_mel_bins", -1)) != metadata["feature_dim"]:
        raise RuntimeError("Model-card architecture and HF config mel dimensions disagree")

    processor = AutoProcessor.from_pretrained(snapshot, local_files_only=True)
    hf_model = AutoModelForSpeechSeq2Seq.from_pretrained(
        snapshot,
        torch_dtype=torch.float32,
        low_cpu_mem_usage=True,
        local_files_only=True,
    )
    if getattr(hf_model.config, "scale_embedding", False):
        raise RuntimeError("HF checkpoint uses scaled token embeddings; mapping is not validated")
    if not getattr(hf_model.config, "tie_word_embeddings", True):
        raise RuntimeError("HF checkpoint does not tie the decoder output projection to token embeddings")

    from whisper.model import Whisper
    dims = dimensions_from_config(hf_model.config)
    openai_model = Whisper(dims)
    tensor_report = strict_map_weights(hf_model, openai_model)
    tokenizer_report = verify_tokenizer(processor, metadata["base"])

    device = args.device
    if device == "auto":
        device = "cuda" if torch.cuda.is_available() else "cpu"
    if device == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("--device cuda requested but CUDA is unavailable")

    parity_report = verify_forward_parity(
        hf_model, openai_model, metadata["feature_dim"], device
    )
    # verify_forward_parity releases the HF module after its forward pass.
    del hf_model, processor
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()

    exporter_path = args.sherpa_exporter.resolve()
    run_exporter(exporter_path, metadata["base"], openai_model, args.output_dir)
    del openai_model
    gc.collect()

    # Sherpa names files after its architecture ("turbo-..."). Link resolves
    # model files by the package-specific runtime.model_prefix, so rename the
    # entire set, including any external ONNX tensor sidecars, consistently.
    rename_report = rename_exported_files(
        args.output_dir, metadata["base"], metadata["prefix"]
    )
    prefix = metadata["prefix"]
    # The exporter must leave both the FP32 source graphs and the INT8
    # graphs. The FP32 files are required for parity checks before accepting
    # the quantized package; external .weights sidecars are included below.
    required = [
        f"{prefix}-encoder.onnx",
        f"{prefix}-decoder.onnx",
        f"{prefix}-encoder.int8.onnx",
        f"{prefix}-decoder.int8.onnx",
        f"{prefix}-tokens.txt",
    ]
    for filename in required:
        path = args.output_dir / filename
        if not path.is_file() or path.stat().st_size == 0:
            raise RuntimeError(f"Sherpa exporter did not produce required file: {filename}")

    # Validate the exported graph structures using the exact ONNX checker.
    # Pass paths rather than loading entire external tensor payloads into RAM.
    import onnx

    for filename in required:
        if filename.endswith(".onnx"):
            onnx.checker.check_model(str(args.output_dir / filename))

    files = []
    for path in sorted(args.output_dir.iterdir()):
        if path.is_file():
            files.append({
                "path": path.name,
                "size_bytes": path.stat().st_size,
                "sha256": sha256(path),
            })

    report = {
        "model_id": args.model_id,
        "source_revision": source_sha,
        "downloaded_source_files": snapshot_files,
        "license": metadata["license"],
        "base_architecture": metadata["base"],
        "feature_dim": metadata["feature_dim"],
        "sherpa_exporter": "v1.13.8",
        "tensor_mapping": {
            "count": len(tensor_report),
            "all_target_tensors_mapped": True,
            "entries": tensor_report,
        },
        "tokenizer_parity": tokenizer_report,
        "forward_parity": parity_report,
        "package_model_prefix": prefix,
        "renamed_export_files": rename_report,
        "output_files": files,
        "status": "exported; still requires Sherpa runtime/JNI and Android device validation",
    }
    (args.output_dir / "conversion-report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({
        "model_id": args.model_id,
        "source_revision": source_sha,
        "feature_dim": metadata["feature_dim"],
        "tensor_count": len(tensor_report),
        "forward_parity": parity_report,
        "output_dir": str(args.output_dir.resolve()),
        "status": report["status"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
