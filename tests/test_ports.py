from __future__ import annotations

import os
import unittest
from tempfile import TemporaryDirectory

from za3im_runtime.ports import CopyProviderPort, ExecutionRepositoryPort, IdempotencyConflict
from za3im_runtime.provider import OpenAIResponsesClient
from za3im_runtime.store import ExecutionStore, IdempotencyConflict as StoreIdempotencyConflict


class _DeterministicProvider:
    provider = "test-double"
    model = "test-model"
    live_enabled = True

    def generate_copy(self, profile: dict, max_output_tokens: int = 1200) -> dict:
        return {"content": {}, "provider": self.provider, "model": self.model}


class PortContractTests(unittest.TestCase):
    def test_real_provider_adapter_matches_provider_port(self):
        provider = OpenAIResponsesClient(api_key="", model="test-model", live_enabled=False)
        self.assertIsInstance(provider, CopyProviderPort)

    def test_deterministic_provider_matches_provider_port_without_live_network(self):
        self.assertIsInstance(_DeterministicProvider(), CopyProviderPort)

    def test_sqlite_store_matches_execution_repository_port(self):
        with TemporaryDirectory() as root:
            store = ExecutionStore(
                os.path.join(root, "state.sqlite3"),
                os.path.join(root, "artifacts"),
            )
            self.assertIsInstance(store, ExecutionRepositoryPort)

    def test_idempotency_conflict_is_shared_domain_exception(self):
        self.assertIs(StoreIdempotencyConflict, IdempotencyConflict)


if __name__ == "__main__":
    unittest.main(verbosity=2)
