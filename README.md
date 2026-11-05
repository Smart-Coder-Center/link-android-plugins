# Link Android Plugins

Public plugin catalog and release distribution repository for Link Android.

The main Link Android source repository remains private. This repository contains:
- A public JSON catalog consumed by Link.
- Plugin package specifications and release metadata.
- Documentation and license notices.

Large plugin archives are distributed as GitHub Release assets rather than committed to Git history.

## Current status

The catalog is intentionally empty until each package has been built, tested, licensed, and published with a verified SHA-256 checksum. Do not treat planned plugins as downloadable or installed.

## Planned plugin families

- Persian and English offline speech recognition (ASR).
- Persian and English offline speech synthesis (TTS), with separately selectable voices where available.

## Catalog

Raw catalog URL:

`https://raw.githubusercontent.com/smart-center-code/link-android-plugins/main/manifest/plugins.json`

## Publishing a package

1. Prepare a ZIP matching the package layout in [docs/package-format.md](docs/package-format.md).
2. Verify that redistribution is permitted by the model, runtime, and voice licenses.
3. Compute SHA-256 for the final ZIP.
4. Upload the ZIP as an asset to a versioned GitHub Release.
5. Add its exact release asset URL, byte size, version, compatibility, and SHA-256 to `manifest/plugins.json`.
6. Validate the catalog and verify the download before enabling the plugin in Link.

Never publish API keys, signing credentials, private source, or user data here.
