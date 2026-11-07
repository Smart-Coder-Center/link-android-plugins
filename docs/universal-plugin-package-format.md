# Universal Link plugin package format (v2)

This repository is the public source and distribution point for every downloadable Link plugin. The format is category-neutral: speech engines, AI prompts, model/data packs, translation resources, and future plugin types use the same archive, catalog, download, integrity, and installation pipeline.

## Source layout

Each plugin has one source directory:

```text
plugins/
  <kind>/
    <plugin-id>/
      plugin.json
      ...payload files...
```

The source `plugin.json` contains package metadata:

- `id`: stable unique ID matching `^[a-z0-9]+([.-][a-z0-9]+)*$`.
- `name`, `description`: user-facing metadata.
- `kind`: extensible lowercase category such as `asr`, `tts`, `prompt`, `translation`, or `ai-model`. The catalog must not hard-code a closed list of kinds.
- `language`: language tag, or `und` for language-neutral packages.
- `version`: immutable package version.
- `min_link_version`: minimum compatible Link version in `major.minor.patch` form.
- `license`: object with at least `name`; include `url` and attribution/provenance when available.
- Optional `release_notes` and consumer-specific metadata.

Do not put generated `files` checksums or archive URL/size/hash in the source manifest; the packaging Action generates these values.

## Generated ZIP layout

The Action creates a data-only ZIP with a root-level `plugin.json` and all payload files, preserving relative paths. The generated manifest contains the source metadata plus a `files` array with one SHA-256 entry per payload file. The public catalog entry contains the exact release URL, byte size, and SHA-256 of the complete ZIP.

Downloaded packages must contain data only. Do not package APK, DEX, JAR, native libraries, executable binaries, scripts, or code intended to be loaded/executed by Link. Link's signed APK supplies trusted runtime code; plugins supply data/configuration only.

## Publishing

The generic workflow scans `plugins/**/plugin.json`, validates metadata and payload paths, creates an immutable GitHub Release asset for each new plugin version, and updates `manifest/plugins.json`. The version/tag is immutable: change the plugin version whenever payload or metadata changes. Existing catalog entries are retained unless the same plugin ID is being advanced to a new version.

Large archives belong in GitHub Releases, never Git history. The Android app downloads the catalog's ZIP through its shared download manager, verifies archive size/SHA-256, extracts into app-private versioned storage, and verifies every payload checksum before activating the package.

## License metadata

License and attribution files should be included in the source package when supplied. License notices are not a reason to stop independent inspection, conversion, packaging preparation, or integration work; provide a concise reminder for restrictive terms and continue. Do not misstate license terms or remove notices.
