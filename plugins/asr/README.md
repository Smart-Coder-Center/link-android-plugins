# Speech recognition plugins (ASR)

## Current test package

The live catalog now contains one experimental Persian ASR package:

- **Koochik RNNT فارسی (آزمایشی)** — INT8 FastConformer RNNT, offline, CPU, Sherpa-ONNX `nemo_transducer`.
- Model archive: approximately 137 MB.
- Upstream license: Apache-2.0.
- The model card reports WER 9.50% / CER 2.60% on its own Golden-6669 held-out set. These are author-reported figures, not measurements from Link devices.
- The previous multilingual Whisper Base and Small packages have been retired and are no longer offered.

Release: https://github.com/Smart-Coder-Center/link-android-plugins/releases/tag/koochik-rnnt-test-1.0.0-test.1

## Release requirements

Do not promote this package from experimental status until it has passed:

- Link Android smoke testing with the pinned Sherpa-ONNX v1.13.8 runtime
- A fixed, human-transcribed Persian conversational test set
- CER/WER measurement with the same normalizer used for all candidate engines
- Latency, peak RAM, storage, thermal, and battery checks on real Android devices
- Model provenance, license, checksums, and archive-size verification

Keep model weights as data-only plugins outside the APK. Mana remains the only Persian TTS voice.
