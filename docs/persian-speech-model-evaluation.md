# Persian speech model quality review — ASR only

Last reviewed: 2026-11-06

**Scope decision:** evaluate speech-to-text engines only. Keep the existing Mana Piper voice as the only Persian TTS option. Do not add, download, publish, or expose any additional TTS voices until ASR quality evaluation is complete and a separate decision is made.

This is a research comparison from published model cards and benchmark reports. It is not a claim that these models have been run on Link phones. Published scores use different datasets and normalizers; compare scores only within the same benchmark/table.

## Link's current constraints

- The Link integration branch uses Sherpa-ONNX Java `OfflineRecognizer` and supports both the existing Koochik RNNT package and multilingual Whisper packages.
- The Whisper adapter preserves the legacy Small/Base filenames and also accepts manifest-declared model prefixes, feature dimensions (80/128), Persian language and transcription task. This is the runtime integration only; the three fine-tuned checkpoints still require verified conversion and package publication.
- The app currently pins Sherpa-ONNX Android dependency `v1.13.8`; newer model support must be verified against this exact runtime before integration.
- Downloaded plugin packages are data-only ZIP files. The current integration branch temporarily allows up to 10 GiB compressed and 16 GiB expanded because the requested large Persian checkpoints exceed the old cap. This does not remove the need to measure actual download size, free storage, peak RAM, and download time.
- The signed app already contains Sherpa-ONNX native runtime. Keep weights outside the APK.

## Published Persian quality evidence

## Requested Persian Whisper models

### Whisper Large-v3 Turbo Persian

- Upstream checkpoint: `givia/whisper-large-v3-turbo-persian`.
- Base architecture: OpenAI Whisper Large-v3 Turbo; approximately 809M parameters.
- Training: the model card describes roughly 236 hours of openly licensed Persian speech and a full Persian fine-tune.
- License: CC-BY-4.0; retain the required attribution and model provenance.
- Sherpa contract: Whisper encoder/decoder plus matching multilingual tokens; `feature_dim=128`.
- Conversion status: source checkpoint is Hugging Face Whisper; the pinned Sherpa exporter only loads OpenAI Whisper checkpoints by built-in model name. A strict HF-to-OpenAI weight converter is required before export. Do not use the separate browser ONNX repository as a drop-in Sherpa package: its graph signatures are for Transformers.js.

Sources:
- https://huggingface.co/givia/whisper-large-v3-turbo-persian
- https://huggingface.co/mehrshadjavid/whisper-large-v3-turbo-persian-ONNX

### Whisper Persian V4

- Upstream checkpoint: `nezamisafa/whisper-persian-v4`.
- Base architecture: Whisper Large-v3; the Hugging Face repository reports a 6.18 GB F32 checkpoint and approximately 2B parameters.
- License: Apache-2.0; retain the original notice and attribution.
- Published PESTE v2.1.0 result: normalized CER 4.97% and WER 13.18% on 871 FLEURS Persian test recordings. Treat this as benchmark evidence, not a prediction of Link device performance.
- Sherpa contract: Whisper encoder/decoder plus matching multilingual tokens; `feature_dim=128`.
- Conversion status: Hugging Face Whisper checkpoint; requires the same strict tensor/tokenizer conversion and parity validation as Taraneh-WMedium.

Sources:
- https://huggingface.co/nezamisafa/whisper-persian-v4
- https://github.com/ArmanJR/PESTE-Benchmark

### Taraneh-ASR family

Taraneh publishes five models fine-tuned on about 1,560 hours of Persian speech. The author reports WER/CER after a shared Persian text normalization. The following values are percentages:

| Model | FLEURS WER / CER | Common Voice WER / CER | Media WER / CER | Notes |
|---|---:|---:|---:|---|
| Taraneh-WBase | 7.88 / 2.93 | 10.76 / 4.45 | 24.43 / 13.46 | Small checkpoint; weakest Taraneh Whisper variant |
| Taraneh-WMedium | 4.16 / 1.52 | 3.47 / 1.67 | 14.97 / 8.99 | Best balance candidate for further device evaluation |
| Taraneh-WLarge | 3.86 / 1.33 | 3.34 / 1.53 | 16.06 / 9.54 | Slightly better on FLEURS/CV, but much larger; Media score is worse than WMedium |
| Taraneh-Q0.6B | 7.11 / 2.54 | 9.65 / 3.86 | 22.32 / 11.73 | Qwen3-ASR architecture; not a Whisper drop-in |
| Taraneh-Q1.7B | 6.25 / 2.15 | 7.85 / 3.13 | 21.91 / 11.46 | Qwen3-ASR architecture; too large to assume mobile suitability |

The same source reports WMedium and WLarge substantially outperform WBase across the listed sets. It also reports singing/music results, where WMedium and WLarge are materially better than WBase. These are upstream-reported figures and still need independent reproduction.

**Decision:** do not spend effort publishing Taraneh-WBase as a quality upgrade. Prioritize a conversion/integration feasibility spike for Taraneh-WMedium. Keep WLarge as a quality ceiling/reference, not the first mobile package.

Source: https://github.com/areffarhadi/persian-asr  
Model cards: https://huggingface.co/areffarhadi/Taraneh-WMedium and https://huggingface.co/areffarhadi/Taraneh-WLarge

### Independent Persian benchmark (PESTE)

PESTE v2.1.0 reports normalized CER/WER on 871 FLEURS Persian test recordings. CER is its primary metric:

| Model | CER | WER |
|---|---:|---:|
| whisper-persian-v4-nezamisafa | 4.97% | 13.18% |
| VisualEars FastConformer Persian | 5.18% | 15.52% |
| Whisper Large v3 fine-tune (vhdm) | 5.50% | 14.57% |
| Whisper Large v3 | 5.97% | 20.37% |
| Whisper Large v3 Turbo | 6.10% | 20.27% |
| Shenava Rizeh v1.0 | 6.40% | 15.55% |
| Whisper Small Persian fine-tune | 7.27% | 28.05% |

This leaderboard shows that Persian-specialized models can beat generic multilingual Whisper, but its leading models are not currently drop-in replacements for Link's adapter. Shenava Rizeh remains retired in Link and must not be reintroduced.

Source and full methodology: https://github.com/ArmanJR/PESTE-Benchmark

### Sherpa-ONNX Qwen3-ASR

Sherpa-ONNX documents Qwen3-ASR support on Android (including Java/Kotlin APIs) and lists Persian (`fa`) among supported languages for the 0.6B model. The published INT8 model package is large (the documented archive contains roughly gigabyte-scale model files), so it exceeds Link's current 400 MiB plugin archive cap and would need a separate size/quantization assessment. It is a distinct recognizer API, not a Whisper file triplet.

**Decision:** keep Qwen3-ASR 0.6B as an experimental candidate only. Do not add it to the catalog or change installer limits until the exact Android runtime API, quantized model footprint, peak RAM, and device latency are measured.

Sources:
- https://k2-fsa.github.io/sherpa/onnx/qwen3-asr/index.html
- https://k2-fsa.github.io/sherpa/onnx/qwen3-asr/pretrained.html

### Whisper Base/Small multilingual baseline

The current workflow packages official Sherpa-ONNX multilingual Whisper Base and Small INT8 models. They are useful as a consistent mobile baseline and fit the current adapter, but generic multilingual checkpoints should not be assumed to deliver the best Persian accuracy. The Persian-specific results above justify testing specialized checkpoints before selecting a production default.

Official model packaging reference: https://k2-fsa.github.io/sherpa/onnx/pretrained_models/whisper/

## Recommended evaluation order

1. **Baseline:** run current official Whisper Base and Small INT8 on the same fixed Persian test set and Link Android devices.
2. **Size gate before conversion:** Taraneh-WMedium is listed as 0.8B F32 parameters (3.06 GB source). Standard INT8 weights alone are roughly 800 MB before overhead, but the current Link installer allows 10 GiB compressed / 16 GiB expanded. Do not treat the old 500 MiB cap as current or reject WMedium on that estimate. Measure the actual archive, download/storage needs, and peak RAM; the user's current instruction is to defer size limits while evaluating quality. See the detailed [conversion spike](taraneh-wmedium-conversion-spike.md).
3. **Upper bound:** evaluate Taraneh-WLarge off-device or on a high-memory Android device to quantify quality gain versus size, RAM, and latency.
4. **Alternative architecture:** evaluate Qwen3-ASR 0.6B only after confirming Link's pinned Sherpa 1.13.8 Java API supports it, or explicitly planning a safe dependency upgrade. Measure model size and memory first.
5. Consider VisualEars/FastConformer only after validating the full raw-audio feature pipeline, decoder, language model/tokenizer, license, and compatibility. A standalone quantized acoustic ONNX file is not a complete ASR plugin.

## Taraneh-WMedium conversion feasibility spike (2026-11-06)

The first source-level compatibility check is complete. **The checkpoint is Whisper-based, but it is not directly accepted by Sherpa's published Whisper exporter.**

Verified facts:

- The Taraneh model card identifies the checkpoint as a Hugging Face `WhisperForConditionalGeneration` model based on `openai/whisper-medium`. The published repository contains a 3.06 GB `model.safetensors` file and tokenizer/configuration assets.
- Taraneh's own inference path loads it through Transformers and optionally converts it to **CTranslate2**. That fast path does not produce Sherpa-ONNX files and cannot be used by Link's current Sherpa Java recognizer.
- Sherpa's documented Whisper exporter imports `openai-whisper`, creates an OpenAI Whisper model with `whisper.load_model()`, then exports encoder/decoder graphs and dynamically quantizes their MatMul weights. Its current built-in loader does not load a Hugging Face `WhisperForConditionalGeneration` directory; the special `medium-aishell` path expects a different icefall checkpoint, not Taraneh's safetensors.
- Link's updated integration branch now supports manifest-declared Whisper model prefixes and the 80-dimensional Medium feature layout, while preserving the legacy Small/Base package names. The conversion and package itself remain unverified.
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

The detailed v1.13.8 exporter findings and proposed strict HF-to-OpenAI tensor mapping are recorded in [the conversion spike](taraneh-wmedium-conversion-spike.md). The next technical milestone is a reproducible conversion prototype for each of the three requested checkpoints that produces FP32 ONNX and a parity report before any INT8 packaging. The user's Android device is still required for final latency, RAM, heat, battery, and real-world Persian quality measurements.

Sources:
- Taraneh model card and checkpoint details: https://huggingface.co/areffarhadi/Taraneh-WMedium
- Taraneh inference implementation: https://github.com/areffarhadi/persian-asr
- Sherpa Whisper exporter: https://github.com/k2-fsa/sherpa-onnx/blob/master/scripts/whisper/export-onnx.py
- Sherpa export guide: https://k2-fsa.github.io/sherpa/onnx/pretrained_models/whisper/export-onnx.html

## Fair test protocol required before choosing a default

Use the same audio clips, audio preprocessing, language setting, decoding settings, and text normalizer for every candidate. Separate at least:
- conversational Tehran Persian;
- other Iranian accents and regional pronunciation;
- quiet studio/read speech;
- phone microphone and noisy environments;
- short commands/names/numbers;
- long utterances and mixed Persian/English terms.

Record:
- CER as the primary Persian text accuracy metric;
- WER as a secondary metric;
- exact-match accuracy for short commands and numbers;
- real-time factor and end-to-end latency (p50/p95);
- peak RAM, model download size, installed storage, CPU usage, and battery impact;
- crash rate and behavior after screen rotation/backgrounding.

Use a fixed, consented, locally stored evaluation set with human-checked transcripts. Do not use public benchmark numbers as a substitute for real-device testing. Preserve raw outputs and a versioned normalizer so later engine versions remain comparable.

## Release gate

No new ASR package is production-ready until its model provenance and commercial redistribution license are recorded, the exact package matches the current Android runtime/adapter, package size fits the installer constraints, and install/transcription/update/removal plus real-device quality/performance tests pass.

## TTS status

Mana Piper remains the sole Persian TTS voice in the Link catalog. No additional TTS voices are part of this work.
