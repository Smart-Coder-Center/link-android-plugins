# Three-model Persian Whisper rollout

## Scope

The user has explicitly requested that all three Persian Whisper candidates continue through the integration pipeline. Process one checkpoint at a time to control workstation memory and disk usage, but do not defer the second or third model pending a new approval.

1. Givia Whisper Large-v3 Turbo Persian — `givia/whisper-large-v3-turbo-persian`, CC-BY-4.0, Sherpa feature dimension 128.
2. Taraneh-WMedium — `areffarhadi/Taraneh-WMedium`, MIT, Sherpa feature dimension 80.
3. Whisper Persian V4 — `nezamisafa/whisper-persian-v4`, Apache-2.0, Sherpa feature dimension 128.

Koochik RNNT remains the existing baseline and fallback; it is not one of the three new candidates.

## Per-model conversion and release gates

For each checkpoint, in the order above:

1. Resolve and record an immutable Hugging Face revision and verify the license.
2. Download the actual fine-tuned safetensors checkpoint and tokenizer/configuration assets only. Do not download duplicate GGML/GGUF inference files.
3. Map the complete HF state dict into the matching OpenAI Whisper architecture used by the pinned Sherpa-ONNX v1.13.8 exporter. Reject missing, extra, duplicate, or shape-mismatched tensors.
4. Verify tokenizer vocabulary, all special-token IDs, language/task tokens, mel dimension, and decoder contract.
5. Export FP32 ONNX and compare Transformers and ONNX outputs on identical fixtures.
6. Quantize to INT8 only after FP32 parity passes. Measure CER/WER degradation on the same Persian conversational test set.
7. Run Sherpa Python and Java/JNI smoke tests against the exact v1.13.8 runtime.
8. Package as data-only ZIP with complete file inventory, SHA-256 hashes, immutable source revision, and model-specific license attribution.
9. Test download, extraction, activation, transcription, switching to Koochik, update, and uninstall on the target Link device.
10. Publish a versioned GitHub Release asset and catalog entry only after all gates for that model pass.

## Shared quality test set

Use identical audio fixtures and one normalization/scoring pipeline for all three models. Include colloquial Persian, short single-word answers inside complete sentences, Persian numerals, punctuation, half-spaces, mixed Persian/English, different speaking rates, silence, and realistic background noise. Report WER, CER, short-utterance exact match, latency, peak RSS, thermal behavior, model initialization time, and archive/expanded size.

Model-card scores from different datasets are not directly comparable. Do not declare a winner until Link evaluates all three on the same held-out test set.

## Current implementation status

- Link Android contains the Sherpa-ONNX Whisper runtime adapter and supports manifest-declared model prefixes and 80/128 mel dimensions.
- The companion converter and packager command paths now declare all three source checkpoints.
- This is implementation support only. No successful multi-gigabyte checkpoint conversion, INT8 quality result, final ZIP, public catalog entry, or Android device validation is claimed until the corresponding artifacts and reports exist.
- Never add placeholder entries to the public catalog. Keep model weights outside the APK.
