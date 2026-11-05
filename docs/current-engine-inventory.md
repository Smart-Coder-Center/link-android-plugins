# Current Link speech-engine inventory

This inventory describes the currently published plugin catalog and Android app integration.

## Current catalog

- **Persian TTS:** Mana Piper is the only published Persian voice. Keep it as the sole voice for now; do not add alternative voices until the ASR quality evaluation is complete and a separate decision is made.
- **Persian ASR:** no Whisper package is currently published in the catalog. The app-side adapter currently supports official multilingual Whisper Small/Base INT8 package layouts, but those packages must be built, released, and added to the catalog before they can be downloaded.
- **ASR research candidates:** Taraneh-WMedium is the first quality candidate, but its 0.8B-parameter F32 checkpoint makes the current 500 MiB expanded-package limit a likely blocker for standard INT8. Taraneh-WBase (72.6M parameters) is the compact fallback to evaluate if WMedium exceeds the measured cap; WLarge remains a quality ceiling/reference; Qwen3-ASR 0.6B is an experimental alternative architecture. See `persian-speech-model-evaluation.md` for published metrics, compatibility limits, and the test protocol.
- **Retired engine:** Shenava Rizeh and its custom Rust runtime are retired and must not be reintroduced.

## Runtime integration

- ASR currently uses the Sherpa-ONNX Java `OfflineRecognizer` API with Persian Whisper Small/Base model data stored in app-private plugin storage.
- TTS uses the Sherpa-ONNX Java `OfflineTts` API with the single Mana Piper voice package.
- Model packages are downloaded from the public Link plugin repository, verified by SHA-256, and extracted into app-private storage.
- The current plugin installer enforces a 400 MiB compressed archive cap and 500 MiB expanded payload cap.

## Taraneh-WMedium conversion status

Taraneh-WMedium is a Hugging Face Whisper Medium fine-tune, not a ready-made Sherpa-ONNX package. Its 0.8B-parameter F32 checkpoint is a likely size blocker for Link's 500 MiB expanded-package ceiling even after standard INT8 quantization; the exact ONNX size must be measured before spending effort on Android integration. The upstream Sherpa exporter currently loads OpenAI Whisper checkpoint formats; Taraneh's published inference path uses Transformers/CTranslate2. A validated weight conversion and tokenizer-ID parity check are required before ONNX export can be trusted. Link's current ASR adapter also only recognizes Small/Base filenames. See [the conversion feasibility spike](persian-speech-model-evaluation.md#taraneh-wmedium-conversion-feasibility-spike-2026-11-06).

## Quality evaluation before publishing more engines

1. Establish a fixed-device baseline with official Whisper Small/Base INT8.
2. Investigate conversion of Taraneh-WMedium to the exact Sherpa-ONNX Whisper format supported by Link.
3. Compare Taraneh-WLarge as an upper-bound reference, measuring accuracy against storage, RAM, and latency.
4. Assess Qwen3-ASR only after verifying compatibility with Link's pinned Sherpa-ONNX v1.13.8 API and its much larger model footprint.
5. Use the same consented Persian audio set, preprocessing, and text normalizer; report CER, WER, latency, peak RAM, storage, and battery impact.

Do not publish an ASR catalog entry until the exact package, license, checksums, installation, transcription, update/removal, and real-device quality/performance have been verified.

## Publication requirements

For the existing Whisper workflow, publish complete Small/Base multilingual INT8 packages and add their exact archive URLs, byte sizes, SHA-256 values, versions, and minimum Link version to `manifest/plugins.json`. Do not advertise a downloadable engine before the release assets and catalog entries exist.

## Parallel Persian ASR candidates

A parallel candidate screen is maintained in [persian-asr-alternative-candidates.md](persian-asr-alternative-candidates.md). Current highest-priority alternatives are Shenava Koochik v1.5 RNNT/CTC (Sherpa-native, Apache-2.0, INT8 package reported around 136 MB for RNNT) and Diba-STT fa-small (about 53 MB claimed, but its accuracy and Android runtime still need independent verification). C1Tech Whisper Small Persian and Taraneh-WBase remain conditional Whisper conversion candidates. Quds-v4 is excluded due to its non-commercial license; Rizeh-Pizeh is low-priority due to its reported WER. No new model has been added to the production catalog and no app integration or build has been performed.

## Android ASR integration audit

The Android adapter was checked against the exact Sherpa-ONNX v1.13.8 API. Koochik v1.5 RNNT is source-level compatible but needs a dedicated `nemo_transducer` adapter and package layout; Diba-STT currently has no documented native Android/Sherpa integration path. See [the Android integration audit](android-asr-integration-audit-2026-11-06.md) before implementing either candidate.
