#!/usr/bin/env python3
import hashlib
import json
import sys
from pathlib import Path

root = Path(sys.argv[1]).resolve()
manifest_path = root / "plugin.json"
generated_path = root / ".link-runtime-generated.json"
manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
generated = json.loads(generated_path.read_text(encoding="utf-8"))

adapter_path = Path(__file__).resolve().parent / "mlkit-translate-src/eu/siacs/link/plugins/translate/MlKitTranslatePlugin.java"
adapter_source = adapter_path.read_text(encoding="utf-8")
if "RemoteModelManager.getInstance()" in adapter_source or "new TranslateRemoteModel" in adapter_source:
    raise SystemExit("Translate runtime must not call the optional RemoteModelManager download API directly")
if "translator.downloadModelIfNeeded()" not in adapter_source:
    raise SystemExit("Translate runtime must delegate on-demand downloads to Translator.downloadModelIfNeeded()")

if manifest.get("id") != "ml-translate" or manifest.get("package_type") != "native_runtime":
    raise SystemExit("Translate runtime must use the signed native_runtime package type")

source = manifest.get("source") or {}
common_version = source.get("common_version")
if not common_version:
    raise SystemExit("The shared ML Kit common runtime version must be pinned in plugin.json")
aar_report = root / "provenance" / "mlkit-aar-audit.json"
if not aar_report.is_file():
    raise SystemExit("ML Kit AAR dependency audit is missing")
artifacts = json.loads(aar_report.read_text(encoding="utf-8")).get("artifacts", [])
common_artifacts = [
    item.get("file", "") for item in artifacts
    if item.get("file", "").startswith("com_google_mlkit__common__")
]
expected_common = f"com_google_mlkit__common__{common_version}.aar"
if common_artifacts != [expected_common]:
    raise SystemExit(
        "ML Kit common dependency mismatch: expected exactly "
        + expected_common + ", resolved " + repr(common_artifacts)
    )

# The plugin must own the registry classes, not just Translate's front-end classes.
required_isolated = (
    "com_google_mlkit__language-id-common__16.1.0.aar",
    "com_google_firebase__firebase-components__16.1.0.aar",
    "com_google_firebase__firebase-encoders-json__17.1.0.aar",
    "com_google_firebase__firebase-encoders__16.1.0.jar",
    "com_google_android_datatransport__transport-api__2.2.1.aar",
    "com_google_android_datatransport__transport-runtime__2.2.6.aar",
    "com_google_android_datatransport__transport-backend-cct__2.3.3.aar",
)
artifact_names = {item.get("file", "") for item in artifacts}
missing_isolated = sorted(set(required_isolated) - artifact_names)
if missing_isolated:
    raise SystemExit("Pinned plugin-local ML Kit registry dependencies are missing: " + ", ".join(missing_isolated))

build_script = (Path(__file__).resolve().parent / "build_mlkit_translate_runtime.sh").read_text(encoding="utf-8")
for required in ("com_google_mlkit__common__", "com_google_firebase__firebase-components__", "com_google_android_datatransport__"):
    if required not in build_script:
        raise SystemExit("Build script does not bundle plugin-local component dependency: " + required)

if '"com.google.mlkit.common.sdkinternal.MlKitContext", true, pluginLoader' not in adapter_source:
    raise SystemExit("MlKitContext must be loaded from the isolated plugin class loader")
if '"com.google.firebase.components.ComponentRegistrar", true, pluginLoader' not in adapter_source:
    raise SystemExit("ComponentRegistrar must be loaded from the isolated plugin class loader")

api_report = root / "provenance" / "mlkit-internal-api.txt"
if not api_report.is_file():
    raise SystemExit("ML Kit component API audit is missing")
api_text = api_report.read_text(encoding="utf-8")
required_api = [
    "public static com.google.mlkit.common.sdkinternal.MlKitContext initialize(android.content.Context, java.util.List<com.google.firebase.components.ComponentRegistrar>);",
    "public com.google.mlkit.common.internal.CommonComponentRegistrar();",
    "public com.google.mlkit.nl.languageid.internal.LanguageIdRegistrar();",
    "public com.google.mlkit.nl.languageid.bundled.internal.ThickLanguageIdRegistrar();",
    "public com.google.mlkit.nl.translate.NaturalLanguageTranslateRegistrar();",
]
missing_api = [signature for signature in required_api if signature not in api_text]
if missing_api:
    raise SystemExit("Pinned ML Kit registrar API changed; cannot safely initialize from plugin DEX: " + "; ".join(missing_api))

runtime = dict(manifest.get("runtime") or {})
runtime.update(generated)
manifest["runtime"] = runtime

if runtime.get("abis") != ["arm64-v8a"]:
    raise SystemExit("Translate runtime must declare the tested arm64-v8a ABI")
if runtime.get("code_api_version") != 1:
    raise SystemExit("Translate runtime code API version must be 1")
if runtime.get("entry_class") != "eu.siacs.link.plugins.translate.MlKitTranslatePlugin":
    raise SystemExit("Translate runtime entry class is incorrect")

actual_dex = sorted("code/" + p.name for p in (root / "code").glob("*.dex"))
actual_so = sorted("lib/arm64-v8a/" + p.name for p in (root / "lib/arm64-v8a").glob("*.so"))
if not actual_dex or sorted(runtime.get("code_files", [])) != actual_dex:
    raise SystemExit("runtime.code_files does not match the generated DEX payload")
if not actual_so or sorted(runtime.get("load_order", [])) != actual_so:
    raise SystemExit("runtime.load_order does not list every ARM64 JNI library exactly once")

payload = []
for path in sorted(root.rglob("*")):
    if not path.is_file() or path == manifest_path or path == generated_path:
        continue
    relative = path.relative_to(root)
    if "provenance" in relative.parts:
        continue
    if relative.parts[0] not in {"code", "lib", "NOTICE"}:
        raise SystemExit(f"Unexpected file in runtime package source: {relative}")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    payload.append({"path": relative.as_posix(), "sha256": digest, "size_bytes": path.stat().st_size})

payload_paths = {item["path"] for item in payload}
if payload_paths != set(actual_dex) | set(actual_so) | {"NOTICE"}:
    raise SystemExit("Runtime package contains missing or unreviewed payload files")

print(json.dumps({
    "plugin_id": manifest["id"],
    "package_type": manifest["package_type"],
    "abi": runtime["abis"][0],
    "entry_class": runtime["entry_class"],
    "dex_files": actual_dex,
    "native_libraries": actual_so,
    "payload_bytes": sum(item["size_bytes"] for item in payload),
    "sha256": payload
}, indent=2))
