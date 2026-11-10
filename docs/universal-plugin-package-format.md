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

### Pinned upstream acquisition

A source manifest may include an optional `source` object for reproducible remote acquisition. The current supported source types are:

- `huggingface_files`: requires a repository ID, a full 40-character commit SHA, and a list of relative file paths. The publisher downloads those exact files over HTTPS and checks the final redirect host against the Hugging Face allowlist.
- `github_release_zip`: imports an already-published immutable migration seed ZIP from this repository. It requires the canonical Release URL, exact byte size, and SHA-256; extraction rejects unsafe paths, symlinks, excessive entry counts, and expanded archives over 16 GiB.

The private acquisition descriptor is removed from both the generated inner manifest and public catalog; only generated payload checksums and provenance/attribution metadata are published. A migration seed proves the integrity of the imported archive, but does not replace independent pinning of its original upstream source.

Example:

```json
{
  "source": {
    "type": "huggingface_files",
    "repo": "owner/model",
    "revision": "0123456789abcdef0123456789abcdef01234567",
    "files": ["encoder.onnx", "tokens.txt", "LICENSE"]
  }
}
```

An existing public package can be used as a temporary migration seed only when its canonical GitHub Release URL, exact size, and SHA-256 are pinned. The packager verifies the archive and safely extracts its payload before generating a fresh universal ZIP.

The publisher is manual-dispatch only. Adding or editing source manifests does not trigger a release automatically. Large model files are acquired in the ephemeral workflow runner and must never be committed to Git history.


## Generated ZIP layout

The Action creates a data-only ZIP with a root-level `plugin.json` and all payload files, preserving relative paths. The generated manifest contains the source metadata plus a `files` array with one SHA-256 entry per payload file. The public catalog entry contains the exact release URL, byte size, and SHA-256 of the complete ZIP.

Downloaded packages must contain data only. Do not package APK, DEX, JAR, native libraries, executable binaries, scripts, or code intended to be loaded/executed by Link. Link's signed APK supplies trusted runtime code; plugins supply data/configuration only.

## Automatic dependency declarations

A plugin may declare an optional `dependencies` array in its catalog metadata. Each entry must pin an exact immutable version and declare its package type:

```json
{
  "dependencies": [
    {
      "id": "runtime.sherpa-onnx",
      "version": "1.13.8-link.1",
      "package_type": "native_runtime"
    }
  ]
}
```

The user selects only the desired plugin. Link resolves the complete dependency graph, checks exact compatible versions already installed, downloads only missing dependencies, deduplicates shared dependencies, and installs them in dependency-first order. The resolver must reject missing artifacts, version/type conflicts and cycles before changing installed state. Removing a plugin must not remove a dependency still referenced by another installed plugin. This declaration format does not make native runtimes eligible for the ordinary data ZIP workflow; native runtime artifacts remain subject to the separate signed package contract below.

## Publishing

The generic workflow scans `plugins/**/plugin.json`, validates metadata and payload paths, creates an immutable GitHub Release asset for each new plugin version, and updates `manifest/plugins.json`. The version/tag is immutable: change the plugin version whenever payload or metadata changes. Existing catalog entries are retained unless the same plugin ID is being advanced to a new version.

Large archives belong in GitHub Releases, never Git history. The Android app downloads the catalog's ZIP through its shared download manager, verifies archive size/SHA-256, extracts into app-private versioned storage, and verifies every payload checksum before activating the package.

## License metadata

License and attribution files should be included in the source package when supplied. License notices are not a reason to stop independent inspection, conversion, packaging preparation, or integration work; provide a concise reminder for restrictive terms and continue. Do not misstate license terms or remove notices.


## Native runtime dependency packages (planned, separate security class)

Native runtime packages are not enabled in the current data-only ZIP workflow. Do not add `.so` files to ordinary plugin source folders: the current packager intentionally rejects native libraries and executable payloads.

A future `package_type: "native_runtime"` contract must be introduced separately and must require:
- a pinned signing key and detached signature over the exact runtime manifest;
- ABI, Android API, ELF machine/class, SONAME and `DT_NEEDED` dependency metadata;
- an allowlist of native library filenames and exact per-file hashes;
- immutable versioned releases and an explicit dependency graph;
- a direct-download distribution gate, with no external native-code downloads in Google Play builds.

Until the signed runtime packager and Android verifier exist, keep Sherpa/ONNX native binaries out of this repository's data-only plugin ZIP pipeline. See the private Link Android repository's `docs/NATIVE_RUNTIME_PLUGIN_ARCHITECTURE.md` for the design decision.
