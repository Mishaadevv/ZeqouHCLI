import unittest

from zeqouhcli.model_metadata import effective_context_window, effort_options, extract_model_metadata


class ModelMetadataTests(unittest.TestCase):
    def test_usable_context_is_capped_by_upstream_provider(self):
        item = {
            "id": "vendor/model-x",
            "context_length": 131072,
            "max_input_tokens": 100000,
            "top_provider": {"context_length": 65536},
            "architecture": {"input_modalities": ["text", "image"]},
            "supported_parameters": ["reasoning_effort"],
            "reasoning_efforts": ["low", "high"],
        }
        metadata = extract_model_metadata(item)
        self.assertEqual(metadata["context_window"], 65536)
        self.assertEqual(metadata["model_context_window"], 100000)
        self.assertIn("most restrictive", metadata["context_source"])
        self.assertTrue(metadata["supports_images"])
        self.assertEqual(metadata["supported_reasoning_efforts"], ["low", "high"])
        self.assertTrue(metadata["reasoning_effort_supported"])

    def test_no_context_is_not_falsely_marked_as_reported(self):
        metadata = extract_model_metadata({}, "custom/model-id")
        self.assertIsNone(metadata["context_window"])
        self.assertEqual(metadata["context_source"], "unknown; using configured fallback")

    def test_context_override_wins_and_auto_uses_model_metadata(self):
        provider = {
            "model": "custom/model",
            "model_metadata": {
                "model_id": "custom/model",
                "context_window": 32768,
                "context_source": "provider model metadata",
            },
        }
        self.assertEqual(effective_context_window({}, provider), (32768, "provider model metadata"))
        self.assertEqual(effective_context_window({"context_window_override": 16384}, provider), (16384, "manual override"))

    def test_effort_options_are_scoped_to_active_model_metadata(self):
        provider = {
            "model": "custom/model",
            "model_metadata": {"model_id": "custom/model", "supported_reasoning_efforts": ["low", "high"]},
        }
        self.assertEqual(effort_options(provider), ["low", "high"])
        provider["model"] = "custom/other-model"
        self.assertEqual(effort_options(provider), [])


if __name__ == "__main__":
    unittest.main()
