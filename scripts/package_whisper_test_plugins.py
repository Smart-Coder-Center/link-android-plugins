#!/usr/bin/env python3
"""Build verified, data-only Persian Whisper test plugins for Link."""
import argparse
import hashlib
import json
import os
import pathlib
import urllib.request
import zipfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
WORK = ROOT / ".whisper-build"
OPENAI_LICENSE_URL = (
    "https://raw.githubusercontent.com/openai/whisper/"
    "31243bad24cc746f07d4c8bfdd2d974872cb1803/LICENSE"
)
MODELS = {
    "base": {
        "id": "asr.whisper-base.fa",
        "name": "Whisper Base فارسی (آزمایشی)",
        "description": "مدل چندزبانه Whisper Base برای تبدیل آفلاین گفتار فارسی به نوشتار",
        "repo": "csukuangfj/sherpa-onnx-whisper-base",
        "revision": "bb53ee204431c90d314c1cc08d28d23e5b7927cc",
        "files": ["base-encoder.int8.onnx", "base-decoder.int8.onnx", "base-tokens.txt"],
        "version": "1.0.0-test.1",
    },
    "small": {
        "id": "asr.whisper-small.fa",
        "name": "Whisper Small فارسی (آزمایشی)",
        "description": "مدل چندزبانه Whisper Small برای تبدیل آفلاین گفتار فارسی به نوشتار؛ دقت بالقوه بالاتر با مصرف حافظه بیشتر",
        "repo": "csukuangfj/sherpa-onnx-whisper-small",
        "revision": "8f3c18b358db4d1f2fc1eae49d75cd20989e4309",
        "files": ["small-encoder.int8.onnx", "small-decoder.int8.onnx", "small-tokens.txt"],
        "version": "1.0.0-test.1",
    },
}

def sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()

def download(url, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(url, headers={"User-Agent": "Link-Whisper-Test-Packager/1.0"})
    with urllib.request.urlopen(request, timeout=120) as response, target.open("wb") as output:
        while True:
            block = response.read(1024 * 1024)
            if not block:
                break
            output.write(block)
    if not target.is_file() or target.stat().st_size == 0:
        raise RuntimeError(f"Download produced an empty file: {url}")

def build_one(key, version, license_text):
    model = MODELS[key]
    source = WORK / key
    package = WORK / f"{key}-package"
    if package.exists():
        import shutil
        shutil.rmtree(package)
    package.mkdir(parents=True)
    checksums = []
    for filename in model["files"]:
        url = (
            f"https://huggingface.co/{model['repo']}/resolve/"
            f"{model['revision']}/{filename}"
        )
        target = package / filename
        print(f"Downloading {key}: {filename}", flush=True)
        download(url, target)
        checksums.append({"path": filename, "sha256": sha256(target)})
    license_file = package / "LICENSE.txt"
    license_file.write_text(license_text, encoding="utf-8")
    checksums.append({"path": "LICENSE.txt", "sha256": sha256(license_file)})
    inner = {
        "id": model["id"],
        "version": version,
        "kind": "asr",
        "language": "fa",
        "files": checksums,
    }
    (package / "plugin.json").write_text(
        json.dumps(inner, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    DIST.mkdir(parents=True, exist_ok=True)
    archive_name = f"whisper-{key}-fa-{version}.zip"
    archive = DIST / archive_name
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_STORED) as output:
        for item in sorted(package.iterdir()):
            output.write(item, arcname=item.name)
    archive_size = archive.stat().st_size
    if archive_size > 400 * 1024 * 1024:
        raise RuntimeError(f"{archive_name} exceeds Link's 400 MiB archive limit")
    expanded = sum((package / name).stat().st_size for name in model["files"]) + license_file.stat().st_size
    if expanded > 500 * 1024 * 1024:
        raise RuntimeError(f"{archive_name} exceeds Link's 500 MiB expanded limit")
    return {
        "id": model["id"],
        "name": model["name"],
        "description": model["description"],
        "kind": "asr",
        "language": "fa",
        "version": version,
        "min_link_version": "2.21.0",
        "archive": {
            "url": f"https://github.com/smart-center-code/link-android-plugins/releases/download/whisper-test-{version}/{archive_name}",
            "size_bytes": archive_size,
            "sha256": sha256(archive),
        },
        "license": {
            "name": "MIT (OpenAI Whisper weights; Sherpa-ONNX conversion)",
            "url": "https://github.com/openai/whisper/blob/31243bad24cc746f07d4c8bfdd2d974872cb1803/LICENSE",
            "attribution": "OpenAI Whisper weights; ONNX conversion published by k2-fsa/sherpa-onnx. Test package, not endorsed by OpenAI or k2-fsa.",
        },
        "release_notes": "Experimental Persian ASR test package. Multilingual Whisper model, INT8 ONNX, offline CPU inference. Compare Base and Small on the same device and audio set.",
    }

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", required=True)
    args = parser.parse_args()
    if not all(c.isalnum() or c in ".-_" for c in args.version) or ".." in args.version:
        raise SystemExit("Invalid version")
    import shutil
    if WORK.exists():
        shutil.rmtree(WORK)
    WORK.mkdir(parents=True)
    DIST.mkdir(parents=True, exist_ok=True)
    for item in DIST.iterdir():
        if item.is_file():
            item.unlink()
    license_path = WORK / "OPENAI-WHISPER-LICENSE"
    download(OPENAI_LICENSE_URL, license_path)
    license_text = license_path.read_text(encoding="utf-8")
    entries = [build_one(key, args.version, license_text) for key in ("base", "small")]
    manifest_path = ROOT / "manifest" / "plugins.json"
    catalog = json.loads(manifest_path.read_text(encoding="utf-8"))
    existing = {item["id"]: item for item in catalog["plugins"]}
    for entry in entries:
        existing[entry["id"]] = entry
    catalog["plugins"] = list(existing.values())
    catalog["catalog_version"] = int(catalog.get("catalog_version", 0)) + 1
    manifest_path.write_text(
        json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    for entry in entries:
        print(
            f"PLUGIN={entry['id']} SIZE={entry['archive']['size_bytes']} "
            f"SHA256={entry['archive']['sha256']} URL={entry['archive']['url']}"
        )

if __name__ == "__main__":
    main()
