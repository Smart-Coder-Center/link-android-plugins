# Link Android Plugins

Public plugin catalog and release distribution repository for Link Android.

The main Link Android source repository remains private. This repository contains:
- A public JSON catalog consumed by Link.
- Plugin package specifications and release metadata.
- Documentation and license notices.

Large plugin archives are distributed as GitHub Release assets rather than committed to Git history.

## Current status

- **Persian offline TTS:** Mana Piper 1.0.0 is listed in the catalog. Its installation and speech quality still require end-to-end testing on supported Android devices.
- **Persian offline ASR:** no Whisper package is currently published in the catalog. The Android app contains a Sherpa-ONNX Whisper adapter for multilingual Whisper Small/Base INT8 packages, but a compatible archive must be built, released, and added to the catalog before it can be downloaded.
- **Retired engine:** Shenava Rizeh is not part of the active catalog. Its retired-package cleanup in the app exists only to remove data left by older installations.

Do not treat an engine as production-ready solely because its metadata or release asset exists. Verify model provenance, redistribution rights, package checksums, installation, inference, update, and removal on real devices.

## Model evaluation

See [the Persian speech model evaluation shortlist](docs/persian-speech-model-evaluation.md) for ASR/TTS alternatives, compatibility notes, and the proposed validation order. These are research candidates, not downloadable catalog entries until their packages pass the release checks.

## Catalog

Raw catalog URL:

`https://raw.githubusercontent.com/smart-center-code/link-android-plugins/main/manifest/plugins.json`

## Publishing a package

1. Prepare a data-only ZIP matching [docs/package-format.md](docs/package-format.md).
2. Verify redistribution rights for the model, voice, runtime, and all bundled data.
3. Compute SHA-256 for every payload file and for the final ZIP.
4. Upload the ZIP as an asset to a versioned GitHub Release.
5. Add its exact release asset URL, byte size, version, compatibility, and SHA-256 to `manifest/plugins.json`.
6. Validate the catalog and verify download, installation, inference, update, and removal.

Never publish API keys, signing credentials, private source, or user data here.
