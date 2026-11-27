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
required_runtime_behaviors = (
    "languageIdentifier.identifyLanguage(text)",
    "RemoteModelManager.getInstance()",
    "getDownloadedModels(TranslateRemoteModel.class)",
    "new TranslateRemoteModel.Builder(language).build()",
    "RemoteModelManager.getInstance().download(model, conditions.build())",
    "RemoteModelManager.getInstance().deleteDownloadedModel(model)",
    "cached.translator.downloadModelIfNeeded()",
    "MAX_CACHED_TRANSLATORS",
    "languageIdentifier.close()",
    "cached.translator.close()",
    "TessBaseAPI",
    "candidate.init(new File(packageDirectory, \"model\").getAbsolutePath(),",
    "\"fas+eng\"",
    "TessBaseAPI.PageSegMode.PSM_AUTO",
    "engine.setImage(bitmap)",
    "engine.getUTF8Text()",
    "decodeScaled(imageUri)",
)
missing_behaviors = [item for item in required_runtime_behaviors if item not in adapter_source]
if missing_behaviors:
    raise SystemExit("Translate runtime is missing managed module/model lifecycle or translator caching: "
                     + ", ".join(missing_behaviors))
if "MAX_LANGUAGE_ID_RETRIES" in adapter_source or "mainHandler.postDelayed" in adapter_source:
    raise SystemExit("Bundled Language ID must not wait for an optional module or run delayed retry loops")
if adapter_source.index("patchResourceIds(context.getApplicationContext());") > adapter_source.index("initializeMlKitComponents(context.getApplicationContext());"):
    raise SystemExit("Translate host resource IDs must be patched before ML Kit initialization")
for required in (
    'patchResourceId(context, "raw", "translate_models_metadata")',
    'patchResourceId(context, "xml", "rapid_response_client_defaults")',
    'context.getResources().getIdentifier(name, type, context.getPackageName())',
    'resourceClass.getDeclaredField(name)',
):
    if required not in adapter_source:
        raise SystemExit("Translate host resource binding is incomplete: " + required)

if manifest.get("id") != "ml-translate" or manifest.get("package_type") != "native_runtime":
    raise SystemExit("Translate runtime must use the signed native_runtime package type")
if (manifest.get("source") or {}).get("language_id_flow") != "bundled_model":
    raise SystemExit("Language ID must use the bundled model runtime for release 1.0.22")

source = manifest.get("source") or {}
if source.get("language_id_provider") != "com.google.mlkit:language-id" or source.get("language_id_version") != "17.0.6":
    raise SystemExit("Language ID must be pinned to the bundled com.google.mlkit:language-id:17.0.6 artifact")
if source.get("tesseract4android_version") != "4.9.0" or source.get("tessdata_fast_revision") != "87416418657359cb625c412a48b6e1d6d41c29bd" or source.get("ocr_languages") != ["fas", "eng"] or source.get("ocr_engine") != "tesseract4android_offline":
    raise SystemExit("Image OCR must use the pinned offline Tesseract Persian+English runtime and models")
expected_models = {
    "fas.traineddata": (431500, "1a17ee02076107e73abd15d2038389150c8f824f"),
    "eng.traineddata": (4113088, "bbef4675053b5b468cdb477053e28b1c698ba08e"),
}
for name, (expected_size, expected_blob_sha) in expected_models.items():
    model = root / "model" / "tessdata" / name
    if not model.is_file() or model.stat().st_size != expected_size:
        raise SystemExit("Missing or unpinned Persian/English OCR model: " + name)
    data = model.read_bytes()
    actual_blob_sha = hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()
    if actual_blob_sha != expected_blob_sha:
        raise SystemExit("OCR model Git blob SHA-1 mismatch: " + name)

if source.get("translate_version") != "17.0.2":
    raise SystemExit("Translate must be pinned to com.google.mlkit:translate:17.0.2")
common_version = source.get("common_version")
if not common_version:
    raise SystemExit("The shared ML Kit common runtime version must be pinned in plugin.json")
if source.get("okhttp_version") != "3.12.13" or source.get("okio_version") != "1.15.0":
    raise SystemExit("Plugin-local OkHttp/Okio versions must match the pinned ML Kit-compatible runtime")
aar_report = root / "provenance" / "mlkit-aar-audit.json"
if not aar_report.is_file():
    raise SystemExit("ML Kit AAR dependency audit is missing")
aar_audit = json.loads(aar_report.read_text(encoding="utf-8"))
artifacts = aar_audit.get("artifacts", [])
aar_components = aar_audit.get("aar_components", [])
aar_assets = aar_audit.get("aar_assets", [])
native_libraries = aar_audit.get("native_libraries", [])
model_assets = [
    item for item in aar_assets
    if item.get("aar") == "com_google_mlkit__language-id__17.0.6.aar"
    and item.get("path") == "assets/tflite_langid.tflite.jpg"
]
if len(model_assets) != 1 or not (0 < model_assets[0].get("size_bytes", 0) <= 8 * 1024 * 1024):
    raise SystemExit("Bundled Language ID model asset is missing, duplicated, or outside the size limit")
if not __import__("re").fullmatch(r"[a-f0-9]{64}", model_assets[0].get("sha256", "")):
    raise SystemExit("Bundled Language ID model asset SHA-256 audit is missing or invalid")
if not any(item.get("aar") == "com_google_mlkit__language-id__17.0.6.aar"
           and item.get("path") == "lib/arm64-v8a/liblanguage_id_l2c_jni.so"
           for item in native_libraries):
    raise SystemExit("Bundled Language ID JNI library is absent from the audited AAR")
bundled_registrar_declared = any(
    component.get("aar") == "com_google_mlkit__language-id__17.0.6.aar"
    and any(
        item.get("name") == "com.google.firebase.components:com.google.mlkit.nl.languageid.bundled.internal.ThickLanguageIdRegistrar"
        and item.get("value") == "com.google.firebase.components.ComponentRegistrar"
        for item in component.get("metadata", [])
    )
    for component in aar_components
)
if not bundled_registrar_declared:
    raise SystemExit("Pinned bundled Language ID AAR does not declare ThickLanguageIdRegistrar in its manifest")
if any(
    "ThinLanguageIdRegistrar" in item.get("name", "")
    for component in aar_components
    for item in component.get("metadata", [])
):
    raise SystemExit("Unbundled ThinLanguageIdRegistrar must not be present in the runtime AAR set")
artifact_names_for_policy = {item.get("file", "") for item in artifacts}
if any(name.startswith("com_google_android_gms__play-services-mlkit-language-id__")
       for name in artifact_names_for_policy):
    raise SystemExit("Unbundled Play Services Language ID module must not be packaged")
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
    "cz_adaptech_tesseract4android__tesseract4android__4.9.0.aar",
    "com_google_mlkit__translate__17.0.2.aar",
    "com_google_firebase__firebase-components__16.1.0.aar",
    "com_google_firebase__firebase-encoders-json__17.1.0.aar",
    "com_google_firebase__firebase-encoders__16.1.0.jar",
    "com_google_android_datatransport__transport-api__2.2.1.aar",
    "com_google_android_datatransport__transport-runtime__2.2.6.aar",
    "com_google_android_datatransport__transport-backend-cct__2.3.3.aar",
    "com_google_android_gms__play-services-base__18.10.0.aar",
    "com_google_android_gms__play-services-basement__18.10.0.aar",
    "com_google_android_gms__play-services-tasks__18.4.1.aar",
    "com_google_mlkit__language-id__17.0.6.aar",
    "com_google_mlkit__language-id-common__16.1.0.aar",
    "javax_inject__javax.inject__1.jar",
)
artifact_names = {item.get("file", "") for item in artifacts}
collection_artifacts = sorted(
    name for name in artifact_names
    if name.startswith("androidx_collection__collection-jvm__") and name.endswith(".jar")
)
kotlin_stdlib_artifacts = sorted(
    name for name in artifact_names
    if name.startswith("org_jetbrains_kotlin__kotlin-stdlib__") and name.endswith(".jar")
)
if len(kotlin_stdlib_artifacts) != 1:
    raise SystemExit("Expected exactly one resolved Kotlin stdlib JAR; got " + repr(kotlin_stdlib_artifacts))
if len(collection_artifacts) != 1:
    raise SystemExit("Expected exactly one resolved AndroidX Collection JVM JAR for plugin isolation; got " + repr(collection_artifacts))
missing_isolated = sorted(set(required_isolated) - artifact_names)
if missing_isolated:
    raise SystemExit("Pinned plugin-local ML Kit registry dependencies are missing: " + ", ".join(missing_isolated))

build_script = (Path(__file__).resolve().parent / "build_mlkit_translate_runtime.sh").read_text(encoding="utf-8")
for required in ("com_google_mlkit__common__", "com_google_mlkit__language-id-common__", "com_google_firebase__firebase-components__", "com_google_android_datatransport__", "com_google_android_gms__play-services-basement__", "com_google_mlkit__language-id__",  "androidx_collection__collection-jvm__", "org_jetbrains_kotlin__kotlin-stdlib__", "javax_inject__javax.inject__", "public static int translate_models_metadata;", "public static int rapid_response_client_defaults;", "com_squareup_okhttp3__okhttp__3.12.13.jar", "com_squareup_okio__okio__1.15.0.jar"):
    if required not in build_script:
        raise SystemExit("Build script does not bundle plugin-local component dependency: " + required)

if '"com.google.mlkit.common.sdkinternal.MlKitContext", true, pluginLoader' not in adapter_source:
    raise SystemExit("MlKitContext must be loaded from the isolated plugin class loader")
if '"com.google.firebase.components.ComponentRegistrar", true, pluginLoader' not in adapter_source:
    raise SystemExit("ComponentRegistrar must be loaded from the isolated plugin class loader")
if '"com.google.mlkit.nl.languageid.internal.LanguageIdRegistrar", registrarInterface' not in adapter_source:
    raise SystemExit("LanguageIdRegistrar must register LanguageIdentifierImpl.Factory")
if '"com.google.mlkit.nl.languageid.bundled.internal.ThickLanguageIdRegistrar", registrarInterface' not in adapter_source:
    raise SystemExit("Bundled Language ID must register ThickLanguageIdRegistrar as the creator delegate")

# Verify both the existing-context and fresh-initialization paths before exposing the plugin.
# Bundled Language ID must use the bundled Thick registrar, not a Play Services module loader.
if "private static synchronized void initializeMlKitComponents(Context context)" not in adapter_source:
    raise SystemExit("ML Kit component initialization must be synchronized")
if adapter_source.count("verifyLanguageIdFactory(pluginLoader, mlKitContext,") != 2:
    raise SystemExit("Both existing and freshly initialized MlKitContext paths must verify Language ID Factory")
for required in (
    '"com.google.mlkit.nl.languageid.internal.LanguageIdentifierImpl$Factory", true, loader',
    'mlKitContextClass.getMethod("get", Class.class)',
    'LanguageIdentification.getClient()',
    'identifier.close()',
    'factoryClass.getClassLoader() != loader',
    'LanguageIdentification.class.getClassLoader() != loader',
    'LanguageIdentifier.class.getClassLoader() != loader',
    'RemoteModelManager.class.getClassLoader() != loader',
    'TranslateRemoteModel.class.getClassLoader() != loader',
    'manager.getDownloadedModels(TranslateRemoteModel.class)',
    'Translation.getClient(smokeOptions)',
    'smokeTranslator.close()',
    'registrarInterface.getClassLoader() != loader',
    'registrarClass.getClassLoader() != loader',
    'catch (Exception | LinkageError error)',
):
    if required not in adapter_source:
        raise SystemExit("ML Kit runtime Factory/class-loader verification is incomplete: " + required)

api_report = root / "provenance" / "mlkit-internal-api.txt"
if not api_report.is_file():
    raise SystemExit("ML Kit component API audit is missing")
api_text = api_report.read_text(encoding="utf-8")
required_api = [
    "public static com.google.mlkit.common.sdkinternal.MlKitContext initialize(android.content.Context, java.util.List<com.google.firebase.components.ComponentRegistrar>);",
    "public static com.google.mlkit.common.sdkinternal.MlKitContext getInstance();",
    "public <T> T get(java.lang.Class<T>);",
    "public static synchronized com.google.mlkit.common.model.RemoteModelManager getInstance();",
    "public com.google.mlkit.common.internal.CommonComponentRegistrar();",
    "public com.google.mlkit.nl.languageid.internal.LanguageIdRegistrar();",
    "public com.google.mlkit.nl.languageid.bundled.internal.ThickLanguageIdRegistrar();",
    "public com.google.mlkit.nl.translate.NaturalLanguageTranslateRegistrar();",
    "public static int translate_models_metadata;",
    "public static int rapid_response_client_defaults;",
]
missing_api = [signature for signature in required_api if signature not in api_text]
if missing_api:
    raise SystemExit("Pinned ML Kit registrar API changed; cannot safely initialize from plugin DEX: " + "; ".join(missing_api))

declared_runtime = dict(manifest.get("runtime") or {})
for key in ("abis", "load_order", "code_files", "entry_class", "code_api_version"):
    if declared_runtime.get(key) != generated.get(key):
        raise SystemExit("plugin.json runtime metadata is stale for generated field: " + key)
runtime = dict(declared_runtime)
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

# Parse DEX class_defs. A descriptor string or method reference is not proof that
# the class is actually defined in the plugin; the previous check accepted that false positive.
import struct

def uleb(data, offset):
    value = shift = 0
    while True:
        byte = data[offset]
        offset += 1
        value |= (byte & 0x7f) << shift
        if not byte & 0x80:
            return value, offset
        shift += 7
        if shift > 35:
            raise SystemExit("Malformed ULEB128 in plugin DEX")

def dex_defined_classes(path):
    data = path.read_bytes()
    if len(data) < 112 or data[:4] != b"dex\n":
        raise SystemExit(f"Invalid DEX header: {path.name}")
    string_count, string_off = struct.unpack_from("<II", data, 56)
    type_count, type_off = struct.unpack_from("<II", data, 64)
    class_count, class_off = struct.unpack_from("<II", data, 96)
    strings = []
    for index in range(string_count):
        offset = struct.unpack_from("<I", data, string_off + index * 4)[0]
        _, offset = uleb(data, offset)
        end = data.index(0, offset)
        strings.append(data[offset:end].decode("utf-8", errors="replace"))
    types = [
        strings[struct.unpack_from("<I", data, type_off + index * 4)[0]]
        for index in range(type_count)
    ]
    defined = set()
    for index in range(class_count):
        class_index = struct.unpack_from("<I", data, class_off + index * 32)[0]
        if class_index >= len(types):
            raise SystemExit("Invalid class_idx in plugin DEX class_defs")
        defined.add(types[class_index])
    return defined

dex_files = sorted((root / "code").glob("classes*.dex"))
defined_classes = set().union(*(dex_defined_classes(path) for path in dex_files))
required_classes = (
    "Lcom/google/android/gms/common/internal/Preconditions;",
    "Lcom/google/firebase/components/ComponentRegistrar;",
    "Lcom/google/firebase/components/ComponentRuntime;",
    "Lcom/google/mlkit/common/sdkinternal/MlKitContext;",
    "Lcom/google/mlkit/common/internal/CommonComponentRegistrar;",
    "Lcom/google/mlkit/nl/translate/NaturalLanguageTranslateRegistrar;",
    "Lcom/google/mlkit/common/model/RemoteModelManager;",
    "Lcom/google/mlkit/common/model/DownloadConditions;",
    "Lcom/google/mlkit/nl/translate/TranslateRemoteModel;",
    "Landroidx/collection/ArraySet;",
    "Lokhttp3/MediaType;",
    "Lokio/ByteString;",
    "Lkotlin/jvm/internal/markers/KMutableCollection;",
    "Ljavax/inject/Provider;",
    "Lcom/google/mlkit/nl/languageid/LanguageIdentification;",
    "Lcom/google/mlkit/nl/languageid/internal/LanguageIdRegistrar;",
    "Lcom/google/mlkit/nl/languageid/bundled/internal/ThickLanguageIdRegistrar;",
    "Lcom/google/mlkit/nl/languageid/internal/LanguageIdentifierImpl$Factory;",
    "Lcom/googlecode/tesseract/android/TessBaseAPI;",
)
missing_classes = [name for name in required_classes if name not in defined_classes]
if missing_classes:
    raise SystemExit(
        "Plugin DEX does not DEFINE required plugin-local GMS/AndroidX/Kotlin classes; "
        "parent-loader fallback can reproduce the crash: " + ", ".join(missing_classes)
    )

payload = []
for path in sorted(root.rglob("*")):
    if not path.is_file() or path == manifest_path or path == generated_path:
        continue
    relative = path.relative_to(root)
    if "provenance" in relative.parts:
        continue
    if relative.parts[0] not in {"code", "lib", "model", "NOTICE"}:
        raise SystemExit(f"Unexpected file in runtime package source: {relative}")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    payload.append({"path": relative.as_posix(), "sha256": digest, "size_bytes": path.stat().st_size})

payload_paths = {item["path"] for item in payload}
expected_model_paths = {"model/tessdata/fas.traineddata", "model/tessdata/eng.traineddata"}
if payload_paths != set(actual_dex) | set(actual_so) | expected_model_paths | {"NOTICE"}:
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
