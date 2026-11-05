# Current Link speech-engine inventory

Inspected from the private `smart-center-code/link-android` repository on `main` at commit `199385c6868c393325d2b2c693ed1019ebe0cc1a`. This document records the current integration only; it does not redistribute any private source or model binaries.

## Current build-time inputs

The current `.github/workflows/build-apk.yml`:
- Installs the Android NDK and Rust Android targets for arm64-v8a, armeabi-v7a, x86, and x86_64.
- Downloads the Persian Shenava/Rizeh ASR ONNX model, tokens, and mel filter configuration.
- Downloads the Persian Mana Piper TTS ONNX model and configuration.
- Uses Python `onnx` to rewrite TTS model metadata and generate a token file.
- Downloads and extracts eSpeak NG phoneme data.
- Compiles `native/link-asr` with Cargo into Android native libraries under `src/main/jniLibs`.
- Runs unit tests and builds the signed universal APK.

These inputs explain why merely moving model files out of APK assets would not remove the Rust compilation or all speech-related build work.

## Current runtime integration

- `LinkOfflineAsr` calls `System.loadLibrary("link_asr")` and passes private-storage model paths to JNI.
- `LinkOfflineTts` imports Sherpa-ONNX Java APIs and creates an offline TTS engine from the model and eSpeak data.
- The Sherpa-ONNX Android dependency is currently declared as a global `implementation` dependency in `build.gradle`, not isolated to a speech-only variant.
- Speech model assets are copied from APK assets to app-private files on first use.

## Migration constraints

1. Keep the plugin catalog empty until a package is complete and verified.
2. First isolate speech-only source, dependencies, model preparation, and Rust compilation from the lightweight variant.
3. Define a stable app-side engine adapter API that does not expose model/runtime implementation details to UI code.
4. Decide whether native runtime libraries can be loaded safely from validated app-private plugin storage on supported Android versions and ABIs. This requires checking transitive native dependencies and linker behavior; do not assume that placing a `.so` in a ZIP makes it loadable.
5. Keep Java/Kotlin bridge code and native engine binaries version-compatible. If runtime code cannot be safely modularized for a non-Play installation, retain the small compatible bridge in the APK and download only model/data packages.
6. Verify each model/runtime/voice license permits redistribution in downloadable packages and preserve all required notices.

## Target behavior

- Lightweight build: no speech UI/engine dependency, model downloads, model assets, or Rust ASR compilation.
- Full build: speech capability is available through separately downloadable language/voice packages; installing one language must not require downloading the other.
- If a speech action is selected without its package, Link opens Settings > Plugins and explains what the package enables in user-friendly language.
