# Link Android Plugins

Public plugin catalog and release distribution repository for Link Android.

The main Link Android source repository remains private. This repository contains:
- A public JSON catalog consumed by Link.
- Plugin package specifications and release metadata.
- Documentation and license notices.

Large plugin archives are distributed as GitHub Release assets rather than committed to Git history.

## Current status

- **Persian offline TTS:** Mana Piper 1.0.0 is the only published voice and remains the only TTS option for now. No additional voices will be added until ASR engine quality evaluation is complete and a separate decision is made.
- **Persian offline ASR:** no Whisper package is currently published in the catalog. The Android app contains a Sherpa-ONNX Whisper adapter for multilingual Whisper Small/Base INT8 packages, but a compatible archive must be built, released, and added to the catalog before it can be downloaded.
- **Retired engine:** Shenava Rizeh is not part of the active catalog. Its retired-package cleanup in the app exists only to remove data left by older installations.

Do not treat an engine as production-ready solely because its metadata or release asset exists. Verify model provenance, redistribution rights, package checksums, installation, inference, update, and removal on real devices.

## Model evaluation

See [the Persian speech model evaluation shortlist](docs/persian-speech-model-evaluation.md) for Persian ASR candidates, conversion feasibility, compatibility notes, and the proposed validation order. These are research candidates, not downloadable catalog entries until their packages pass the release checks.

## Catalog

Raw catalog URL:

`https://raw.githubusercontent.com/smart-center-code/link-android-plugins/main/manifest/plugins.json`

## Universal plugin publishing

All downloadable plugin categories use one source layout and one installer contract:

`plugins/<kind>/<plugin-id>/plugin.json` plus that plugin's data files.

The generic workflow `.github/workflows/package-universal-plugins.yml` runs on changes under `plugins/**` or by manual dispatch. It validates each source package, creates a root-manifest data-only ZIP, computes payload and archive SHA-256 values, publishes immutable GitHub Release assets, and updates `manifest/plugins.json`.

Supported kinds are extensible; examples include `asr`, `tts`, `prompt`, `translation`, and `ai-model`. Do not add a new kind by editing a closed allowlist in the app. The app must route a kind to its built-in consumer while using the same catalog, downloader, integrity checks, and private storage pipeline.

See [the universal package format](docs/universal-plugin-package-format.md) for the source layout, metadata contract, and security rules. The [legacy pipeline migration status](docs/legacy-pipeline-migration.md) tracks existing model acquisition workflows and their remaining migration work. The older [speech package format](docs/package-format.md) remains as a compatibility reference for existing speech adapters.

Large archives belong in GitHub Releases, never Git history. Never publish API keys, signing credentials, private source, or user data.
