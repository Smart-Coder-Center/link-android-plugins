# Persian Whisper test runbook

## Purpose

Publish two data-only Persian ASR test plugins for the existing Link Whisper adapter. This is deliberately separate from Android APK builds: the model weights are downloaded only by the plugin installer after the user chooses Install in Settings > Plugins.

## Models

- **Whisper Base INT8** — approximately 29.1 MB encoder + 131 MB decoder + 817 KB tokens (about 161 MB decimal before ZIP metadata). Smaller and the first model to install.
- **Whisper Small INT8** — approximately 112 MB encoder + 262 MB decoder + 817 KB tokens (about 375 MB decimal before ZIP metadata). Larger and more memory-intensive.

Both are multilingual Whisper models, not the English-only `.en` variants. Sherpa's documentation lists the multilingual Base and Small exports and states that model names ending in `.en` are English-only.

Sources:
- https://huggingface.co/csukuangfj/sherpa-onnx-whisper-base
- https://huggingface.co/csukuangfj/sherpa-onnx-whisper-small
- https://k2-fsa.github.io/sherpa/onnx/pretrained_models/whisper/export-onnx.html

## Publish the test packages

1. Open the `smart-center-code/link-android-plugins` repository on GitHub.
2. Open Actions → **Publish Persian Whisper test plugins**.
3. Select **Run workflow** on `main`; keep the default version `1.0.0-test.1` for the first run.
4. The workflow downloads the exact pinned upstream revisions, adds the OpenAI Whisper MIT license notice, creates each inner `plugin.json` with per-file SHA-256 checksums, packages the files, checks Link's 400 MiB compressed / 500 MiB expanded limits, publishes a GitHub release, and commits the generated catalog metadata.
5. Wait for the workflow to finish successfully. The catalog is not populated with test plugins until this manual workflow succeeds.

Do not reuse the same version/tag for a second release attempt. If a run partially publishes a release but fails before catalog commit, inspect the release first and use a new version for a clean retry.

## Install and test on Android

1. Use a Link APK that already includes the Sherpa-ONNX v1.13.8 runtime and the Whisper adapter.
2. Open Settings → Plugins → speech engines.
3. Install **Whisper Base فارسی (آزمایشی)** first. Wait for checksum verification and installation to finish.
4. Test Persian dictation with the fixed test protocol below.
5. Install **Whisper Small فارسی (آزمایشی)** and select it in Plugins before repeating the same test set.
6. Only one ASR model can be selected for Persian at a time. Both can remain installed; explicitly select Base or Small before each test.

## Fixed comparison protocol

Use the same Android phone, microphone, room, speaking distance, audio capture path, and phrase list for all engines. Include:
- 10 short everyday Persian sentences
- 10 conversational/colloquial sentences
- 5 longer sentences (10–20 seconds)
- 5 samples with mild background noise
- 5 samples with numbers, dates, names, and mixed Persian/English terms

Record for every sample:
- exact reference transcript
- engine output
- CER and WER after one shared normalizer
- elapsed transcription time and audio duration (RTF)
- phone model, Android version, available RAM, and whether the app became warm or was killed

Also test a 1-second silence, 3-second silence, and 10-second silence. These must not produce invented words. Do not compare a Whisper output normalized differently from another engine.

## Current integration boundaries

- The existing Link adapter already recognizes the exact Base and Small INT8 filenames and configures multilingual Whisper with `language=fa`, `task=transcribe`, 16 kHz audio, 80-dimensional features, and CPU provider.
- The plugin settings screen recognizes IDs starting with `asr.whisper-`; the test plugin IDs intentionally use that prefix.
- No new native runtime is added to the APK.
- No Android build or test is run by the packaging workflow.
- Mana remains the only Persian TTS voice.
- These are experimental test packages, not an accuracy claim or production approval.
