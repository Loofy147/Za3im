from __future__ import annotations

import hashlib
import json
import os
import threading
import time
import unittest
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from tempfile import TemporaryDirectory
from threading import Thread

from za3im_runtime.api import make_handler
from za3im_runtime.provider import OpenAIResponsesClient, ProviderError
from za3im_runtime.service import Za3imService, verify_html
from za3im_runtime.store import ExecutionStore


class FakeProvider:
    provider = "openai-test-double"
    model = "test-model"
    live_enabled = True  # deterministic fake only; never sends network requests

    def __init__(self, delay: float = 0.0, fail: bool = False):
        self.calls = 0
        self.delay = delay
        self.fail = fail
        self.lock = threading.Lock()
        self.last_profile = None

    def generate_copy(self, profile: dict, max_output_tokens: int = 1200) -> dict:
        with self.lock:
            self.calls += 1
            self.last_profile = dict(profile)
        if self.delay:
            time.sleep(self.delay)
        if self.fail:
            raise ProviderError("synthetic provider failure")
        name = profile["business_name"]
        return {
            "content": {
                "site_title": f"{name} — الموقع الرسمي",
                "tagline": "خدمة قريبة منك، بعناية واحترافية.",
                "intro": f"مرحباً بك لدى {name}. نعتني بالتفاصيل ونرحب بزيارتك.",
                "services": ["قص الشعر", "العناية باللحية"],
                "cta": "احجز موعدك",
                "promotional_copy": f"زر {name} اليوم! خدمة احترافية في {profile['wilaya']}."
            },
            "provider": self.provider,
            "model": self.model,
            "request_id": "req_synthetic_01",
            "usage": {"input_tokens": 20, "output_tokens": 45, "total_tokens": 65}
        }


def request(execution_id="exec-test-001", idem="idem-test-001", name="صالون الأمير", budget=1.0):
    return {
        "schema_version": "za3im.execution.request/0.1",
        "execution_id": execution_id,
        "tenant_id": "tenant-test-01",
        "project_id": "project-test-01",
        "task_id": "task-business-presence-01",
        "parent_execution_id": None,
        "idempotency_key": idem,
        "trace_id": "trace-test-01",
        "objective": "Create a draft website and promotional copy for this fictional business.",
        "locale": "ar-DZ",
        "acceptance_criteria": [
            {"criterion_id": "website-valid", "description": "Generate a valid HTML draft with a SHA-256 hash.", "verification_method": "automated_test"},
            {"criterion_id": "no-external-effects", "description": "Do not publish or spend advertising money.", "verification_method": "automated_test"}
        ],
        "context_references": [],
        "capabilities": [
            {"capability_id": "website.generate-draft", "version_constraint": "^0.1", "input_reference_ids": []},
            {"capability_id": "marketing.copy.generate", "version_constraint": "^0.1", "input_reference_ids": []},
            {"capability_id": "website.contact-channels.render", "version_constraint": "^0.1", "input_reference_ids": []}
        ],
        "constraints": {
            "deadline_at": None,
            "max_runtime_seconds": 120,
            "max_tool_calls": 5,
            "max_steps": 5,
            "data_classification": "confidential",
            "approval_mode": "external_actions",
            "network_policy": "allowlist_only",
            "allowed_capability_ids": ["website.generate-draft", "marketing.copy.generate", "website.contact-channels.render", "artifact.write", "provider.openai.responses"],
            "allowed_domain_names": ["api.openai.com"],
            "allowed_model_providers": ["openai"],
            "allow_subdelegation": False
        },
        "budget": {"max_provider_cost_usd": budget, "max_customer_credits": 100, "max_external_spend": 0, "external_spend_currency": "DZD"},
        "created_at": "2026-10-10T14:00:00Z",
        "input_payload": {
            "business_profile": {
                "business_name": name,
                "wilaya": "Blida",
                "service_category": "barbershop",
                "business_description": "A fictional local barbershop used for tests.",
                "languages": ["ar-DZ", "fr-DZ"],
                "contact_preferences": {"preferred_channels": ["phone", "website_form"], "public_phone": "+213555000000"},
                "data_classification": "confidential"
            }
        },
        "metadata": {"test_case": "synthetic"}
    }


class ProviderContractTests(unittest.TestCase):
    def test_responses_api_client_parses_output_text_usage_and_request_id(self):
        import io

        captured = {}

        class FakeHTTPResponse(io.BytesIO):
            status = 200
            def __enter__(self): return self
            def __exit__(self, *args): self.close()
            def getcode(self): return 200
            def headers(self): return {}

        def fake_urlopen(req, timeout):
            captured["url"] = req.full_url
            captured["headers"] = dict(req.header_items())
            captured["payload"] = json.loads(req.data.decode("utf-8"))
            response = {
                "id": "resp_test_01",
                "output_text": json.dumps({"site_title":"Title","tagline":"Tag","intro":"Intro","services":["A","B"],"cta":"Go","promotional_copy":"Promo"}),
                "usage": {"input_tokens": 10, "output_tokens": 20, "total_tokens": 30}
            }
            return FakeHTTPResponse(json.dumps(response).encode("utf-8"))

        client = OpenAIResponsesClient(api_key="test-key", model="test-model", urlopen=fake_urlopen, live_enabled=True)
        result = client.generate_copy({"business_name":"Test","wilaya":"Blida","service_category":"salon"}, max_output_tokens=1200)
        self.assertEqual(captured["url"], "https://api.openai.com/v1/responses")
        self.assertEqual(captured["payload"]["model"], "test-model")
        self.assertEqual(captured["payload"]["text"]["format"]["type"], "json_object")
        self.assertEqual(result["request_id"], "resp_test_01")
        self.assertEqual(result["usage"]["total_tokens"], 30)
        self.assertEqual(result["content"]["site_title"], "Title")

    def test_provider_requires_api_key_without_making_network_call(self):
        client = OpenAIResponsesClient(api_key="", model="test-model", live_enabled=True)
        with self.assertRaisesRegex(ProviderError, "OPENAI_API_KEY"):
            client.generate_copy({"business_name":"Test","wilaya":"Blida","service_category":"salon"})

    def test_live_gpt_is_disabled_by_default_even_with_a_key(self):
        calls = {"count": 0}
        def unexpected_network_call(req, timeout):
            calls["count"] += 1
            raise AssertionError("network transport must not be called while live GPT is disabled")
        client = OpenAIResponsesClient(api_key="test-key", model="test-model", urlopen=unexpected_network_call, live_enabled=False)
        with self.assertRaisesRegex(ProviderError, "disabled until finished-product validation"):
            client.generate_copy({"business_name":"Test","wilaya":"Blida","service_category":"salon"})
        self.assertEqual(calls["count"], 0)


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = self.tmp.name
        self.store = ExecutionStore(os.path.join(self.root, "state.sqlite3"), os.path.join(self.root, "artifacts"))
        self.provider = FakeProvider()
        self.service = Za3imService(self.store, self.provider)

    def test_contact_channels_follow_preferences_and_filter_unsafe_links(self):
        payload = request()
        contact = payload["input_payload"]["business_profile"]["contact_preferences"]
        contact.update({
            "preferred_channels": ["phone", "whatsapp", "email", "social"],
            "public_phone": "0555 000 000",
            "public_email": "salon@example.dz",
            "public_address": "شارع <الحرية> & المدينة",
            "social_profile_references": [
                "javascript:alert(1)",
                "http://insecure.example/profile",
                "https://www.instagram.com/salon.example"
            ]
        })
        status, body = self.service.execute_request(payload)
        self.assertEqual(status, 201)
        record = self.store.get_artifact(next(
            item["artifact_id"] for item in body["result"]["artifacts"] if item["role"] == "website_html"
        ))
        with open(record["path"], encoding="utf-8") as stream:
            document = stream.read()
        self.assertIn('href="tel:+213555000000"', document)
        self.assertIn('href="https://wa.me/213555000000"', document)
        self.assertIn('href="mailto:salon@example.dz"', document)
        self.assertIn('https://www.instagram.com/salon.example', document)
        self.assertIn('rel="noopener noreferrer"', document)
        self.assertIn("شارع &lt;الحرية&gt; &amp; المدينة", document)
        self.assertNotIn("javascript:", document.lower())
        self.assertNotIn("http://insecure.example", document)
        check_ids = {check["check_id"] for check in body["result"]["verification"]["checks"]}
        self.assertIn("contact-links-safety", check_ids)

    def test_unselected_contact_channels_are_not_exposed(self):
        payload = request()
        contact = payload["input_payload"]["business_profile"]["contact_preferences"]
        contact.update({
            "preferred_channels": ["website_form"],
            "public_phone": "+213555000000",
            "public_email": "private@example.dz",
            "public_address": "Blida centre",
            "social_profile_references": ["https://www.instagram.com/private.profile"]
        })
        status, body = self.service.execute_request(payload)
        self.assertEqual(status, 201)
        record = self.store.get_artifact(next(
            item["artifact_id"] for item in body["result"]["artifacts"] if item["role"] == "website_html"
        ))
        with open(record["path"], encoding="utf-8") as stream:
            document = stream.read()
        self.assertNotIn("tel:+213555000000", document)
        self.assertNotIn("wa.me/213555000000", document)
        self.assertNotIn("mailto:private@example.dz", document)
        self.assertNotIn("instagram.com/private.profile", document)
        self.assertIn("Blida centre", document)

    def test_arabic_indic_algerian_phone_is_normalized_for_whatsapp(self):
        payload = request()
        contact = payload["input_payload"]["business_profile"]["contact_preferences"]
        contact["preferred_channels"] = ["whatsapp"]
        contact["public_phone"] = "٠٥٥٥٠٠٠٠٠٠"
        status, body = self.service.execute_request(payload)
        self.assertEqual(status, 201)
        record = self.store.get_artifact(next(
            item["artifact_id"] for item in body["result"]["artifacts"] if item["role"] == "website_html"
        ))
        with open(record["path"], encoding="utf-8") as stream:
            document = stream.read()
        self.assertIn('href="https://wa.me/213555000000"', document)
        self.assertNotIn('href="tel:', document)

    def test_html_verifier_rejects_script_scheme_contact_link(self):
        status, body = self.service.execute_request(request())
        self.assertEqual(status, 201)
        record = self.store.get_artifact(next(
            item["artifact_id"] for item in body["result"]["artifacts"] if item["role"] == "website_html"
        ))
        with open(record["path"], encoding="utf-8") as stream:
            document = stream.read()
        self.assertIn('href="tel:+213555000000"', document)
        mutated = document.replace('href="tel:+213555000000"', 'href="javascript:alert(1)"', 1)
        valid, message = verify_html(mutated)
        self.assertFalse(valid)
        self.assertIn("safe-link", message)

    def test_contact_fields_are_not_sent_to_model_provider(self):
        payload = request()
        profile = payload["input_payload"]["business_profile"]
        contact = profile["contact_preferences"]
        contact.update({
            "preferred_channels": ["phone", "email", "social"],
            "public_phone": "+213555000000",
            "public_email": "private@example.dz",
            "public_address": "Private avenue 42",
            "social_profile_references": ["https://social.example/private-profile"]
        })
        profile["opening_hours_reference"] = "hours-reference-secret"
        profile["approved_facts_reference_ids"] = ["private-fact-reference-secret"]
        status, _body = self.service.execute_request(payload)
        self.assertEqual(status, 201)
        forwarded = self.provider.last_profile
        self.assertIsNotNone(forwarded)
        self.assertEqual(
            set(forwarded),
            {"business_name", "wilaya", "service_category", "business_description", "languages"}
        )
        encoded = json.dumps(forwarded, ensure_ascii=False)
        for local_only in (
            "+213555000000",
            "private@example.dz",
            "Private avenue 42",
            "social.example/private-profile",
            "hours-reference-secret",
            "private-fact-reference-secret"
        ):
            self.assertNotIn(local_only, encoded)

    def test_malformed_phone_is_not_emitted_as_a_contact_link(self):
        payload = request()
        contact = payload["input_payload"]["business_profile"]["contact_preferences"]
        contact["preferred_channels"] = ["phone", "whatsapp"]
        contact["public_phone"] = "++213 555 000 000"
        status, body = self.service.execute_request(payload)
        self.assertEqual(status, 201)
        record = self.store.get_artifact(next(
            item["artifact_id"] for item in body["result"]["artifacts"] if item["role"] == "website_html"
        ))
        with open(record["path"], encoding="utf-8") as stream:
            document = stream.read()
        self.assertNotIn("href=\"tel:", document)
        self.assertNotIn("wa.me/", document)
        self.assertTrue(body["result"]["verification"]["status"] == "passed")

    def test_success_generates_two_artifacts_and_verifiable_hashes(self):
        status, body = self.service.execute_request(request())
        self.assertEqual(status, 201)
        self.assertEqual(body["status"], "succeeded")
        result = body["result"]
        self.assertEqual(result["verification"]["status"], "passed")
        self.assertEqual(len(result["artifacts"]), 2)
        for artifact in result["artifacts"]:
            record = self.store.get_artifact(artifact["artifact_id"])
            self.assertIsNotNone(record)
            with open(record["path"], "rb") as stream:
                raw = stream.read()
            self.assertEqual(hashlib.sha256(raw).hexdigest(), artifact["sha256"])
        website = next(a for a in result["artifacts"] if a["role"] == "website_html")
        with open(self.store.get_artifact(website["artifact_id"])["path"], encoding="utf-8") as stream:
            html = stream.read()
        self.assertIn("<!doctype html>", html.lower())
        self.assertIn("dir=\"rtl\"", html)
        self.assertIn("احجز موعدك", html)
        self.assertTrue(result["event_reference_ids"])
        event_ids = {str(event["event_id"]) for event in self.store.list_events("exec-test-001")}
        self.assertTrue(set(result["event_reference_ids"]).issubset(event_ids))
        self.assertTrue(result["accounting"]["usage_reference_ids"])
        for check in result["verification"]["checks"]:
            self.assertTrue(check["evidence_reference_ids"], check["check_id"])
            self.assertTrue(set(check["evidence_reference_ids"]).issubset(event_ids))

    def test_business_input_is_html_escaped_not_executable(self):
        payload = request(name="<script>alert('x')</script>")
        status, body = self.service.execute_request(payload)
        self.assertEqual(status, 201)
        artifact = next(a for a in body["result"]["artifacts"] if a["role"] == "website_html")
        with open(self.store.get_artifact(artifact["artifact_id"])["path"], encoding="utf-8") as stream:
            html = stream.read()
        self.assertNotIn("<script>", html.lower())
        self.assertIn("&lt;script&gt;", html.lower())

    def test_idempotent_replay_returns_recorded_result_without_second_provider_call(self):
        first_status, first = self.service.execute_request(request())
        retry_status, retry = self.service.execute_request(request())
        self.assertEqual(first_status, 201)
        self.assertEqual(retry_status, 200)
        self.assertEqual(retry, first)
        self.assertEqual(self.provider.calls, 1)

    def test_same_idempotency_key_with_different_request_is_rejected(self):
        self.service.execute_request(request())
        status, body = self.service.execute_request(request(name="Different business"))
        self.assertEqual(status, 409)
        self.assertEqual(body["error"]["code"], "IDEMPOTENCY_CONFLICT")
        self.assertEqual(self.provider.calls, 1)

    def test_invalid_profile_is_rejected_before_claim_or_provider_call(self):
        payload = request()
        del payload["input_payload"]["business_profile"]["wilaya"]
        status, body = self.service.execute_request(payload)
        self.assertEqual(status, 400)
        self.assertEqual(body["error"]["code"], "INVALID_BUSINESS_PROFILE")
        self.assertEqual(self.provider.calls, 0)
        self.assertIsNone(self.store.get_execution("exec-test-001"))

    def test_restricted_data_is_blocked_before_provider_egress(self):
        payload = request()
        payload["constraints"]["data_classification"] = "restricted"
        status, body = self.service.execute_request(payload)
        self.assertEqual(status, 403)
        self.assertEqual(body["error"]["code"], "DATA_CLASSIFICATION_BLOCKED")
        self.assertEqual(self.provider.calls, 0)

    def test_provider_egress_requires_explicit_domain_allowlist(self):
        payload = request()
        payload["constraints"]["allowed_domain_names"] = []
        status, body = self.service.execute_request(payload)
        self.assertEqual(status, 403)
        self.assertEqual(body["error"]["code"], "PROVIDER_EGRESS_NOT_ALLOWED")
        self.assertEqual(self.provider.calls, 0)

    def test_live_gpt_disabled_blocks_before_claim_and_provider(self):
        provider = OpenAIResponsesClient(api_key="test-key", model="test-model", live_enabled=False)
        service = Za3imService(self.store, provider)
        status, body = service.execute_request(request())
        self.assertEqual(status, 503)
        self.assertEqual(body["error"]["code"], "LIVE_GPT_DISABLED")
        self.assertIsNone(self.store.get_execution("exec-test-001"))

    def test_budget_preflight_rejects_before_provider_call(self):
        status, body = self.service.execute_request(request(budget=0.000001))
        self.assertEqual(status, 422)
        self.assertEqual(body["status"], "budget_exceeded")
        self.assertEqual(self.provider.calls, 0)

    def test_provider_failure_is_persisted_and_not_retried_implicitly(self):
        provider = FakeProvider(fail=True)
        service = Za3imService(self.store, provider)
        first_status, first = service.execute_request(request())
        second_status, second = service.execute_request(request())
        self.assertEqual(first_status, 502)
        self.assertEqual(first["status"], "failed")
        self.assertEqual(second_status, 200)
        self.assertEqual(second, first)
        self.assertEqual(provider.calls, 1)

    def test_concurrent_same_key_executes_provider_once(self):
        provider = FakeProvider(delay=0.12)
        service = Za3imService(self.store, provider)
        barrier = threading.Barrier(5)
        outputs = []
        errors = []
        def work():
            try:
                barrier.wait(timeout=2)
                outputs.append(service.execute_request(request()))
            except Exception as exc:
                errors.append(exc)
        threads = [Thread(target=work) for _ in range(5)]
        for t in threads: t.start()
        for t in threads: t.join(timeout=5)
        self.assertEqual(errors, [])
        self.assertEqual(provider.calls, 1)
        self.assertEqual(len(outputs), 5)
        self.assertIn(201, [status for status, _ in outputs])
        self.assertTrue(all(status in (201, 200, 202) for status, _ in outputs))

    def test_restart_marks_running_execution_interrupted_without_replay(self):
        payload = request(execution_id="exec-interrupted-001", idem="idem-interrupted-001")
        self.store.claim(payload)
        restarted = ExecutionStore(os.path.join(self.root, "state.sqlite3"), os.path.join(self.root, "artifacts"), recover_interrupted=True)
        record = restarted.get_execution("exec-interrupted-001")
        self.assertEqual(record["status"], "interrupted")
        self.assertEqual(record["result"]["status"], "failed")
        self.assertEqual(record["result"]["errors"][0]["code"], "INTERRUPTED_EXECUTION")

    def test_http_health_execution_replay_and_artifact_download(self):
        server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(self.service, api_token=""))
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(lambda: (server.shutdown(), server.server_close(), thread.join(timeout=3)))
        conn = HTTPConnection("127.0.0.1", server.server_port, timeout=3)
        self.addCleanup(conn.close)
        conn.request("GET", "/healthz")
        resp = conn.getresponse()
        health = json.loads(resp.read())
        self.assertEqual(resp.status, 200)
        self.assertIn("provider_configured", health)

        raw = json.dumps(request()).encode()
        conn.request("POST", "/v1/executions", body=raw, headers={"Content-Type":"application/json", "Content-Length":str(len(raw))})
        resp = conn.getresponse()
        created = json.loads(resp.read())
        self.assertEqual(resp.status, 201)
        artifact_id = created["result"]["artifacts"][0]["artifact_id"]

        conn.request("GET", f"/v1/artifacts/{artifact_id}")
        resp = conn.getresponse()
        artifact = resp.read().decode("utf-8")
        self.assertEqual(resp.status, 200)
        self.assertIn("default-src 'none'", resp.getheader("Content-Security-Policy", ""))
        self.assertIn("<!doctype html>", artifact.lower())

        conn.request("GET", "/v1/capabilities")
        resp = conn.getresponse()
        caps = json.loads(resp.read())
        self.assertEqual(resp.status, 200)
        ids = {item["capability_id"] for item in caps["capabilities"] if item["status"].startswith("implemented")}
        self.assertIn("website.generate-draft", ids)
        self.assertIn("marketing.copy.generate", ids)
        self.assertIn("website.contact-channels.render", ids)

    def test_api_token_is_required_when_configured(self):
        server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(self.service, api_token="test-secret-token"))
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(lambda: (server.shutdown(), server.server_close(), thread.join(timeout=3)))
        conn = HTTPConnection("127.0.0.1", server.server_port, timeout=3)
        self.addCleanup(conn.close)
        conn.request("GET", "/v1/capabilities")
        response = conn.getresponse()
        self.assertEqual(response.status, 401)
        response.read()
        conn.request("GET", "/v1/capabilities", headers={"Authorization": "Bearer test-secret-token"})
        response = conn.getresponse()
        self.assertEqual(response.status, 200)
        response.read()


if __name__ == "__main__":
    unittest.main(verbosity=2)
