# Speech recognition plugins (ASR)

## Recommended engine

Use **sherpa-onnx OfflineRecognizer with multilingual Whisper** as the single ASR runtime in Link.

Why:
- Link already uses sherpa-onnx Java APIs for offline speech features, so the same Java runtime and audio preprocessing path can serve ASR and TTS.
- sherpa-onnx documents Android Java integration and provides pre-trained Whisper ONNX models.
- Whisper is multilingual and supports Persian; one model family can handle Persian and English without separate language-specific recognizers.
- Replacing the current custom Rust ASR path with the existing sherpa-onnx runtime should remove custom Rust/NDK ASR compilation and model-conversion steps from the Standard app workflow.

## First model candidate

**Whisper large-v3, int8 ONNX** (encoder, decoder, and tokens).

This is the accuracy-first candidate for Persian. It is a large model, so the app must check available memory and run inference off the UI thread. It is non-streaming and best suited to recorded voice messages or completed audio clips. A smaller/faster model can be offered later if device benchmarks show large-v3 is too slow.

Do not silently substitute English-only tiny.en models for Persian.

## Suggested package ID

asr.whisper-large-v3.int8.multilingual

Required payload:
- large-v3-encoder.int8.onnx
- large-v3-decoder.int8.onnx
- large-v3-tokens.txt
- license and attribution notices

The final package must be built from a pinned model revision. Record exact archive size and SHA-256 in the catalog and SHA-256 for every payload file in plugin.json.

## Compatibility requirements

- Keep sherpa-onnx runtime in the Link Standard APK initially; do not dynamically load a second ASR runtime.
- Use the sherpa-onnx Java OfflineRecognizer API.
- Explicitly set language to Persian (fa) for Persian recordings; support English (en) as a selectable language or automatic language detection only after testing.
- Normalize input to the model's expected mono 16 kHz audio format.
- Add duration/memory guards and cancellable background inference.
- Validate Persian numerals, names, mixed Persian/English, punctuation, and noisy voice notes with a fixed evaluation set.

## Publication gate

No ASR package is published yet. Before release, benchmark real Android devices, check peak memory and latency, pin upstream revisions, verify model redistribution terms, and publish only after checksums are final.
