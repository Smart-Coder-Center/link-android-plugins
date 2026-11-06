import unittest
import json
import sys
import zipfile
from types import SimpleNamespace
from unittest.mock import patch
import tempfile
from pathlib import Path

from whisper_hf_to_sherpa import map_key, rename_exported_files, verify_special_token_inventory
from package_givia_whisper_plugin import build_package, validate_conversion_report



class _FakeEncoding:
    def __init__(self, special_tokens, n_vocab):
        self._special_tokens = special_tokens
        self.n_vocab = n_vocab


class _FakeOpenAITokenizer:
    def __init__(self, special_tokens, n_vocab):
        self.encoding = _FakeEncoding(special_tokens, n_vocab)


class _FakeHFTokenizer:
    def __init__(self, added_vocab, vocab_size):
        self._added_vocab = added_vocab
        self._vocab_size = vocab_size

    def __len__(self):
        return self._vocab_size

    def get_added_vocab(self):
        return dict(self._added_vocab)

    def convert_tokens_to_ids(self, token):
        return self._added_vocab.get(token, -1)




class GiviaPackageBuilderTests(unittest.TestCase):
    def _valid_report(self):
        return {
            "model_id": "givia/whisper-large-v3-turbo-persian",
            "source_revision": "a" * 40,
            "license": "CC-BY-4.0",
            "base_architecture": "turbo",
            "feature_dim": 128,
            "package_model_prefix": "large-v3-turbo-persian",
            "forward_parity": {"passed": True},
            "tokenizer_parity": {
                "inventory": {"all_special_token_ids_match": True}
            },
        }

    def test_report_rejects_wrong_model(self):
        report = self._valid_report()
        report["model_id"] = "areffarhadi/Taraneh-WMedium"
        with self.assertRaisesRegex(RuntimeError, "Wrong source model"):
            validate_conversion_report(report)

    def test_builds_data_only_zip_with_embedded_checksums(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            report = self._valid_report()
            (root / "conversion-report.json").write_text(
                json.dumps(report), encoding="utf-8"
            )
            prefix = "large-v3-turbo-persian"
            for suffix in ("encoder.int8.onnx", "decoder.int8.onnx", "tokens.txt"):
                (root / f"{prefix}-{suffix}").write_bytes(b"fixture-model-data")

            fake_onnx = SimpleNamespace(
                load=lambda *_args, **_kwargs: SimpleNamespace(
                    graph=SimpleNamespace(initializer=[])
                )
            )
            archive_path = root / "givia-plugin.zip"
            with patch.dict(sys.modules, {"onnx": fake_onnx}):
                package_report = build_package(root, archive_path, "1.0.0-test.1")

            self.assertEqual(package_report["model_id"], "givia/whisper-large-v3-turbo-persian")
            self.assertTrue(archive_path.is_file())
            with zipfile.ZipFile(archive_path) as archive:
                names = set(archive.namelist())
                self.assertIn("plugin.json", names)
                self.assertIn("ATTRIBUTION.txt", names)
                self.assertIn(f"{prefix}-encoder.int8.onnx", names)
                embedded = json.loads(archive.read("plugin.json"))
                self.assertEqual(embedded["runtime"]["model_prefix"], prefix)
                self.assertEqual(len(embedded["files"]), 4)
                self.assertTrue(all(len(item["sha256"]) == 64 for item in embedded["files"]))


class ExportedFilenameTests(unittest.TestCase):
    def test_renames_graph_tokens_and_external_sidecars(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            for name in (
                "turbo-encoder.onnx",
                "turbo-encoder.weights",
                "turbo-decoder.int8.onnx",
                "turbo-tokens.txt",
            ):
                (root / name).write_text("fixture", encoding="utf-8")
            renamed = rename_exported_files(root, "turbo", "large-v3-turbo-persian")
            self.assertEqual(len(renamed), 4)
            self.assertTrue((root / "large-v3-turbo-persian-encoder.weights").is_file())
            self.assertTrue((root / "large-v3-turbo-persian-tokens.txt").is_file())
            self.assertFalse((root / "turbo-encoder.onnx").exists())

    def test_refuses_to_overwrite_existing_package_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "turbo-encoder.onnx").write_text("source", encoding="utf-8")
            (root / "large-v3-turbo-persian-encoder.onnx").write_text("existing", encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "Refusing to overwrite"):
                rename_exported_files(root, "turbo", "large-v3-turbo-persian")


class WhisperTokenizerInventoryTests(unittest.TestCase):
    def test_exact_special_token_inventory_passes(self):
        special = {"<|startoftranscript|>": 1, "<|fa|>": 2, "<|transcribe|>": 3}
        hf = _FakeHFTokenizer(special, vocab_size=10)
        openai = _FakeOpenAITokenizer(special, n_vocab=10)
        report = verify_special_token_inventory(hf, openai)
        self.assertTrue(report["all_special_token_ids_match"])
        self.assertEqual(report["special_token_count"], 3)

    def test_unknown_hf_added_token_fails(self):
        special = {"<|startoftranscript|>": 1, "<|fa|>": 2}
        hf = _FakeHFTokenizer({**special, "<|custom|>": 10}, vocab_size=11)
        openai = _FakeOpenAITokenizer(special, n_vocab=11)
        with self.assertRaisesRegex(RuntimeError, "special-token inventory mismatch"):
            verify_special_token_inventory(hf, openai)

    def test_vocabulary_size_mismatch_fails(self):
        special = {"<|fa|>": 2}
        hf = _FakeHFTokenizer(special, vocab_size=10)
        openai = _FakeOpenAITokenizer(special, n_vocab=11)
        with self.assertRaisesRegex(RuntimeError, "vocabulary size mismatch"):
            verify_special_token_inventory(hf, openai)


class WhisperStateDictMappingTests(unittest.TestCase):
    def test_encoder_convolution_and_positions(self):
        self.assertEqual(map_key("model.encoder.conv1.weight"), "encoder.conv1.weight")
        self.assertEqual(map_key("model.encoder.conv2.bias"), "encoder.conv2.bias")
        self.assertEqual(
            map_key("model.encoder.embed_positions.weight"),
            "encoder.positional_embedding",
        )

    def test_encoder_attention_projection(self):
        self.assertEqual(
            map_key("model.encoder.layers.7.self_attn.q_proj.weight"),
            "encoder.blocks.7.attn.query.weight",
        )
        self.assertEqual(
            map_key("model.encoder.layers.2.self_attn.out_proj.bias"),
            "encoder.blocks.2.attn.out.bias",
        )

    def test_decoder_self_and_cross_attention(self):
        self.assertEqual(
            map_key("model.decoder.layers.3.self_attn.v_proj.weight"),
            "decoder.blocks.3.attn.value.weight",
        )
        self.assertEqual(
            map_key("model.decoder.layers.3.encoder_attn.k_proj.bias"),
            "decoder.blocks.3.cross_attn.key.bias",
        )

    def test_layer_norm_and_mlp(self):
        self.assertEqual(
            map_key("model.encoder.layers.1.self_attn_layer_norm.weight"),
            "encoder.blocks.1.attn_ln.weight",
        )
        self.assertEqual(
            map_key("model.decoder.layers.4.encoder_attn_layer_norm.bias"),
            "decoder.blocks.4.cross_attn_ln.bias",
        )
        self.assertEqual(
            map_key("model.decoder.layers.4.final_layer_norm.weight"),
            "decoder.blocks.4.mlp_ln.weight",
        )
        self.assertEqual(
            map_key("model.encoder.layers.0.fc1.weight"),
            "encoder.blocks.0.mlp.0.weight",
        )
        self.assertEqual(
            map_key("model.decoder.layers.0.fc2.bias"),
            "decoder.blocks.0.mlp.2.bias",
        )

    def test_embeddings_and_global_norms(self):
        self.assertEqual(
            map_key("model.decoder.embed_tokens.weight"),
            "decoder.token_embedding.weight",
        )
        self.assertEqual(
            map_key("model.decoder.embed_positions.weight"),
            "decoder.positional_embedding",
        )
        self.assertEqual(map_key("model.encoder.layer_norm.bias"), "encoder.ln_post.bias")
        self.assertEqual(map_key("model.decoder.layer_norm.weight"), "decoder.ln.weight")

    def test_projection_head_is_handled_separately(self):
        self.assertIsNone(map_key("proj_out.weight"))

    def test_unrecognized_key_is_not_mapped(self):
        self.assertIsNone(map_key("model.encoder.layers.0.unexpected.weight"))


if __name__ == "__main__":
    unittest.main()
