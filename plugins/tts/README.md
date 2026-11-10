# Speech synthesis plugins (TTS)

## Current published package

The public catalog currently contains **Mana Persian Piper**:

- Plugin ID: `tts.mana.piper.fa`
- Catalog version: `1.0.0`
- Download: approximately 67.5 MB
- Catalog license metadata: MIT + GPL-3.0-or-later
- Runtime: Sherpa-ONNX TTS with Piper voice data

The existing release/catalog package `1.0.0` remains available. A universal source manifest for `1.0.1` now imports that immutable ZIP using its verified SHA-256 and byte size as a migration seed, preserving the known-good payload and license notices. This does not yet pin the original Piper/eSpeak upstream archives independently. Do not replace the current catalog entry until the universal package has been published and verified.

## Recommended engine

Use **Piper VITS ONNX voices through sherpa-onnx TTS**.

Why:
- The Link Standard app already includes sherpa-onnx Java support for offline TTS.
- Piper voices are distributed as an ONNX model plus a small JSON configuration file.
- sherpa-onnx documents support for Piper model formats and Android TTS integration.
- This avoids adding a separate PyTorch, Coqui, or Chatterbox runtime to Link.

## Additional Persian voice candidates

Use the existing Persian (fa_IR) Piper voice set as an evaluation pool:
- fa_IR-ganji-medium
- fa_IR-ganji_adabi-medium
- fa_IR-amir-medium
- fa_IR-gyro-medium
- fa_IR-reza_ibrahim-medium

Each voice is currently listed as a single-speaker, medium-quality voice. Do not label a voice male or female in the UI unless actual samples have been listened to and attribution confirms it. Start with one default Persian voice, then add other choices after listening tests with native Persian speakers.

Ganji Adabi is a useful candidate for a more literary reading style; Ganji is a practical baseline. This is a shortlist for listening tests, not a claim that one has objectively superior quality.

## Packaging requirements

Every new voice must use the shared universal plugin source and publishing pipeline:
- Source directory: `plugins/tts/<plugin-id>/`
- Root source manifest: `plugin.json`
- Payload includes model, configuration, required phonemizer data (only if not already supplied by Link's shared runtime), and license/attribution notices.
- The common packager generates the inner file checksums, immutable ZIP release, archive checksum, and catalog entry.
- Do not add another independent catalog writer or downloader.

Pin upstream revisions and verify Persian pronunciation (including ی/ک variants, نیم‌فاصله, Arabic loanwords, numbers, URLs, and English words) before promoting additional voices. Do not download or duplicate eSpeak data per voice if the shared runtime data is sufficient.

## License and attribution

Piper's code repository being MIT does not automatically mean every voice model is MIT-licensed. Inspect each voice's MODEL_CARD, configuration, dataset attribution, and redistribution terms separately. Preserve all original attribution and license files in each package.

The current additional-voice publishing workflow is still a legacy bespoke path and must be migrated to the universal packager before it becomes the standard release path. A restrictive license is not a reason to stop independent research or packaging preparation; give a concise reminder of the relevant restriction and continue without misrepresenting redistribution rights.
