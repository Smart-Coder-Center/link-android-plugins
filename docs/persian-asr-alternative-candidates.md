# Persian ASR alternative-candidate screening

Last reviewed: 2026-11-06

This is a source-level screening only. None of these candidates has been converted, benchmarked on Link phones, or approved for release. Published scores from different datasets/normalizers are not directly comparable.

## Fixed Link gates

- Persian quality must be supported by a reproducible benchmark, not marketing language alone.
- Must run fully offline on Android.
- Prefer the already bundled Sherpa-ONNX v1.13.8 Java runtime; a separate runtime is possible only if its APK/native-library cost is justified.
- Plugin payload must fit the current 400 MiB compressed / 500 MiB expanded limits.
- Commercial redistribution rights must be clear.
- Evaluate CER/WER on the same fixed Persian test set, plus latency, peak RAM, storage, battery, and robustness to conversational speech/noise.
- Keep Mana Piper as the only Persian TTS voice. This document is ASR-only.

## Candidates screened in parallel

| Candidate | Public evidence | Android/runtime fit | Size gate | License gate | Initial decision |
|---|---|---|---|---|---|
| Shenava Koochik v1.5 RNNT Sherpa-ONNX | Held-out Golden-6669 reports WER 9.50%, CER ~2.6%; same family CTC head is reported at WER 8.12%, CER ~2.3% | Native Sherpa-ONNX transducer package; Android supported | INT8 files reported as encoder 131 MB + decoder 4 MB + joiner 1.4 MB, plus tokens; comfortably below expanded cap | Apache-2.0 stated by model card | **High-priority candidate**; test RNNT package first, and inspect the related CTC artifact as a potentially more accurate alternative |
| Diba-STT fa-small-0.42 | Vendor describes offline, real-time Persian recognition; no independent WER/CER table found in the reviewed model card | Mobile/browser/CPU claimed, but its documented Python package/runtime is not Sherpa's current recognizer API | ~53 MB claimed for small model | Apache-2.0 stated by model card | **High-priority investigation**; obtain reproducible benchmark and inspect native/WASM runtime and Android integration cost |
| C1Tech/whisper_small_persian | Claims strong Persian benchmark results; links to Open Persian ASR Leaderboard, but detailed numbers are not exposed in the reviewed card | Whisper architecture; Transformers usage documented, not a ready-made Sherpa package | 74M parameters; actual INT8 ONNX package size not yet measured | Apache-2.0 metadata, but repository requires Hugging Face access/conditions acceptance | **Conditional candidate**; verify access/redistribution conditions, exact benchmark scores, tokenizer parity, and HF-to-Sherpa export |
| Taraneh-WBase | Fine-tuned on ~1,560 hours; FLEURS WER/CER 7.88/2.93; Common Voice 10.76/4.45; Media 24.43/13.46 | Transformers Whisper checkpoint; requires the same conversion work as Taraneh-WMedium | 72.6M parameters F32; INT8 package size must be measured | MIT | **Compact Whisper candidate**; compare directly against current Whisper Base/Small, but published quality is below Taraneh-WMedium |
| Shenava Rizeh-Pizeh v1.0 | Its own card reports ~24.5% WER; 6.9M parameters | Ready Sherpa-ONNX CTC export, Android supported | ~33.23 MB repository bundle | Apache-2.0 | **Low-priority / likely reject on quality**; tiny size does not compensate for the reported WER unless a very-low-resource device tier is needed |
| Quds-v4 Sherpa-ONNX | Self-reported WER 22.9–26.6% on domain-specific sets; trained on private 600-hour data; formal/domain-specialized Persian | Sherpa-ONNX RNNT | Exact package size not confirmed | **CC-BY-NC-4.0 / non-commercial only** | **Reject for Link commercial distribution**; domain specialization and non-commercial license fail the current requirements |
| BuzzASR Persian | Strong reported FLEURS/Common Voice results, but fine-tuned from Whisper Large v3 | Transformers/PyTorch example; not a ready Link Android/Sherpa package | Large-model source; likely incompatible with current mobile package/memory budget | Verify exact model/data redistribution terms before any use | **Reference only**, not a practical current mobile candidate |

## Candidate details and caveats

### 1. Shenava Koochik v1.5 RNNT — first technical priority

The Sherpa-ONNX model card identifies a 114M-parameter FastConformer hybrid and provides an INT8 transducer bundle. The reported INT8 components total about 136.4 MB before tokens and packaging overhead. It explicitly documents Android and Sherpa-ONNX usage. The held-out Golden-6669 figures are WER 9.50% / CER 2.6%. The card also reports a related CTC head from the same Koochik v1.5 family at WER 8.12% / CER about 2.3%; the CTC model artifact must be inspected separately before selecting the better head. These scores are from the model author's own held-out set and must not be compared directly with Taraneh or PESTE scores.

Technical checks:
- Confirm the exact sherpa-onnx API and model type are supported by Link's pinned v1.13.8 AAR.
- Confirm the RNNT triplet, tokens, sample rate, feature configuration, and endpointing.
- Inspect the related CTC export, its exact files/size, and its reproducibility.
- Verify Android JNI smoke test and compare quality/latency with current Whisper.
- Preserve Apache-2.0 notices and exact upstream revision.

Source: https://huggingface.co/Reza2kn/Shenava-Koochik-v1.5-RNNT-sherpa-onnx

### 2. Diba-STT fa-small — strongest size/architecture alternative

The model card describes fa-small-0.42 as roughly 53 MB, designed for real-time mobile/browser use, offline on CPU, and supports Persian conversational speech. It also lists larger fa-0.42 (~1.6 GB) and fa-0.5 (~1 GB), which exceed Link's current expanded package limit. The card warns that small models trade some accuracy for speed/size and that noise/accent affect results. The reviewed card does not provide a reproducible WER/CER table, so the accuracy claim is not yet established against the same test set as the other candidates.

Technical checks:
- Obtain a fixed, versioned checkpoint and inspect all package files and actual size.
- Identify the exact inference runtime, native libraries, model format, tokenizer/decoder, and whether Android Java/Kotlin integration is available.
- Measure APK/native runtime overhead before considering a new runtime.
- Require WER/CER results on the same test set as Koochik and Whisper.
- Verify Apache-2.0 notices for both weights and runtime dependencies.

Source: https://huggingface.co/Dibachain/Diba-STT

### 3. C1Tech Whisper Small Persian — potentially compact fine-tune

The card describes a 74M-parameter Whisper-based Persian model and claims results superior to several larger baselines. However, the repository currently requires accepting Hugging Face access conditions to retrieve files, and the reviewed model card does not provide numeric benchmark tables in readable text. It documents Transformers inference, not a Sherpa-ready ONNX bundle.

Technical checks:
- Confirm access conditions and redistribution rights independently of the Apache-2.0 metadata.
- Obtain numeric results and test-set/normalization definitions from the linked leaderboard.
- Inspect tokenizer, added tokens, decoder prompt, model config, and checkpoint keys.
- Convert to the exact Sherpa version pinned by Link and compare FP32 parity before INT8.
- Measure actual package size and accuracy loss after quantization.

Source: https://huggingface.co/C1Tech/whisper_small_persian

### 4. Taraneh-WBase — compact Whisper-family comparator

Taraneh-WBase is a 72.6M-parameter F32 Whisper Base fine-tune. The reported metrics are weaker than WMedium, but the smaller checkpoint is worth evaluating as a compact Persian-specialized comparator. It still needs HF-to-Sherpa weight/tokenizer conversion; it is not currently a drop-in package.

Source: https://huggingface.co/areffarhadi/Taraneh-WBase

### 5. Rizeh-Pizeh — small fallback only

The package is a ready Sherpa-ONNX CTC export, about 33.23 MB, with Apache-2.0 licensing. However, its own card reports around 24.5% WER. Keep it out of the primary shortlist unless real-device testing reveals a useful low-memory niche. This is a separate Shenava model and does not authorize restoring the retired Shenava Rizeh engine or its custom Rust runtime in Link.

Source: https://huggingface.co/Reza2kn/Shenava-Rizeh-Pizeh-v1.0-sherpa-onnx

### Explicit exclusions

- **Quds-v4:** the model card explicitly says non-commercial use only and declares CC-BY-NC-4.0. Link's commercial redistribution requirement excludes it regardless of its Sherpa packaging.
- **BuzzASR Persian:** promising benchmark reference, but its Large-v3 origin and Transformers/PyTorch deployment path do not meet Link's current mobile package/runtime constraints without major work. Do not treat it as an installable candidate.

## Recommended parallel workstreams

1. **Sherpa-native lane:** Koochik v1.5 RNNT and its related CTC export. Verify v1.13.8 compatibility, exact package sizes, and Android smoke test.
2. **Tiny-runtime lane:** Diba fa-small. Establish reproducible quality and determine its Android runtime/integration cost.
3. **Whisper conversion lane:** C1Tech Whisper Small Persian and Taraneh-WBase, in parallel with the existing Taraneh-WMedium feasibility spike. Do not write app adapters until a valid export and tokenizer parity are demonstrated.
4. **Baseline lane:** current official Whisper Small/Base INT8 with the exact same test set and normalizer.

## Current recommendation

Start with Koochik v1.5 Sherpa RNNT/CTC and Diba fa-small as the two most promising alternatives, while inspecting C1Tech and Taraneh-WBase as Whisper-family candidates. No model should be added to the production catalog, no installer size limit should be changed, and no Android app integration should be merged until license, reproducible accuracy, package size, exact Sherpa v1.13.8 compatibility, and real-device RAM/latency have been verified.

No build or Android test is performed as part of this screening. Mana remains the only Persian TTS voice.
