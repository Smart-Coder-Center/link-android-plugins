# Taraneh-WMedium to Sherpa-ONNX: conversion feasibility

This document records the source-level feasibility findings and release gates for evaluating Taraneh-WMedium in Link. It does not claim that a conversion has been run.

The first source-level compatibility check is complete. **The checkpoint is Whisper-based, but it is not directly accepted by Sherpa's published Whisper exporter.**

Verified facts:

- The Taraneh model card identifies the checkpoint as a Hugging Face `WhisperForConditionalGeneration` model based on `openai/whisper-medium`. The published repository contains a 3.06 GB `model.safetensors` file and tokenizer/configuration assets.
- Taraneh's own inference path loads it through Transformers and optionally converts it to **CTranslate2**. That fast path does not produce Sherpa-ONNX files and cannot be used by Link's current Sherpa Java recognizer.
- Sherpa's documented Whisper exporter imports `openai-whisper`, creates an OpenAI Whisper model with `whisper.load_model()`, then exports encoder/decoder graphs and dynamically quantizes their MatMul weights. Its current built-in loader does not load a Hugging Face `WhisperForConditionalGeneration` directory; the special `medium-aishell` path expects a different icefall checkpoint, not Taraneh's safetensors.
- Link's current `LinkOfflineAsr` adapter only searches for `small-*` and `base-*` filenames. Even a valid Sherpa Whisper Medium package would not currently be selected without a small app-side adapter update.
- Link's package installer currently caps a compressed archive at 400 MiB and expanded data at 500 MiB. The 3.06 GB source checkpoint is not a distributable package and must not be placed in the catalog.

### Exact v1.13.8 exporter finding and proposed tensor mapping

The pinned v1.13.8 exporter was inspected directly at:
`https://github.com/k2-fsa/sherpa-onnx/blob/v1.13.8/scripts/whisper/export-onnx.py`.

Its CLI accepts `--model medium`, but that branch calls `whisper.load_model("medium")` and therefore loads the **stock OpenAI Whisper Medium checkpoint**. It does not load Taraneh. Passing `--model medium` and then publishing the result under a Taraneh name would silently ship the wrong model. The only built-in fine-tuned checkpoint special case is `medium-aishell`, which downloads an unrelated icefall checkpoint.

A dedicated HF-to-OpenAI state-dict adapter is therefore required. The expected name mapping, to be validated against the exact downloaded checkpoint before use, is:

| Hugging Face Transformers key family | OpenAI Whisper key family |
|---|---|
| `model.encoder.conv1.*` | `encoder.conv1.*` |
| `model.encoder.conv2.*` | `encoder.conv2.*` |
| `model.encoder.embed_positions.weight` | `encoder.positional_embedding` |
| `model.encoder.layers.i.self_attn.q_proj.*` | `encoder.blocks.i.attn.query.*` |
| `model.encoder.layers.i.self_attn.k_proj.*` | `encoder.blocks.i.attn.key.*` |
| `model.encoder.layers.i.self_attn.v_proj.*` | `encoder.blocks.i.attn.value.*` |
| `model.encoder.layers.i.self_attn.out_proj.*` | `encoder.blocks.i.attn.out.*` |
| `model.encoder.layers.i.self_attn_layer_norm.*` | `encoder.blocks.i.attn_ln.*` |
| `model.encoder.layers.i.fc1.*` / `fc2.*` | `encoder.blocks.i.mlp.0.*` / `mlp.2.*` |
| `model.encoder.layers.i.final_layer_norm.*` | `encoder.blocks.i.mlp_ln.*` |
| `model.encoder.layer_norm.*` | `encoder.ln_post.*` |
| `model.decoder.layers.i.self_attn.*` | `decoder.blocks.i.attn.*` (same projection mapping as encoder) |
| `model.decoder.layers.i.encoder_attn.*` | `decoder.blocks.i.cross_attn.*` |
| `model.decoder.layers.i.self_attn_layer_norm.*` | `decoder.blocks.i.attn_ln.*` |
| `model.decoder.layers.i.encoder_attn_layer_norm.*` | `decoder.blocks.i.cross_attn_ln.*` |
| `model.decoder.layers.i.fc1.*` / `fc2.*` | `decoder.blocks.i.mlp.0.*` / `mlp.2.*` |
| `model.decoder.layers.i.final_layer_norm.*` | `decoder.blocks.i.mlp_ln.*` |
| `model.decoder.embed_tokens.weight` | `decoder.token_embedding.weight` |
| `model.decoder.embed_positions.weight` | `decoder.positional_embedding` (must handle HF's positional offset explicitly) |
| `model.decoder.layer_norm.*` | `decoder.ln.*` |

This table is a mapping hypothesis, not a completed converter. The adapter must fail closed on every missing, unexpected, duplicate, or shape-mismatched tensor. In particular:

- Check the HF decoder positional embedding's offset/row count before copying it; do not blindly copy a larger HF table into OpenAI Whisper's decoder position tensor.
- Check whether `proj_out.weight` is tied to `model.decoder.embed_tokens.weight`; preserve the exact shared vocabulary matrix and do not create a separately initialized output head.
- Verify the attention projection bias layout, layer-norm epsilon, convolution weights, and every tensor shape against the constructed OpenAI Whisper Medium model.
- Compare every mapped tensor numerically against the source tensor after the explicitly documented reshape/slice operations. The report must list source key, destination key, source shape, destination shape, and max absolute difference.
- Validate tokenizer vocabulary and every special token ID, not just the Persian language/task prefix. The HF repository includes `added_tokens.json`, `vocab.json`, `merges.txt`, and tokenizer configuration files; Sherpa's exporter generates tokens from OpenAI Whisper's multilingual tiktoken asset. Those token tables must be proven identical in ID assignment before using Sherpa's generated `*-tokens.txt`.

### Prototype implementation gates

The first converter should be a standalone offline tool in the plugin repository (not Android runtime code). It should:
1. Download/pin the exact Taraneh revision and record its commit SHA.
2. Load the HF checkpoint on CPU or GPU with Transformers and construct the matching OpenAI Whisper Medium model.
3. Map all tensors with strict key/shape checks and export a temporary OpenAI-compatible checkpoint.
4. Run the v1.13.8 Sherpa exporter against that temporary checkpoint, using a patched local copy that loads the temporary file rather than the stock `medium` alias.
5. Emit a machine-readable conversion report and source/model/tokenizer hashes.
6. Compare source Transformers and FP32 ONNX greedy-decoding outputs on a fixed set of Persian audio clips before attempting INT8.

The 3.06 GB source checkpoint means conversion is a workstation/server-side packaging task, not an Android download. The model itself is not included in Link APK.

### Required conversion work

1. Pin the exporter source to the Sherpa-ONNX release corresponding to Link's bundled v1.13.8 runtime; do not use an unpinned `master` exporter for a production artifact.
2. Load Taraneh-WMedium with its own Transformers config and map every encoder/decoder tensor into the exact OpenAI Whisper model structure expected by the pinned Sherpa exporter, or implement a separately reviewed exporter for the Hugging Face model. No model weights may be silently replaced with stock Whisper Medium weights.
3. Verify architecture dimensions, tensor names/shapes, multilingual tokenizer IDs, language/task tokens, and any added/special tokens. The Sherpa token table must represent the same token IDs used by the fine-tuned checkpoint.
4. Export FP32 ONNX first. Compare the ONNX output/transcripts with the original Transformers checkpoint on a fixed audio subset. Only after parity passes, dynamically quantize encoder and decoder to INT8 and measure CER/WER degradation.
5. Run Sherpa's own model test, then a small Java/JNI smoke test using the exact v1.13.8 AAR. Finally update the Link adapter to recognize the Medium file layout and verify package installation/removal.
6. Measure actual archive size. If it exceeds the 400 MiB compressed or 500 MiB expanded limit, stop and assess a supported quantization/compression strategy; do not raise limits before measuring device storage and peak RAM.

### Current decision

**Feasibility is promising but not yet proven.** The base architecture is Whisper Medium, but the HF-to-OpenAI weight mapping, tokenizer parity, ONNX numerical parity, INT8 accuracy, v1.13.8 execution, and package footprint remain unverified. No conversion script, ONNX artifact, catalog entry, release asset, or app adapter change is being published yet. This avoids shipping a package that silently runs stock Whisper or fails at runtime.

The next technical milestone is a reproducible conversion prototype that produces FP32 ONNX and a parity report before any INT8 packaging. The user's Android device is still required for final latency, RAM, heat, battery, and real-world Persian quality measurements.

Sources:
- Taraneh model card and checkpoint details: https://huggingface.co/areffarhadi/Taraneh-WMedium
- Taraneh inference implementation: https://github.com/areffarhadi/persian-asr
- Sherpa Whisper exporter: https://github.com/k2-fsa/sherpa-onnx/blob/v1.13.8/scripts/whisper/export-onnx.py
- Sherpa export guide: https://k2-fsa.github.io/sherpa/onnx/pretrained_models/whisper/export-onnx.html
