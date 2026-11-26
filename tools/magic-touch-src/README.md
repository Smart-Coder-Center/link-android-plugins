# Magic Touch runtime adapter

This Java adapter is compiled with the pinned MediaPipe Tasks Vision runtime into DEX files by
`tools/build_magic_touch_runtime.sh`. It is intentionally source-only in this directory and
is not copied into the downloadable plugin ZIP as Java source.

The entry point contract is:

- class: `eu.siacs.link.plugins.magic_touch.MagicTouchPlugin`
- factory: `public static MagicTouchPlugin create(Context, File)`
- `setImage(Bitmap)`
- `segment(float[] x, float[] y, int[] mode)`:
  - 0 is a stroke separator
  - 1 is the legacy KEEP/POSITIVE brush
  - 2 is the legacy REMOVE/NEGATIVE brush
  - 3 is the Keep+ lasso
  - 4 is the Keep- lasso
- `getMaskWidth()`, `getMaskHeight()`, and `close()`

The DEX is loaded by Link's shared `PluginDexClassLoader`. Classes in plugin-owned
namespaces are loaded child-first; AndroidX APIs outside the DEX are delegated to
Link's host class loader. The builder therefore runs
`tools/audit_dex_androidx_parent_api.py` and writes a report plus candidate host
ProGuard rules under `provenance/`. Magic Touch's first audit is report-only:
review its generated report before establishing a committed API baseline.

Only the compiled DEX output, required ABI-scoped native libraries, and the model are packaged.
