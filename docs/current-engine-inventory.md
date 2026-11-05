# Current Link speech-engine inventory

This inventory describes the currently published plugin catalog and Android app integration.

## Current catalog

- **Persian TTS:** Mana Piper is the only published Persian voice. Keep it as the sole voice for now; do not add alternative voices until the ASR quality evaluation is complete and a separate decision is made.
- **Persian ASR:** no Whisper package is currently published in the catalog. The app-side adapter currently supports official multilingual Whisper Small/Base INT8 package layouts, but those packages must be built, released, and added to the catalog before they can be downloaded.
- **ASR research candidates:** Taraneh-WMedium is the first Persian-specialized candidate to evaluate; Taraneh-WLarge is a quality ceiling/reference; Qwen3-ASR 0.6B is an experimental alternative architecture. See `persian-speech-model-evaluation.md` for published metrics, compatibility limits, and the test protocol.
- **Retired engine:** Shenava Rizeh and its custom Rust runtime are retired and must not be reintroduced.

## Runtime integration

- ASR currently uses the Sherpa-ONNX Java `OfflineRecognizer` API with Persian Whisper Small/Base model data stored in app-private plugin storage.
- TTS uses the Sherpa-ONNX Java `OfflineTts` API with the single Mana Piper voice package.
- Model packages are downloaded from the public Link plugin repository, verified by SHA-256, and extracted into app-private storage.
- The current plugin installer enforces a 400 MiB compressed archive cap and 500 MiB expanded payload cap.

## Quality evaluation before publishing more engines

1. Establish a fixed-device baseline with official Whisper Small/Base INT8.
2. Investigate conversion of Taraneh-WMedium to the exact Sherpa-ONNX Whisper format supported by Link.
3. Compare Taraneh-WLarge as an upper-bound reference, measuring accuracy against storage, RAM, and latency.
4. Assess Qwen3-ASR only after verifying compatibility with Link's pinned Sherpa-ONNX v1.13.8 API and its much larger model footprint.
5. Use the same consented Persian audio set, preprocessing, and text normalizer; report CER, WER, latency, peak RAM, storage, and battery impact.

Do not publish an ASR catalog entry until the exact package, license, checksums, installation, transcription, update/removal, and real-device quality/performance have been verified.

## Publication requirements

For the existing Whisper workflow, publish complete Small/Base multilingual INT8 packages and add their exact archive URLs, byte sizes, SHA-256 values, versions, and minimum Link version to `manifest/plugins.json`. Do not advertise a downloadable engine before the release assets and catalog entries exist.
