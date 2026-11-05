# Link speech model selection and plugin plan

## Decision: one runtime, downloadable model/voice packs

Use **sherpa-onnx** as the shared on-device speech runtime for the first implementation. Keep its Java API and native runtime in the Standard APK initially. Download only model/voice data as plugins.

This is the lowest-change route because the existing Link code already depends on sherpa-onnx for TTS. It avoids shipping a second inference engine and allows the custom Rust ASR path to be retired after the Whisper path is integrated and verified.

Do not dynamically load native libraries from downloaded ZIPs in the first release. Runtime libraries and ABI compatibility are a separate engineering problem and are not required to make model packs downloadable.

## Selected model shortlist

| Feature | Initial candidate | Reason | Package |
|---|---|---|---|
| Persian speech-to-text | Whisper large-v3 int8 ONNX | Multilingual and accuracy-first for Persian; supported by sherpa-onnx OfflineRecognizer | One ASR package |
| Persian text-to-speech | Piper VITS ONNX, evaluate Ganji Adabi and Ganji first | Existing sherpa-onnx TTS path; compact model/config files; Persian voice set available | One package per voice |
| English speech-to-text | Same Whisper multilingual package | No separate English model required | Included with ASR |
| English text-to-speech | Select a Piper en-US/en-GB voice after listening and license review | Same runtime and package shape | One package per voice |

The Persian Piper candidate list is amir, ganji, ganji_adabi, gyro, and reza_ibrahim. They are currently listed as medium-quality, single-speaker voices. Select the default only after native-speaker listening tests. Do not infer male/female labels from names.

## Why not Chatterbox / Pocket-TTS Persian first?

A Persian ONNX Pocket-TTS conversion exists and may sound more natural, but its Persian model is marked CC-BY-NC-4.0 (non-commercial). It is not a safe default for a public Link product without separate commercial permission. It also introduces a more complex model pipeline and more runtime glue than Piper plus the existing sherpa-onnx dependency.

## Planned plugin catalog IDs

- asr.whisper-large-v3.int8.multilingual
- tts.piper.fa-IR.ganji-adabi
- tts.piper.fa-IR.ganji
- Later: other Persian Piper voices and a selected English Piper voice.

The catalog remains empty until each package is assembled, checksummed, license-reviewed, and tested on Android.

## Implementation sequence

1. Freeze the current Link Standard runtime version and use the existing sherpa-onnx dependency for both ASR and TTS.
2. Replace the custom Rust ASR model pipeline with sherpa-onnx Whisper OfflineRecognizer. Keep the current ASR Java-facing interface so the rest of Link does not need to know which model is active.
3. Convert TTS model loading to resolve a selected Piper plugin directory (ONNX plus JSON config plus shared phonemizer data) rather than copying the old bundled model assets.
4. Keep model packs separate from runtime binaries. Lite builds contain neither speech runtime nor speech UI; Standard builds contain the runtime but no large speech models.
5. Add catalog entries only after package metadata, inner file checksums, upstream revision, model license and test results are recorded.
6. Test Persian transcription and synthesis on representative Android devices. Measure cold-start time, peak RAM, CPU time, and battery impact. Add a smaller ASR alternative only if large-v3 is too slow for target devices.
7. After model plugins work, consider moving the sherpa runtime to a separately downloadable runtime package. Do not attempt this until Android linker and ABI behavior is explicitly verified.

## Non-negotiable release checks

- Model files and voices must be pinned to immutable revisions.
- License and attribution are checked per model/voice, not inferred from the engine license.
- SHA-256 is recorded for the release ZIP and every payload file.
- No network access is required during inference after installation.
- Inference runs on worker threads and can be cancelled.
- Existing speech controls remain disabled until a compatible plugin is installed.
- The installer validates archive size, archive checksum, file checksums, paths, and compatibility before activation.
- No build/test has been run as part of this planning update.
