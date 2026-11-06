# Experimental HF Whisper to Sherpa-ONNX converter

tools/whisper_hf_to_sherpa.py is the first reproducible conversion prototype for the three Persian Whisper checkpoints requested for Link.

It does not publish plugins or edit the catalog. It is deliberately fail-closed:

1. Resolves the requested Hugging Face revision to an immutable commit SHA.
2. Loads the actual fine-tuned Transformers checkpoint (not the stock OpenAI model).
3. Maps all expected encoder/decoder tensors to the OpenAI Whisper state-dict layout. Missing, extra, duplicate, or shape-mismatched tensors stop conversion.
4. Checks Persian tokenizer probes, the full vocabulary size, every OpenAI Whisper special-token ID, and the complete Hugging Face added-token inventory against OpenAI Whisper's multilingual tokenizer.
5. Compares Transformers and OpenAI Whisper forward logits on a deterministic 30-second synthetic log-mel input.
6. Runs the Whisper ONNX export and INT8 quantization code from the exact Sherpa-ONNX v1.13.8 exporter supplied by the operator, including the exporter's SDPA workaround even though it is imported as a module.
7. Requires both FP32 and INT8 encoder/decoder graphs and the tokenizer file, then runs the ONNX structural checker on all four graphs. FP32 graphs and any external weight sidecars are retained for parity testing.
7. Writes hashes, tensor mapping, tokenizer checks, and parity results to conversion-report.json.

## Supported source checkpoints

| Model ID | Base architecture | Feature dimension | License |
|---|---|---:|---|
| givia/whisper-large-v3-turbo-persian | turbo | 128 | CC-BY-4.0 |
| areffarhadi/Taraneh-WMedium | medium | 80 | MIT |
| nezamisafa/whisper-persian-v4 | large-v3 | 128 | Apache-2.0 |

## Environment

Use a dedicated Linux workstation with adequate RAM, free disk, and preferably a CUDA GPU. The three source repositories contain multi-gigabyte Transformers checkpoints. The converter downloads only safetensors weights and required tokenizer/config files, explicitly excluding GGML/GGUF/binary inference copies. Sharded safetensors snapshots are accepted when the index and all shards are present. Source weights, mapped model, activations, ONNX export, and quantization may still require substantial memory and several tens of GB of temporary disk.

Install compatible versions of Python 3.10 or 3.11, PyTorch, Transformers, huggingface_hub, accelerate, safetensors, openai-whisper, onnx, and onnxruntime.

Use the same Python environment for the Sherpa exporter. The exporter itself comes from the Sherpa-ONNX v1.13.8 source tree; do not use an unpinned development-branch copy.

## Example

```bash
python tools/whisper_hf_to_sherpa.py \
  --model-id givia/whisper-large-v3-turbo-persian \
  --revision main \
  --sherpa-exporter /path/to/sherpa-onnx/scripts/whisper/export-onnx.py \
  --output-dir /data/link-asr/givia-turbo-fa \
  --device cuda

# Repeat for the other requested checkpoints, using separate empty output folders:
python tools/whisper_hf_to_sherpa.py --model-id areffarhadi/Taraneh-WMedium \
  --revision main --sherpa-exporter /path/to/sherpa-onnx/scripts/whisper/export-onnx.py \
  --output-dir /data/link-asr/taraneh-wmedium --device cuda

python tools/whisper_hf_to_sherpa.py --model-id nezamisafa/whisper-persian-v4 \
  --revision main --sherpa-exporter /path/to/sherpa-onnx/scripts/whisper/export-onnx.py \
  --output-dir /data/link-asr/whisper-persian-v4 --device cuda
```

After conversion completes and all gates in the report pass, create the data-only plugin ZIP:

```bash
python tools/package_givia_whisper_plugin.py \
  --model-id givia/whisper-large-v3-turbo-persian \
  --conversion-dir /data/link-asr/givia-turbo-fa \
  --output-zip /data/link-asr/givia-whisper-plugin-1.0.0-test.1.zip \
  --version 1.0.0-test.1

# Use the same packager for Taraneh-WMedium and Whisper Persian V4 by changing
# --model-id, --conversion-dir, and --output-zip to their corresponding values.
```

The packager re-checks the source model/revision, license, forward parity, tokenizer inventory, INT8 graph files, external ONNX sidecars, and SHA-256 values. It writes the root `plugin.json`, attribution notice, archive, and a separate package report. This creates a local ZIP only; it does not upload a GitHub Release or modify the public catalog.

The three requested models are supported by the conversion and packaging command paths. Process them sequentially to control workstation memory and disk pressure, but do not silently substitute stock OpenAI Whisper weights for any fine-tuned checkpoint. Each run records the resolved immutable source commit SHA even when --revision main is used. A model remains unpublished until its own conversion, tokenizer, numerical parity, audio quality, Sherpa JNI, and Android device gates pass.

## Important limitations

- The script is a conversion prototype, not a completed conversion result. It must be executed against each real checkpoint.
- The synthetic forward parity test is a structural/numerical gate, not a substitute for transcript comparison on held-out Persian WAV files.
- Tokenizer checks cover Persian/Latin probes and key special-token IDs; release review must additionally audit the complete tokenizer vocabulary and added-token inventory.
- ONNX Runtime INT8 accuracy loss, Sherpa Python/JNI loading, Android latency/RAM/thermal behavior, and final ZIP size are not established by this script.
- Large-model ONNX external-data files must be retained beside their graph. The report lists all generated files and hashes.
- No output from this tool should be added to manifest/plugins.json until the complete release gates in docs/whisper-model-conversion-feasibility-matrix.md pass.
- Keep each model's license and attribution with its generated data package. This tool intentionally does not create a public release or catalog entry.
