import tempfile
import unittest
from pathlib import Path
from whisper_hf_to_sherpa import (
    map_key,
    rename_exported_files,
    validate_model_config,
    verify_special_token_inventory,
)



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





class WhisperArchitectureGateTests(unittest.TestCase):
    def test_expected_medium_architecture_passes(self):
        config = {
            "model_type": "whisper",
            "num_mel_bins": 80,
            "d_model": 1024,
            "encoder_layers": 24,
            "encoder_attention_heads": 16,
            "decoder_layers": 24,
            "decoder_attention_heads": 16,
            "max_source_positions": 1500,
            "max_target_positions": 448,
            "vocab_size": 51866,
        }
        validate_model_config(config, "areffarhadi/Taraneh-WMedium")

    def test_wrong_decoder_depth_fails(self):
        config = {
            "model_type": "whisper",
            "num_mel_bins": 80,
            "d_model": 1024,
            "encoder_layers": 24,
            "encoder_attention_heads": 16,
            "decoder_layers": 32,
            "decoder_attention_heads": 16,
            "max_source_positions": 1500,
            "max_target_positions": 448,
            "vocab_size": 51866,
        }
        with self.assertRaisesRegex(RuntimeError, "does not match its declared Whisper architecture"):
            validate_model_config(config, "areffarhadi/Taraneh-WMedium")


class WhisperExportRenameTests(unittest.TestCase):
    def test_renames_model_and_external_sidecars(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            for name in ("medium-encoder.onnx", "medium-encoder.weights",
                         "medium-decoder.int8.onnx", "medium-tokens.txt"):
                (root / name).write_text("fixture", encoding="utf-8")
            renamed = rename_exported_files(root, "medium", "taraneh-wmedium")
            self.assertEqual(len(renamed), 4)
            self.assertTrue((root / "taraneh-wmedium-encoder.weights").is_file())
            self.assertTrue((root / "taraneh-wmedium-tokens.txt").is_file())
            self.assertFalse((root / "medium-encoder.onnx").exists())

    def test_refuses_to_overwrite_existing_package_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "medium-encoder.onnx").write_text("source", encoding="utf-8")
            (root / "taraneh-wmedium-encoder.onnx").write_text("existing", encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "Refusing to overwrite"):
                rename_exported_files(root, "medium", "taraneh-wmedium")


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
