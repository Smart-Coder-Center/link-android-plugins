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

for required in "$ANDROID_JAR" "$D8"; do
  test -f "$required" || { echo "Missing Android SDK tool: $required" >&2; exit 2; }
done
command -v gradle >/dev/null
command -v javac >/dev/null
command -v python3 >/dev/null

mkdir -p "$SOURCE_DIR/code" "$SOURCE_DIR/provenance" "$WORK_DIR/artifacts" "$WORK_DIR/unpacked" "$WORK_DIR/jars" "$WORK_DIR/classes" "$WORK_DIR/dex"
find "$SOURCE_DIR/code" -maxdepth 1 -type f -name 'classes*.dex' -delete
rm -rf "$SOURCE_DIR/vendor-jars"
rm -f "$SOURCE_DIR/.link-runtime-generated.json"

gradle --no-daemon --stacktrace --project-dir "$REPO_ROOT/tools" \
  copyMlKitTranslateRuntimeArtifacts -PmlKitOutputDir="$WORK_DIR/artifacts"

python3 - "$WORK_DIR/artifacts" "$WORK_DIR/unpacked" "$WORK_DIR/jars" "$SOURCE_DIR/provenance/mlkit-aar-audit.json" <<'PY'
import json, sys, zipfile
from pathlib import Path
from xml.etree import ElementTree

artifacts, unpacked, jars, report_path = map(Path, sys.argv[1:])
files = sorted(p for p in artifacts.iterdir() if p.is_file())
if not files:
    raise SystemExit("No ML Kit runtime artifacts were resolved")
if sum(p.stat().st_size for p in files) > 1024**3:
    raise SystemExit("Resolved ML Kit runtime artifacts exceed the 1 GiB safety limit")

report = {"artifacts": [], "aar_resources": [], "aar_components": [], "native_libraries": []}
for artifact in files:
    record = {"file": artifact.name, "size_bytes": artifact.stat().st_size}
    if artifact.suffix.lower() == ".aar":
        target = unpacked / artifact.stem
        target.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(artifact) as archive:
            bad = archive.testzip()
            if bad:
                raise SystemExit(f"Corrupt AAR {artifact.name}: {bad}")
            archive.extractall(target)
        classes = target / "classes.jar"
        if classes.is_file() and classes.stat().st_size:
            destination = jars / (artifact.stem + "-classes.jar")
            destination.write_bytes(classes.read_bytes())
        libs = target / "libs"
        if libs.is_dir():
            for jar in sorted(libs.glob("*.jar")):
                (jars / (artifact.stem + "-" + jar.name)).write_bytes(jar.read_bytes())
        resources = target / "res"
        if resources.is_dir():
            entries = [p.relative_to(target).as_posix() for p in resources.rglob("*") if p.is_file()]
            report["aar_resources"].extend({"aar": artifact.name, "path": item} for item in entries)
        jni = target / "jni"
        if jni.is_dir():
            report["native_libraries"].extend(
                {"aar": artifact.name, "path": p.relative_to(target).as_posix()}
                for p in jni.rglob("*.so") if p.is_file())
        manifest = target / "AndroidManifest.xml"
        if manifest.is_file() and manifest.stat().st_size:
            try:
                root = ElementTree.parse(manifest).getroot()
                for child in list(root):
                    tag = child.tag.split("}")[-1]
                    if tag in {"uses-permission", "permission", "uses-feature"}:
                        report["aar_components"].append({"aar": artifact.name, "element": tag})
                    if tag == "application":
                        for component in list(child):
                            report["aar_components"].append({
                                "aar": artifact.name,
                                "element": component.tag.split("}")[-1],
                                "name": component.attrib.get("{http://schemas.android.com/apk/res/android}name", "")
                            })
            except ElementTree.ParseError as error:
                raise SystemExit(f"Cannot inspect AAR manifest {artifact.name}: {error}")
    elif artifact.suffix.lower() == ".jar":
        (jars / artifact.name).write_bytes(artifact.read_bytes())
    else:
        raise SystemExit(f"Unsupported ML Kit dependency artifact: {artifact.name}")
    report["artifacts"].append(record)

report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
print(json.dumps(report, indent=2))
if report["aar_resources"]:
    raise SystemExit("ML Kit AAR resources were found; DEX-only runtime cannot merge Android resources")
if report["aar_components"]:
    raise SystemExit("ML Kit AAR manifest components/permissions were found; host manifest integration is required")
if report["native_libraries"]:
    raise SystemExit("ML Kit AARs contain native libraries; this DEX-only package cannot load them")
PY

mapfile -t JARS < <(find "$WORK_DIR/jars" -maxdepth 1 -type f -name '*.jar' | sort)
(("${#JARS[@]}" > 0)) || { echo "No ML Kit classes JARs were extracted" >&2; exit 3; }
CLASSPATH="$(IFS=:; echo "${JARS[*]}")"
ADAPTER="$REPO_ROOT/tools/mlkit-translate-src/eu/siacs/link/plugins/translate/MlKitTranslatePlugin.java"
javac -source 8 -target 8 -Xlint:-options -cp "$CLASSPATH:$ANDROID_JAR" \
  -d "$WORK_DIR/classes" "$ADAPTER"
jar --create --file "$WORK_DIR/mlkit-translate-adapter.jar" -C "$WORK_DIR/classes" .

"$D8" --min-api 23 --lib "$ANDROID_JAR" --output "$WORK_DIR/dex" \
  "$WORK_DIR/mlkit-translate-adapter.jar" "${JARS[@]}"

mapfile -t DEX_FILES < <(find "$WORK_DIR/dex" -maxdepth 1 -type f -name 'classes*.dex' | sort -V)
(("${#DEX_FILES[@]}" > 0)) || { echo "D8 did not produce ML Kit DEX output" >&2; exit 4; }
for dex in "${DEX_FILES[@]}"; do
  cp "$dex" "$SOURCE_DIR/code/$(basename "$dex")"
done

python3 - "$SOURCE_DIR" <<'PY'
import json, re, sys
from pathlib import Path
root = Path(sys.argv[1])
dex = sorted((root / "code").glob("classes*.dex"),
             key=lambda p: int(re.search(r"(\d+)?\.dex$", p.name).group(1) or 1))
if not dex:
    raise SystemExit("No DEX output was found")
metadata = {
    "code_files": ["code/" + p.name for p in dex],
    "entry_class": "eu.siacs.link.plugins.translate.MlKitTranslatePlugin",
    "code_api_version": 1
}
(root / ".link-runtime-generated.json").write_text(
    json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
print(json.dumps(metadata, indent=2))
PY

cat > "$SOURCE_DIR/NOTICE" <<'NOTICE'
Link Translate Runtime uses Google ML Kit Translation and Language Identification APIs.
Translation language models are downloaded on demand by ML Kit and are not included in this archive.
The runtime dependency coordinates and inspected AAR metadata are recorded in
provenance/mlkit-aar-audit.json. Third-party notices and licenses remain those of their
respective upstream projects.
NOTICE

echo "ML Kit Translate DEX runtime assembled in $SOURCE_DIR"
