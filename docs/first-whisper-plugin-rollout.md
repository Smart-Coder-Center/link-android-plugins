# Sequential rollout: first Persian Whisper plugin

## Decision

Process one multi-gigabyte model at a time. The first and only active candidate is Givia Whisper Large-v3 Turbo Persian (givia/whisper-large-v3-turbo-persian, CC-BY-4.0).

Taraneh-WMedium and Whisper Persian V4 are deferred. Do not download, convert, package, or publish either until Givia has passed installation and real-device testing in Link and the user approves the next stage.

## Why this order

Givia is the selected first candidate because it is the first model in the agreed rollout and its base architecture (Whisper Large-v3 Turbo) is supported by the pinned Sherpa-ONNX v1.13.8 exporter. Its Hugging Face fine-tuned weights still require the custom adapter and parity checks; stock Whisper Turbo weights must never be substituted.

## Stage 1: Givia only

1. Resolve and record an immutable Hugging Face revision.
2. Download only the Givia checkpoint. Do not fetch the other two checkpoints.
3. Convert the actual fine-tuned weights with tools/whisper_hf_to_sherpa.py using the Sherpa-ONNX v1.13.8 exporter.
4. Require strict tensor mapping, full special-token inventory checks, and forward-logit parity to pass.
5. Rename all Sherpa output files and external-data sidecars to the Link package prefix `large-v3-turbo-persian`.
6. Export FP32 ONNX and compare against the original Transformers checkpoint on identical Persian WAV fixtures.
7. Quantize only after FP32 parity passes. Measure CER, WER, short-utterance exact match, latency, peak RAM, and archive/expanded size.
8. Run Sherpa Python and Java/JNI smoke tests against the exact v1.13.8 runtime.
9. Build one data-only ZIP with complete file inventory, hashes, source revision, and CC-BY-4.0 attribution.
10. Only after all conversion gates pass, publish one versioned GitHub Release asset and add one Givia entry to manifest/plugins.json.
11. Install from the public catalog in Link. Test download, extraction, activation, transcription, switching back to Koochik/Whisper Small/Base, update, and uninstall on the target phone.

## Stage 1 acceptance checklist

- [ ] Source revision and license provenance recorded.
- [ ] Every source tensor mapped; no unexpected or missing tensors.
- [ ] Full tokenizer vocabulary and special-token inventory audited.
- [ ] FP32 ONNX numerical/transcript parity passed.
- [ ] INT8 CER/WER regression measured on the same held-out Persian set.
- [ ] Sherpa v1.13.8 Python and Android JNI smoke tests passed.
- [ ] Final archive and expanded sizes, SHA-256, and contents recorded.
- [ ] Link installation, activation, transcription, switching, update, and removal tested.
- [ ] User confirms the first model is acceptable before Stage 2 begins.

## Stage 2 and Stage 3

Only after Stage 1 acceptance and explicit approval, repeat the same process for Taraneh-WMedium. Whisper Persian V4 remains deferred until Taraneh has also been evaluated and a further stage is approved.

## Current truthful status

The conversion prototype and static mapping CI exist, but no Givia ONNX files or plugin ZIP have been generated yet. No catalog entry is present. The large checkpoint conversion requires a suitable machine with sufficient RAM, disk, and preferably CUDA; do not create a placeholder catalog entry or claim that the plugin is installable before the real archive exists.
