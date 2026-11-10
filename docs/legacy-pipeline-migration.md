# Legacy plugin pipeline migration status

This document records the verified state of older model-publishing paths while they are migrated to the universal package contract in [universal-plugin-package-format.md](universal-plugin-package-format.md).

The universal source of truth is this repository's `main` branch:
- Source packages: `plugins/<kind>/<plugin-id>/`
- Shared publisher: `.github/workflows/package-universal-plugins.yml`
- Public catalog: `manifest/plugins.json`
- Distribution: immutable GitHub Release ZIP assets

Do not delete or disable an older acquisition workflow until its required upstream download/conversion behavior has been preserved in the common pipeline and the replacement package is available.

## Verified inventory (2026-11-10)

| Plugin / path | Current state | Required migration |
|---|---|---|
| Mana Persian Piper (`tts.mana.piper.fa`) | Existing catalog/release `1.0.0` remains available. A universal source manifest for `1.0.1` now uses the existing immutable release ZIP as a SHA-256/size-pinned migration seed, preserving its payload and license notices. This is a reproducible migration seed, not yet a reconstruction of the original upstream acquisition. | Run the universal publisher manually when authorized, verify the replacement package and catalog, then separately pin original Piper/eSpeak source archives and their hashes before claiming upstream-reproducible acquisition. |
| Koochik RNNT (`asr.koochik-rnnt.fa`) | Existing catalog/release `1.0.0-test.1` remains available. A source manifest for `1.0.0-test.2` now pins the exact Hugging Face commit and lists all five upstream files. The universal publisher now acquires pinned Hugging Face files, generates inner checksums, ZIP, immutable release metadata, and catalog entry. The bespoke Koochik publisher was removed. | Run the universal publisher manually when authorized, verify the new release/catalog entry, then test install and Persian speech on Link devices. Keep experimental status until device validation is recorded. |
| Whisper Small/Base | The Android repository still has `.github/workflows/publish-whisper-asr-plugins.yml`, which downloads Sherpa-ONNX archives and publishes release assets. It does not update the current public catalog. The ASR README states that Whisper packages are retired and Koochik is the current experimental ASR package. | Do not silently republish retired models. Preserve the workflow/history until its status is reviewed; only migrate it if the owner restores Whisper as a supported candidate. |
| Additional Piper Persian voices | The Android repository has `.github/workflows/publish-persian-tts-voices.yml`. It downloads three voices, creates ZIPs, and writes catalog metadata itself. Its final catalog write targets `feature/persian-whisper-models`, not `main`, and it uses a separate publishing token. | Replace the bespoke catalog writer with the common packager. All resulting catalog changes must land on `main`. Keep voice candidates separate until pronunciation/listening validation is recorded. |
| Pocket TTS Farsi v2 | The Android repository has `.github/workflows/package-pocket-tts-farsi.yml` and `tools/package_pocket_tts_farsi.py`. The workflow uploads a short-lived Actions artifact only; it does not publish a public release asset or catalog entry. | Preserve its upstream revision pin and package verification, then connect its output to the universal package/catalog pipeline. Its current workflow labels the model CC BY-NC 4.0 (non-commercial evaluation only); preserve that notice and keep the reminder narrow. |

## Android-side consumer boundary

The Android catalog parser currently accepts extensible `kind` values and validates the public catalog independently of ASR/TTS naming. However, the visible manager entry point and installer classes are still speech-oriented (`PluginManagerSettingsFragment`, `SpeechPluginsSettingsFragment`, `SpeechPluginCatalog`, `SpeechPluginInstaller`, and `PluginDownloadManager`).

Accepting and installing a data-only ZIP is not equivalent to implementing a consumer for its contents. Each non-speech kind (for example `prompt`, `translation`, or `ai-model`) still needs a trusted in-app consumer with a defined schema and lifecycle. Downloaded packages must remain data-only; do not load executable code from them.

## Publishing invariants

1. The public catalog on `main` is the only catalog consumed by Link.
2. Every new package version is immutable and published by the universal workflow.
3. The generated ZIP has a root `plugin.json`, payload SHA-256 values, and a catalog entry with the release URL, byte size, and archive SHA-256.
4. Keep existing known-good catalog entries available during migration; replace an entry only with a verified newer version.
5. Preserve upstream revisions, source provenance, license texts, and attribution.
6. Do not run a publishing workflow or Android build as part of this migration unless explicitly authorized.

## Completion checklist

- [x] Mana has a SHA-256/size-pinned migration seed manifest for the universal workflow. Original upstream acquisition pinning, publication, and device validation remain pending.
- [x] Koochik acquisition is pinned in a universal source manifest; the bespoke catalog writer is removed. Publishing and device verification remain pending.
- [ ] Additional Persian Piper voices are routed through the universal workflow and target `main`.
- [ ] Pocket TTS can be installed from the public catalog without a local ZIP picker.
- [ ] Retired Whisper workflows are clearly marked as historical or restored intentionally; no accidental re-publication.
- [ ] Every advertised plugin kind has a trusted app-side consumer or is clearly marked as metadata-only/not yet consumable.
- [ ] Generic publisher execution and Android/device validation have been performed by an authorized operator before the stage is marked complete.
