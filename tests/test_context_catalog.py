from __future__ import annotations

import json
import os
import unittest
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Thread

from jsonschema import Draft202012Validator, FormatChecker

from za3im_runtime.api import make_handler
from za3im_runtime.context_catalog import ContextCatalog, CONTEXT_CATALOG_VERSION
from za3im_runtime.service import Za3imService
from za3im_runtime.store import ExecutionStore


class _NeverCalledProvider:
    provider = "test-only"
    model = "test-only"
    live_enabled = False
    api_key = ""

    def generate_copy(self, profile: dict, max_output_tokens: int = 1200):
        raise AssertionError("Context catalog routes must never call a model provider")


class ContextCatalogTests(unittest.TestCase):
    def setUp(self):
        self.catalog = ContextCatalog()
        self.schema_path = Path(__file__).resolve().parents[1] / "schemas" / "context-source.schema.json"
        self.schema = json.loads(self.schema_path.read_text(encoding="utf-8"))

    def test_catalog_schema_is_valid_and_all_sources_match_it(self):
        Draft202012Validator.check_schema(self.schema)
        validator = Draft202012Validator(self.schema, format_checker=FormatChecker())
        for source in self.catalog.list_sources()["sources"]:
            with self.subTest(source_id=source["source_id"]):
                validator.validate(source)

    def test_catalog_contains_only_locators_not_ingested_context_data(self):
        response = self.catalog.list_sources()
        self.assertEqual(response["registry_version"], CONTEXT_CATALOG_VERSION)
        self.assertGreaterEqual(len(response["sources"]), 6)
        for source in response["sources"]:
            with self.subTest(source_id=source["source_id"]):
                self.assertEqual(source["status"], "source_only")
                self.assertEqual(source["data_state"], "not_ingested")
                self.assertEqual(source["connector_state"], "not_implemented")
                self.assertFalse(source["queryable"])
                self.assertIsNone(source["content_sha256"])
                self.assertIn("review_required", source["license_status"])

    def test_official_sources_are_classified_by_domain_without_network_access(self):
        legal = self.catalog.list_sources(domain="legal")
        self.assertGreaterEqual(len(legal["sources"]), 2)
        self.assertTrue(all(source["domain"] == "legal" for source in legal["sources"]))
        all_sources = self.catalog.list_sources()["sources"]
        self.assertTrue(any("joradp" in source["source_uri"] for source in all_sources))
        self.assertTrue(any("worldbank.org" in source["source_uri"] for source in all_sources))
        self.assertTrue(any("imf.org" in source["source_uri"] for source in all_sources))

    def test_source_lookup_is_deterministic_and_unknown_id_returns_none(self):
        all_sources = self.catalog.list_sources()["sources"]
        source_id = all_sources[0]["source_id"]
        self.assertEqual(self.catalog.get_source(source_id), all_sources[0])
        self.assertIsNone(self.catalog.get_source("not-a-source"))

    def test_catalog_rejects_invalid_domains_instead_of_silently_returning_empty(self):
        with self.assertRaisesRegex(ValueError, "domain"):
            self.catalog.list_sources(domain="made-up-domain")

    def test_http_catalog_endpoints_are_read_only_and_do_not_call_provider(self):
        with TemporaryDirectory() as root:
            store = ExecutionStore(os.path.join(root, "state.sqlite3"), os.path.join(root, "artifacts"))
            provider = _NeverCalledProvider()
            service = Za3imService(store, provider)
            handler = make_handler(service, api_token="", context_catalog=self.catalog)
            server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            self.addCleanup(lambda: (server.shutdown(), server.server_close(), thread.join(timeout=3)))
            conn = HTTPConnection("127.0.0.1", server.server_port, timeout=3)
            self.addCleanup(conn.close)

            conn.request("GET", "/v1/context/sources")
            response = conn.getresponse()
            payload = json.loads(response.read())
            self.assertEqual(response.status, 200)
            self.assertEqual(payload["registry_version"], CONTEXT_CATALOG_VERSION)
            self.assertGreaterEqual(len(payload["sources"]), 6)

            first = payload["sources"][0]
            conn.request("GET", f"/v1/context/sources/{first['source_id']}")
            response = conn.getresponse()
            detail = json.loads(response.read())
            self.assertEqual(response.status, 200)
            self.assertEqual(detail, first)

            conn.request("GET", "/v1/context/sources/does-not-exist")
            response = conn.getresponse()
            missing = json.loads(response.read())
            self.assertEqual(response.status, 404)
            self.assertEqual(missing["error"]["code"], "CONTEXT_SOURCE_NOT_FOUND")

    def test_context_catalog_route_obeys_the_existing_bearer_gate(self):
        with TemporaryDirectory() as root:
            store = ExecutionStore(os.path.join(root, "state.sqlite3"), os.path.join(root, "artifacts"))
            service = Za3imService(store, _NeverCalledProvider())
            server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(service, api_token="test-context-token"))
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            self.addCleanup(lambda: (server.shutdown(), server.server_close(), thread.join(timeout=3)))
            conn = HTTPConnection("127.0.0.1", server.server_port, timeout=3)
            self.addCleanup(conn.close)

            conn.request("GET", "/v1/context/sources")
            response = conn.getresponse()
            response.read()
            self.assertEqual(response.status, 401)

            conn.request("GET", "/v1/context/sources", headers={"Authorization": "Bearer test-context-token"})
            response = conn.getresponse()
            response.read()
            self.assertEqual(response.status, 200)


if __name__ == "__main__":
    unittest.main(verbosity=2)
