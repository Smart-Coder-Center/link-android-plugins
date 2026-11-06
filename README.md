# Link Android Plugins

Public plugin catalog and release distribution repository for Link Android.

The main Link Android source repository remains private. This repository contains:
- A public JSON catalog consumed by Link.
- Plugin package specifications and release metadata.
- Documentation and license notices.

Large plugin archives are distributed as GitHub Release assets rather than committed to Git history.

## Current status

- **Persian offline TTS:** Mana Piper 1.0.0 remains the only published voice. No additional TTS voices are part of the current work.
- **Persian offline ASR:** the Link integration branch supports both the existing Koochik RNNT engine and multilingual Sherpa-ONNX Whisper packages. Previously installed Whisper Small/Base packages are retained and remain selectable.
- **Sequential Persian Whisper rollout:** only Whisper Large-v3 Turbo Persian (`givia/whisper-large-v3-turbo-persian`, CC-BY-4.0) is the first active conversion and device-test candidate. Taraneh-WMedium and Whisper Persian V4 are deferred; do not download, convert, package, or publish them until Givia passes Link device testing and the next stage is approved.
- **Publication status:** Givia is not yet converted or published. Its actual fine-tuned weights must be converted to the pinned Sherpa-ONNX v1.13.8 format, checked for tensor/tokenizer parity, quantized, and measured before catalog publication. See [the sequential rollout plan](docs/first-whisper-plugin-rollout.md).
- **Retired engine:** Shenava Rizeh is not part of the active catalog and must not be reintroduced.

Do not treat an engine as production-ready solely because its metadata or release asset exists. Verify model provenance, redistribution rights, package checksums, installation, inference, update, removal, and real-device memory/latency.

## Model evaluation

See [the Persian speech model evaluation shortlist](docs/persian-speech-model-evaluation.md) for Persian ASR candidates, benchmark evidence, conversion feasibility, and the proposed validation order. These are research candidates, not downloadable catalog entries until their packages pass the release checks.

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
