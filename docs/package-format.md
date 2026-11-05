# Link speech data-pack format (v1)

This document is the publication contract for speech packages currently supported by Link Android. Packages are **data-only ZIP archives**. Link installs them in app-private storage and never loads DEX, JAR, APK, native libraries, scripts, or other executable code from a downloaded package.

Each ZIP must be no larger than **419,430,400 bytes (400 MiB)**. The installer also limits expanded payload to 500 MiB, ZIP entries to 10,000, and the embedded manifest to 1 MiB.

## Required archive layout

The archive contains a root-level `plugin.json` and exactly the payload files declared by its `files` array. Payload paths are relative to the archive root and use forward slashes.

Example Persian ASR package:

```
plugin.zip
├── plugin.json
├── model.int4.onnx
├── tokens.txt
└── mel_filters_slaney_80x257.json
```

Example Persian TTS package:

```
plugin.zip
├── plugin.json
├── fa_IR-mana-medium.onnx
├── fa_IR-mana-medium.onnx.json
├── tokens.txt
└── espeak-ng-data/
    ├── phondata
    └── ... remaining required eSpeak data files
```

Do not add a `payload/` prefix. Do not include unlisted files. ZIP directory entries such as `espeak-ng-data/` are supported.

## Embedded manifest

The root `plugin.json` must contain:

- `id`: stable lowercase package ID.
- `version`: immutable package version.
- `kind`: `asr` or `tts`.
- `language`: language tag; the currently integrated Persian adapters request `fa` and accept regional declarations such as `fa-IR`.
- `files`: non-empty array containing every payload file (excluding `plugin.json`), each as `{ "path": "relative/file", "sha256": "64 hexadecimal characters" }`.

Every payload file must be listed exactly once and pass its SHA-256 check. The archive checksum in the public catalog separately protects the complete ZIP.

## Current integrated file contracts

For Persian ASR (`kind: "asr"`, language `fa`), the current adapter expects these files at the archive root:

- `model.int4.onnx`
- `tokens.txt`
- `mel_filters_slaney_80x257.json`

For Persian TTS (`kind: "tts"`, language `fa`), the current adapter expects:

- `fa_IR-mana-medium.onnx`
- `fa_IR-mana-medium.onnx.json`
- `tokens.txt`
- `espeak-ng-data/phondata` and the remaining required eSpeak data files under `espeak-ng-data/`

A package is not ready to publish merely because it has these filenames. Confirm the exact model/runtime compatibility and test it on supported Android devices first.

## Public catalog entry

Add an entry to `manifest/plugins.json` only after the final ZIP is ready. Each entry must provide:

- `id`, `name`, `description`, `kind`, `language`, and `version`.
- `min_link_version` in `major.minor.patch` form.
- `archive.url`: HTTPS GitHub Release asset URL matching this repository's release path.
- `archive.size_bytes`: exact ZIP byte count, between 1 and 419,430,400.
- `archive.sha256`: exact 64-character SHA-256 of the ZIP.
- `license.name`: license identifier/name and required attribution should be documented alongside the release.

The app currently accepts archive URLs under this repository's GitHub Releases only. Redirects are manually checked and limited to GitHub's release asset hosts.

## Safe installation and release checklist

1. Verify model provenance, redistribution rights, attribution, and all model/voice/runtime licenses.
2. Build the ZIP with only the required data files and root `plugin.json`.
3. Compute SHA-256 for every payload file and place each digest in `plugin.json`.
4. Compute the final ZIP byte count and SHA-256.
5. Upload the ZIP as an asset to a versioned GitHub Release.
6. Add exact metadata to `manifest/plugins.json`.
7. Validate the catalog and download the release asset independently.
8. Test installation, model initialization, transcription/synthesis, update, fallback, and removal on supported Android devices before treating the package as production-ready.

Downloaded packages must remain data-only. Native speech runtimes stay bundled in the signed Link APK; do not put native libraries or executable content in these ZIPs.
