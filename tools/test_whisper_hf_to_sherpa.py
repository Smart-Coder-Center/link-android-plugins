import unittest

from whisper_hf_to_sherpa import map_key


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
