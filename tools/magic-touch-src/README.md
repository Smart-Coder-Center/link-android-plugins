# Magic Touch runtime adapter

This Java adapter is compiled with the pinned MediaPipe Tasks Vision runtime into DEX files by
`tools/build_magic_touch_runtime.sh`. It is intentionally source-only in this directory and
is not copied into the downloadable plugin ZIP as Java source.

The entry point contract is:

- class: `eu.siacs.link.plugins.magic_touch.MagicTouchPlugin`
- factory: `public static MagicTouchPlugin create(Context, File)`
- `setImage(Bitmap)`
- `segment(float[] x, float[] y, int[] mode)`, where 0 is a stroke separator, 1 is KEEP/POSITIVE,
  and 2 is REMOVE/NEGATIVE
- `getMaskWidth()`, `getMaskHeight()`, and `close()`

Only the compiled DEX output, required ABI-scoped native libraries, and the model are packaged.
