# Persian speech model evaluation shortlist

Last reviewed: 2026-11-06

This document is a research shortlist, not a downloadable plugin catalog. A model must not be added to `manifest/plugins.json` until its exact files, Android runtime compatibility, license, archive size, and SHA-256 have been verified.

## Current Link constraints

- Link runs speech inference locally through the Sherpa-ONNX runtime already bundled in the app.
- Downloads must be data-only ZIP archives. No DEX/JAR/APK/native libraries/scripts may be shipped as plugins.
- Current ASR adapter accepts multilingual Whisper Small or Base INT8 encoder/decoder/token files.
- Current TTS adapter accepts one Piper-compatible ONNX voice, its JSON config, tokens, and eSpeak NG data.
- Keep model files outside the APK and download on demand to avoid increasing the base APK size.

## Speech-to-text (ASR)

| Candidate | Persian suitability | Android / integration fit | Recommendation |
|---|---|---|---|
| Whisper Small multilingual INT8 | General multilingual baseline; supports Persian. | Direct match for the existing Link adapter and current packaging workflow. | **First package to publish**; best balance to benchmark first. |
| Whisper Base multilingual INT8 | Supports Persian; smaller/faster than Small but generally less accurate. | Direct match for the existing adapter. | **Publish as low-resource option** alongside Small. |
| Taraneh-WBase | Persian-fine-tuned Whisper family. The upstream project reports training on roughly 1,560 hours of Persian speech. | Not a drop-in package yet: export/quantize to the exact Sherpa-ONNX Whisper files and validate decoding before catalog publication. | **High-priority experimental candidate**; potentially better Persian accuracy than generic Whisper. |
| Taraneh-WMedium | Persian-fine-tuned Whisper Medium. | Likely too heavy for many phones; requires ONNX export, quantization, memory/latency testing, and possible adapter changes. | **Research only**, not a first release. |
| Taraneh-WLarge | Persian-fine-tuned Whisper Large. | Very large for on-device Android; requires substantial memory and performance testing. | **Do not prioritize for mobile**; consider server/desktop evaluation only. |
| Shenava Koochik / FastConformer | A separate Persian FastConformer model family, not Shenava Rizeh. A public quantized model card reports streaming support, but the surfaced quantized card lists CC-BY-NC-4.0. | Different Sherpa-ONNX recognizer path and adapter work required; non-commercial license is unsuitable for Link commercial redistribution unless explicit commercial rights are obtained. | **Do not package now**. Reconsider only after license clearance and a device-compatible adapter. |

### ASR sources

- Sherpa-ONNX Whisper export/model documentation: https://k2-fsa.github.io/sherpa/onnx/pretrained_models/whisper/export-onnx.html
- Taraneh Persian ASR family and training/licensing notes: https://github.com/areffarhadi/persian-asr
- Persian ASR benchmark (use as a research reference, not as a guarantee of on-device speed): https://github.com/ArmanJR/PESTE-Benchmark
- Shenava Koochik quantized model card and license declaration: https://huggingface.co/mah92/sherpa-onnx-nemo-ctc-fa-shenava-koochik-v1.0-streaming-int8-2026-06-26

## Text-to-speech (TTS)

| Candidate | Persian suitability | Android / integration fit | Recommendation |
|---|---|---|---|
| Mana Persian Piper | Persian-specific voice trained for Persian speech; already listed in Link catalog. | Directly aligned with current Piper/Sherpa-ONNX adapter and package format. | **Keep as baseline** and compare alternatives with the same test sentences. |
| Piper fa_IR-amir-medium | Persian voice available in public Piper voice indexes. | Likely compatible with the existing Piper adapter, subject to exact model/config/tokens/eSpeak packaging checks. | **Add as first alternative** after license and package validation. |
| Piper fa_IR-ganji-medium | Persian voice available in public Piper voice indexes. | Same Piper integration path; verify the exact model files and voice license. | **Add as second alternative** after validation. |
| Piper fa_IR-gyro-medium | Persian voice available in public Piper voice indexes. | Same Piper integration path; verify exact model files and voice license. | **Add as third alternative** after validation. |
| Mimic3 Persian Haaniye | Listed as a Persian TTS option in Sherpa-ONNX Android model listings. | Not the current Piper package format; requires confirming the exact OfflineTts model configuration and adapting the app's TTS loader if necessary. | **Experimental candidate** after checking quality, files, and license. |

### TTS sources

- Sherpa-ONNX Android TTS model listing includes a Persian Mimic3 Haaniye build: https://k2-fsa.github.io/sherpa/onnx/flutter/tts-android.html
- Piper Persian voice index (Amir, Ganji, Gyro and other candidates): https://huggingface.co/4-alokk/piper-voices
- Mana Persian Piper model card: https://huggingface.co/MahtaFetrat/Mana-Persian-Piper
- Sherpa-ONNX TTS Android documentation: https://k2-fsa.github.io/sherpa/onnx/tts/apk.html

## Models not recommended for the Persian catalog yet

- Kokoro and PocketTTS have attractive quality/size trade-offs in supported languages, but the currently documented locale lists do not include Persian. Do not list them as Persian engines without a verified Persian checkpoint.
- Generic English-only Whisper checkpoints (`.en`) must not be used for Persian.
- Do not reintroduce Shenava Rizeh or its retired custom runtime.

## Proposed evaluation order

1. Publish and test Whisper Small INT8 and Base INT8 using the existing adapter.
2. Add Piper Amir, Ganji, and Gyro as separate selectable voice packages after checking upstream redistribution terms and preparing exact ZIP checksums.
3. Export Taraneh-WBase to the supported Sherpa-ONNX Whisper format and benchmark it against generic Whisper Small on the same Persian audio set.
4. Investigate Mimic3 Haaniye only if its voice quality is competitive and the runtime integration remains small.
5. Consider larger ASR models only after measuring real device RAM, latency, battery use, and transcription quality.

## Release gate

No candidate is a release until the exact upstream revision and license are recorded, all files are checked, the package matches the Android adapter, catalog size and SHA-256 are computed from the final ZIP, and install/transcription-or-synthesis/update/removal are verified on physical Android devices.
