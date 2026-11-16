#!/usr/bin/env bash
set -euo pipefail

SOURCE_DIR="${1:?plugin source directory is required}"
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
WORK_DIR="$(mktemp -d)"
trap 'rm -rf "$WORK_DIR"' EXIT

TASKS_VERSION="1.1.1"
MODEL_URL="https://storage.googleapis.com/mediapipe-models/interactive_segmenter_v2/magic_touch/int8/1/interactive_segmentation.task"
ANDROID_PLATFORM="${ANDROID_PLATFORM:-35}"
BUILD_TOOLS_VERSION="${BUILD_TOOLS_VERSION:-35.0.0}"
ANDROID_JAR="${ANDROID_HOME}/platforms/android-${ANDROID_PLATFORM}/android.jar"
D8="${ANDROID_HOME}/build-tools/${BUILD_TOOLS_VERSION}/d8"

for required in "$ANDROID_JAR" "$D8"; do
  test -f "$required" || { echo "Missing Android SDK tool: $required" >&2; exit 2; }
done
command -v gradle >/dev/null
command -v javac >/dev/null
command -v readelf >/dev/null

mkdir -p "$SOURCE_DIR/model" "$SOURCE_DIR/lib/arm64-v8a" "$SOURCE_DIR/code" "$WORK_DIR/artifacts"
curl --fail --location --retry 3 --connect-timeout 20 "$MODEL_URL" -o "$SOURCE_DIR/model/interactive_segmentation.task"
test -s "$SOURCE_DIR/model/interactive_segmentation.task"

gradle --no-daemon --stacktrace -b "$REPO_ROOT/tools/mediapipe-runtime.gradle" \
  copyMediaPipeRuntimeArtifacts -PruntimeOutputDir="$WORK_DIR/artifacts"

python3 - "$SOURCE_DIR" "$WORK_DIR/artifacts" "$REPO_ROOT" <<'PY'
import hashlib, json, os, sys
from pathlib import Path
source, artifacts, repo = map(Path, sys.argv[1:])
def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return {"size_bytes": path.stat().st_size, "sha256": h.hexdigest()}
model = source / "model/interactive_segmentation.task"
entries = [{"file": p.name, **digest(p)} for p in sorted(artifacts.iterdir()) if p.is_file()]
lock = {
    "tasks_version": "1.1.1",
    "model": {
        "url": "https://storage.googleapis.com/mediapipe-models/interactive_segmenter_v2/magic_touch/int8/1/interactive_segmentation.task",
        **digest(model)
    },
    "artifacts": entries
}
lock_path = repo / "tools/mediapipe-runtime.lock.json"
generated = repo / "tools/mediapipe-runtime.lock.generated.json"
if os.environ.get("MEDIAPIPE_AUDIT_ONLY") == "1":
    generated.write_text(json.dumps(lock, indent=2) + "\n", encoding="utf-8")
    print("MEDIAPIPE_RUNTIME_LOCK=" + json.dumps(lock, sort_keys=True))
else:
    if not lock_path.is_file():
        raise SystemExit("Pinned MediaPipe checksum lock is missing. Run the dedicated audit workflow, review its output, and commit tools/mediapipe-runtime.lock.json first.")
    expected = json.loads(lock_path.read_text(encoding="utf-8"))
    if expected != lock:
        raise SystemExit("MediaPipe upstream artifacts do not match the committed SHA-256 lock.")
    provenance = source / "provenance"
    provenance.mkdir(parents=True, exist_ok=True)
    (provenance / "mediapipe-runtime-lock.json").write_text(
        json.dumps(lock, indent=2) + "\n", encoding="utf-8")
PY

mkdir -p "$WORK_DIR/unpacked" "$WORK_DIR/jars" "$WORK_DIR/classes" "$WORK_DIR/dex"
shopt -s nullglob
for artifact in "$WORK_DIR"/artifacts/*; do
  base="$(basename "$artifact")"
  case "$artifact" in
    *.aar)
      unpack="$WORK_DIR/unpacked/${base%.aar}"
      mkdir -p "$unpack"
      unzip -q "$artifact" -d "$unpack"
      if [[ -s "$unpack/classes.jar" ]]; then
        cp "$unpack/classes.jar" "$WORK_DIR/jars/${base%.aar}-classes.jar"
      fi
      if [[ -d "$unpack/jni/arm64-v8a" ]]; then
        while IFS= read -r -d '' library; do
          target="$SOURCE_DIR/lib/arm64-v8a/$(basename "$library")"
          if [[ -e "$target" ]] && ! cmp -s "$library" "$target"; then
            echo "Conflicting native library filename: $(basename "$library")" >&2
            exit 3
          fi
          cp "$library" "$target"
        done < <(find "$unpack/jni/arm64-v8a" -maxdepth 1 -type f -name '*.so' -print0)
      fi
      ;;
    *.jar)
      cp "$artifact" "$WORK_DIR/jars/$base"
      ;;
    *)
      echo "Unsupported resolved MediaPipe artifact: $artifact" >&2
      exit 4
      ;;
  esac
done

mapfile -t JARS < <(find "$WORK_DIR/jars" -maxdepth 1 -type f -name '*.jar' | sort)
(("${#JARS[@]}" > 0)) || { echo "No Java runtime JARs resolved" >&2; exit 5; }
( find "$SOURCE_DIR/lib/arm64-v8a" -maxdepth 1 -type f -name '*.so' | grep -q . ) || {
  echo "No ARM64 native libraries were found in resolved AARs" >&2
  exit 6
}

CLASSPATH="$(IFS=:; echo "${JARS[*]}")"
ADAPTER="$REPO_ROOT/tools/magic-touch-src/eu/siacs/link/plugins/magic_touch/MagicTouchPlugin.java"
javac -source 8 -target 8 -Xlint:-options -cp "$CLASSPATH:$ANDROID_JAR" \
  -d "$WORK_DIR/classes" "$ADAPTER"
jar --create --file "$WORK_DIR/magic-touch-adapter.jar" -C "$WORK_DIR/classes" .

"$D8" --min-api 24 --lib "$ANDROID_JAR" --classpath "$CLASSPATH" \
  --output "$WORK_DIR/dex" "$WORK_DIR/magic-touch-adapter.jar" "${JARS[@]}"

mapfile -t DEX_FILES < <(find "$WORK_DIR/dex" -maxdepth 1 -type f -name 'classes*.dex' | sort -V)
(("${#DEX_FILES[@]}" > 0)) || { echo "D8 did not produce DEX output" >&2; exit 7; }
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
    raise SystemExit("No native libraries to order")
needed = {}
for library in libraries:
    result = subprocess.run(["readelf", "-d", str(library)], check=True, text=True, capture_output=True)
    needed[library.name] = re.findall(r"Shared library: \[(.+?)\]", result.stdout)
by_name = {p.name: p for p in libraries}
system_prefixes = ("libandroid.", "libc.", "libdl.", "liblog.", "libm.", "libz.", "libEGL.", "libGLES", "libOpenSLES.", "libvulkan.", "libjnigraphics.", "libmediandk.", "libnativewindow.", "libaaudio.", "libstdc++.so", "libatomic.so", "libgcc_s.so", "libGLESv1_CM.so", "libOpenMAXAL.so")
order, visiting, visited = [], set(), set()
def visit(name):
    if name in visited: return
    if name in visiting: raise SystemExit("Native library dependency cycle: " + name)
    visiting.add(name)
    for dependency in needed.get(name, []):
        if dependency in by_name:
            visit(dependency)
        elif not dependency.startswith(system_prefixes):
            raise SystemExit(f"Unresolved non-system native dependency {dependency} required by {name}")
    visiting.remove(name)
    visited.add(name)
    order.append("lib/arm64-v8a/" + name)
for name in sorted(by_name):
    visit(name)
dex_files = sorted((root / "code").glob("classes*.dex"), key=lambda p: int(re.search(r"(\d+)?\.dex$", p.name).group(1) or 1))
metadata = {
    "abis": ["arm64-v8a"],
    "load_order": order,
    "code_files": ["code/" + p.name for p in dex_files],
    "entry_class": "eu.siacs.link.plugins.magic_touch.MagicTouchPlugin",
    "code_api_version": 1
}
(root / ".link-runtime-generated.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"native_libraries": order, "dex_files": metadata["code_files"]}, indent=2))
PY

curl --fail --location --retry 3 --connect-timeout 20 https://www.apache.org/licenses/LICENSE-2.0.txt -o "$SOURCE_DIR/LICENSE-APACHE-2.0.txt"
cat > "$SOURCE_DIR/NOTICE" <<'NOTICE'
Magic Touch Photo includes MediaPipe Tasks Vision and the Google MediaPipe MagicTouch model.
MediaPipe and model licensing: Apache License 2.0.
Upstream model: https://storage.googleapis.com/mediapipe-assets/Model%20Card%20MagicTouch.pdf
NOTICE

echo "Magic Touch runtime assembled in $SOURCE_DIR"
