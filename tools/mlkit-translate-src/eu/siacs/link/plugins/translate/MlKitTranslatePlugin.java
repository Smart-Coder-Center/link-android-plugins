package eu.siacs.link.plugins.translate;

import android.content.Context;
import android.os.Handler;
import android.os.Looper;
import android.util.Log;

import com.google.android.gms.tasks.Task;
import com.google.android.gms.tasks.Tasks;
import com.google.mlkit.common.MlKitException;
import com.google.mlkit.common.model.DownloadConditions;
import com.google.mlkit.common.model.RemoteModelManager;
import com.google.mlkit.nl.languageid.LanguageIdentification;
import com.google.mlkit.nl.languageid.LanguageIdentifier;
import com.google.mlkit.nl.translate.TranslateLanguage;
import com.google.mlkit.nl.translate.Translation;
import com.google.mlkit.nl.translate.Translator;
import com.google.mlkit.nl.translate.TranslatorOptions;
import com.google.mlkit.nl.translate.TranslateRemoteModel;

import org.json.JSONArray;

import java.io.File;
import java.lang.reflect.Field;
import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Method;
import java.util.ArrayList;
import java.util.Collections;
import java.util.Iterator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;

/**
 * ML Kit translation adapter loaded only from a verified Link DEX runtime package.
 * Language models are downloaded by ML Kit on demand and are not included in this ZIP.
 */
public final class MlKitTranslatePlugin implements AutoCloseable {
    public interface Callback {
        void onSuccess(String value);
        void onFailure(String message);
    }

    private static final int MAX_CACHED_TRANSLATORS = 4;
    private static final int MAX_LANGUAGE_ID_RETRIES = 120;

    private final Context context;
    private final Handler mainHandler = new Handler(Looper.getMainLooper());
    private final LanguageIdentifier languageIdentifier;
    private final LinkedHashMap<String, CachedTranslator> translatorCache =
            new LinkedHashMap<>(4, 0.75f, true);
    private boolean closed;

    private static final class CachedTranslator {
        final Translator translator;
        int activeOperations;
        boolean evicted;
        boolean modelReady;
        Task<Void> modelDownloadTask;

        CachedTranslator(Translator translator) {
            this.translator = translator;
        }
    }

    private MlKitTranslatePlugin(Context context) {
        this.context = context.getApplicationContext();
        this.languageIdentifier = LanguageIdentification.getClient();
    }

    public static MlKitTranslatePlugin create(Context context, File packageDirectory) {
        if (context == null || packageDirectory == null || !packageDirectory.isDirectory()) {
            throw new IllegalArgumentException("Context and installed plugin directory are required");
        }
        patchResourceIds(context.getApplicationContext());
        initializeMlKitComponents(context.getApplicationContext());
        return new MlKitTranslatePlugin(context);
    }

    public List<String> getSupportedLanguages() {
        return Collections.unmodifiableList(TranslateLanguage.getAllLanguages());
    }

    /**
     * Explicitly prepare Google Play services' optional Language ID module.
     * The system may display its own consent/download UI. Completion is reported only
     * after the module is confirmed available, not when the request is merely accepted.
     */
    public void prepareLanguageIdModule(Callback callback) {
        ensureLanguageIdModule()
                .addOnSuccessListener(ignored -> success(callback, "ready"))
                .addOnFailureListener(error -> fail(callback, error));
    }

    public void identifyLanguage(String text, Callback callback) {
        if (text == null || text.trim().isEmpty()) {
            fail(callback, "متنی برای تشخیص زبان وارد نشده است");
            return;
        }
        // Match the standalone ML Translate flow: invoke Language ID directly.
        // The unbundled SDK manages first-use model availability through Play services.
        identifyLanguageAttempt(text, callback, 0);
    }

    private void identifyLanguageAttempt(String text, Callback callback, int attempt) {
        synchronized (this) {
            if (closed) {
                fail(callback, "Smart Translate is closed");
                return;
            }
        }
        try {
            languageIdentifier.identifyLanguage(text)
                    .addOnSuccessListener(language -> {
                        if (language == null || "und".equals(language)) {
                            fail(callback, "زبان متن قابل تشخیص نیست؛ زبان را دستی انتخاب کنید");
                        } else {
                            String supportedLanguage = TranslateLanguage.fromLanguageTag(language);
                            if (supportedLanguage == null) {
                                fail(callback, "این زبان برای ترجمه پشتیبانی نمی‌شود: " + language);
                            } else {
                                success(callback, supportedLanguage);
                            }
                        }
                    })
                    .addOnFailureListener(error -> {
                        // The unbundled model may report code 14 while Play services
                        // completes its first-use download. Retry that state only.
                        if (error instanceof MlKitException
                                && ((MlKitException) error).getErrorCode() == 14
                                && attempt < MAX_LANGUAGE_ID_RETRIES) {
                            mainHandler.postDelayed(
                                    () -> identifyLanguageAttempt(text, callback, attempt + 1),
                                    1000L);
                        } else {
                            fail(callback, error);
                        }
                    });
        } catch (Throwable error) {
            fail(callback, error);
        }
    }

    /**
     * The ML Kit AAR resource table is merged into the Link host APK, while its code stays
     * in this plugin DEX. Patch the generated library R fields to the host resource IDs
     * before any ML Kit client is initialized.
     */
    /**
     * Keep ML Kit Common + Firebase Components inside this plugin's class loader. A host-wide
     * MlKitContext may already exist without the Translate registrar; reusing it leaves
     * Translate's RemoteModelManager unregistered. The plugin-local MlKitContext and
     * ComponentRegistrar API must therefore come from the same DEX loader.
     */
    private static synchronized void initializeMlKitComponents(Context context) {
        try {
            ClassLoader pluginLoader = MlKitTranslatePlugin.class.getClassLoader();
            // Do not let a missing plugin class silently fall back to the APK's older GMS copy.
            Class<?> preconditions = Class.forName(
                    "com.google.android.gms.common.internal.Preconditions", false, pluginLoader);
            if (preconditions.getClassLoader() != pluginLoader) {
                throw new LinkageError("Google Play Services Preconditions resolved from the host APK, not the Smart Translate plugin DEX");
            }
            Method checkState = preconditions.getDeclaredMethod("checkState", boolean.class, Object.class);
            if (!java.lang.reflect.Modifier.isStatic(checkState.getModifiers())) {
                throw new LinkageError("Plugin-local Preconditions.checkState(boolean, Object) is not static");
            }
            Class<?> mlKitContext = Class.forName(
                    "com.google.mlkit.common.sdkinternal.MlKitContext", true, pluginLoader);
            if (mlKitContext.getClassLoader() != pluginLoader) {
                throw new LinkageError("ML Kit Common resolved outside the Smart Translate plugin DEX");
            }
            try {
                Object existingContext = mlKitContext.getMethod("getInstance").invoke(null);
                verifyLanguageIdFactory(pluginLoader, mlKitContext, existingContext);
                return;
            } catch (InvocationTargetException notInitialized) {
                if (!(notInitialized.getCause() instanceof IllegalStateException)) throw notInitialized;
            }

            Class<?> registrarInterface = Class.forName(
                    "com.google.firebase.components.ComponentRegistrar", true, pluginLoader);
            List<Object> registrars = new ArrayList<>();
            registrars.add(createRegistrar(pluginLoader,
                    "com.google.mlkit.common.internal.CommonComponentRegistrar", registrarInterface));
            // LanguageIdRegistrar owns the LanguageIdentifierImpl.Factory component.
            // ThinLanguageIdRegistrar contributes the unbundled Play Services creator delegate.
            // Both are required: omitting the former leaves Factory null; omitting the latter
            // makes Factory creation fail with "No delegate creator registered".
            registrars.add(createRegistrar(pluginLoader,
                    "com.google.mlkit.nl.languageid.internal.LanguageIdRegistrar", registrarInterface));
            registrars.add(createRegistrar(pluginLoader,
                    "com.google.mlkit.nl.languageid.thin.internal.ThinLanguageIdRegistrar", registrarInterface));
            registrars.add(createRegistrar(pluginLoader,
                    "com.google.mlkit.nl.translate.NaturalLanguageTranslateRegistrar", registrarInterface));

            Method initialize = mlKitContext.getMethod("initialize", Context.class, List.class);
            Object initializedContext = initialize.invoke(null, context, registrars);
            verifyLanguageIdFactory(pluginLoader, mlKitContext, initializedContext);
        } catch (Exception | LinkageError error) {
            Throwable cause = error instanceof InvocationTargetException
                    && ((InvocationTargetException) error).getCause() != null
                    ? ((InvocationTargetException) error).getCause() : error;
            throw new IllegalStateException("ML Kit components could not be initialized from the Translate plugin",
                    cause);
        }
    }

    private static void verifyLanguageIdFactory(ClassLoader loader, Class<?> mlKitContextClass,
            Object mlKitContextInstance) throws Exception {
        if (LanguageIdentification.class.getClassLoader() != loader
                || LanguageIdentifier.class.getClassLoader() != loader) {
            throw new LinkageError("Language ID API classes were not loaded from the Smart Translate plugin DEX");
        }
        Class<?> factoryClass = Class.forName(
                "com.google.mlkit.nl.languageid.internal.LanguageIdentifierImpl$Factory", true, loader);
        if (factoryClass.getClassLoader() != loader) {
            throw new LinkageError("LanguageIdentifierImpl.Factory was not loaded from the Smart Translate plugin DEX");
        }
        Method getComponent = mlKitContextClass.getMethod("get", Class.class);
        Object factory = getComponent.invoke(mlKitContextInstance, factoryClass);
        if (factory == null) {
            throw new IllegalStateException("ML Kit Language ID Factory is not registered in the plugin-local MlKitContext");
        }
        // Force Factory.create() now so a missing unbundled Play Services delegate is reported
        // during plugin initialization, rather than later as an opaque translation failure.
        LanguageIdentifier identifier = LanguageIdentification.getClient();
        if (identifier == null) {
            throw new IllegalStateException("ML Kit Language ID Factory returned a null client");
        }
        identifier.close();
    }

    private static Object createRegistrar(ClassLoader loader, String className,
            Class<?> registrarInterface) throws Exception {
        if (registrarInterface.getClassLoader() != loader) {
            throw new SecurityException("ComponentRegistrar interface was not loaded from the plugin DEX");
        }
        Class<?> registrarClass = Class.forName(className, true, loader);
        if (registrarClass.getClassLoader() != loader) {
            throw new SecurityException("ML Kit registrar was not loaded from the plugin DEX: " + className);
        }
        Object registrar = registrarClass.getDeclaredConstructor().newInstance();
        if (!registrarInterface.isInstance(registrar)) {
            throw new SecurityException("ML Kit registrar was not linked to the plugin-local component API: " + className);
        }
        return registrar;
    }

    private static void patchResourceIds(Context context) {
        patchResourceId(context, "raw", "translate_models_metadata");
        patchResourceId(context, "xml", "rapid_response_client_defaults");
    }

    private static void patchResourceId(Context context, String type, String name) {
        int resourceId = context.getResources().getIdentifier(name, type, context.getPackageName());
        if (resourceId == 0) {
            throw new IllegalStateException("Required ML Kit resource is missing: " + type + "/" + name);
        }
        try {
            Class<?> resourceClass = Class.forName(
                    "com.google.mlkit.nl.translate.R$" + type,
                    true, MlKitTranslatePlugin.class.getClassLoader());
            Field field = resourceClass.getDeclaredField(name);
            field.setAccessible(true);
            field.setInt(null, resourceId);
        } catch (ReflectiveOperationException error) {
            throw new IllegalStateException("Could not bind ML Kit host resource: " + type + "/" + name, error);
        }
    }

    /**
     * sourceLanguage may be "und" to request automatic detection. Translation models are
     * prepared before translating; the English model is handled internally by ML Kit.
     */
    public void translate(String sourceLanguage, String targetLanguage, String text, Callback callback) {
        if (text == null || text.trim().isEmpty()) {
            fail(callback, "متنی برای ترجمه وارد نشده است");
            return;
        }
        if (targetLanguage == null || !TranslateLanguage.getAllLanguages().contains(targetLanguage)) {
            fail(callback, "زبان مقصد پشتیبانی نمی‌شود");
            return;
        }
        if (sourceLanguage == null || sourceLanguage.trim().isEmpty() || "und".equals(sourceLanguage)) {
            identifyLanguage(text, new Callback() {
                @Override public void onSuccess(String detected) {
                    translateKnownLanguage(detected, targetLanguage, text, callback);
                }
                @Override public void onFailure(String message) { fail(callback, message); }
            });
            return;
        }
        if (!TranslateLanguage.getAllLanguages().contains(sourceLanguage)) {
            fail(callback, "زبان مبدأ پشتیبانی نمی‌شود");
            return;
        }
        translateKnownLanguage(sourceLanguage, targetLanguage, text, callback);
    }

    private void translateKnownLanguage(String source, String target, String text, Callback callback) {
        if (source.equals(target)) {
            success(callback, text);
            return;
        }
        TranslatorOptions options = new TranslatorOptions.Builder()
                .setSourceLanguage(source)
                .setTargetLanguage(target)
                .build();
        CachedTranslator acquired = null;
        try {
            acquired = acquireTranslator(source + "->" + target, options);
            final CachedTranslator cached = acquired;
            ensureTranslatorModel(cached)
                    .continueWithTask(ready -> {
                        if (!ready.isSuccessful()) {
                            Exception error = ready.getException();
                            throw error == null
                                    ? new IllegalStateException("Translation model is unavailable")
                                    : error;
                        }
                        return cached.translator.translate(text);
                    })
                    .addOnCompleteListener(result -> {
                        releaseTranslator(cached);
                        if (result.isSuccessful()) success(callback, result.getResult());
                        else fail(callback, result.getException());
                    });
        } catch (Throwable error) {
            if (acquired != null) releaseTranslator(acquired);
            fail(callback, error);
        }
    }

    private synchronized CachedTranslator acquireTranslator(String key, TranslatorOptions options) {
        if (closed) throw new IllegalStateException("Smart Translate is closed");
        CachedTranslator cached = translatorCache.get(key);
        if (cached == null) {
            cached = new CachedTranslator(Translation.getClient(options));
            translatorCache.put(key, cached);
        }
        cached.activeOperations++;
        while (translatorCache.size() > MAX_CACHED_TRANSLATORS) {
            Iterator<Map.Entry<String, CachedTranslator>> iterator =
                    translatorCache.entrySet().iterator();
            if (!iterator.hasNext()) break;
            CachedTranslator oldest = iterator.next().getValue();
            iterator.remove();
            oldest.evicted = true;
            if (oldest.activeOperations == 0) oldest.translator.close();
        }
        return cached;
    }

    private Task<Void> ensureTranslatorModel(CachedTranslator cached) {
        synchronized (this) {
            if (cached.modelReady) return Tasks.forResult(null);
            if (cached.modelDownloadTask != null && !cached.modelDownloadTask.isComplete()) {
                return cached.modelDownloadTask;
            }
            cached.modelDownloadTask = cached.translator.downloadModelIfNeeded();
            cached.modelDownloadTask.addOnCompleteListener(result -> {
                synchronized (MlKitTranslatePlugin.this) {
                    if (result.isSuccessful()) cached.modelReady = true;
                    else cached.modelDownloadTask = null;
                }
            });
            return cached.modelDownloadTask;
        }
    }

    private synchronized void releaseTranslator(CachedTranslator cached) {
        if (cached.activeOperations > 0) cached.activeOperations--;
        if (cached.evicted && cached.activeOperations == 0) cached.translator.close();
    }

    /** Returns a JSON array of downloaded translation language codes. */
    public void getDownloadedTranslationModels(Callback callback) {
        try {
            RemoteModelManager.getInstance()
                    .getDownloadedModels(TranslateRemoteModel.class)
                    .addOnSuccessListener(models -> {
                        JSONArray languages = new JSONArray();
                        for (TranslateRemoteModel model : models) {
                            String language = model.getLanguage();
                            if (language != null) languages.put(language);
                        }
                        success(callback, languages.toString());
                    })
                    .addOnFailureListener(error -> fail(callback, error));
        } catch (Throwable error) {
            fail(callback, error);
        }
    }

    /** Returns a JSON array of model codes that must be downloaded for this pair. */
    public void getMissingTranslationModels(String source, String target, Callback callback) {
        if (source == null || target == null
                || !TranslateLanguage.getAllLanguages().contains(source)
                || !TranslateLanguage.getAllLanguages().contains(target)) {
            fail(callback, "زبان مبدأ یا مقصد پشتیبانی نمی‌شود");
            return;
        }
        if (source.equals(target)) {
            success(callback, "[]");
            return;
        }
        final Set<String> required = new java.util.LinkedHashSet<>();
        if (!TranslateLanguage.ENGLISH.equals(source)) required.add(source);
        if (!TranslateLanguage.ENGLISH.equals(target)) required.add(target);
        if (required.isEmpty()) {
            success(callback, "[]");
            return;
        }
        try {
            RemoteModelManager.getInstance()
                    .getDownloadedModels(TranslateRemoteModel.class)
                    .addOnSuccessListener(models -> {
                        Set<String> downloaded = new java.util.HashSet<>();
                        for (TranslateRemoteModel model : models) downloaded.add(model.getLanguage());
                        JSONArray missing = new JSONArray();
                        for (String language : required) {
                            if (!downloaded.contains(language)) missing.put(language);
                        }
                        success(callback, missing.toString());
                    })
                    .addOnFailureListener(error -> fail(callback, error));
        } catch (Throwable error) {
            fail(callback, error);
        }
    }

    /** Starts an explicit, user-approved language-model download. */
    public void downloadTranslationModel(String language, boolean requireWifi, Callback callback) {
        if (language == null || !TranslateLanguage.getAllLanguages().contains(language)) {
            fail(callback, "زبان مدل پشتیبانی نمی‌شود");
            return;
        }
        if (TranslateLanguage.ENGLISH.equals(language)) {
            success(callback, language);
            return;
        }
        try {
            DownloadConditions.Builder conditions = new DownloadConditions.Builder();
            if (requireWifi) conditions.requireWifi();
            TranslateRemoteModel model = new TranslateRemoteModel.Builder(language).build();
            RemoteModelManager.getInstance().download(model, conditions.build())
                    .addOnSuccessListener(ignored -> success(callback, language))
                    .addOnFailureListener(error -> fail(callback, error));
        } catch (Throwable error) {
            fail(callback, error);
        }
    }

    /** Deletes a downloaded language model after the user unchecks it in model settings. */
    public void deleteTranslationModel(String language, Callback callback) {
        if (language == null || !TranslateLanguage.getAllLanguages().contains(language)) {
            fail(callback, "زبان مدل پشتیبانی نمی‌شود");
            return;
        }
        if (TranslateLanguage.ENGLISH.equals(language)) {
            fail(callback, "مدل انگلیسی داخلی است و قابل حذف نیست");
            return;
        }
        try {
            TranslateRemoteModel model = new TranslateRemoteModel.Builder(language).build();
            RemoteModelManager.getInstance().deleteDownloadedModel(model)
                    .addOnSuccessListener(ignored -> {
                        synchronized (MlKitTranslatePlugin.this) {
                            Iterator<Map.Entry<String, CachedTranslator>> iterator =
                                    translatorCache.entrySet().iterator();
                            while (iterator.hasNext()) {
                                Map.Entry<String, CachedTranslator> entry = iterator.next();
                                if (entry.getKey().startsWith(language + "->")
                                        || entry.getKey().endsWith("->" + language)) {
                                    CachedTranslator cached = entry.getValue();
                                    iterator.remove();
                                    cached.evicted = true;
                                    if (cached.activeOperations == 0) cached.translator.close();
                                }
                            }
                        }
                        success(callback, language);
                    })
                    .addOnFailureListener(error -> fail(callback, error));
        } catch (Throwable error) {
            fail(callback, error);
        }
    }

    private static void success(Callback callback, String value) {
        if (callback != null) callback.onSuccess(value == null ? "" : value);
    }

    private static void fail(Callback callback, Throwable error) {
        if (error == null) {
            fail(callback, "Unknown ML Kit error");
            return;
        }
        Log.e("LinkSmartTranslate", "ML Kit operation failed", error);
        StringBuilder details = new StringBuilder();
        Throwable current = error;
        int depth = 0;
        while (current != null && depth++ < 6) {
            if (details.length() > 0) details.append(" <- ");
            details.append(current.getClass().getSimpleName());
            String message = current.getMessage();
            if (message != null && !message.trim().isEmpty()) {
                details.append(": ").append(message.trim());
            }
            // MlKitException exposes a numeric error code; include it without linking
            // this adapter to an implementation-specific exception class.
            try {
                Method getErrorCode = current.getClass().getMethod("getErrorCode");
                Object code = getErrorCode.invoke(current);
                if (code instanceof Number) details.append(" [code=").append(code).append("]");
            } catch (Exception ignored) {
            }
            current = current.getCause();
        }
        fail(callback, details.toString());
    }

    private static void fail(Callback callback, String message) {
        if (callback != null) callback.onFailure(
                message == null || message.trim().isEmpty() ? "ML Kit operation failed" : message);
    }

    @Override
    public void close() {
        List<Translator> translatorsToClose = new ArrayList<>();
        TaskCompletionSource<Void> pendingPreparation;
        synchronized (this) {
            if (closed) return;
            closed = true;
            pendingPreparation = languageIdPreparationCompletion;
            languageIdPreparationCompletion = null;
            languageIdPreparationTask = null;
            for (CachedTranslator cached : translatorCache.values()) {
                cached.evicted = true;
                if (cached.activeOperations == 0) translatorsToClose.add(cached.translator);
            }
            translatorCache.clear();
        }
        mainHandler.removeCallbacksAndMessages(null);
        if (pendingPreparation != null) {
            pendingPreparation.trySetException(new IllegalStateException("Smart Translate is closed"));
        }
        for (Translator translator : translatorsToClose) {
            try { translator.close(); } catch (Exception ignored) {}
        }
        try { languageIdentifier.close(); } catch (Exception ignored) {}
    }
}
