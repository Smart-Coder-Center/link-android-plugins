# Link three-model Persian ASR comparison — implementation plan

Last reviewed: 2026-11-06

## Goal

Add an ASR-only comparison area under Settings > Plugins. Users can install multiple approved Persian ASR data packs, select one engine at a time, and run the same local audio clips through each engine. Keep the existing Mana Persian TTS voice unchanged.

This plan is not a claim that all three candidates are currently installable or runnable. Do not publish placeholder catalog entries or show an Install button until a complete, verified Android inference path and downloadable package exist.

## Candidate set

1. **Whisper Large-v3 Turbo Persian** — candidate for a Whisper.cpp-based adapter if the chosen checkpoint/quantized artifact is verified. This is a separate runtime path from the app's existing Sherpa-ONNX RNNT adapter. Confirm upstream model license, redistribution terms, exact GGML/GGUF format, tokenizer/task behavior, Android ABI support, APK/runtime overhead, and measured package size.
2. **Taraneh-WMedium** — Hugging Face WhisperForConditionalGeneration checkpoint (~3.06 GB F32 source). It is not a ready-to-install Sherpa package. Requires strict HF-to-supported-runtime conversion, tokenizer-ID parity, FP32 output parity, INT8 accuracy testing, and measured package size. Current 500 MiB expanded plugin cap must not be raised without device storage/RAM evidence. Standard INT8 may exceed the cap.
3. **Whisper Persian V4** — Hugging Face Whisper Large-v3 fine-tune. Treat as a conversion candidate, not a ready Sherpa/Whisper.cpp pack. Verify checkpoint format, tokenizer and special-token parity, exporter support, license/attribution, quantization, package size, and mobile RAM/latency before catalog publication.

## Existing Link architecture constraints

- The current Android ASR implementation is model-specific; a catalog entry alone does not make an arbitrary model executable.
- The current experimental Koochik RNNT path uses the bundled Sherpa-ONNX runtime and expects encoder.int8.onnx, decoder.int8.onnx, joiner.int8.onnx, and tokens.txt with NeMo transducer configuration.
- The signed APK must contain any native inference runtime. Downloaded plugins remain data-only; never load DEX, JAR, APK, scripts, or native libraries from plugin storage.
- Current plugin limits are 400 MiB compressed and 500 MiB expanded. Do not change these limits until actual package sizes and device storage/RAM have been measured.
- Keep model weights out of the APK and download them only through the plugin manager.

## Required implementation phases

### Phase A — runtime feasibility (before UI/catalog exposure)

For each candidate:
- Pin immutable upstream revision and inspect the complete license/redistribution terms.
- Identify exact checkpoint files, tokenizer, decoder, and model configuration.
- Select a runtime actually supported on Android. Do not assume Whisper-family checkpoints are interchangeable.
- Produce a reproducible conversion/quantization pipeline where required.
- Compare source-framework and converted FP32 output on fixed audio samples before quantizing.
- Measure quantized CER/WER, package size, peak RAM, cold start, latency, CPU load, and thermal/battery impact.
- Run a Java/JNI smoke test against the exact runtime version included in Link.

A candidate that fails runtime compatibility, license, package-size, or memory gates remains research-only and must not appear as installable.

### Phase B — plugin packaging

For each passing candidate:
- Create a data-only ZIP with root plugin.json and checksums for every payload file.
- Pin the exact upstream revision and include required license notices.
- Publish the ZIP as a versioned GitHub Release asset.
- Add exact byte size and SHA-256 to manifest/plugins.json.
- Verify download, checksum, install, activation, selection, update, and removal on Android.

Do not add a catalog entry before the release asset and runtime smoke test are complete.

### Phase C — comparison UI and lifecycle

- Add an ASR comparison section in Settings > Plugins, separate from TTS voices.
- Allow multiple ASR data packs to remain installed.
- Load only one ASR engine/model in RAM at a time; release it before loading the next candidate.
- Provide one shared recording/file input and pass the exact same audio samples and preprocessing to every candidate.
- Display each transcript, elapsed time, peak memory when measurable, model version, and errors.
- Permit saving/exporting test results locally; do not upload recordings or transcripts.
- Include optional reference transcripts and report CER/WER using one versioned Persian normalizer.
- Preserve the existing microphone and assistant flows until the user explicitly selects a validated default.

## Fair comparison protocol

Use a fixed, consented Persian dataset with human-verified transcripts. Include conversational Tehran Persian, other Iranian accents, read speech, phone-mic recordings, noisy environments, names/numbers, short commands, long utterances, and mixed Persian/English. Use identical audio sample rate, channel handling, trimming, and normalization across models.

Report:
- CER (primary) and WER (secondary);
- exact match for names, numbers, and short commands;
- p50/p95 end-to-end latency and real-time factor;
- peak RAM, installed storage, cold-start time, CPU use, heat/battery observations;
- failures, crashes, and model load/unload reliability.

Published benchmark scores from different datasets or normalizers must not be presented as a head-to-head result.

## Current decision

The three candidates may be compared in one Link test area only after each has a verified Android runtime and installable data package. The immediate next work is Phase A feasibility, beginning with the Turbo checkpoint/runtime format and the two Hugging Face fine-tunes. No build or phone benchmark is implied by this plan.