# Speech synthesis plugins (TTS)

## Recommended engine

Use **Piper VITS ONNX voices through sherpa-onnx TTS**.

Why:
- The Link Standard app already includes sherpa-onnx Java support for offline TTS.
- Piper voices are distributed as an ONNX model plus a small JSON configuration file.
- sherpa-onnx documents support for Piper model formats and Android TTS integration.
- This avoids adding a separate PyTorch, Coqui, or Chatterbox runtime to Link.

## First Persian voice candidates

Use the existing Persian (fa_IR) Piper voice set as the first evaluation pool:
- fa_IR-ganji-medium
- fa_IR-ganji_adabi-medium
- fa_IR-amir-medium
- fa_IR-gyro-medium
- fa_IR-reza_ibrahim-medium

Each voice is currently listed as a single-speaker, medium-quality voice. Do not label a voice male or female in the UI unless actual samples have been listened to and attribution confirms it. Start with one default Persian voice, then add other choices after listening tests with native Persian speakers.

Ganji Adabi is a useful first candidate for a more literary reading style; Ganji is a practical baseline. This is a shortlist for listening tests, not a claim that one has objectively superior quality.

## Suggested first package

Suggested package ID: tts.piper.fa-IR.ganji-adabi

Required payload:
- fa_IR-ganji_adabi-medium.onnx
- fa_IR-ganji_adabi-medium.onnx.json
- required eSpeak NG phonemizer data, unless a compatible shared runtime copy already exists in Link
- license and attribution notices

Do not download or duplicate eSpeak data per voice if the shared runtime data is sufficient.

## English voices

Add English only after choosing and checking an actual voice sample and its model card. Keep each voice as an independent catalog item. Avoid hard-coding gender labels from voice names.

## License and release gate

Piper's code repository being MIT does not automatically mean every voice has an MIT model license. Inspect each voice's MODEL_CARD, configuration, dataset attribution, and redistribution terms separately. The Persian voice cards currently identify the source dataset as CC0; preserve original attribution and license files in the package.

No TTS package is published yet. Pin the upstream revision, run Persian pronunciation tests (including ی/ک variants, نیم‌فاصله, Arabic loanwords, numbers, URLs, and English words), and publish only after the selected voice passes listening tests and package checksums are final.
