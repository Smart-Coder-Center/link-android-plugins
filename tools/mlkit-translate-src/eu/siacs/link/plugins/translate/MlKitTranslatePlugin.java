package eu.siacs.link.plugins.translate;

import android.content.Context;
import android.util.Log;

import com.google.mlkit.nl.languageid.LanguageIdentification;
import com.google.mlkit.nl.languageid.LanguageIdentifier;
import com.google.mlkit.nl.translate.TranslateLanguage;
import com.google.mlkit.nl.translate.Translation;
import com.google.mlkit.nl.translate.Translator;
import com.google.mlkit.nl.translate.TranslatorOptions;

import java.io.File;
import java.lang.reflect.Field;
import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Method;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

/**
 * ML Kit translation adapter loaded only from a verified Link DEX runtime package.
 * Language models are downloaded by ML Kit on demand and are not included in this ZIP.
 */
public final class MlKitTranslatePlugin implements AutoCloseable {
    public interface Callback {
        void onSuccess(String value);
        void onFailure(String message);
    }

    private final Context context;

    private MlKitTranslatePlugin(Context context) {
        this.context = context.getApplicationContext();
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

    public void identifyLanguage(String text, Callback callback) {
        if (text == null || text.trim().isEmpty()) {
            fail(callback, "متنی برای تشخیص زبان وارد نشده است");
            return;
        }
        final LanguageIdentifier identifier;
        try {
            // Client creation can throw synchronously when a registrar or native component
            // is unavailable. Route that exception through the same detailed diagnostic path.
            identifier = LanguageIdentification.getClient();
        } catch (Throwable error) {
            fail(callback, error);
            return;
        }
        try {
            identifier.identifyLanguage(text)
                .addOnSuccessListener(language -> {
                    identifier.close();
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
                    identifier.close();
                    fail(callback, error);
                });
        } catch (Throwable error) {
            identifier.close();
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
    private static void initializeMlKitComponents(Context context) {
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
                mlKitContext.getMethod("getInstance").invoke(null);
                return;
            } catch (InvocationTargetException notInitialized) {
                if (!(notInitialized.getCause() instanceof IllegalStateException)) throw notInitialized;
            }

            Class<?> registrarInterface = Class.forName(
                    "com.google.firebase.components.ComponentRegistrar", true, pluginLoader);
            List<Object> registrars = new ArrayList<>();
            registrars.add(createRegistrar(pluginLoader,
                    "com.google.mlkit.common.internal.CommonComponentRegistrar", registrarInterface));
            registrars.add(createRegistrar(pluginLoader,
                    "com.google.mlkit.nl.languageid.internal.LanguageIdRegistrar", registrarInterface));
            registrars.add(createRegistrar(pluginLoader,
                    "com.google.mlkit.nl.languageid.bundled.internal.ThickLanguageIdRegistrar", registrarInterface));
            registrars.add(createRegistrar(pluginLoader,
                    "com.google.mlkit.nl.translate.NaturalLanguageTranslateRegistrar", registrarInterface));

            Method initialize = mlKitContext.getMethod("initialize", Context.class, List.class);
            initialize.invoke(null, context, registrars);
        } catch (Exception error) {
            Throwable cause = error instanceof InvocationTargetException
                    && ((InvocationTargetException) error).getCause() != null
                    ? ((InvocationTargetException) error).getCause() : error;
            throw new IllegalStateException("ML Kit components could not be initialized from the Translate plugin",
                    cause);
        }
    }

    private static Object createRegistrar(ClassLoader loader, String className,
            Class<?> registrarInterface) throws Exception {
        Class<?> registrarClass = Class.forName(className, true, loader);
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
        Translator translator = null;
        try {
            // getClient() itself may throw before a Task exists; keep it inside this
            // guarded block so the original ML Kit exception reaches fail() with its cause.
            translator = Translation.getClient(options);
            final Translator activeTranslator = translator;
            // Let the Translate API download the required pair itself. Avoid the optional
            // RemoteModelManager API, which requires feature-model registration separately.
            activeTranslator.downloadModelIfNeeded()
                    .continueWithTask(ready -> {
                        if (!ready.isSuccessful()) {
                            Exception error = ready.getException();
                            throw error == null
                                    ? new IllegalStateException("Translation model is unavailable")
                                    : error;
                        }
                        return activeTranslator.translate(text);
                    })
                    .addOnCompleteListener(result -> {
                        activeTranslator.close();
                        if (result.isSuccessful()) success(callback, result.getResult());
                        else fail(callback, result.getException());
                    });
        } catch (Throwable error) {
            if (translator != null) translator.close();
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
    }
}
