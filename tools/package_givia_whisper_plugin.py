#!/usr/bin/env python3
"""Build a data-only Link plugin ZIP from a validated Givia Sherpa conversion."""

from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

MODEL_ID = "givia/whisper-large-v3-turbo-persian"
PLUGIN_ID = "asr.givia-whisper-large-v3-turbo.fa"
PACKAGE_PREFIX = "large-v3-turbo-persian"
LICENSE = "CC-BY-4.0"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def external_data_files(onnx_path: Path) -> list[str]:
    """Return safe relative external-data paths referenced by an ONNX graph."""
    import onnx

    model = onnx.load(str(onnx_path), load_external_data=False)
    locations = set()
    for initializer in model.graph.initializer:
        for item in initializer.external_data:
            if item.key == "location":
                location = item.value
                pure = PurePosixPath(location)
                if pure.is_absolute() or ".." in pure.parts or len(pure.parts) != 1:
                    raise RuntimeError(f"Unsafe ONNX external-data path: {location}")
                locations.add(location)
    return sorted(locations)


def validate_conversion_report(report: dict[str, Any]) -> None:
    if report.get("model_id") != MODEL_ID:
        raise RuntimeError(f"Wrong source model in conversion report: {report.get('model_id')}")
    if report.get("license") != LICENSE:
        raise RuntimeError(f"Unexpected model license: {report.get('license')}")
    if report.get("base_architecture") != "turbo" or report.get("feature_dim") != 128:
        raise RuntimeError("Conversion report is not the expected Whisper Turbo/128-mel model")
    if report.get("package_model_prefix") != PACKAGE_PREFIX:
        raise RuntimeError("Conversion report has the wrong Link package model prefix")
    revision = report.get("source_revision", "")
    if len(revision) != 40 or any(ch not in "0123456789abcdef" for ch in revision.lower()):
        raise RuntimeError("Conversion report does not contain an immutable 40-character source SHA")
    if report.get("forward_parity", {}).get("passed") is not True:
        raise RuntimeError("HF/OpenAI forward parity did not pass")
    inventory = report.get("tokenizer_parity", {}).get("inventory", {})
    if inventory.get("all_special_token_ids_match") is not True:
        raise RuntimeError("Full Whisper special-token inventory did not pass")


def build_package(conversion_dir: Path, output_zip: Path, version: str) -> dict[str, Any]:
    conversion_dir = conversion_dir.resolve()
    output_zip = output_zip.resolve()
    report_path = conversion_dir / "conversion-report.json"
    if not report_path.is_file():
        raise FileNotFoundError(report_path)
    report = json.loads(report_path.read_text(encoding="utf-8"))
    validate_conversion_report(report)

    encoder = f"{PACKAGE_PREFIX}-encoder.int8.onnx"
    decoder = f"{PACKAGE_PREFIX}-decoder.int8.onnx"
    tokens = f"{PACKAGE_PREFIX}-tokens.txt"
    payload_names = {encoder, decoder, tokens}
    for graph_name in (encoder, decoder):
        graph = conversion_dir / graph_name
        if not graph.is_file() or graph.stat().st_size == 0:
            raise RuntimeError(f"Missing INT8 graph: {graph_name}")
        for sidecar in external_data_files(graph):
            payload_names.add(sidecar)
    payload_names.add("ATTRIBUTION.txt")

    for name in payload_names:
        path = conversion_dir / name
        if not path.is_file() or path.is_symlink() or path.stat().st_size == 0:
            raise RuntimeError(f"Missing, empty, or unsafe plugin payload: {name}")

    attribution = (
        "Link Persian speech recognition plugin attribution\n"
        f"Model: {MODEL_ID}\n"
        f"Upstream author: givia\n"
        f"Source revision: {report['source_revision']}\n"
        "License: Creative Commons Attribution 4.0 International (CC BY 4.0)\n"
        "License URL: https://creativecommons.org/licenses/by/4.0/\n"
        "Changes: converted from the upstream Hugging Face checkpoint to Sherpa-ONNX "
        "and dynamically quantized to INT8 for Link.\n"
    )
    attribution_path = conversion_dir / "ATTRIBUTION.txt"
    attribution_path.write_text(attribution, encoding="utf-8")

    files = []
    for name in sorted(payload_names):
        path = conversion_dir / name
        files.append({"path": name, "sha256": sha256(path)})

    plugin_manifest = {
        "id": PLUGIN_ID,
        "version": version,
        "kind": "asr",
        "language": "fa",
        "runtime": {
            "architecture": "whisper",
            "model_prefix": PACKAGE_PREFIX,
            "feature_dim": 128,
            "language": "fa",
            "task": "transcribe",
            "tail_paddings": 300,
        },
        "files": files,
    }
    manifest_path = conversion_dir / "plugin.json"
    manifest_path.write_text(
        json.dumps(plugin_manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    output_zip.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output_zip, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=1) as archive:
        archive.write(manifest_path, arcname="plugin.json")
        for name in sorted(payload_names):
            archive.write(conversion_dir / name, arcname=name)

    archive_sha = sha256(output_zip)
    package_report = {
        "plugin_id": PLUGIN_ID,
        "version": version,
        "model_id": MODEL_ID,
        "source_revision": report["source_revision"],
        "license": LICENSE,
        "archive": str(output_zip),
        "archive_size_bytes": output_zip.stat().st_size,
        "archive_sha256": archive_sha,
        "payload_files": files,
        "status": "built locally; not published and not yet device-tested",
    }
    output_zip.with_suffix(output_zip.suffix + ".report.json").write_text(
        json.dumps(package_report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return package_report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--conversion-dir", required=True, type=Path)
    parser.add_argument("--output-zip", required=True, type=Path)
    parser.add_argument("--version", default="1.0.0-test.1")
    args = parser.parse_args()
    result = build_package(args.conversion_dir, args.output_zip, args.version)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
