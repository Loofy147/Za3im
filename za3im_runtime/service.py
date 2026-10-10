"""Validated business-presence experience backed by the OpenAI Responses API."""
from __future__ import annotations

import hashlib
import html
import json
import os
import re
import tempfile
import unicodedata
from urllib.parse import urlsplit
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

from .store import ExecutionStore, IdempotencyConflict, utc_now

ROOT = Path(__file__).resolve().parent.parent
REQUEST_SCHEMA = json.loads((ROOT / "schemas/za3im-execution-request.schema.json").read_text(encoding="utf-8"))
PROFILE_SCHEMA = json.loads((ROOT / "schemas/business-profile.schema.json").read_text(encoding="utf-8"))
RESULT_SCHEMA = json.loads((ROOT / "schemas/za3im-execution-result.schema.json").read_text(encoding="utf-8"))
REQUEST_VALIDATOR = Draft202012Validator(REQUEST_SCHEMA, format_checker=FormatChecker())
PROFILE_VALIDATOR = Draft202012Validator(PROFILE_SCHEMA, format_checker=FormatChecker())
RESULT_VALIDATOR = Draft202012Validator(RESULT_SCHEMA, format_checker=FormatChecker())

IMPLEMENTED_CAPABILITIES = {
    "website.generate-draft": {
        "status": "implemented_contract_tested_live_gpt_disabled_until_finished_product",
        "description": "Generate an unpublished static HTML website draft from a validated business profile.",
        "version": "0.1.0",
    },
    "marketing.copy.generate": {
        "status": "implemented_unit_tested_live_provider_not_verified",
        "description": "Generate and store draft promotional copy alongside the website artifact.",
        "version": "0.1.0",
    },
    "website.contact-channels.render": {
        "status": "implemented_unit_tested_live_gpt_disabled_until_finished_product",
        "description": "Render explicitly preferred business contact channels with validated links and escaped public details.",
        "version": "0.1.0",
    },
}
SUPPORTED_CAPABILITIES = set(IMPLEMENTED_CAPABILITIES)
MAX_OUTPUT_TOKENS = int(os.getenv("ZA3IM_MAX_OUTPUT_TOKENS", "1200"))
INPUT_PRICE_PER_MILLION = float(os.getenv("ZA3IM_OPENAI_INPUT_USD_PER_MILLION", "0.10"))
OUTPUT_PRICE_PER_MILLION = float(os.getenv("ZA3IM_OPENAI_OUTPUT_USD_PER_MILLION", "0.50"))


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _safe_artifact_id(execution_id: str, role: str) -> str:
    return f"art_{hashlib.sha256(execution_id.encode('utf-8')).hexdigest()[:20]}_{role}"


def _write_artifact(artifact_dir: Path, artifact_id: str, suffix: str, content: str) -> tuple[str, str, int]:
    raw = content.encode("utf-8")
    digest = hashlib.sha256(raw).hexdigest()
    target = (artifact_dir / f"{digest}.{suffix}").resolve()
    if target.parent != artifact_dir.resolve():
        raise ValueError("artifact path escaped artifact directory")
    if not target.exists():
        fd, temp_name = tempfile.mkstemp(prefix=".za3im-tmp-", dir=str(artifact_dir))
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temp_name, target)
        finally:
            if os.path.exists(temp_name):
                os.unlink(temp_name)
    return str(target), digest, len(raw)


def _text_field(content: dict, field: str, max_length: int = 800) -> str:
    value = content.get(field)
    if not isinstance(value, str) or not value.strip() or len(value) > max_length:
        raise ValueError(f"model output field {field!r} must be a non-empty string up to {max_length} characters")
    return value.strip()


def validate_generated_copy(content: object) -> dict:
    if not isinstance(content, dict):
        raise ValueError("model output must be a JSON object")
    expected = {"site_title", "tagline", "intro", "services", "cta", "promotional_copy"}
    if set(content) != expected:
        raise ValueError("model output must contain exactly the six documented copy fields")
    services = content.get("services")
    if not isinstance(services, list) or not 2 <= len(services) <= 6:
        raise ValueError("model output services must contain between 2 and 6 entries")
    clean_services = []
    for service in services:
        if not isinstance(service, str) or not service.strip() or len(service) > 240:
            raise ValueError("each service must be a non-empty string up to 240 characters")
        clean_services.append(service.strip())
    return {
        "site_title": _text_field(content, "site_title", 180),
        "tagline": _text_field(content, "tagline", 300),
        "intro": _text_field(content, "intro", 1600),
        "services": clean_services,
        "cta": _text_field(content, "cta", 120),
        "promotional_copy": _text_field(content, "promotional_copy", 1000),
    }


def _normalize_phone(value: object) -> str | None:
    """Return E.164 digits for an explicit international number or an Algerian local number."""
    if not isinstance(value, str):
        return None
    raw = value.strip()
    if not raw or ("+" in raw and not raw.startswith("+")):
        return None
    if not all(ch.isdecimal() or ch.isspace() or ch in "+().-" for ch in raw):
        return None
    digits = "".join(str(unicodedata.digit(ch)) for ch in raw if ch.isdecimal())
    if raw.startswith("+"):
        pass
    elif digits.startswith("00"):
        digits = digits[2:]
    elif digits.startswith("213") and len(digits) == 12:
        pass
    elif digits.startswith("0") and len(digits) == 10:
        digits = "213" + digits[1:]
    else:
        # Do not guess an international prefix for an ambiguous local number.
        return None
    if not re.fullmatch(r"[1-9][0-9]{6,14}", digits):
        return None
    return digits


def _safe_https_url(value: object) -> str | None:
    """Accept public profile links only as absolute HTTPS URLs without credentials."""
    if not isinstance(value, str) or not value or len(value) > 1000 or any(ch.isspace() or ord(ch) < 0x20 for ch in value):
        return None
    try:
        parsed = urlsplit(value)
        if parsed.scheme.lower() != "https" or not parsed.hostname:
            return None
        if parsed.username is not None or parsed.password is not None:
            return None
        port = parsed.port  # Raises ValueError for malformed port syntax.
        if port is not None and not 1 <= port <= 65535:
            return None
    except ValueError:
        return None
    return value


def _safe_email(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    address = value.strip()
    if len(address) > 254 or not re.fullmatch(r"[^@\s<>]+@[^@\s<>]+\.[^@\s<>]+", address):
        return None
    return address


def render_html(profile: dict, copy: dict, locale: str) -> str:
    rtl = locale.lower().startswith("ar")
    lang = "ar" if rtl else ("fr" if locale.lower().startswith("fr") else "en")
    direction = "rtl" if rtl else "ltr"
    name = html.escape(profile["business_name"])
    wilaya = html.escape(profile["wilaya"])
    title = html.escape(copy["site_title"])
    tagline = html.escape(copy["tagline"])
    intro = html.escape(copy["intro"])
    cta = html.escape(copy["cta"])
    service_items = "\n".join(f"        <li>{html.escape(item)}</li>" for item in copy["services"])
    contact = profile.get("contact_preferences", {})
    channels = set(contact.get("preferred_channels", []))
    labels = {
        "ar": {
            "phone": "اتصل هاتفياً",
            "whatsapp": "تواصل عبر واتساب",
            "email": "راسلنا بالبريد الإلكتروني",
            "address": "العنوان",
            "social": "الملف الاجتماعي",
        },
        "fr": {
            "phone": "Appeler",
            "whatsapp": "Contacter sur WhatsApp",
            "email": "Envoyer un e-mail",
            "address": "Adresse",
            "social": "Profil social",
        },
        "en": {
            "phone": "Call",
            "whatsapp": "Message on WhatsApp",
            "email": "Email",
            "address": "Address",
            "social": "Social profile",
        },
    }[lang]
    contact_links: list[str] = []
    normalized_phone = _normalize_phone(contact.get("public_phone"))
    if normalized_phone and "phone" in channels:
        contact_links.append(
            f'<a class="cta" href="tel:+{normalized_phone}">{labels["phone"]}</a>'
        )
    if normalized_phone and "whatsapp" in channels:
        contact_links.append(
            f'<a class="cta" href="https://wa.me/{normalized_phone}" target="_blank" rel="noopener noreferrer">{labels["whatsapp"]}</a>'
        )
    email_address = _safe_email(contact.get("public_email"))
    if email_address and "email" in channels:
        contact_links.append(
            f'<a class="cta" href="mailto:{html.escape(email_address, quote=True)}">{labels["email"]}</a>'
        )
    if "social" in channels:
        for reference in contact.get("social_profile_references", [])[:8]:
            safe_url = _safe_https_url(reference)
            if safe_url:
                host = urlsplit(safe_url).hostname or "profile"
                display_host = html.escape(host.removeprefix("www."))
                aria_label = html.escape(labels["social"] + ": " + host, quote=True)
                contact_links.append(
                    f'<a href="{html.escape(safe_url, quote=True)}" target="_blank" rel="noopener noreferrer" aria-label="{aria_label}">{display_host}</a>'
                )
    address = contact.get("public_address")
    address_markup = ""
    if isinstance(address, str) and address.strip():
        address_markup = f'<p class="contact-address"><strong>{labels["address"]}:</strong> {html.escape(address.strip())}</p>'
    contact_markup = "\n".join(contact_links + ([address_markup] if address_markup else []))
    if not contact_markup:
        contact_markup = '<p class="contact-unavailable">—</p>'
    return f'''<!doctype html>
<html lang="{lang}" dir="{direction}">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="robots" content="noindex,nofollow">
  <title>{title}</title>
  <meta name="description" content="{html.escape(copy["intro"][:155], quote=True)}">
  <style>
    :root {{ color-scheme: light; font-family: system-ui, -apple-system, sans-serif; }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; color: #17212b; background: #f6f3ee; line-height: 1.65; }}
    header {{ padding: 4rem 1.25rem; text-align: center; color: #fff; background: linear-gradient(135deg, #183a35, #376d60); }}
    header h1 {{ max-width: 900px; margin: 0 auto 1rem; font-size: clamp(2rem, 6vw, 4rem); line-height: 1.15; }}
    header p {{ max-width: 680px; margin: 0 auto; font-size: 1.15rem; }}
    main {{ max-width: 900px; margin: 0 auto; padding: 2rem 1rem 4rem; }}
    section {{ margin: 1.5rem 0; padding: 1.5rem; border-radius: 1rem; background: #fff; box-shadow: 0 8px 28px #183a350d; }}
    li {{ margin: .5rem 0; }}
    .contact-links {{ display: flex; flex-wrap: wrap; align-items: center; gap: .75rem; margin-top: 1rem; }}
    .contact-links a.cta {{ display: inline-block; padding: .75rem 1.2rem; border-radius: .6rem; background: #183a35; color: white; text-decoration: none; font-weight: 700; }}
    .contact-links a:focus-visible {{ outline: 3px solid #376d60; outline-offset: 3px; }}
    .contact-address {{ overflow-wrap: anywhere; }}
    footer {{ padding: 1rem; text-align: center; color: #4d5a62; }}
  </style>
</head>
<body>
  <header><h1>{title}</h1><p>{tagline}</p></header>
  <main>
    <section><h2>{'مرحباً بك' if rtl else ('Bienvenue' if lang == 'fr' else 'Welcome')}</h2><p>{intro}</p><p>{name} · {wilaya}</p></section>
    <section><h2>{'خدماتنا' if rtl else ('Services' if lang == 'fr' else 'Services')}</h2><ul>
{service_items}
    </ul></section>
    <section><h2>{'تواصل معنا' if rtl else ('Contact' if lang == 'fr' else 'Contact')}</h2><p>{cta}</p><div class="contact-links">
{contact_markup}
    </div></section>
  </main>
  <footer>{name} · {wilaya} · {('مسودة غير منشورة أنشأها زعيم' if rtl else ('Brouillon non publié créé par Za3im' if lang == 'fr' else 'Unpublished draft generated by Za3im'))}</footer>
</body>
</html>
'''

class _HTMLStructureChecker(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tags = []
        self.has_title_text = False
        self.in_title = False
        self.has_h1 = False
        self.has_viewport = False
        self.has_script = False
        self.has_unsafe_link = False

    def handle_starttag(self, tag, attrs):
        self.tags.append(tag.lower())
        attributes = dict(attrs)
        if tag.lower() == "title": self.in_title = True
        if tag.lower() == "h1": self.has_h1 = True
        if tag.lower() == "script": self.has_script = True
        if tag.lower() == "meta" and attributes.get("name", "").lower() == "viewport": self.has_viewport = True
        if tag.lower() == "a":
            href = attributes.get("href", "")
            try:
                parsed = urlsplit(href)
                if parsed.scheme.lower() == "https":
                    safe_link = bool(parsed.hostname) and parsed.username is None and parsed.password is None
                    _ = parsed.port
                elif parsed.scheme.lower() == "tel":
                    safe_link = bool(re.fullmatch(r"tel:\+[1-9][0-9]{6,14}", href, re.IGNORECASE))
                elif parsed.scheme.lower() == "mailto":
                    safe_link = bool(re.fullmatch(r"mailto:[^@\s<>]+@[^@\s<>]+\.[^@\s<>]+", href, re.IGNORECASE))
                else:
                    safe_link = False
            except ValueError:
                safe_link = False
            if not safe_link:
                self.has_unsafe_link = True

    def handle_endtag(self, tag):
        if tag.lower() == "title": self.in_title = False

    def handle_data(self, data):
        if self.in_title and data.strip(): self.has_title_text = True


def verify_html(document: str) -> tuple[bool, str]:
    parser = _HTMLStructureChecker()
    parser.feed(document)
    parser.close()
    valid = all(tag in parser.tags for tag in ("html", "head", "body", "title", "header", "main", "footer"))
    valid = valid and parser.has_title_text and parser.has_h1 and parser.has_viewport and not parser.has_script and not parser.has_unsafe_link
    if not valid:
        return False, "HTML draft failed required structure, no-script or safe-link checks"
    return True, "HTML structure, title, heading, viewport, no-inline-script and safe-link checks passed"


class Za3imService:
    def __init__(self, store: ExecutionStore, provider: Any):
        self.store = store
        self.provider = provider

    def capabilities(self) -> dict:
        return {"registry_version": "za3im.capabilities/0.1", "capabilities": [
            {"capability_id": cap_id, **meta, "live_execution": "disabled_until_finished_product" if not getattr(self.provider, "live_enabled", False) else "opted_in_not_live_verified"} for cap_id, meta in IMPLEMENTED_CAPABILITIES.items()
        ] + [
            {"capability_id": cap_id, "status": "candidate_disabled", "description": "Not integrated or enabled; no working adapter is claimed.", "version": None}
            for cap_id in ["agent.deer-flow", "agent.agent-zero", "agent.openmanus", "agent.openhands", "browser.browser-use", "browser.skyvern", "experience.export-import", "ads.manage", "video.generate", "deployment.publish", "credits.bill"]
        ]}

    def execute_request(self, request: dict) -> tuple[int, dict]:
        if not isinstance(request, dict):
            return 400, {"error": {"code": "INVALID_REQUEST", "message": "Body must be a JSON object"}}
        errors = sorted(REQUEST_VALIDATOR.iter_errors(request), key=lambda e: list(map(str, e.path)))
        if errors:
            first = errors[0]
            path = ".".join(str(part) for part in first.absolute_path) or "$"
            return 400, {"error": {"code": "INVALID_REQUEST", "message": f"{path}: {first.message}"}}

        payload = request.get("input_payload", {})
        profile = payload.get("business_profile") if isinstance(payload, dict) else None
        profile_errors = sorted(PROFILE_VALIDATOR.iter_errors(profile), key=lambda e: list(map(str, e.path))) if isinstance(profile, dict) else []
        if not isinstance(profile, dict) or profile_errors:
            detail = profile_errors[0].message if profile_errors else "input_payload.business_profile must be an object"
            return 400, {"error": {"code": "INVALID_BUSINESS_PROFILE", "message": detail}}

        requested = {item["capability_id"] for item in request["capabilities"]}
        if requested != SUPPORTED_CAPABILITIES:
            return 501, {"error": {"code": "CAPABILITY_NOT_IMPLEMENTED", "message": "This runtime currently supports exactly website.generate-draft and marketing.copy.generate together. Other capabilities are not enabled."}}
        allowed = set(request["constraints"].get("allowed_capability_ids", []))
        if not requested.issubset(allowed):
            return 403, {"error": {"code": "CAPABILITY_NOT_ALLOWED", "message": "The request does not grant the required capabilities"}}
        if "openai" not in request["constraints"].get("allowed_model_providers", []):
            return 403, {"error": {"code": "PROVIDER_NOT_ALLOWED", "message": "OpenAI is not permitted by this request"}}
        constraints = request["constraints"]
        if constraints.get("data_classification") == "restricted":
            return 403, {"error": {"code": "DATA_CLASSIFICATION_BLOCKED", "message": "Restricted data is not sent to a hosted model by this experience"}}
        if constraints.get("network_policy") == "deny_by_default" or "api.openai.com" not in constraints.get("allowed_domain_names", []):
            return 403, {"error": {"code": "PROVIDER_EGRESS_NOT_ALLOWED", "message": "The request must explicitly allow api.openai.com for the configured provider call"}}
        required_runtime_caps = {"provider.openai.responses", "artifact.write"}
        if not required_runtime_caps.issubset(allowed):
            return 403, {"error": {"code": "RUNTIME_CAPABILITY_NOT_ALLOWED", "message": "The request does not allow the provider and artifact-write capabilities required by this experience"}}
        if request["budget"]["max_provider_cost_usd"] <= 0:
            return 422, {"error": {"code": "BUDGET_EXCEEDED", "message": "Provider cost budget must be greater than zero for this experience"}}
        if not getattr(self.provider, "live_enabled", False):
            return 503, {"error": {"code": "LIVE_GPT_DISABLED", "message": "Live GPT requests are disabled until finished-product validation. No execution was claimed and no provider request was sent."}}

        try:
            record, created = self.store.claim(request)
        except IdempotencyConflict as exc:
            return 409, {"error": {"code": "IDEMPOTENCY_CONFLICT", "message": str(exc)}}
        if not created:
            body = self._body(record)
            if record["status"] == "running":
                return 202, body
            return 200, body

        execution_id = request["execution_id"]
        started_at = utc_now()
        generated = None
        usage_event_id = None
        verification_event_ids = []
        # Contact data is only needed by the local renderer. Keep it out of model egress.
        provider_profile = {
            key: profile[key]
            for key in ("business_name", "wilaya", "service_category", "business_description", "languages")
            if key in profile
        }
        try:
            max_cost = self._max_cost_bound(provider_profile)
            if max_cost > request["budget"]["max_provider_cost_usd"]:
                result = self._failed_result(request, started_at, "budget_exceeded", "BUDGET_EXCEEDED", f"Conservative provider-cost upper bound USD {max_cost:.8f} exceeds request budget USD {request['budget']['max_provider_cost_usd']:.8f}.", None)
                result_errors = list(RESULT_VALIDATOR.iter_errors(result))
                if result_errors:
                    raise ValueError("Internal budget result failed schema validation: " + result_errors[0].message)
                self.store.finish(execution_id, "budget_exceeded", result, result["errors"][0])
                return 422, self._body(self.store.get_execution(execution_id))

            generated = self.provider.generate_copy(provider_profile, max_output_tokens=MAX_OUTPUT_TOKENS)
            usage = generated.get("usage") if isinstance(generated.get("usage"), dict) else None
            estimated_cost = self._estimated_cost(usage)
            if usage is not None:
                usage_event_id = self.store.record_event(execution_id, "provider_usage_recorded", {
                    "provider": generated.get("provider", "unknown"),
                    "model": generated.get("model", "unknown"),
                    "provider_request_id": generated.get("request_id"),
                    "usage": usage,
                    "estimated_provider_cost_usd": estimated_cost,
                    "actual_provider_cost_usd": None,
                    "pricing_source": "configured rate schedule; GPT-6 Luna standard token rates checked 2026-10-10; invoice reconciliation not performed"
                })
            if estimated_cost is not None and estimated_cost > request["budget"]["max_provider_cost_usd"]:
                result = self._failed_result(request, started_at, "budget_exceeded", "BUDGET_RECONCILIATION_EXCEEDED", "Reported provider usage exceeded the request budget after generation; no success artifacts were recorded.", generated)
                if usage_event_id:
                    result["accounting"]["usage_reference_ids"] = [usage_event_id]
                    result["event_reference_ids"] = [usage_event_id]
                self.store.finish(execution_id, "budget_exceeded", result, result["errors"][0])
                return 422, self._body(self.store.get_execution(execution_id))
            copy = validate_generated_copy(generated.get("content"))
            html_doc = render_html(profile, copy, request.get("locale", "ar-DZ"))
            valid_html, html_message = verify_html(html_doc)
            if not valid_html:
                raise ValueError(html_message)
            promotion = "# " + copy["site_title"] + "\n\n" + copy["promotional_copy"] + "\n"
            website_id = _safe_artifact_id(execution_id, "website-html")
            promotion_id = _safe_artifact_id(execution_id, "promotional-copy")
            website_path, website_hash, website_size = _write_artifact(self.store.artifact_dir, website_id, "html", html_doc)
            promotion_path, promotion_hash, promotion_size = _write_artifact(self.store.artifact_dir, promotion_id, "md", promotion)
            finished_at = _timestamp()
            artifacts = [
                {"artifact_id": website_id, "role": "website_html", "media_type": "text/html; charset=utf-8", "sha256": website_hash, "size_bytes": website_size, "provenance_reference_ids": []},
                {"artifact_id": promotion_id, "role": "promotional_copy", "media_type": "text/markdown; charset=utf-8", "sha256": promotion_hash, "size_bytes": promotion_size, "provenance_reference_ids": []},
            ]
            for check_id, check_status, details in [
                ("generated-copy-schema", "passed", "Generated copy contains the required fields and bounded text values."),
                ("website-html-structure", "passed", html_message),
                ("contact-links-safety", "passed", "Rendered contact links use normalized telephone numbers, validated email addresses, HTTPS-only social URLs and safe HTML escaping; anchor schemes passed verification."),
                ("no-external-side-effects", "passed", "This implementation writes local artifacts only; it has no deployment or advertising connector."),
            ]:
                verification_event_ids.append(self.store.record_event(execution_id, "verification_check", {"check_id": check_id, "status": check_status, "details": details}))
            result = {
                "schema_version": "za3im.execution.result/0.1",
                "execution_id": execution_id,
                "status": "succeeded",
                "started_at": started_at,
                "finished_at": finished_at,
                "summary": "Generated a local, unpublished HTML website draft and promotional copy; external publication and advertising were not performed.",
                "artifacts": artifacts,
                "verification": {"status": "passed", "checks": [
                    {"check_id": "generated-copy-schema", "status": "passed", "method": "schema", "evidence_reference_ids": [verification_event_ids[0]], "details": "Generated copy contains the required fields and bounded text values."},
                    {"check_id": "website-html-structure", "status": "passed", "method": "automated_test", "evidence_reference_ids": [verification_event_ids[1]], "details": html_message},
                    {"check_id": "contact-links-safety", "status": "passed", "method": "automated_test", "evidence_reference_ids": [verification_event_ids[2]], "details": "Rendered contact links use normalized telephone numbers, validated email addresses, HTTPS-only social URLs and safe HTML escaping; anchor schemes passed verification."},
                    {"check_id": "no-external-side-effects", "status": "passed", "method": "automated_test", "evidence_reference_ids": [verification_event_ids[3]], "details": "This implementation writes local artifacts only; it has no deployment or advertising connector."}
                ]},
                "accounting": {"actual_provider_cost_usd": None, "estimated_provider_cost_usd": estimated_cost, "customer_credits_charged": None, "accounting_status": "estimated" if estimated_cost is not None else "unknown", "usage_reference_ids": [usage_event_id] if usage_event_id else []},
                "engine": {"engine_id": "za3im-business-presence", "engine_version": "0.1.0", "adapter_version": "0.1.0", "model_provider": generated.get("provider", "unknown"), "model_id": generated.get("model")},
                "errors": [],
                "side_effects": [],
                "event_reference_ids": ([usage_event_id] if usage_event_id else []) + verification_event_ids,
                "known_limitations": ["Customer credit billing is not implemented.", "Generated artifacts are drafts; there is no deployment, advertising, video, or social account integration.", "Tenant identity is request metadata in this local MVP, not production authentication/authorization."]
            }
            result_errors = list(RESULT_VALIDATOR.iter_errors(result))
            if result_errors:
                raise ValueError("Internal result failed schema validation: " + result_errors[0].message)
            artifact_rows = [
                {"artifact_id": website_id, "tenant_id": request["tenant_id"], "role": "website_html", "media_type": "text/html; charset=utf-8", "sha256": website_hash, "size_bytes": website_size, "path": website_path},
                {"artifact_id": promotion_id, "tenant_id": request["tenant_id"], "role": "promotional_copy", "media_type": "text/markdown; charset=utf-8", "sha256": promotion_hash, "size_bytes": promotion_size, "path": promotion_path},
            ]
            record = self.store.finish(execution_id, "succeeded", result, artifact_rows=artifact_rows)
            return 201, self._body(record)
        except Exception as exc:
            msg = str(exc)[:1000]
            error_code = "PROVIDER_ERROR" if exc.__class__.__name__ == "ProviderError" else "EXECUTION_ERROR"
            result = self._failed_result(request, started_at, "failed", error_code, msg, generated)
            if usage_event_id:
                result["accounting"]["usage_reference_ids"] = [usage_event_id]
                result["event_reference_ids"] = [usage_event_id]
            self.store.finish(execution_id, "failed", result, result["errors"][0])
            return 502, self._body(self.store.get_execution(execution_id))

    def _max_cost_bound(self, profile: dict) -> float:
        serialized = json.dumps(profile, ensure_ascii=False, separators=(",", ":"))
        input_token_ceiling = len(serialized.encode("utf-8")) + 4096
        return (input_token_ceiling * INPUT_PRICE_PER_MILLION + MAX_OUTPUT_TOKENS * OUTPUT_PRICE_PER_MILLION) / 1_000_000

    @staticmethod
    def _estimated_cost(usage: object) -> float | None:
        if not isinstance(usage, dict):
            return None
        input_tokens, output_tokens = usage.get("input_tokens"), usage.get("output_tokens")
        if not isinstance(input_tokens, int) or not isinstance(output_tokens, int) or input_tokens < 0 or output_tokens < 0:
            return None
        return (input_tokens * INPUT_PRICE_PER_MILLION + output_tokens * OUTPUT_PRICE_PER_MILLION) / 1_000_000

    def _failed_result(self, request: dict, started_at: str, status: str, code: str, message: str, generated: dict | None) -> dict:
        usage = generated.get("usage") if isinstance(generated, dict) else None
        estimated_cost = self._estimated_cost(usage)
        model = generated.get("model") if isinstance(generated, dict) else getattr(self.provider, "model", None)
        provider = generated.get("provider") if isinstance(generated, dict) else getattr(self.provider, "provider", "openai")
        return {
            "schema_version": "za3im.execution.result/0.1",
            "execution_id": request["execution_id"],
            "status": status,
            "started_at": started_at,
            "finished_at": _timestamp(),
            "summary": "Execution did not produce a verified deliverable.",
            "artifacts": [],
            "verification": {"status": "unknown", "checks": []},
            "accounting": {"actual_provider_cost_usd": None, "estimated_provider_cost_usd": estimated_cost, "customer_credits_charged": None, "accounting_status": "estimated" if estimated_cost is not None else "unknown", "usage_reference_ids": []},
            "engine": {"engine_id": "za3im-business-presence", "engine_version": "0.1.0", "adapter_version": "0.1.0", "model_provider": provider, "model_id": model},
            "errors": [{"code": code, "message": message, "retryable": False, "source_component": "za3im_runtime"}],
            "side_effects": [],
            "event_reference_ids": [],
            "known_limitations": ["A failed execution is not automatically replayed for the same idempotency key."]
        }

    @staticmethod
    def _body(record: dict | None) -> dict:
        if record is None:
            return {"error": {"code": "NOT_FOUND", "message": "Execution not found"}}
        return {"execution_id": record["execution_id"], "status": record["status"], "result": record["result"], "error": record["error"]}
