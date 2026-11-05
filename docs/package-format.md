# Plugin package format (draft v1)

This is the packaging contract for downloadable Link plugins. A package is a ZIP uploaded as an asset to a versioned GitHub Release. Do not commit large model or runtime binaries to the Git repository.

## Required archive layout

```
plugin.zip
├── plugin.json
├── payload/
│   ├── models/
│   ├── data/
│   └── lib/
│       ├── arm64-v8a/
│       ├── armeabi-v7a/
│       ├── x86/
│       └── x86_64/
└── LICENSES/
    └── ...
```

Only include directories/files required by that plugin. ABI-specific native libraries are optional and must be listed in plugin metadata. The app must reject unsupported ABI/runtime combinations.

## plugin.json

Each ZIP must contain a manifest with:
- `id`: stable catalog ID.
- `version`: semantic or otherwise consistently ordered package version.
- `kind`: `asr` or `tts`.
- `language`: BCP-47 language tag such as `fa-IR` or `en-US`.
- `files`: relative file paths and SHA-256 digests for every payload file.
- `runtime`: engine identifier/version and supported ABIs, when applicable.
- `license`: license and attribution information.

The outer catalog archive checksum protects the complete ZIP. The inner file checksums allow validation after safe extraction.

## Installation requirements

The Link app must:
1. Download over HTTPS to a temporary file in app-private storage.
2. Verify exact byte size and SHA-256 against the public catalog.
3. Reject ZIP entries with absolute paths, parent traversal, unexpected symlinks, duplicate paths, or excessive expanded size/file count.
4. Verify every extracted file against `plugin.json`.
5. Install into a versioned private directory and atomically activate only after validation.
6. Keep the previous working version until activation succeeds.
7. Never execute scripts or load code from an untrusted archive.
8. Expose download progress, total size, pause/resume where supported, and a clear failure reason.

Native libraries, if included, must be loaded only from the validated app-private plugin directory and only for a supported ABI. Runtime loading design must be reviewed against Android linker dependencies before publishing any native engine package.

## Important

The package format is a draft contract, not proof that any engine package is ready. A plugin must not appear as installable until its binaries, licenses, ABI coverage, runtime integration, and checksum have all been verified.
