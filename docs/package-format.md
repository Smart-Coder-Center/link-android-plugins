# Link speech data-pack format (v1)

This document is the publication contract for speech packages supported by Link Android. Packages are **data-only ZIP archives**. Link installs them in app-private storage and never loads DEX, JAR, APK, native libraries, scripts, or other executable code from a downloaded package.

Each ZIP must be no larger than **419,430,400 bytes (400 MiB)**. The installer also limits expanded payload to 500 MiB, ZIP entries to 10,000, and the embedded manifest to 1 MiB.

## Required archive layout

The archive contains a root-level `plugin.json` and exactly the payload files declared by its `files` array. Payload paths are relative to the archive root and use forward slashes. Do not add a `payload/` prefix or include unlisted files.

### Persian ASR — Whisper

The current Android adapter supports multilingual Whisper Small or Base through Sherpa-ONNX. A package may contain either model family, with these exact root-level filenames:

```
plugin.zip
├── plugin.json
├── small-encoder.int8.onnx
├── small-decoder.int8.onnx
└── small-tokens.txt
```

or:

```
plugin.zip
├── plugin.json
├── base-encoder.int8.onnx
├── base-decoder.int8.onnx
└── base-tokens.txt
```

A package can include both model families, but it must include the complete encoder/decoder/token triplet for each model it advertises. The current app adapter checks for the Small triplet first and otherwise uses the Base triplet. The Whisper configuration is multilingual, with language set to Persian (`fa`) and task set to transcription.

### Persian TTS — Piper

The current Android adapter expects one ONNX voice model, its adjacent Piper JSON configuration, tokens, and eSpeak NG phoneme data:

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

The adapter currently requires exactly one non-empty root-level ONNX model. A package with multiple ONNX models is rejected.

## Embedded manifest

The root `plugin.json` must contain:

- `id`: stable lowercase package ID.
- `version`: immutable package version.
- `kind`: `asr` or `tts`.
- `language`: language tag; the Persian adapters request `fa` and accept regional declarations such as `fa-IR`.
- `files`: non-empty array containing every payload file (excluding `plugin.json`), each as `{ "path": "relative/file", "sha256": "64 hexadecimal characters" }`.

Every payload file must be listed exactly once and pass its SHA-256 check. The archive checksum in the public catalog separately protects the complete ZIP.

## Public catalog entry

Add an entry to `manifest/plugins.json` only after the final ZIP is ready. Each entry must provide:

- `id`, `name`, `description`, `kind`, `language`, and `version`.
- `min_link_version` in `major.minor.patch` form.
- `archive.url`: HTTPS GitHub Release asset URL matching this repository's release path.
- `archive.size_bytes`: exact ZIP byte count, between 1 and 419,430,400.
- `archive.sha256`: exact 64-character SHA-256 of the ZIP.
- `license.name`: license identifier/name; required attribution and upstream provenance must be documented alongside the release.

The app accepts archive URLs under this repository's GitHub Releases only. Redirects are manually checked and limited to GitHub's release asset hosts.

## Safe installation and release checklist

1. Verify model provenance, redistribution rights, attribution, and all model/voice/runtime licenses.
2. Confirm the exact filenames and model architecture are supported by the current Android adapter.
3. Build the ZIP with only the required data files and root `plugin.json`.
4. Compute SHA-256 for every payload file and place each digest in `plugin.json`.
5. Compute the final ZIP byte count and SHA-256.
6. Upload the ZIP as an asset to a versioned GitHub Release.
7. Add exact metadata to `manifest/plugins.json`.
8. Validate the catalog and download the release asset independently.
9. Test installation, model initialization, Persian transcription/synthesis, update, fallback, and removal on supported Android devices before treating the package as production-ready.

Downloaded packages must remain data-only. Native speech runtimes stay bundled in the signed Link APK; do not put native libraries or executable content in these ZIPs.
