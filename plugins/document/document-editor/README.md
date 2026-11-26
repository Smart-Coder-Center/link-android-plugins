# Document Editor runtime

One optional Link capability, delivered as one signed ARM64 runtime package.

## Included tools

- Image to Text: local Tesseract 5 OCR using Persian (fas) and English (eng) fast models.
- Document Scanner: Google Play services document scanner UI with automatic page detection, capture, crop, rotation and PDF/JPEG output.
- Document Editor: local PDF and editable DOCX export from text and an optional source image.
- Barcode & QR Reader: Google Code Scanner UI for common 1D/2D formats, including QR, EAN, UPC, Code 128, PDF417, Aztec and Data Matrix.

## Delivery

The package is built by `tools/build_document_editor_runtime.sh` and published by the shared manual universal-plugin workflow. It contains the signed plugin DEX, the ARM64 Tesseract JNI libraries, and the two pinned Tesseract language files. Google scanner models and UI are delivered by Google Play services when first needed; they are not bundled into the Link APK or plugin archive.

The source model files are pinned to the immutable `tessdata_fast` commit `87416418657359cb625c412a48b6e1d6d41c29bd`.

## Platform note

The Google document and code scanner interfaces require compatible Google Play services. The OCR and PDF/DOCX processing are local. Direct native-runtime delivery is supported only by Link builds that explicitly permit signed runtime installation; Play-distributed builds must use the approved Play delivery path.
