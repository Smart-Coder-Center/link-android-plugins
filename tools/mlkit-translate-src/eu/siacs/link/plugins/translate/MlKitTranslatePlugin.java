package eu.siacs.link.plugins.translate;

import android.content.Context;

import com.google.android.gms.tasks.Task;
import com.google.mlkit.common.model.DownloadConditions;
import com.google.mlkit.common.model.RemoteModelManager;
import com.google.mlkit.nl.languageid.LanguageIdentification;
import com.google.mlkit.nl.languageid.LanguageIdentifier;
import com.google.mlkit.nl.translate.TranslateLanguage;
import com.google.mlkit.nl.translate.TranslateRemoteModel;
import com.google.mlkit.nl.translate.Translation;
import com.google.mlkit.nl.translate.Translator;
import com.google.mlkit.nl.translate.TranslatorOptions;

import java.io.File;
import java.lang.reflect.Field;
import java.util.Collections;
import java.util.List;
import java.util.concurrent.ConcurrentHashMap;

/**
 * ML Kit translation adapter loaded only from a verified Link DEX runtime package.
 * Language models are downloaded by ML Kit on demand and are not included in this ZIP.
 */
public final class MlKitTranslatePlugin implements AutoCloseable {
    public interface Callback {
        void onSuccess(String value);
        void onFailure(String message);
    }

    private static final String ENGLISH = "en";
    private final Context context;
    private final ConcurrentHashMap<String, Task<Void>> pendingDownloads = new ConcurrentHashMap<>();
    private final java.util.Set<String> downloadedModels = ConcurrentHashMap.newKeySet();

    private MlKitTranslatePlugin(Context context) {
        this.context = context.getApplicationContext();
    }

    public static MlKitTranslatePlugin create(Context context, File packageDirectory) {
        if (context == null || packageDirectory == null || !packageDirectory.isDirectory()) {
            throw new IllegalArgumentException("Context and installed plugin directory are required");
        }
        patchResourceIds(context.getApplicationContext());
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
        LanguageIdentifier identifier = LanguageIdentification.getClient();
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
    }

    /**
     * The ML Kit AAR resource table is merged into the Link host APK, while its code stays
     * in this plugin DEX. Patch the generated library R fields to the host resource IDs
     * before any ML Kit client is initialized.
     */
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

    /** Ensures one language model is present; English is built in and needs no download. */
    public void ensureModel(String language, Callback callback) {
        if (language == null || language.trim().isEmpty()
                || !TranslateLanguage.getAllLanguages().contains(language)) {
            fail(callback, "کد زبان برای دانلود مدل معتبر نیست");
            return;
        }
        if (ENGLISH.equals(language) || downloadedModels.contains(language)) {
            success(callback, language);
            return;
        }

        Task<Void> task = pendingDownloads.get(language);
        if (task == null) {
            synchronized (pendingDownloads) {
                task = pendingDownloads.get(language);
                if (task == null) {
                    TranslateRemoteModel model = new TranslateRemoteModel.Builder(language).build();
                    task = RemoteModelManager.getInstance().download(
                            model, new DownloadConditions.Builder().build());
                    pendingDownloads.put(language, task);
                }
            }
        }
        final Task<Void> sharedTask = task;
        sharedTask.addOnCompleteListener(result -> {
            if (result.isSuccessful()) {
                downloadedModels.add(language);
                success(callback, language);
            } else {
                Throwable error = result.getException();
                fail(callback, error == null
                        ? new IllegalStateException("Language model download failed") : error);
            }
            if (sharedTask.isComplete()) pendingDownloads.remove(language, sharedTask);
        });
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
        ensureModel(source, new Callback() {
            @Override public void onSuccess(String ignored) {
                ensureModel(target, new Callback() {
                    @Override public void onSuccess(String ignoredTarget) {
                        TranslatorOptions options = new TranslatorOptions.Builder()
                                .setSourceLanguage(source)
                                .setTargetLanguage(target)
                                .build();
                        Translator translator = Translation.getClient(options);
                        translator.downloadModelIfNeeded()
                                .continueWithTask(ready -> {
                                    if (!ready.isSuccessful()) {
                                        Exception error = ready.getException();
                                        throw error == null ? new IllegalStateException("Translation model is unavailable") : error;
                                    }
                                    return translator.translate(text);
                                })
                                .addOnCompleteListener(result -> {
                                    translator.close();
                                    if (result.isSuccessful()) success(callback, result.getResult());
                                    else fail(callback, result.getException());
                                });
                    }
                    @Override public void onFailure(String message) { fail(callback, message); }
                });
            }
            @Override public void onFailure(String message) { fail(callback, message); }
        });
    }

    private static void success(Callback callback, String value) {
        if (callback != null) callback.onSuccess(value == null ? "" : value);
    }

    private static void fail(Callback callback, Throwable error) {
        fail(callback, error == null ? "Unknown ML Kit error" : error.getMessage());
    }

    private static void fail(Callback callback, String message) {
        if (callback != null) callback.onFailure(
                message == null || message.trim().isEmpty() ? "ML Kit operation failed" : message);
    }

    @Override
    public void close() {
        pendingDownloads.clear();
        downloadedModels.clear();
    }
}
