# Android ASR integration audit — 2026-11-06

This is a source-level integration audit only. No model was downloaded, converted, installed, benchmarked on a phone, or added to the live catalog. No Android build or test was run.

## Findings

### 1. Link's current adapter is Whisper-only

The current `LinkOfflineAsr` implementation:
- Initializes `OfflineWhisperModelConfig` only.
- Looks only for `small-encoder.int8.onnx` / `small-decoder.int8.onnx` / `small-tokens.txt`, or the equivalent Base files.
- Throws an error if neither Whisper layout exists.

The plugin catalog and installer are mostly model-data generic, but the ASR inference adapter is not. A new model cannot be made usable merely by adding a catalog entry.

### 2. Koochik v1.5 RNNT — compatible runtime path, adapter work required

The Link app pins Sherpa-ONNX `v1.13.8`. That exact tag's Kotlin/Java API contains:
- `OfflineTransducerModelConfig(encoder, decoder, joiner)`
- `OfflineModelConfig.transducer`
- `OfflineModelConfig.modelType`
- `OfflineRecognizer` and the same offline stream/decode/result lifecycle used by Link.

The Koochik v1.5 RNNT model card specifies:
- `encoder.int8.onnx`, `decoder.int8.onnx`, `joiner.int8.onnx`, and `tokens.txt`
- `model_type="nemo_transducer"` (not generic `transducer`)
- 16 kHz audio and 80-dimensional features
- CPU inference and offline full-utterance decoding
- Apache-2.0 license metadata
- Self-reported Golden-6669 WER 9.50% / CER 2.60%; these are upstream figures, not Link-device measurements.

The INT8 model components are about 136.4 MB total before tokens and ZIP overhead. The model card says the ONNX metadata already carries an empty `normalize_type`; the export is intended to avoid NeMo per-feature normalization. Do not add a separate normalization transform in Link.

**Integration decision:** Koochik v1.5 RNNT is technically compatible with the pinned Sherpa Java API at source level. A dedicated model-type branch and package filename contract are required in `LinkOfflineAsr`, plus a smoke test and real-device evaluation before release. It is not currently supported by Link's adapter.

### 3. Koochik CTC export — promising but license/size must be pinned carefully

The canonical Koochik v1.0 Sherpa CTC repository currently advertises Apache-2.0 and provides a single `model.onnx` plus `tokens.txt`; the listed model file is about 459 MB, so it is not a viable compressed plugin payload as-is and leaves little room under the expanded limit. Older revisions of that repository showed different license metadata, so the exact revision and its LICENSE file must be pinned before any distribution decision.

An INT8 CTC mirror exists, but its model card says CC-BY-NC 4.0 inherited from its parent. That is not suitable for a commercial Link distribution. Do not use that mirror.

**Integration decision:** do not select the CTC export for packaging yet. Prefer the Apache-2.0 v1.5 RNNT INT8 bundle for the first technical prototype, subject to exact revision/license verification and device testing.

### 4. Diba-STT fa-small-0.42 — small, but no ready Link runtime path

The Diba model card describes fa-small-0.42 as approximately 53 MB, offline, CPU/mobile/browser capable, and Apache-2.0. The same card documents a Python package API and a browser/WASM package. It does not document a Sherpa-ONNX export or a native Android Java/Kotlin API.

The model directory exposes Kaldi-style components (`am`, `conf`, `graph`, `ivector`) rather than the ONNX triplet or Whisper layout Link currently consumes. The hosted repository tree reports roughly 101 MB for that directory, so the stated 53 MB needs clarification (download archive/weights versus full repository contents).

No reproducible WER/CER table was found in the reviewed model card. The small model is explicitly described as trading accuracy for speed/size.

**Integration decision:** keep Diba as a research candidate only. Before Android work, obtain the exact inference engine and Android native integration/redistribution terms, measure the actual deployable package, and request or produce reproducible Persian WER/CER results. Do not add a Python runtime or WebView/WASM bridge to Link just to make the model run without a separate size, lifecycle, microphone, and maintenance assessment.

## Recommended next steps

1. Prototype Koochik v1.5 RNNT as a data-only package on a non-production test branch; implement a separate `nemo_transducer` adapter path.
2. Verify exact upstream revision, LICENSE, checksums, model metadata, and package size before creating any release asset.
3. Run fixed WAV samples through Sherpa 1.13.8 on a desktop harness first, then an Android smoke test, then a fixed-device Persian test set.
4. Compare with the same Whisper baseline using identical audio, normalization, and CER/WER scripts.
5. Keep Diba in parallel research until its native Android runtime and quality evidence are established.

No catalog entry, production app code, model download, or build/test was changed/performed by this audit. Mana remains the only Persian TTS voice.

### 5. Plugin settings screen has Whisper-specific navigation

The settings screen lists catalog plugins generically by `kind`, so a future Koochik catalog item can appear under ASR. However, the screen decides whether to show the non-actionable “Whisper pending” row by checking only IDs beginning with `asr.whisper-`, and the ASR deep-link scroll target also searches only for that prefix. A non-Whisper ASR plugin would therefore be listed alongside a misleading Whisper-pending row, and opening the ASR category may scroll to that row instead of the available model. This should be generalized to “no ASR plugins available” / first ASR plugin when the adapter work is implemented.
