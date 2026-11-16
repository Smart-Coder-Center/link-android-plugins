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

Packages have an explicit `package_type`:

- `data` (default): data/configuration only. APK, DEX, JAR, native libraries, executable binaries, scripts, and code intended to be loaded/executed by Link are rejected.
- `native_runtime`: a separate, signed, ABI-specific package class. It may contain approved native `.so` libraries under `lib/<abi>/` plus model/data assets. It may not contain APK, DEX, JAR, scripts, or arbitrary executable files.

Native runtime ZIPs are signed as follows:
- The workflow requires the GitHub Actions secret `LINK_PLUGIN_RUNTIME_SIGNING_PRIVATE_KEY` (Ed25519 PEM) and the matching pinned public key at `keys/native-runtime-ed25519-public.pem`.
- The canonical JSON representation of the generated root `plugin.json` is signed with Ed25519. The detached Base64 signature is included inside the same ZIP as `plugin.json.sig`, so the user still downloads one archive.
- The manifest lists SHA-256 for every payload file. The catalog separately pins the complete ZIP's exact size and SHA-256.
- Native libraries must be placed under `lib/<abi>/`, and every ABI must be declared in `runtime.abis`. The source manifest must also declare `runtime.load_order` with every packaged `.so` path exactly once, in dependency-first load order. The workflow rejects unsupported ABIs, incomplete load order and unsafe paths.

**Important:** repository-side packaging is not sufficient to make a runtime safe to load. Before publishing or enabling a native-runtime plugin to users, the Link Android app must embed/pin the matching public key, verify the signature and every hash before extraction/loading, enforce ABI/API/ELF dependency checks, extract only into app-private storage, and make native files read-only before loading. Google Play builds must not download executable native code from outside Play; keep this package type disabled for Play-distributed builds. The runtime workflow fails closed when the signing secret or pinned public key is absent.

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


## Native runtime package requirements

The publisher now has a separate `native_runtime` package path. Ordinary data plugins remain data-only. Native runtime source packages may include approved `.so` libraries under `lib/<abi>/` and model/data assets in the same plugin ZIP; APK, DEX, JAR, scripts, and arbitrary executable payloads remain forbidden.

Before any native runtime is enabled for users, the Android consumer must independently implement and pass:
- pinned Ed25519 public-key verification of the canonical root manifest;
- SHA-256 verification of every payload file and the complete archive;
- ABI, Android API, ELF machine/class, SONAME and `DT_NEEDED` validation against explicit allowlists;
- safe extraction (no traversal, symlinks, duplicate paths, or zip bombs) into app-private versioned storage;
- read-only native library files before loading, plus dependency ordering and rollback-safe installation/removal;
- a distribution gate that disables remote executable-code packages in Google Play builds.

The publisher requires `LINK_PLUGIN_RUNTIME_SIGNING_PRIVATE_KEY` as a GitHub Actions secret and its matching public key committed at `keys/native-runtime-ed25519-public.pem`. The public key must also be pinned in the Link APK; a key shipped only inside the downloaded ZIP is not a trust anchor. Until the Android verifier and distribution gate are implemented, do not advertise or activate native runtime packages in production.
