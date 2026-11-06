# Link speech data-pack format (v1)

This document is the publication contract for speech packages supported by Link Android. Packages are **data-only ZIP archives**. Link installs them in app-private storage and never loads DEX, JAR, APK, native libraries, scripts, or other executable code from a downloaded package.

The current integration accepts archives up to **10 GiB compressed** and **16 GiB expanded**. The installer checks available storage before download, verifies the exact archive byte count and SHA-256, limits ZIP entries, validates every path, and verifies every payload checksum. These are temporary high limits for the requested large Persian ASR candidates; actual package sizes and device storage/RAM still must be measured before publication.

## Required archive layout

The archive contains a root-level `plugin.json` and exactly the payload files declared by its `files` array. Payload paths are relative to the archive root and use forward slashes. Do not add a `payload/` prefix or include unlisted files.

## Persian ASR — supported architectures

The current Link integration supports two Sherpa-ONNX architectures:

### 1. Whisper (legacy Small/Base and new Persian models)

Legacy Whisper Small/Base packages remain supported without changing their existing file names:

```
plugin.json
small-encoder.int8.onnx
small-decoder.int8.onnx
small-tokens.txt
```

or:

```
plugin.json
base-encoder.int8.onnx
base-decoder.int8.onnx
base-tokens.txt
```

New Whisper packages declare their runtime configuration in `plugin.json`:

```json
{
  "id": "asr.persian-whisper-example.fa",
  "version": "1.0.0",
  "kind": "asr",
  "language": "fa",
  "runtime": {
    "architecture": "whisper",
    "model_prefix": "large-v3-turbo-persian",
    "feature_dim": 128,
    "language": "fa",
    "task": "transcribe",
    "tail_paddings": 300
  },
  "files": [
    {"path": "large-v3-turbo-persian-encoder.int8.onnx", "sha256": "64-hex-digest"},
    {"path": "large-v3-turbo-persian-decoder.int8.onnx", "sha256": "64-hex-digest"},
    {"path": "large-v3-turbo-persian-tokens.txt", "sha256": "64-hex-digest"}
  ]
}
```

The adapter resolves the three model files using `model_prefix`. If the ONNX graphs reference external tensor-data files, include those files beside the graph and list each one in `files`. The Sherpa runtime loads ONNX external data from the graph's adjacent files.

Use `feature_dim: 80` for Whisper Small/Base/Medium and `feature_dim: 128` for Whisper Large-v3 and Large-v3 Turbo. Set `language: "fa"` and `task: "transcribe"`. Only `80` and `128` are accepted by the current adapter.

### 2. Koochik RNNT (existing package)

The existing Koochik package remains supported with these root-level files:

- `encoder.int8.onnx`
- `decoder.int8.onnx`
- `joiner.int8.onnx`
- `tokens.txt`

Declare `"runtime": {"architecture": "nemo_transducer"}` for newly built RNNT packages. The adapter also recognizes the legacy Koochik file triplet when this field is absent.

## Persian model candidates

The following Whisper models are being prepared as separate ASR packages:

| Model | Upstream checkpoint | Base architecture | Feature dimension | Upstream license |
|---|---|---|---:|---|
| Whisper Large-v3 Turbo Persian | `givia/whisper-large-v3-turbo-persian` | Whisper Large-v3 Turbo | 128 | CC-BY-4.0 |
| Taraneh-WMedium | `areffarhadi/Taraneh-WMedium` | Whisper Medium | 80 | MIT |
| Whisper Persian V4 | `nezamisafa/whisper-persian-v4` | Whisper Large-v3 | 128 | Apache-2.0 |

**Important:** each archive must contain the actual fine-tuned checkpoint weights. Do not export stock `openai/whisper-medium`, `large-v3`, or `turbo` weights and label them as a Persian fine-tune. For custom Hugging Face checkpoints, the conversion pipeline must fail on missing/unexpected/shape-mismatched tensors, verify tokenizer IDs and special tokens, compare FP32 ONNX output against the source checkpoint, then measure INT8 accuracy loss. Preserve upstream model and tokenizer notices.

## Persian TTS — Piper

The current Android adapter expects one ONNX voice model, its adjacent Piper JSON configuration, tokens, and eSpeak NG phoneme data:

```
plugin.json
fa_IR-mana-medium.onnx
fa_IR-mana-medium.onnx.json
tokens.txt
espeak-ng-data/
  phondata
  ... remaining required eSpeak data files
```

The adapter currently requires exactly one non-empty root-level ONNX model. A package with multiple ONNX models is rejected.

## Embedded manifest

The root `plugin.json` must contain:

- `id`: stable lowercase package ID.
- `version`: immutable package version.
- `kind`: `asr` or `tts`.
- `language`: language tag; the Persian adapters request `fa` and accept regional declarations such as `fa-IR`.
- `runtime`: optional ASR architecture and model-specific settings; required for newly published Whisper model packs.
- `files`: non-empty array containing every payload file (excluding `plugin.json`), each as `{ "path": "relative/file", "sha256": "64 hexadecimal characters" }`.

Every payload file must be listed exactly once and pass its SHA-256 check. The archive checksum in the public catalog separately protects the complete ZIP.

## Public catalog entry

Add an entry to `manifest/plugins.json` only after the final ZIP is ready. Each entry must provide:

- `id`, `name`, `description`, `kind`, `language`, and `version`.
- `min_link_version` in `major.minor.patch` form.
- `archive.url`: HTTPS GitHub Release asset URL matching this repository's release path.
- `archive.size_bytes`: exact ZIP byte count, within the app's 10 GiB compressed limit.
- `archive.sha256`: exact 64-character SHA-256 of the ZIP.
- `license.name`: license identifier/name; required attribution and upstream provenance must be documented alongside the release.

The app accepts archive URLs under this repository's GitHub Releases only. Redirects are manually checked and limited to GitHub's release asset hosts.

## Safe installation and release checklist

1. Verify model provenance, redistribution rights, attribution, and all model/voice/runtime licenses.
2. Confirm the exact filenames and model architecture are supported by the current Android adapter.
3. Build the ZIP with only the required payload files and root `plugin.json`.
4. Compute SHA-256 for every payload file and place each digest in `plugin.json`.
5. Compute the final ZIP byte count and SHA-256.
6. Upload the ZIP as an asset to a versioned GitHub Release.
7. Add exact metadata to `manifest/plugins.json`.
8. Validate the catalog and download the release asset independently.
9. Test installation, model initialization, Persian transcription, update, fallback, and removal on supported Android devices before treating the package as production-ready.

Downloaded packages must remain data-only. Native speech runtimes stay bundled in the signed Link APK; do not put native libraries or executable content in these ZIPs.
