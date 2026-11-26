#!/usr/bin/env python3
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

root = Path(sys.argv[1])
manifest = json.loads((root / "plugin.json").read_text(encoding="utf-8"))
if manifest.get("id") != "document-editor" or manifest.get("kind") != "document":
    raise SystemExit("Unexpected Document Editor plugin identity")
if manifest.get("package_type") != "native_runtime":
    raise SystemExit("Document Editor must use the signed native_runtime package type")
source = manifest.get("source", {})
pins = {
    "tesseract4android_version": "4.9.0",
    "document_scanner_version": "16.0.0",
    "code_scanner_version": "16.1.0",
    "tessdata_fast_revision": "87416418657359cb625c412a48b6e1d6d41c29bd",
    "languages": ["fas", "eng"],
}
for key, expected in pins.items():
    if source.get(key) != expected:
        raise SystemExit(f"Unreviewed Document Editor dependency/model pin: {key}")

runtime = manifest.get("runtime", {})
if runtime.get("entry_class") != "eu.siacs.link.plugins.document.DocumentEditorPlugin":
    raise SystemExit("Invalid Document Editor runtime entry class")
if runtime.get("code_api_version") != 1 or runtime.get("abis") != ["arm64-v8a"]:
    raise SystemExit("Document Editor runtime API/ABI declaration is invalid")

expected_models = {
    "fas.traineddata": (431500, "1a17ee02076107e73abd15d2038389150c8f824f"),
    "eng.traineddata": (4113088, "bbef4675053b5b468cdb477053e28b1c698ba08e"),
}
for name, (expected_size, expected_blob_sha) in expected_models.items():
    model = root / "model" / "tessdata" / name
    if not model.is_file() or model.stat().st_size != expected_size:
        raise SystemExit(f"Missing or unpinned OCR model payload: {name}")
    data = model.read_bytes()
    actual_blob_sha = hashlib.sha1(b"blob " + str(len(data)).encode() + b"\\0" + data).hexdigest()
    if actual_blob_sha != expected_blob_sha:
        raise SystemExit(f"OCR model Git blob SHA-1 mismatch: {name}")

code_files = runtime.get("code_files", [])
if not isinstance(code_files, list) or not code_files:
    raise SystemExit("Document Editor runtime has no DEX code files")
dex_payload = bytearray()
for relative in code_files:
    if not re.fullmatch(r"code/[A-Za-z0-9_./+-]+\.dex", relative):
        raise SystemExit(f"Unsafe DEX path: {relative}")
    path = root / relative
    data = path.read_bytes()
    if not data.startswith(b"dex\n"):
        raise SystemExit(f"Invalid DEX payload: {relative}")
    dex_payload.extend(data)
for symbol in (
    "eu/siacs/link/plugins/document/DocumentEditorPlugin",
    "recognizeText", "startDocumentScan", "startCodeScan",
    "exportPdf", "exportDocx", "handleActivityResult",
):
    if symbol.encode("utf-8") not in dex_payload:
        raise SystemExit(f"Document Editor DEX is missing required API: {symbol}")

libraries = sorted((root / "lib" / "arm64-v8a").glob("*.so"))
if not libraries:
    raise SystemExit("Document Editor has no ARM64 Tesseract native libraries")
expected_load_order = {"lib/arm64-v8a/" + p.name for p in libraries}
load_order = runtime.get("load_order", [])
if len(load_order) != len(expected_load_order) or set(load_order) != expected_load_order:
    raise SystemExit("Document Editor native load order does not cover the exact ARM64 payload")
for library in libraries:
    header = subprocess.run(["readelf", "-h", str(library)], check=True,
                            text=True, capture_output=True).stdout
    if not re.search(r"Class:\\s+ELF64", header) or not re.search(r"Machine:\\s+AArch64", header):
        raise SystemExit(f"Invalid ARM64 ELF library: {library.name}")

print("Document Editor runtime metadata, OCR models, DEX APIs and ARM64 libraries validated.")
