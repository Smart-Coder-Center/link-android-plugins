# Taraneh-WMedium to Sherpa-ONNX: conversion feasibility

This document records the source-level feasibility findings and release gates for evaluating Taraneh-WMedium in Link. It does not claim that a conversion has been run.

The first source-level compatibility check is complete. **The checkpoint is Whisper-based, but it is not directly accepted by Sherpa's published Whisper exporter.**

Verified facts:

- The Taraneh model card identifies the checkpoint as a Hugging Face `WhisperForConditionalGeneration` model based on `openai/whisper-medium`. The published repository contains a 3.06 GB `model.safetensors` file and tokenizer/configuration assets.
- Taraneh's own inference path loads it through Transformers and optionally converts it to **CTranslate2**. That fast path does not produce Sherpa-ONNX files and cannot be used by Link's current Sherpa Java recognizer.
- Sherpa's documented Whisper exporter imports `openai-whisper`, creates an OpenAI Whisper model with `whisper.load_model()`, then exports encoder/decoder graphs and dynamically quantizes their MatMul weights. Its current built-in loader does not load a Hugging Face `WhisperForConditionalGeneration` directory; the special `medium-aishell` path expects a different icefall checkpoint, not Taraneh's safetensors.
- Link's current `LinkOfflineAsr` adapter only searches for `small-*` and `base-*` filenames. Even a valid Sherpa Whisper Medium package would not currently be selected without a small app-side adapter update.
- Link's package installer currently caps a compressed archive at 400 MiB and expanded data at 500 MiB. The 3.06 GB source checkpoint is not a distributable package and must not be placed in the catalog.

### Required conversion work

1. Pin the exporter source to the Sherpa-ONNX release corresponding to Link's bundled v1.13.8 runtime; do not use an unpinned `master` exporter for a production artifact.
2. Load Taraneh-WMedium with its own Transformers config and map every encoder/decoder tensor into the exact OpenAI Whisper model structure expected by the pinned Sherpa exporter, or implement a separately reviewed exporter for the Hugging Face model. No model weights may be silently replaced with stock Whisper Medium weights.
3. Verify architecture dimensions, tensor names/shapes, multilingual tokenizer IDs, language/task tokens, and any added/special tokens. The Sherpa token table must represent the same token IDs used by the fine-tuned checkpoint.
4. Export FP32 ONNX first. Compare the ONNX output/transcripts with the original Transformers checkpoint on a fixed audio subset. Only after parity passes, dynamically quantize encoder and decoder to INT8 and measure CER/WER degradation.
5. Run Sherpa's own model test, then a small Java/JNI smoke test using the exact v1.13.8 AAR. Finally update the Link adapter to recognize the Medium file layout and verify package installation/removal.
6. Measure actual archive size. If it exceeds the 400 MiB compressed or 500 MiB expanded limit, stop and assess a supported quantization/compression strategy; do not raise limits before measuring device storage and peak RAM.

### Current decision

**Feasibility is promising but not yet proven.** The base architecture is Whisper Medium, but the HF-to-OpenAI weight mapping, tokenizer parity, ONNX numerical parity, INT8 accuracy, v1.13.8 execution, and package footprint remain unverified. No conversion script, ONNX artifact, catalog entry, release asset, or app adapter change is being published yet. This avoids shipping a package that silently runs stock Whisper or fails at runtime.

The next technical milestone is a reproducible conversion prototype that produces FP32 ONNX and a parity report before any INT8 packaging. The user's Android device is still required for final latency, RAM, heat, battery, and real-world Persian quality measurements.

Sources:
- Taraneh model card and checkpoint details: https://huggingface.co/areffarhadi/Taraneh-WMedium
- Taraneh inference implementation: https://github.com/areffarhadi/persian-asr
- Sherpa Whisper exporter: https://github.com/k2-fsa/sherpa-onnx/blob/master/scripts/whisper/export-onnx.py
- Sherpa export guide: https://k2-fsa.github.io/sherpa/onnx/pretrained_models/whisper/export-onnx.html
