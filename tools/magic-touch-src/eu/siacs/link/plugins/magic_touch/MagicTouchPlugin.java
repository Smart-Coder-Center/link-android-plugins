package eu.siacs.link.plugins.magic_touch;

import android.content.Context;
import android.graphics.Bitmap;

import com.google.mediapipe.framework.image.BitmapImageBuilder;
import com.google.mediapipe.framework.image.ByteBufferExtractor;
import com.google.mediapipe.framework.image.MPImage;
import com.google.mediapipe.tasks.components.containers.NormalizedKeypoint;
import com.google.mediapipe.tasks.core.BaseOptions;
import com.google.mediapipe.tasks.core.Delegate;
import com.google.mediapipe.tasks.vision.interactivesegmenter.InteractiveSegmenter;
import com.google.mediapipe.tasks.vision.interactivesegmenter.InteractiveSegmenterOptions;
import com.google.mediapipe.tasks.vision.interactivesegmenter.Stroke;

import java.io.File;
import java.nio.FloatBuffer;
import java.util.ArrayList;
import java.util.List;

/** Runtime entry point. Link loads this class only after signature and payload verification. */
public final class MagicTouchPlugin implements AutoCloseable {
    private final InteractiveSegmenter segmenter;
    private MPImage currentImage;
    private int maskWidth;
    private int maskHeight;

    private MagicTouchPlugin(Context context, File packageDirectory) throws Exception {
        File model = new File(packageDirectory, "model/interactive_segmentation.task");
        if (!model.isFile() || model.length() <= 0) {
            throw new IllegalStateException("MagicTouch model is missing");
        }
        BaseOptions baseOptions = BaseOptions.builder()
                .setModelAssetPath(model.getAbsolutePath())
                .setDelegate(Delegate.CPU)
                .build();
        InteractiveSegmenterOptions options = InteractiveSegmenterOptions.builder()
                .setBaseOptions(baseOptions)
                .build();
        segmenter = InteractiveSegmenter.createFromOptions(context, options);
    }

    public static MagicTouchPlugin create(Context context, File packageDirectory) throws Exception {
        if (context == null || packageDirectory == null) {
            throw new IllegalArgumentException("Context and package directory are required");
        }
        return new MagicTouchPlugin(context.getApplicationContext(), packageDirectory);
    }

    public synchronized void setImage(Bitmap bitmap) {
        if (bitmap == null || bitmap.isRecycled()) {
            throw new IllegalArgumentException("A valid image bitmap is required");
        }
        MPImage next = new BitmapImageBuilder(bitmap).build();
        segmenter.setImage(next);
        if (currentImage != null) currentImage.close();
        currentImage = next;
        maskWidth = bitmap.getWidth();
        maskHeight = bitmap.getHeight();
    }

    /**
     * x/y are normalized image coordinates in [0,1]. Mode 1 is KEEP/POSITIVE
     * (include foreground); mode 2 is REMOVE/NEGATIVE (exclude foreground).
     * Consecutive points with the same mode form one stroke.
     */
    /**
     * Modes 1/2 remain supported for older clients as positive/negative brush strokes.
     * Modes 3/4 are the Link editor's Keep+/Keep- lasso selections. Keep+ keeps
     * the lasso-selected area; Keep- subtracts its lasso-selected area.
     */
    public synchronized float[] segment(float[] x, float[] y, int[] mode) {
        if (currentImage == null) throw new IllegalStateException("Set an image before segmentation");
        if (x == null || y == null || mode == null || x.length == 0
                || x.length != y.length || x.length != mode.length) {
            throw new IllegalArgumentException("Stroke coordinate arrays must have equal non-zero lengths");
        }

        List<Stroke> legacyStrokes = new ArrayList<>();
        List<Stroke> keepLassos = new ArrayList<>();
        List<Stroke> removeLassos = new ArrayList<>();
        int start = 0;
        while (start < x.length) {
            if (mode[start] == 0) {
                start++;
                continue;
            }
            int brush = mode[start];
            if (brush < 1 || brush > 4) {
                throw new IllegalArgumentException("Brush mode must be 1..4");
            }
            List<NormalizedKeypoint> points = new ArrayList<>();
            int end = start;
            while (end < x.length && mode[end] == brush) {
                if (!Float.isFinite(x[end]) || !Float.isFinite(y[end])
                        || x[end] < 0f || x[end] > 1f || y[end] < 0f || y[end] > 1f) {
                    throw new IllegalArgumentException("Stroke coordinates must be normalized");
                }
                points.add(NormalizedKeypoint.create(x[end], y[end]));
                end++;
            }

            Stroke.BrushMode brushMode;
            switch (brush) {
                case 1: brushMode = Stroke.BrushMode.POSITIVE; break;
                case 2: brushMode = Stroke.BrushMode.NEGATIVE; break;
                case 3:
                case 4: brushMode = Stroke.BrushMode.LASSO; break;
                default: throw new IllegalArgumentException("Unknown brush mode");
            }
            Stroke stroke = Stroke.builder()
                    .setBrushMode(brushMode)
                    .setPoints(points)
                    .setCompleted(true)
                    .build();
            if (brush == 1 || brush == 2) {
                legacyStrokes.add(stroke);
            } else if (brush == 3) {
                keepLassos.add(stroke);
            } else {
                removeLassos.add(stroke);
            }
            start = end;
        }

        // Preserve the original positive/negative brush contract for older APKs.
        if (!legacyStrokes.isEmpty()) {
            if (!keepLassos.isEmpty() || !removeLassos.isEmpty()) {
                throw new IllegalArgumentException("Do not mix legacy brush strokes and lasso selections");
            }
            return segmentMask(legacyStrokes);
        }

        // A Keep- only session starts from the complete image, then subtracts
        // the selected red lasso area. Keep+ selections are unioned by MediaPipe.
        float[] keepMask = keepLassos.isEmpty()
                ? filledMask(1f) : segmentMask(keepLassos);
        float[] removeMask = removeLassos.isEmpty()
                ? filledMask(0f) : segmentMask(removeLassos);
        float[] result = new float[maskWidth * maskHeight];
        for (int i = 0; i < result.length; i++) {
            float keep = clampConfidence(keepMask[i]);
            float remove = clampConfidence(removeMask[i]);
            result[i] = keep * (1f - remove);
        }
        return result;
    }

    private float[] segmentMask(List<Stroke> strokes) {
        MPImage mask = segmenter.segment(strokes);
        try {
            FloatBuffer buffer = ByteBufferExtractor.extract(mask).asFloatBuffer();
            buffer.rewind();
            if (buffer.remaining() != maskWidth * maskHeight) {
                throw new IllegalStateException("MediaPipe returned an unexpected confidence-mask size");
            }
            float[] result = new float[buffer.remaining()];
            buffer.get(result);
            return result;
        } finally {
            mask.close();
        }
    }

    private float[] filledMask(float value) {
        float[] result = new float[maskWidth * maskHeight];
        for (int i = 0; i < result.length; i++) result[i] = value;
        return result;
    }

    private float clampConfidence(float value) {
        if (!Float.isFinite(value)) return 0f;
        return Math.max(0f, Math.min(1f, value));
    }

    public int getMaskWidth() {
        return maskWidth;
    }

    public int getMaskHeight() {
        return maskHeight;
    }

    @Override
    public synchronized void close() {
        segmenter.close();
        if (currentImage != null) {
            currentImage.close();
            currentImage = null;
        }
    }
}
