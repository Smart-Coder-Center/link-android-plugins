# Current Link speech-engine inventory

This inventory describes the currently published plugin catalog and the Android app-side integration.

## Current catalog

- Persian TTS: Mana Piper is published in the plugin catalog.
- Persian ASR: no Whisper package is currently published in the catalog. The app-side adapter supports Whisper Small/Base model packages, but those packages must be built, released, and added to the catalog before they can be downloaded from Link.
- Shenava Rizeh and its custom Rust runtime have been retired and removed from the active catalog and app source.

## Runtime integration

- ASR uses the Sherpa-ONNX Java OfflineRecognizer API with Persian Whisper model data stored in app-private plugin storage.
- TTS uses the Sherpa-ONNX Java OfflineTts API with the selected Piper voice package.
- Model packages are downloaded from the public Link plugin repository, verified by SHA-256, and extracted into app-private storage.

## Publication requirements

1. Publish a complete Whisper Small or Base multilingual INT8 package to the plugin repository release.
2. Add the exact archive URL, byte size, SHA-256, version, and minimum Link version to `manifest/plugins.json`.
3. Confirm the package contains the expected encoder, decoder, tokens, and license notices.
4. Verify download, installation, Persian transcription, activation, update, and removal on supported Android devices before enabling the catalog entry.

Until a Whisper package is published and listed, the app must not advertise a downloadable Whisper engine.
