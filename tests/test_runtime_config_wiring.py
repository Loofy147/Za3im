from __future__ import annotations

import unittest
from unittest.mock import patch

from za3im_runtime.config import RuntimeConfig
from za3im_runtime import api


class _StoppedServer:
    instances = []

    def __init__(self, address, handler):
        self.address = address
        self.handler = handler
        self.closed = False
        self.instances.append(self)

    def serve_forever(self):
        raise KeyboardInterrupt

    def server_close(self):
        self.closed = True


class RuntimeConfigWiringTests(unittest.TestCase):
    def setUp(self):
        _StoppedServer.instances.clear()

    def test_validated_settings_are_used_by_every_runtime_boundary(self):
        settings = RuntimeConfig(
            api_host="127.0.0.1",
            api_port=8123,
            api_token="",
            api_max_body_bytes=2048,
            db_path="/tmp/za3im-config-test.sqlite3",
            artifact_dir="/tmp/za3im-config-test-artifacts",
            openai_api_key="test-key",
            openai_model="test-model",
            live_gpt_enabled=False,
            provider_timeout_seconds=12.5,
            max_output_tokens=700,
            input_price_per_million=0.2,
            output_price_per_million=0.7,
        )
        handler_marker = object()

        with (
            patch("za3im_runtime.api.ExecutionStore") as store_factory,
            patch("za3im_runtime.api.OpenAIResponsesClient") as provider_factory,
            patch("za3im_runtime.api.Za3imService") as service_factory,
            patch("za3im_runtime.api.make_handler", return_value=handler_marker) as handler_factory,
            patch("za3im_runtime.api.ThreadingHTTPServer", _StoppedServer),
            patch("builtins.print"),
        ):
            api.serve(settings)

        store_factory.assert_called_once_with(settings.db_path, settings.artifact_dir)
        provider_factory.assert_called_once_with(
            api_key="test-key",
            model="test-model",
            timeout_seconds=12.5,
            live_enabled=False,
        )
        service_factory.assert_called_once_with(
            store_factory.return_value,
            provider_factory.return_value,
            max_output_tokens=700,
            input_price_per_million=0.2,
            output_price_per_million=0.7,
        )
        handler_factory.assert_called_once_with(
            service_factory.return_value,
            "",
            2048,
        )
        self.assertEqual(len(_StoppedServer.instances), 1)
        server = _StoppedServer.instances[0]
        self.assertEqual(server.address, ("127.0.0.1", 8123))
        self.assertIs(server.handler, handler_marker)
        self.assertTrue(server.closed)


if __name__ == "__main__":
    unittest.main(verbosity=2)
