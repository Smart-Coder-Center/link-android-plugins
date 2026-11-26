#!/usr/bin/env bash
set -euo pipefail

SOURCE_DIR="${1:?plugin source directory is required}"
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
WORK_DIR="$(mktemp -d)"
trap 'rm -rf "$WORK_DIR"' EXIT

ANDROID_PLATFORM="${ANDROID_PLATFORM:-35}"
BUILD_TOOLS_VERSION="${BUILD_TOOLS_VERSION:-35.0.0}"
ANDROID_JAR="${ANDROID_HOME}/platforms/android-${ANDROID_PLATFORM}/android.jar"
D8="${ANDROID_HOME}/build-tools/${BUILD_TOOLS_VERSION}/d8"
TESSDATA_REVISION="87416418657359cb625c412a48b6e1d6d41c29bd"

for required in "$ANDROID_JAR" "$D8"; do
  test -f "$required" || { echo "Missing Android SDK tool: $required" >&2; exit 2; }
done
for command in gradle javac readelf curl python3; do
  command -v "$command" >/dev/null || { echo "Missing required command: $command" >&2; exit 2; }
done

mkdir -p "$SOURCE_DIR/model/tessdata" "$SOURCE_DIR/lib/arm64-v8a" \
  "$SOURCE_DIR/code" "$SOURCE_DIR/provenance" "$WORK_DIR/artifacts" \
  "$WORK_DIR/unpacked" "$WORK_DIR/jars" "$WORK_DIR/classes" "$WORK_DIR/dex"
find "$SOURCE_DIR/model/tessdata" -maxdepth 1 -type f -name '*.traineddata' -delete
find "$SOURCE_DIR/lib/arm64-v8a" -maxdepth 1 -type f -name '*.so' -delete
find "$SOURCE_DIR/code" -maxdepth 1 -type f -name 'classes*.dex' -delete
rm -rf "$SOURCE_DIR/vendor-jars"
rm -f "$SOURCE_DIR/.link-runtime-generated.json"

download_model() {
  local language="$1"
  local expected_size="$2"
  local expected_blob_sha="$3"
  local destination="$SOURCE_DIR/model/tessdata/${language}.traineddata"
  local url="https://raw.githubusercontent.com/tesseract-ocr/tessdata_fast/${TESSDATA_REVISION}/${language}.traineddata"
  local final_url
  final_url="$(curl --silent --show-error --fail --location --proto '=https' --proto-redir '=https' \
    --max-filesize 10485760 --retry 3 --connect-timeout 20 \
    "$url" -o "$destination" -w '%{url_effective}')"
  python3 - "$final_url" <<'PY'
import sys
from urllib.parse import urlparse
url = urlparse(sys.argv[1])
if url.scheme != "https" or url.hostname != "raw.githubusercontent.com":
    raise SystemExit("OCR model redirected to an untrusted host")
PY
  test -s "$destination"
  local actual_size
  actual_size="$(stat -c %s "$destination")"
  [[ "$actual_size" == "$expected_size" ]] || {
    echo "Unexpected ${language} OCR model size: $actual_size" >&2
    exit 8
  }
  python3 - "$destination" "$expected_blob_sha" <<'PY'
import hashlib, pathlib, sys
data = pathlib.Path(sys.argv[1]).read_bytes()
actual = hashlib.sha1(b"blob " + str(len(data)).encode() + b"\\0" + data).hexdigest()
if actual != sys.argv[2]:
    raise SystemExit("OCR model Git blob SHA-1 mismatch")
PY
}
download_model fas 431500 1a17ee02076107e73abd15d2038389150c8f824f
download_model eng 4113088 bbef4675053b5b468cdb477053e28b1c698ba08e

# Resolve exact, version-pinned runtime artifacts in the isolated tools Gradle project.
gradle --no-daemon --stacktrace --project-dir "$REPO_ROOT/tools" \
  copyDocumentEditorRuntimeArtifacts -PdocumentEditorOutputDir="$WORK_DIR/artifacts"

python3 - "$WORK_DIR/artifacts" "$WORK_DIR/unpacked" "$WORK_DIR/jars" <<'PY'
import sys, zipfile
from pathlib import Path
artifacts, unpacked, jars = map(Path, sys.argv[1:])
files = sorted(p for p in artifacts.iterdir() if p.is_file())
if not files:
    raise SystemExit("No Document Editor runtime dependencies were resolved")
if sum(p.stat().st_size for p in files) > 1024**3:
    raise SystemExit("Resolved Document Editor artifacts exceed the 1 GiB safety limit")
for artifact in files:
    if artifact.suffix.lower() == ".aar":
        target = unpacked / artifact.stem
        target.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(artifact) as archive:
            bad = archive.testzip()
            if bad:
                raise SystemExit(f"Corrupt AAR {artifact.name}: {bad}")
            for member in archive.infolist():
                if member.filename.startswith("/") or ".." in Path(member.filename).parts:
                    raise SystemExit(f"Unsafe AAR entry: {artifact.name}:{member.filename}")
            archive.extractall(target)
        classes = target / "classes.jar"
        if classes.is_file() and classes.stat().st_size:
            (jars / (artifact.stem + "-classes.jar")).write_bytes(classes.read_bytes())
        nested = target / "libs"
        if nested.is_dir():
            for jar in sorted(nested.glob("*.jar")):
                (jars / (artifact.stem + "-" + jar.name)).write_bytes(jar.read_bytes())
    elif artifact.suffix.lower() == ".jar":
        (jars / artifact.name).write_bytes(artifact.read_bytes())
    else:
        raise SystemExit(f"Unsupported runtime artifact type: {artifact.name}")
PY

# Only the ARM64 native payload is published; Link's current direct-Pro target is ARM64.
for unpacked in "$WORK_DIR"/unpacked/*; do
  native="$unpacked/jni/arm64-v8a"
  if [[ -d "$native" ]]; then
    while IFS= read -r -d '' library; do
      target="$SOURCE_DIR/lib/arm64-v8a/$(basename "$library")"
      if [[ -e "$target" ]] && ! cmp -s "$library" "$target"; then
        echo "Conflicting ARM64 native library: $(basename "$library")" >&2
        exit 3
      fi
      cp "$library" "$target"
    done < <(find "$native" -maxdepth 1 -type f -name '*.so' -print0)
  fi
done
find "$SOURCE_DIR/lib/arm64-v8a" -maxdepth 1 -type f -name '*.so' | grep -q . || {
  echo "Tesseract4Android did not provide ARM64 native libraries" >&2
  exit 4
}

mapfile -t JARS < <(find "$WORK_DIR/jars" -maxdepth 1 -type f -name '*.jar' | sort)
(("${#JARS[@]}" > 0)) || { echo "No Java runtime JARs were resolved" >&2; exit 5; }
mkdir -p "$SOURCE_DIR/vendor-jars"
for jar_file in "${JARS[@]}"; do
  cp "$jar_file" "$SOURCE_DIR/vendor-jars/$(basename "$jar_file")"
done

ADAPTER="$REPO_ROOT/tools/document-editor-src/eu/siacs/link/plugins/document/DocumentEditorPlugin.java"
CLASSPATH="$(IFS=:; echo "${JARS[*]}")"
javac -source 8 -target 8 -Xlint:-options -cp "$CLASSPATH:$ANDROID_JAR" \
  -d "$WORK_DIR/classes" "$ADAPTER"
jar --create --file "$WORK_DIR/document-editor-adapter.jar" -C "$WORK_DIR/classes" .
"$D8" --min-api 23 --lib "$ANDROID_JAR" --output "$WORK_DIR/dex" \
  "$WORK_DIR/document-editor-adapter.jar" "${JARS[@]}"

mapfile -t DEX_FILES < <(find "$WORK_DIR/dex" -maxdepth 1 -type f -name 'classes*.dex' | sort -V)
(("${#DEX_FILES[@]}" > 0)) || { echo "D8 did not produce DEX output" >&2; exit 6; }
for dex in "${DEX_FILES[@]}"; do
  cp "$dex" "$SOURCE_DIR/code/$(basename "$dex")"
done

python3 - "$SOURCE_DIR" <<'PY'
import json, re, subprocess, sys
from pathlib import Path
root = Path(sys.argv[1])
lib_dir = root / "lib" / "arm64-v8a"
libraries = sorted(lib_dir.glob("*.so"))
if not libraries:
    raise SystemExit("No ARM64 native libraries found")
by_name = {p.name: p for p in libraries}
needed = {}
for library in libraries:
    dynamic = subprocess.run(["readelf", "-d", str(library)], check=True,
                             text=True, capture_output=True).stdout
    needed[library.name] = re.findall(r"Shared library: \[(.+?)\]", dynamic)
system_prefixes = (
    "libandroid.", "libc.", "libdl.", "liblog.", "libm.", "libz.",
    "libEGL.", "libGLES", "libOpenSLES.", "libvulkan.", "libjnigraphics.",
    "libmediandk.", "libnativewindow.", "libaaudio.", "libstdc++.so",
    "libatomic.so", "libgcc_s.so", "libunwind.so"
)
order, visiting, visited = [], set(), set()
def visit(name):
    if name in visited: return
    if name in visiting: raise SystemExit("Native library dependency cycle: " + name)
    visiting.add(name)
    for dependency in needed.get(name, []):
        if dependency in by_name:
            visit(dependency)
        elif not dependency.startswith(system_prefixes):
            raise SystemExit(f"Unresolved native dependency {dependency} required by {name}")
    visiting.remove(name)
    visited.add(name)
    order.append("lib/arm64-v8a/" + name)
for name, library in by_name.items():
    header = subprocess.run(["readelf", "-h", str(library)], check=True,
                            text=True, capture_output=True).stdout
    if not re.search(r"Class:\s+ELF64", header) or not re.search(r"Machine:\s+AArch64", header):
        raise SystemExit(f"Native library is not a 64-bit ARM ELF: {library.name}")
for name in sorted(by_name):
    visit(name)
dex_files = sorted((root / "code").glob("classes*.dex"),
                   key=lambda p: int(re.search(r"(\d+)?\.dex$", p.name).group(1) or 1))
metadata = {
    "abis": ["arm64-v8a"],
    "load_order": order,
    "code_files": ["code/" + p.name for p in dex_files],
    "entry_class": "eu.siacs.link.plugins.document.DocumentEditorPlugin",
    "code_api_version": 1
}
(root / ".link-runtime-generated.json").write_text(
    json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
print("Document Editor runtime metadata generated:", json.dumps(metadata, sort_keys=True))
PY

echo "Document Editor runtime build completed."
