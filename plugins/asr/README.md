# Speech recognition plugins (ASR)

## Current status

The experimental multilingual Whisper Base and Small packages have been retired from the live catalog after user testing found their Persian recognition quality unsuitable for Link. They are no longer offered for installation.

No Persian ASR package is currently published in the production catalog. Do not add a replacement until all of the following have been verified:

- Persian conversational-speech accuracy on a fixed, human-transcribed test set
- Offline Android inference using Link's pinned Sherpa-ONNX runtime, or a justified runtime change
- Actual archive size, peak RAM, latency, and battery use on representative Android devices
- Model and runtime licenses permitting commercial redistribution
- Exact model revision, file checksums, and reproducible packaging

## Candidate research

The current research shortlist is recorded in `docs/persian-asr-alternative-candidates.md`. The leading implementation candidate is a Persian FastConformer RNNT/CTC model that can use the existing Sherpa-ONNX runtime, subject to a device test. A separate compact Diba candidate remains research-only until its native Android inference path and reproducible quality results are established.

Keep ASR model weights as data-only plugins outside the APK. Mana remains the only Persian TTS voice.
