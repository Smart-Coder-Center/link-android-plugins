# Persian Whisper checkpoints: Sherpa-ONNX conversion feasibility

This is a source-level compatibility assessment for the three Persian Whisper checkpoints requested for Link. It does not claim that any ONNX conversion, quantization, package build, or Android device test has been completed.

## Summary

| Checkpoint | Upstream base | Source format / reported size | License | Sherpa v1.13.8 path | Current status |
|---|---|---:|---|---|---|
| `givia/whisper-large-v3-turbo-persian` | Whisper Large-v3 Turbo | Transformers safetensors; model card lists about 0.8B parameters and a 3.24 GB weight file; a separate 1.62 GB GGML file is also published | CC-BY-4.0 | Exporter supports the stock `turbo` architecture and 128 mel bins, but its built-in loader loads stock OpenAI Whisper Turbo, not this Hugging Face fine-tune | Needs HF-to-OpenAI weight adapter and parity tests |
| `areffarhadi/Taraneh-WMedium` | Whisper Medium | Transformers safetensors; 3.06 GB checkpoint | MIT | Exporter supports stock `medium`, but its built-in loader loads stock OpenAI Whisper Medium, not Taraneh | Needs HF-to-OpenAI weight adapter and parity tests; see the dedicated spike |
| `nezamisafa/whisper-persian-v4` | Whisper Large-v3 | Transformers safetensors; repository reports 6.18 GB total | Apache-2.0 | Exporter supports stock `large-v3` and 128 mel bins, but its built-in loader loads stock OpenAI Whisper Large-v3, not this fine-tune | Needs HF-to-OpenAI weight adapter and parity tests |

The source checkpoint sizes above are not predicted Android plugin sizes. Final int8 ONNX archive and expanded sizes must be measured after conversion.

## Important exporter distinction

The pinned Sherpa-ONNX v1.13.8 exporter at:

`https://github.com/k2-fsa/sherpa-onnx/blob/v1.13.8/scripts/whisper/export-onnx.py`

supports the stock Whisper architecture names `medium`, `large-v3`, and `turbo`. However, its normal code path calls `whisper.load_model(name)`. Running `--model medium`, `--model large-v3`, or `--model turbo` without replacing that loader exports the corresponding stock OpenAI checkpoint. It does **not** automatically read a Hugging Face fine-tuned checkpoint.

Therefore, do not publish stock exporter output under any of the Persian fine-tune package IDs. A package named for a Persian fine-tune must contain the fine-tuned weights, not the stock base model.

The exporter uses 128 mel bins for `large`, `large-v3`, and `turbo`; it uses 80 for `medium`. Link must put the exact `feature_dim` in each package manifest. The Android adapter now also defaults both `large*` and `turbo*` prefixes to 128 when the field is absent, but explicit manifest metadata remains mandatory for release.

A separate Hugging Face repository exists for a browser-oriented ONNX conversion of the Givia Turbo checkpoint. Its model card describes Transformers.js/WebGPU/WebAssembly quantization and attention outputs. That is not evidence that its graphs, tensor names, decoder cache contract, tokenizer assets, or quantization are compatible with Sherpa-ONNX's Java recognizer. Do not reuse those files as Sherpa package artifacts without a complete compatibility audit.

## Per-model conversion gates

### Givia Whisper Large-v3 Turbo Persian

- Pin the exact source revision and preserve CC-BY-4.0 attribution and notices.
- Load the actual Hugging Face fine-tuned checkpoint and map all encoder/decoder tensors into the OpenAI Whisper Turbo model structure used by the pinned Sherpa exporter.
- Validate all tensor keys, shapes, dtypes, layer counts, tied embeddings, and positional embeddings. Fail closed on missing, extra, duplicate, or mismatched tensors.
- Verify tokenizer vocabulary and every special-token ID. Do not assume that a tokenizer file from a different ONNX conversion is interchangeable.
- Export FP32 ONNX first, compare Transformers and ONNX outputs on identical Persian WAV fixtures, then quantize and measure CER/WER regression.
- Include both model and license provenance in the package manifest/attribution files.

### Taraneh-WMedium

See [taraneh-wmedium-conversion-spike.md](taraneh-wmedium-conversion-spike.md) for the detailed proposed tensor mapping, tokenizer checks, and package-size risks.

### Whisper Persian V4

- Pin the source revision and retain Apache-2.0 notices.
- The model card identifies `openai/whisper-large-v3` as its base and reports a self-evaluated WER of 8.73 on its own `ASR_fa_v1` test split. This result is not directly comparable with scores reported by the other model cards.
- Reuse the Large-v3 architecture conversion path only after confirming the exact configuration and state-dict layout. It is a separate fine-tuned checkpoint and must not be replaced by stock Large-v3 weights.
- Verify the Persian language/task tokens and tokenizer IDs against the checkpoint's own processor/tokenizer assets.
- Export FP32, compare against Transformers, and only then quantize to INT8 and measure quality and actual package size.

## Shared release gates

1. Record source repository, immutable revision, license, conversion tool versions, and hashes.
2. Produce a strict HF-to-OpenAI state-dict conversion report: source key, destination key, shapes, dtypes, and maximum absolute difference.
3. Verify tokenizer IDs, language/task prefix, special tokens, mel dimension, sample rate, and decoder output/cache tensor contract.
4. Compare FP32 Sherpa ONNX output with the upstream Transformers implementation using the same Persian audio fixtures.
5. Run Sherpa's own Whisper test script with the generated files.
6. Quantize only after FP32 parity passes; report CER/WER degradation, not just model file size.
7. Run a Java/JNI smoke test against the exact Sherpa-ONNX 1.13.8 dependency used by Link.
8. Create a data-only plugin archive with SHA-256, attribution, manifest, and exact file inventory.
9. Verify download, extraction, selection, transcription, engine switching, and uninstall on Android.
10. Publish in the public catalog only after all gates pass.

## Benchmark caution

The model cards report scores on different datasets and evaluation setups. Givia's reported FLEURS subset result, Taraneh's multi-dataset table, and Whisper Persian V4's ASR_fa_v1 score cannot be used as a direct ranking. Link must evaluate all candidates on the same held-out Persian audio set with one normalization/scoring pipeline, including short colloquial phrases and single-word utterances.

## Current release decision

None of these three checkpoints is ready to appear as a downloadable production plugin yet. The Android adapter supports Sherpa Whisper packages with declared file prefixes and feature dimensions, but that runtime adapter is not a conversion pipeline. No public catalog entry or placeholder package should be added until a real fine-tuned ONNX artifact passes the shared gates.

## Sources

- Givia model card: https://huggingface.co/givia/whisper-large-v3-turbo-persian
- Taraneh-WMedium model card: https://huggingface.co/areffarhadi/Taraneh-WMedium
- Whisper Persian V4 model card: https://huggingface.co/nezamisafa/whisper-persian-v4
- Sherpa-ONNX v1.13.8 exporter: https://github.com/k2-fsa/sherpa-onnx/blob/v1.13.8/scripts/whisper/export-onnx.py
- Sherpa Whisper export guide: https://k2-fsa.github.io/sherpa/onnx/pretrained_models/whisper/export-onnx.html
- Browser-oriented Givia ONNX conversion (not a Sherpa compatibility claim): https://huggingface.co/mehrshadjavid/whisper-large-v3-turbo-persian-ONNX
