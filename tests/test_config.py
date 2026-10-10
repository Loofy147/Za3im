from __future__ import annotations

import unittest

from za3im_runtime.config import ConfigurationError, RuntimeConfig


class RuntimeConfigTests(unittest.TestCase):
    def test_defaults_are_local_and_live_gpt_is_disabled(self):
        config = RuntimeConfig.from_env({})

        self.assertEqual(config.api_host, "127.0.0.1")
        self.assertEqual(config.api_port, 8080)
        self.assertEqual(config.api_max_body_bytes, 1024 * 1024)
        self.assertFalse(config.live_gpt_enabled)
        self.assertEqual(config.api_token, "")

    def test_explicit_valid_environment_is_parsed_without_mutating_input(self):
        env = {
            "ZA3IM_API_HOST": "localhost",
            "ZA3IM_API_PORT": "9090",
            "ZA3IM_API_TOKEN": "not-a-real-secret",
            "ZA3IM_API_MAX_BODY_BYTES": "4096",
            "ZA3IM_DB_PATH": "/tmp/za3im-test.sqlite3",
            "ZA3IM_ARTIFACT_DIR": "/tmp/za3im-test-artifacts",
            "OPENAI_API_KEY": "test-key",
            "ZA3IM_OPENAI_MODEL": "test-model",
            "ZA3IM_ENABLE_LIVE_GPT": "false",
            "ZA3IM_OPENAI_TIMEOUT_SECONDS": "12.5",
            "ZA3IM_MAX_OUTPUT_TOKENS": "900",
            "ZA3IM_OPENAI_INPUT_USD_PER_MILLION": "0.2",
            "ZA3IM_OPENAI_OUTPUT_USD_PER_MILLION": "0.7",
        }
        original = dict(env)
        config = RuntimeConfig.from_env(env)

        self.assertEqual(config.api_port, 9090)
        self.assertEqual(config.api_token, "not-a-real-secret")
        self.assertEqual(config.api_max_body_bytes, 4096)
        self.assertEqual(config.openai_model, "test-model")
        self.assertEqual(config.provider_timeout_seconds, 12.5)
        self.assertEqual(config.max_output_tokens, 900)
        self.assertEqual(config.input_price_per_million, 0.2)
        self.assertEqual(config.output_price_per_million, 0.7)
        self.assertEqual(env, original)

    def test_rejects_invalid_boolean_instead_of_silently_disabling_gate(self):
        with self.assertRaisesRegex(ConfigurationError, "ZA3IM_ENABLE_LIVE_GPT"):
            RuntimeConfig.from_env({"ZA3IM_ENABLE_LIVE_GPT": "sometimes"})

    def test_rejects_invalid_port_and_unbounded_request_size(self):
        with self.assertRaisesRegex(ConfigurationError, "ZA3IM_API_PORT"):
            RuntimeConfig.from_env({"ZA3IM_API_PORT": "70000"})
        with self.assertRaisesRegex(ConfigurationError, "ZA3IM_API_MAX_BODY_BYTES"):
            RuntimeConfig.from_env({"ZA3IM_API_MAX_BODY_BYTES": str(64 * 1024 * 1024)})

    def test_refuses_non_loopback_bind_without_token(self):
        with self.assertRaisesRegex(ConfigurationError, "ZA3IM_API_TOKEN"):
            RuntimeConfig.from_env({"ZA3IM_API_HOST": "0.0.0.0"})

    def test_rejects_invalid_output_token_limit_and_provider_timeout(self):
        with self.assertRaisesRegex(ConfigurationError, "ZA3IM_MAX_OUTPUT_TOKENS"):
            RuntimeConfig.from_env({"ZA3IM_MAX_OUTPUT_TOKENS": "5000"})
        with self.assertRaisesRegex(ConfigurationError, "ZA3IM_OPENAI_TIMEOUT_SECONDS"):
            RuntimeConfig.from_env({"ZA3IM_OPENAI_TIMEOUT_SECONDS": "nan"})

    def test_rejects_non_finite_or_non_positive_cost_rates(self):
        for key, value in (
            ("ZA3IM_OPENAI_INPUT_USD_PER_MILLION", "nan"),
            ("ZA3IM_OPENAI_OUTPUT_USD_PER_MILLION", "-0.01"),
            ("ZA3IM_OPENAI_INPUT_USD_PER_MILLION", "inf"),
        ):
            with self.subTest(key=key, value=value):
                with self.assertRaisesRegex(ConfigurationError, key):
                    RuntimeConfig.from_env({key: value})

    def test_rejects_empty_model_and_paths(self):
        for key in ("ZA3IM_OPENAI_MODEL", "ZA3IM_DB_PATH", "ZA3IM_ARTIFACT_DIR"):
            with self.subTest(key=key):
                with self.assertRaisesRegex(ConfigurationError, key):
                    RuntimeConfig.from_env({key: "   "})


if __name__ == "__main__":
    unittest.main(verbosity=2)
