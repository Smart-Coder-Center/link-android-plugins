# Speech recognition plugins (ASR)

## Recommended engine

Use **sherpa-onnx OfflineRecognizer with multilingual Whisper** as the single ASR runtime in Link.

Why:
- Link already uses sherpa-onnx Java APIs for offline speech features, so the same Java runtime and audio preprocessing path can serve ASR and TTS.
- sherpa-onnx documents Android Java integration and provides pre-trained Whisper ONNX models.
- Whisper multilingual models support Persian and English; one model family can handle both without separate language-specific recognizers.
- Replacing the current custom Rust ASR path with the existing sherpa-onnx runtime should remove custom Rust/NDK ASR compilation and model-conversion steps from the Standard app workflow.

## Primary model candidate

**Whisper Small multilingual, INT8 ONNX** (encoder, decoder, and tokens).

Approximate official sherpa-onnx INT8 payload:
- small-encoder.int8.onnx: about 112 MB
- small-decoder.int8.onnx: about 262 MB
- small-tokens.txt: about 0.8 MB
- Total: about 374 MB before ZIP packaging

This fits Link's agreed maximum archive size of 375,000,000 bytes narrowly. The release pipeline must measure the exact final ZIP size and refuse publication if it exceeds the cap. Use the multilingual Small model, never the English-only Small model, because Persian is required.

The model's on-disk size is not its peak RAM requirement. Before enabling it by default, measure peak memory, cold start, transcription latency, and battery on representative Android devices. Run inference on a cancellable worker thread.

## Fallback model

**Whisper Base multilingual, INT8 ONNX**. Its encoder is about 29 MB and decoder about 131 MB, plus tokens (about 160 MB total). Offer it as a lower-storage and potentially lower-memory fallback if Small is too slow or memory-heavy on target phones.

## Suggested package IDs

- asr.whisper-small.int8.multilingual
- asr.whisper-base.int8.multilingual

Required payload:
- small-encoder.int8.onnx (or base-encoder.int8.onnx)
- small-decoder.int8.onnx (or base-decoder.int8.onnx)
- small-tokens.txt (or base-tokens.txt)
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
