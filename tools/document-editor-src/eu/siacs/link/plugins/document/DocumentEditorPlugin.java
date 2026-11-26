package eu.siacs.link.plugins.document;

import android.app.Activity;
import android.content.ContentValues;
import android.content.Context;
import android.content.Intent;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.graphics.Canvas;
import android.graphics.Paint;
import android.graphics.RectF;
import android.graphics.pdf.PdfDocument;
import android.net.Uri;
import android.os.Build;
import android.os.Environment;
import android.provider.MediaStore;
import android.text.Layout;
import android.text.StaticLayout;
import android.text.TextPaint;

import com.google.mlkit.vision.documentscanner.GmsDocumentScanning;
import com.google.mlkit.vision.documentscanner.GmsDocumentScanner;
import com.google.mlkit.vision.documentscanner.GmsDocumentScannerOptions;
import com.google.mlkit.vision.documentscanner.GmsDocumentScanningResult;
import com.google.mlkit.vision.codescanner.GmsBarcodeScanner;
import com.google.mlkit.vision.codescanner.GmsBarcodeScannerOptions;
import com.google.mlkit.vision.codescanner.GmsBarcodeScanning;
import com.google.mlkit.vision.barcode.common.Barcode;
import com.googlecode.tesseract.android.TessBaseAPI;

import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.IOException;
import java.io.OutputStream;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.zip.ZipEntry;
import java.util.zip.ZipOutputStream;

/**
 * Signed, optional Document Editor runtime. It owns OCR, scanner integrations and document export.
 * Link loads this class only after verifying the runtime signature and every payload hash.
 */
public final class DocumentEditorPlugin implements AutoCloseable {
    public interface Callback {
        void onSuccess(String value);
        void onFailure(String message);
    }

    private static final int REQUEST_DOCUMENT_SCAN = 0xD0C;
    private static final int MAX_IMAGE_DIMENSION = 3200;
    private final Context app;
    private final File packageDirectory;
    private final ExecutorService worker = Executors.newSingleThreadExecutor();
    private TessBaseAPI ocr;
    private Callback pendingDocumentCallback;
    private boolean closed;

    private DocumentEditorPlugin(Context context, File directory) {
        app = context.getApplicationContext();
        packageDirectory = directory;
        File persian = new File(directory, "model/tessdata/fas.traineddata");
        File english = new File(directory, "model/tessdata/eng.traineddata");
        if (!persian.isFile() || !english.isFile()
                || persian.length() < 100_000L || english.length() < 1_000_000L) {
            throw new IllegalStateException("Persian and English OCR models are missing");
        }
    }

    public static DocumentEditorPlugin create(Context context, File packageDirectory) {
        if (context == null || packageDirectory == null || !packageDirectory.isDirectory()) {
            throw new IllegalArgumentException("A valid installed Document Editor package is required");
        }
        return new DocumentEditorPlugin(context, packageDirectory);
    }

    /** OCR for Persian and English, performed locally with the package's language models. */
    public void recognizeText(Uri imageUri, Callback callback) {
        if (imageUri == null) {
            fail(callback, "No image was selected.");
            return;
        }
        worker.execute(() -> {
            Bitmap bitmap = null;
            try {
                ensureOpen();
                bitmap = decodeScaled(imageUri);
                if (bitmap == null) throw new IOException("The selected image could not be decoded.");
                TessBaseAPI engine = getOcr();
                String text;
                try {
                    engine.setImage(bitmap);
                    text = engine.getUTF8Text();
                } finally {
                    engine.clear();
                }
                success(callback, text == null ? "" : text.trim());
            } catch (Throwable error) {
                fail(callback, safeMessage(error));
            } finally {
                if (bitmap != null && !bitmap.isRecycled()) bitmap.recycle();
            }
        });
    }

    private synchronized TessBaseAPI getOcr() throws Exception {
        ensureOpen();
        if (ocr == null) {
            TessBaseAPI candidate = new TessBaseAPI();
            boolean initialized = false;
            try {
                initialized = candidate.init(new File(packageDirectory, "model").getAbsolutePath(),
                        "fas+eng", TessBaseAPI.OEM_LSTM_ONLY);
                if (!initialized) throw new IllegalStateException("Could not initialize Persian/English OCR.");
                candidate.setPageSegMode(TessBaseAPI.PageSegMode.PSM_AUTO);
                ocr = candidate;
            } finally {
                if (!initialized) candidate.recycle();
            }
        }
        return ocr;
    }

    /** Launches Google's on-device document scanner UI with edge detection and perspective crop. */
    public void startDocumentScan(Activity activity, Callback callback) {
        if (activity == null) {
            fail(callback, "The scanner needs an active Link screen.");
            return;
        }
        synchronized (this) {
            if (closed) {
                fail(callback, "Document Editor is closed.");
                return;
            }
            pendingDocumentCallback = callback;
        }
        GmsDocumentScannerOptions options = new GmsDocumentScannerOptions.Builder()
                .setGalleryImportAllowed(true)
                .setPageLimit(30)
                .setCaptureMode(GmsDocumentScannerOptions.CAPTURE_MODE_AUTO)
                .setResultFormats(GmsDocumentScannerOptions.RESULT_FORMAT_JPEG,
                        GmsDocumentScannerOptions.RESULT_FORMAT_PDF)
                .setScannerMode(GmsDocumentScannerOptions.SCANNER_MODE_FULL)
                .build();
        GmsDocumentScanner scanner = GmsDocumentScanning.getClient(options);
        scanner.getStartScanIntent(activity)
                .addOnSuccessListener(sender -> {
                    try {
                        activity.startIntentSenderForResult(sender, REQUEST_DOCUMENT_SCAN,
                                null, 0, 0, 0);
                    } catch (Exception error) {
                        completeDocumentFailure(safeMessage(error));
                    }
                })
                .addOnFailureListener(error -> completeDocumentFailure(safeMessage(error)));
    }

    /** Called by the host Activity for the request code started above. */
    public boolean handleActivityResult(int requestCode, int resultCode, Intent data) {
        if (requestCode != REQUEST_DOCUMENT_SCAN) return false;
        if (resultCode != Activity.RESULT_OK || data == null) {
            completeDocumentFailure("Document scanning was cancelled.");
            return true;
        }
        try {
            GmsDocumentScanningResult result =
                    GmsDocumentScanningResult.fromActivityResultIntent(data);
            int savedPages = 0;
            if (result != null && result.getPages() != null) {
                for (GmsDocumentScanningResult.Page page : result.getPages()) {
                    Uri image = page.getImageUri();
                    if (image != null) {
                        saveImageToGallery(image, ++savedPages);
                    }
                }
            }
            boolean pdfSaved = false;
            if (result != null && result.getPdf() != null && result.getPdf().getUri() != null) {
                savePdfToDownloads(result.getPdf().getUri());
                pdfSaved = true;
            }
            if (savedPages == 0 && !pdfSaved) {
                throw new IOException("The scanner returned no pages or PDF.");
            }
            Callback callback;
            synchronized (this) {
                callback = pendingDocumentCallback;
                pendingDocumentCallback = null;
            }
            success(callback, "DOCUMENT_SCAN_SAVED:" + savedPages + ":" + (pdfSaved ? "1" : "0"));
        } catch (Throwable error) {
            completeDocumentFailure(safeMessage(error));
        }
        return true;
    }

    /** QR and common 1D/2D barcode scanning, with Google Play services providing the scanner UI. */
    public void startCodeScan(Activity activity, Callback callback) {
        if (activity == null) {
            fail(callback, "The scanner needs an active Link screen.");
            return;
        }
        GmsBarcodeScannerOptions options = new GmsBarcodeScannerOptions.Builder()
                .setBarcodeFormats(
                        Barcode.FORMAT_QR_CODE,
                        Barcode.FORMAT_CODE_128,
                        Barcode.FORMAT_CODE_39,
                        Barcode.FORMAT_CODE_93,
                        Barcode.FORMAT_CODABAR,
                        Barcode.FORMAT_EAN_13,
                        Barcode.FORMAT_EAN_8,
                        Barcode.FORMAT_ITF,
                        Barcode.FORMAT_UPC_A,
                        Barcode.FORMAT_UPC_E,
                        Barcode.FORMAT_PDF417,
                        Barcode.FORMAT_AZTEC,
                        Barcode.FORMAT_DATA_MATRIX)
                .enableAutoZoom()
                .build();
        GmsBarcodeScanner scanner = GmsBarcodeScanning.getClient(activity, options);
        scanner.startScan()
                .addOnSuccessListener(barcode -> {
                    String value = barcode == null ? null : barcode.getRawValue();
                    if (value == null || value.trim().isEmpty()) {
                        fail(callback, "No readable barcode data was returned.");
                    } else {
                        success(callback, barcodeFormatName(barcode.getFormat()) + "\n" + value);
                    }
                })
                .addOnCanceledListener(() -> fail(callback, "Scanning was cancelled."))
                .addOnFailureListener(error -> fail(callback, safeMessage(error)));
    }

    private static String barcodeFormatName(int format) {
        switch (format) {
            case Barcode.FORMAT_QR_CODE: return "QR Code";
            case Barcode.FORMAT_CODE_128: return "Code 128";
            case Barcode.FORMAT_CODE_39: return "Code 39";
            case Barcode.FORMAT_CODE_93: return "Code 93";
            case Barcode.FORMAT_CODABAR: return "Codabar";
            case Barcode.FORMAT_EAN_13: return "EAN-13";
            case Barcode.FORMAT_EAN_8: return "EAN-8";
            case Barcode.FORMAT_ITF: return "ITF";
            case Barcode.FORMAT_UPC_A: return "UPC-A";
            case Barcode.FORMAT_UPC_E: return "UPC-E";
            case Barcode.FORMAT_PDF417: return "PDF417";
            case Barcode.FORMAT_AZTEC: return "Aztec";
            case Barcode.FORMAT_DATA_MATRIX: return "Data Matrix";
            default: return "Barcode";
        }
    }

    /** Creates a multi-page PDF from editable text and an optional selected image. */
    public void exportPdf(String text, Uri imageUri, Uri destination, Callback callback) {
        worker.execute(() -> {
            Bitmap bitmap = null;
            PdfDocument document = new PdfDocument();
            try {
                ensureOpen();
                if ((text == null || text.trim().isEmpty()) && imageUri == null) {
                    throw new IllegalArgumentException("Add text or an image before exporting.");
                }
                if (imageUri != null) {
                    bitmap = decodeScaled(imageUri);
                    if (bitmap == null) throw new IOException("The selected image could not be decoded.");
                }
                TextPaint textPaint = new TextPaint(Paint.ANTI_ALIAS_FLAG);
                textPaint.setColor(0xff202124);
                textPaint.setTextSize(12f);
                int pageWidth = 595;
                int pageHeight = 842;
                int contentWidth = pageWidth - 80;
                StaticLayout layout = StaticLayout.Builder.obtain(
                        text == null ? "" : text, 0, (text == null ? "" : text).length(),
                        textPaint, contentWidth)
                        .setAlignment(Layout.Alignment.ALIGN_NORMAL)
                        .setIncludePad(true)
                        .build();
                int firstPageTop = bitmap == null ? 58 : 390;
                int line = 0;
                int pageNumber = 0;
                do {
                    pageNumber++;
                    int top = pageNumber == 1 ? firstPageTop : 58;
                    int availableHeight = pageHeight - top - 54;
                    int startLine = line;
                    while (line < layout.getLineCount()
                            && layout.getLineBottom(line) - layout.getLineTop(startLine) <= availableHeight) {
                        line++;
                    }
                    if (line == startLine && line < layout.getLineCount()) line++;
                    PdfDocument.Page page = document.startPage(
                            new PdfDocument.PageInfo.Builder(pageWidth, pageHeight, pageNumber).create());
                    Canvas canvas = page.getCanvas();
                    Paint heading = new Paint(Paint.ANTI_ALIAS_FLAG);
                    heading.setColor(0xff27346b);
                    heading.setTextSize(20f);
                    heading.setFakeBoldText(true);
                    canvas.drawText("Link Document", 40, 38, heading);
                    if (pageNumber == 1 && bitmap != null) {
                        RectF target = new RectF(40, 62, pageWidth - 40, 370);
                        float scale = Math.min(target.width() / bitmap.getWidth(),
                                target.height() / bitmap.getHeight());
                        float width = bitmap.getWidth() * scale;
                        float height = bitmap.getHeight() * scale;
                        float left = target.centerX() - width / 2f;
                        float topImage = target.centerY() - height / 2f;
                        canvas.drawBitmap(bitmap, null,
                                new RectF(left, topImage, left + width, topImage + height), null);
                    }
                    canvas.save();
                    canvas.clipRect(40, top, pageWidth - 40, pageHeight - 54);
                    canvas.translate(40, top - layout.getLineTop(startLine));
                    layout.draw(canvas);
                    canvas.restore();
                    document.finishPage(page);
                } while (line < layout.getLineCount());
                try (OutputStream output = app.getContentResolver().openOutputStream(destination, "w")) {
                    if (output == null) throw new IOException("Could not open the PDF destination.");
                    document.writeTo(output);
                }
                success(callback, "PDF_SAVED");
            } catch (Throwable error) {
                fail(callback, safeMessage(error));
            } finally {
                document.close();
                if (bitmap != null && !bitmap.isRecycled()) bitmap.recycle();
            }
        });
    }

    /** Creates an editable Word document and embeds the optional source image. */
    public void exportDocx(String text, Uri imageUri, Uri destination, Callback callback) {
        worker.execute(() -> {
            Bitmap bitmap = null;
            try {
                ensureOpen();
                if ((text == null || text.trim().isEmpty()) && imageUri == null) {
                    throw new IllegalArgumentException("Add text or an image before exporting.");
                }
                if (imageUri != null) {
                    bitmap = decodeScaled(imageUri);
                    if (bitmap == null) throw new IOException("The selected image could not be decoded.");
                }
                try (OutputStream raw = app.getContentResolver().openOutputStream(destination, "w")) {
                    if (raw == null) throw new IOException("Could not open the Word document destination.");
                    writeDocx(raw, text == null ? "" : text, bitmap);
                }
                success(callback, "DOCX_SAVED");
            } catch (Throwable error) {
                fail(callback, safeMessage(error));
            } finally {
                if (bitmap != null && !bitmap.isRecycled()) bitmap.recycle();
            }
        });
    }

    private void writeDocx(OutputStream output, String text, Bitmap image) throws Exception {
        try (ZipOutputStream zip = new ZipOutputStream(output)) {
            put(zip, "[Content_Types].xml",
                    "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
                    + "<Types xmlns=\"http://schemas.openxmlformats.org/package/2006/content-types\">"
                    + "<Default Extension=\"rels\" ContentType=\"application/vnd.openxmlformats-package.relationships+xml\"/>"
                    + "<Default Extension=\"xml\" ContentType=\"application/xml\"/>"
                    + (image == null ? "" : "<Default Extension=\"png\" ContentType=\"image/png\"/>")
                    + "<Override PartName=\"/word/document.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml\"/>"
                    + "</Types>");
            put(zip, "_rels/.rels",
                    "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
                    + "<Relationships xmlns=\"http://schemas.openxmlformats.org/package/2006/relationships\">"
                    + "<Relationship Id=\"rId1\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument\" Target=\"word/document.xml\"/>"
                    + "</Relationships>");
            StringBuilder body = new StringBuilder();
            String paragraphProperties = containsRtl(text)
                    ? "<w:pPr><w:bidi/><w:jc w:val=\"right\"/></w:pPr>" : "";
            String[] lines = text.split("\\R", -1);
            for (String line : lines) {
                body.append("<w:p>").append(paragraphProperties).append("<w:r><w:t xml:space=\"preserve\">")
                        .append(xmlEscape(line)).append("</w:t></w:r></w:p>");
            }
            long imageWidthEmu = 5486400L;
            long imageHeightEmu = 3200400L;
            if (image != null) {
                double imageScale = Math.min(5486400d / image.getWidth(), 7315200d / image.getHeight());
                imageWidthEmu = Math.round(image.getWidth() * imageScale);
                imageHeightEmu = Math.round(image.getHeight() * imageScale);
                body.append("<w:p><w:r><w:drawing><wp:inline distT=\"0\" distB=\"0\" distL=\"0\" distR=\"0\">")
                        .append("<wp:extent cx=\"").append(imageWidthEmu).append("\" cy=\"").append(imageHeightEmu).append("\"/>")
                        .append("<wp:docPr id=\"1\" name=\"Scanned image\"/>")
                        .append("<a:graphic xmlns:a=\"http://schemas.openxmlformats.org/drawingml/2006/main\">")
                        .append("<a:graphicData uri=\"http://schemas.openxmlformats.org/drawingml/2006/picture\">")
                        .append("<pic:pic xmlns:pic=\"http://schemas.openxmlformats.org/drawingml/2006/picture\">")
                        .append("<pic:nvPicPr><pic:cNvPr id=\"0\" name=\"image1.png\"/><pic:cNvPicPr/></pic:nvPicPr>")
                        .append("<pic:blipFill><a:blip r:embed=\"rId2\" xmlns:r=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships\"/><a:stretch><a:fillRect/></a:stretch></pic:blipFill>")
                        .append("<pic:spPr><a:xfrm><a:off x=\"0\" y=\"0\"/><a:ext cx=\"").append(imageWidthEmu).append("\" cy=\"").append(imageHeightEmu).append("\"/></a:xfrm><a:prstGeom prst=\"rect\"><a:avLst/></a:prstGeom></pic:spPr>")
                        .append("</pic:pic></a:graphicData></a:graphic></wp:inline></w:drawing></w:r></w:p>");
            }
            put(zip, "word/document.xml",
                    "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
                    + "<w:document xmlns:w=\"http://schemas.openxmlformats.org/wordprocessingml/2006/main\" "
                    + "xmlns:r=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships\" "
                    + "xmlns:wp=\"http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing\">"
                    + "<w:body>" + body + "<w:sectPr><w:pgSz w:w=\"11906\" w:h=\"16838\"/>"
                    + "<w:pgMar w:top=\"900\" w:right=\"900\" w:bottom=\"900\" w:left=\"900\"/>"
                    + "</w:sectPr></w:body></w:document>");
            if (image != null) {
                put(zip, "word/_rels/document.xml.rels",
                        "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
                        + "<Relationships xmlns=\"http://schemas.openxmlformats.org/package/2006/relationships\">"
                        + "<Relationship Id=\"rId2\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/image\" Target=\"media/image1.png\"/>"
                        + "</Relationships>");
                zip.putNextEntry(new ZipEntry("word/media/image1.png"));
                image.compress(Bitmap.CompressFormat.PNG, 100, zip);
                zip.closeEntry();
            } else {
                put(zip, "word/_rels/document.xml.rels",
                        "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
                        + "<Relationships xmlns=\"http://schemas.openxmlformats.org/package/2006/relationships\"/>");
            }
        }
    }

    private static boolean containsRtl(String value) {
        if (value == null) return false;
        for (int i = 0; i < value.length(); i++) {
            char character = value.charAt(i);
            if ((character >= 0x0590 && character <= 0x08ff)
                    || (character >= 0xfb1d && character <= 0xfdff)
                    || (character >= 0xfe70 && character <= 0xfeff)) {
                return true;
            }
        }
        return false;
    }

    private static void put(ZipOutputStream zip, String name, String value) throws IOException {
        zip.putNextEntry(new ZipEntry(name));
        zip.write(value.getBytes(StandardCharsets.UTF_8));
        zip.closeEntry();
    }

    private static String xmlEscape(String value) {
        return value.replace("&", "&amp;").replace("<", "&lt;")
                .replace(">", "&gt;").replace("\"", "&quot;").replace("'", "&apos;");
    }

    private Bitmap decodeScaled(Uri uri) throws Exception {
        BitmapFactory.Options bounds = new BitmapFactory.Options();
        bounds.inJustDecodeBounds = true;
        try (java.io.InputStream input = app.getContentResolver().openInputStream(uri)) {
            if (input == null) throw new IOException("Could not read the selected image.");
            BitmapFactory.decodeStream(input, null, bounds);
        }
        int sample = 1;
        while (bounds.outWidth / sample > MAX_IMAGE_DIMENSION
                || bounds.outHeight / sample > MAX_IMAGE_DIMENSION) sample *= 2;
        BitmapFactory.Options options = new BitmapFactory.Options();
        options.inSampleSize = sample;
        try (java.io.InputStream input = app.getContentResolver().openInputStream(uri)) {
            if (input == null) throw new IOException("Could not read the selected image.");
            return BitmapFactory.decodeStream(input, null, options);
        }
    }

    private Uri saveImageToGallery(Uri source, int index) throws Exception {
        String name = "Link-Scan-" + System.currentTimeMillis() + "-" + index + ".jpg";
        ContentValues values = new ContentValues();
        values.put(MediaStore.Images.Media.DISPLAY_NAME, name);
        values.put(MediaStore.Images.Media.MIME_TYPE, "image/jpeg");
        if (Build.VERSION.SDK_INT >= 29) {
            values.put("relative_path",
                    Environment.DIRECTORY_PICTURES + "/Link Scans");
            values.put("is_pending", 1);
        }
        Uri target = app.getContentResolver().insert(
                MediaStore.Images.Media.EXTERNAL_CONTENT_URI, values);
        if (target == null) throw new IOException("Could not create a gallery image.");
        try (java.io.InputStream input = app.getContentResolver().openInputStream(source);
             OutputStream output = app.getContentResolver().openOutputStream(target, "w")) {
            if (input == null || output == null) throw new IOException("Could not save the scanned page.");
            copy(input, output);
        }
        if (Build.VERSION.SDK_INT >= 29) {
            ContentValues ready = new ContentValues();
            ready.put("is_pending", 0);
            app.getContentResolver().update(target, ready, null, null);
        }
        return target;
    }

    private Uri savePdfToDownloads(Uri source) throws Exception {
        String name = "Link-Scan-" + System.currentTimeMillis() + ".pdf";
        if (Build.VERSION.SDK_INT >= 29) {
            ContentValues values = new ContentValues();
            values.put(MediaStore.MediaColumns.DISPLAY_NAME, name);
            values.put(MediaStore.MediaColumns.MIME_TYPE, "application/pdf");
            values.put("relative_path", Environment.DIRECTORY_DOWNLOADS + "/Link");
            values.put("is_pending", 1);
            Uri target = app.getContentResolver().insert(Uri.parse("content://media/external/downloads"), values);
            if (target == null) throw new IOException("Could not create the scanned PDF.");
            try (java.io.InputStream input = app.getContentResolver().openInputStream(source);
                 OutputStream output = app.getContentResolver().openOutputStream(target, "w")) {
                if (input == null || output == null) throw new IOException("Could not save the scanned PDF.");
                copy(input, output);
            }
            ContentValues ready = new ContentValues();
            ready.put("is_pending", 0);
            app.getContentResolver().update(target, ready, null, null);
            return target;
        }
        File directory = new File(app.getExternalFilesDir(Environment.DIRECTORY_DOCUMENTS), "Link");
        if (!directory.exists() && !directory.mkdirs()) throw new IOException("Could not create document storage.");
        File target = new File(directory, name);
        try (java.io.InputStream input = app.getContentResolver().openInputStream(source);
             OutputStream output = new java.io.FileOutputStream(target)) {
            if (input == null) throw new IOException("Could not read the scanned PDF.");
            copy(input, output);
        }
        return Uri.fromFile(target);
    }

    private static void copy(java.io.InputStream input, OutputStream output) throws IOException {
        byte[] buffer = new byte[32 * 1024];
        int count;
        while ((count = input.read(buffer)) != -1) output.write(buffer, 0, count);
    }

    private void completeDocumentFailure(String message) {
        Callback callback;
        synchronized (this) {
            callback = pendingDocumentCallback;
            pendingDocumentCallback = null;
        }
        fail(callback, message);
    }

    private static void success(Callback callback, String value) {
        if (callback != null) callback.onSuccess(value == null ? "" : value);
    }

    private static void fail(Callback callback, String message) {
        if (callback != null) callback.onFailure(message == null ? "The operation failed." : message);
    }

    private static String safeMessage(Throwable error) {
        if (error == null) return "The operation failed.";
        String message = error.getMessage();
        if (message == null || message.trim().isEmpty()) return error.getClass().getSimpleName();
        return message;
    }

    private synchronized void ensureOpen() {
        if (closed) throw new IllegalStateException("Document Editor is closed.");
    }

    @Override
    public synchronized void close() {
        if (closed) return;
        closed = true;
        if (ocr != null) {
            ocr.recycle();
            ocr = null;
        }
        worker.shutdownNow();
        pendingDocumentCallback = null;
    }
}
