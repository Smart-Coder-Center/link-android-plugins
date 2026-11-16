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
     * x/y are normalized image coordinates in [0,1]. mode 0 adds foreground;
     * mode 1 removes foreground. Consecutive points with the same mode form one stroke.
     */
    public synchronized float[] segment(float[] x, float[] y, int[] mode) {
        if (currentImage == null) throw new IllegalStateException("Set an image before segmentation");
        if (x == null || y == null || mode == null || x.length == 0
                || x.length != y.length || x.length != mode.length) {
            throw new IllegalArgumentException("Stroke coordinate arrays must have equal non-zero lengths");
        }

        List<Stroke> strokes = new ArrayList<>();
        int start = 0;
        while (start < x.length) {
            int brush = mode[start];
            if (brush != 0 && brush != 1) throw new IllegalArgumentException("Unknown brush mode");
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
            Stroke.BrushMode brushMode = brush == 0
                    ? Stroke.BrushMode.POSITIVE : Stroke.BrushMode.NEGATIVE;
            strokes.add(Stroke.builder()
                    .setBrushMode(brushMode)
                    .setPoints(points)
                    .setCompleted(true)
                    .build());
            start = end;
        }

        MPImage mask = segmenter.segment(strokes);
        try {
            FloatBuffer buffer = ByteBufferExtractor.extract(mask).asFloatBuffer();
            float[] result = new float[buffer.remaining()];
            buffer.get(result);
            return result;
        } finally {
            mask.close();
        }
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
