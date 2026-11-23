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

rm -rf "$SOURCE_DIR/lib/arm64-v8a"
mkdir -p "$SOURCE_DIR/code" "$SOURCE_DIR/provenance" "$SOURCE_DIR/lib/arm64-v8a" "$WORK_DIR/artifacts" "$WORK_DIR/unpacked" "$WORK_DIR/jars" "$WORK_DIR/runtime-jars" "$WORK_DIR/classes" "$WORK_DIR/dex"
find "$SOURCE_DIR/code" -maxdepth 1 -type f -name 'classes*.dex' -delete
rm -rf "$SOURCE_DIR/vendor-jars"
rm -f "$SOURCE_DIR/.link-runtime-generated.json"

gradle --no-daemon --stacktrace --project-dir "$REPO_ROOT/tools" \
  copyMlKitTranslateRuntimeArtifacts -PmlKitOutputDir="$WORK_DIR/artifacts"

python3 - "$WORK_DIR/artifacts" "$WORK_DIR/unpacked" "$WORK_DIR/jars" "$SOURCE_DIR/provenance/mlkit-aar-audit.json" "$WORK_DIR/runtime-jars" <<'PY'
import json, sys, zipfile
from pathlib import Path
from xml.etree import ElementTree

artifacts, unpacked, jars, report_path, runtime_jars = map(Path, sys.argv[1:])
files = sorted(p for p in artifacts.iterdir() if p.is_file())
if not files:
    raise SystemExit("No ML Kit runtime artifacts were resolved")
if sum(p.stat().st_size for p in files) > 1024**3:
    raise SystemExit("Resolved ML Kit runtime artifacts exceed the 1 GiB safety limit")

report = {"artifacts": [], "aar_resources": [], "aar_components": [], "aar_manifests": [], "native_libraries": []}
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
            if artifact.name.startswith(("com_google_mlkit__translate__", "com_google_mlkit__language-id__")):
                (runtime_jars / destination.name).write_bytes(classes.read_bytes())
        libs = target / "libs"
        if libs.is_dir():
            for jar in sorted(libs.glob("*.jar")):
                (jars / (artifact.stem + "-" + jar.name)).write_bytes(jar.read_bytes())
        resources = target / "res"
        if resources.is_dir():
            entries = [p.relative_to(target).as_posix() for p in resources.rglob("*") if p.is_file()]
            report["aar_resources"].extend({"aar": artifact.name, "path": item} for item in entries)
            for resource in resources.rglob("translate_models_metadata.json"):
                destination = report_path.parent / "translate_models_metadata.json"
                destination.write_bytes(resource.read_bytes())
        jni = target / "jni"
        if jni.is_dir():
            for library in sorted((jni / "arm64-v8a").glob("*.so")):
                destination = report_path.parent.parent / "lib" / "arm64-v8a" / library.name
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(library.read_bytes())
                report["native_libraries"].append({
                    "aar": artifact.name,
                    "path": "lib/arm64-v8a/" + library.name,
                    "size_bytes": library.stat().st_size
                })
        manifest = target / "AndroidManifest.xml"
        if manifest.is_file() and manifest.stat().st_size:
            manifest_text = manifest.read_text(encoding="utf-8")
            report["aar_manifests"].append({"aar": artifact.name, "xml": manifest_text})
            try:
                root = ElementTree.parse(manifest).getroot()
                for child in list(root):
                    tag = child.tag.split("}")[-1]
                    if tag in {"uses-permission", "permission", "uses-feature"}:
                        report["aar_components"].append({"aar": artifact.name, "element": tag, "attributes": child.attrib})
                    if tag == "application":
                        for component in list(child):
                            report["aar_components"].append({
                                "aar": artifact.name,
                                "element": component.tag.split("}")[-1],
                                "name": component.attrib.get("{http://schemas.android.com/apk/res/android}name", ""),
                                "attributes": component.attrib,
                                "metadata": [
                                    {"name": meta.attrib.get("{http://schemas.android.com/apk/res/android}name", ""),
                                     "value": meta.attrib.get("{http://schemas.android.com/apk/res/android}value", ""),
                                     "resource": meta.attrib.get("{http://schemas.android.com/apk/res/android}resource", "")}
                                    for meta in list(component) if meta.tag.split("}")[-1] == "meta-data"
                                ]
                            })
            except ElementTree.ParseError as error:
                raise SystemExit(f"Cannot inspect AAR manifest {artifact.name}: {error}")
    elif artifact.suffix.lower() == ".jar":
        (jars / artifact.name).write_bytes(artifact.read_bytes())
        if artifact.name.startswith(("com_squareup_okhttp3__", "com_squareup_okio__", "org_jetbrains_kotlinx__kotlinx-coroutines-")):
            (runtime_jars / artifact.name).write_bytes(artifact.read_bytes())
    else:
        raise SystemExit(f"Unsupported ML Kit dependency artifact: {artifact.name}")
    report["artifacts"].append(record)

report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
print(json.dumps(report, indent=2))
if not report["native_libraries"]:
    raise SystemExit("ML Kit AARs did not provide ARM64 JNI libraries")
if not (report_path.parent / "translate_models_metadata.json").is_file():
    raise SystemExit("ML Kit translate_models_metadata.json resource was not found")
PY

mapfile -t JARS < <(find "$WORK_DIR/jars" -maxdepth 1 -type f -name '*.jar' | sort)
mapfile -t RUNTIME_JARS < <(find "$WORK_DIR/runtime-jars" -maxdepth 1 -type f -name '*.jar' | sort)
(("${#JARS[@]}" > 0 && "${#RUNTIME_JARS[@]}" > 0)) || { echo "ML Kit compile or runtime JAR inputs are missing" >&2; exit 3; }
CLASSPATH="$(IFS=:; echo "${JARS[*]}")"
{
  for type in \
    com.google.mlkit.common.sdkinternal.MlKitContext \
    com.google.mlkit.common.internal.MlKitComponentDiscoveryService \
    com.google.mlkit.nl.translate.NaturalLanguageTranslateRegistrar \
    com.google.mlkit.nl.languageid.bundled.internal.ThickLanguageIdRegistrar \
    com.google.firebase.components.ComponentDiscoveryService \
    com.google.firebase.components.ComponentRegistrar; do
    echo "===== $type ====="
    javap -classpath "$CLASSPATH:$ANDROID_JAR" -c -p "$type" 2>&1 || true
  done
} > "$SOURCE_DIR/provenance/mlkit-internal-api.txt"
ADAPTER="$REPO_ROOT/tools/mlkit-translate-src/eu/siacs/link/plugins/translate/MlKitTranslatePlugin.java"
R_SOURCE="$WORK_DIR/r-src/com/google/mlkit/nl/translate/R.java"
TRANSLATE_CLASSES="$(find "$WORK_DIR/jars" -maxdepth 1 -type f -name 'com_google_mlkit__translate__*-classes.jar' | head -n 1)"
if [[ -z "$TRANSLATE_CLASSES" ]]; then
  echo "The pinned Translate AAR classes.jar was not extracted" >&2
  exit 5
fi
if ! jar tf "$TRANSLATE_CLASSES" | grep -q 'com/google/mlkit/nl/translate/R\$raw.class'; then
  mkdir -p "$(dirname "$R_SOURCE")"
  cat > "$R_SOURCE" <<'JAVA'
package com.google.mlkit.nl.translate;

/** Runtime-bound resource IDs for the two Translate AAR resources merged into Link. */
public final class R {
    public static final class raw {
        public static int translate_models_metadata;
    }
    public static final class xml {
        public static int rapid_response_client_defaults;
    }
}
JAVA
  javac -source 8 -target 8 -Xlint:-options -cp "$CLASSPATH:$ANDROID_JAR" \
    -d "$WORK_DIR/classes" "$R_SOURCE" "$ADAPTER"
else
  javap -classpath "$TRANSLATE_CLASSES" 'com.google.mlkit.nl.translate.R$raw' 'com.google.mlkit.nl.translate.R$xml'
  javac -source 8 -target 8 -Xlint:-options -cp "$CLASSPATH:$ANDROID_JAR" \
    -d "$WORK_DIR/classes" "$ADAPTER"
fi
jar --create --file "$WORK_DIR/mlkit-translate-adapter.jar" -C "$WORK_DIR/classes" .

"$D8" --min-api 23 --lib "$ANDROID_JAR" --output "$WORK_DIR/dex" \
  "$WORK_DIR/mlkit-translate-adapter.jar" "${RUNTIME_JARS[@]}"

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
libraries = sorted((root / "lib" / "arm64-v8a").glob("*.so"))
if not libraries:
    raise SystemExit("No ARM64 ML Kit native libraries were extracted")
metadata = {
    "abis": ["arm64-v8a"],
    "load_order": ["lib/arm64-v8a/" + p.name for p in libraries],
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
