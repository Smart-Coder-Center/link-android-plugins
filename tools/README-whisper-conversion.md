# Experimental HF Whisper to Sherpa-ONNX converter

tools/whisper_hf_to_sherpa.py is the first reproducible conversion prototype for the three Persian Whisper checkpoints requested for Link.

It does not publish plugins or edit the catalog. It is deliberately fail-closed:

1. Resolves the requested Hugging Face revision to an immutable commit SHA.
2. Loads the actual fine-tuned Transformers checkpoint (not the stock OpenAI model).
3. Maps all expected encoder/decoder tensors to the OpenAI Whisper state-dict layout. Missing, extra, duplicate, or shape-mismatched tensors stop conversion.
4. Checks Persian tokenizer probes and key special-token IDs against OpenAI Whisper's multilingual tokenizer.
5. Compares Transformers and OpenAI Whisper forward logits on a deterministic 30-second synthetic log-mel input.
6. Runs the Whisper ONNX export and INT8 quantization code from the exact Sherpa-ONNX v1.13.8 exporter supplied by the operator.
7. Writes hashes, tensor mapping, tokenizer checks, and parity results to conversion-report.json.

## Supported source checkpoints

| Model ID | Base architecture | Feature dimension | License |
|---|---|---:|---|
| givia/whisper-large-v3-turbo-persian | turbo | 128 | CC-BY-4.0 |
| areffarhadi/Taraneh-WMedium | medium | 80 | MIT |
| nezamisafa/whisper-persian-v4 | large-v3 | 128 | Apache-2.0 |

## Environment

Use a dedicated Linux workstation with adequate RAM, free disk, and preferably a CUDA GPU. Large-v3 / Turbo / Persian V4 are large checkpoints; the source model, mapped model, activations, ONNX export, and quantization may require substantial memory and several tens of GB of temporary disk.

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
```

Repeat in a separate empty output directory for Taraneh-WMedium and Whisper Persian V4. The script records the resolved source commit SHA even when --revision main is used.

## Important limitations

- The script is a conversion prototype, not a completed conversion result. It must be executed against each real checkpoint.
- The synthetic forward parity test is a structural/numerical gate, not a substitute for transcript comparison on held-out Persian WAV files.
- Tokenizer checks cover Persian/Latin probes and key special-token IDs; release review must additionally audit the complete tokenizer vocabulary and added-token inventory.
- ONNX Runtime INT8 accuracy loss, Sherpa Python/JNI loading, Android latency/RAM/thermal behavior, and final ZIP size are not established by this script.
- Large-model ONNX external-data files must be retained beside their graph. The report lists all generated files and hashes.
- No output from this tool should be added to manifest/plugins.json until the complete release gates in docs/whisper-model-conversion-feasibility-matrix.md pass.
- Keep each model's license and attribution with its generated data package. This tool intentionally does not create a public release or catalog entry.
