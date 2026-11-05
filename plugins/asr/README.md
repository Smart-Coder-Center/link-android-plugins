# Speech recognition plugins (ASR)

## Supported ASR integration

The Link app-side adapter supports multilingual Persian Whisper Small and Base INT8 ONNX packages through Sherpa-ONNX.

**Important:** no Whisper package is currently published in the live catalog. Do not show a download/install action until a versioned package release has been uploaded, its exact checksum and size have been verified, and its entry has been added to `manifest/plugins.json`.

Required package files:
- Whisper encoder ONNX
- Whisper decoder ONNX
- matching tokens file
- model license and attribution notices

Use a pinned upstream model revision. The final ZIP must remain below the app's 400 MiB archive limit and include per-file SHA-256 entries in `plugin.json`.
