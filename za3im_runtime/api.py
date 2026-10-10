"""HTTP API for the first tested Za3im execution vertical slice."""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

from .provider import OpenAIResponsesClient
from .service import Za3imService
from .store import ExecutionStore

MAX_BODY_BYTES = int(os.getenv("ZA3IM_API_MAX_BODY_BYTES", str(1024 * 1024)))


def make_handler(service: Za3imService, api_token: str = ""):
    class Handler(BaseHTTPRequestHandler):
        server_version = "Za3im/0.1"

        def _send_json(self, status: int, body: dict):
            raw = json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(raw)

        def _authenticated(self) -> bool:
            if not api_token:
                return True
            return hmac.compare_digest(self.headers.get("Authorization", ""), f"Bearer {api_token}")

        def _require_auth(self) -> bool:
            if self._authenticated():
                return True
            self._send_json(401, {"error": {"code": "UNAUTHORIZED", "message": "A valid Bearer token is required"}})
            return False

        def do_GET(self):  # noqa: N802
            path = urlsplit(self.path).path
            if path == "/healthz":
                self._send_json(200, {
                    "status": "ok",
                    "service": "za3im-runtime",
                    "version": "0.1.0",
                    "provider_configured": bool(getattr(service.provider, "api_key", "")),
                })
                return
            if not self._require_auth():
                return
            if path == "/v1/capabilities":
                self._send_json(200, service.capabilities())
                return
            match = re.fullmatch(r"/v1/executions/([^/]+)", path)
            if match:
                record = service.store.get_execution(match.group(1))
                self._send_json(200 if record else 404, service._body(record) if record else {"error": {"code": "NOT_FOUND", "message": "Execution not found"}})
                return
            match = re.fullmatch(r"/v1/artifacts/([A-Za-z0-9_-]+)", path)
            if match:
                artifact = service.store.get_artifact(match.group(1))
                if artifact is None:
                    self._send_json(404, {"error": {"code": "NOT_FOUND", "message": "Artifact not found"}})
                    return
                try:
                    with open(artifact["path"], "rb") as stream:
                        raw = stream.read()
                except OSError:
                    self._send_json(410, {"error": {"code": "ARTIFACT_UNAVAILABLE", "message": "Artifact file is not available"}})
                    return
                if hashlib.sha256(raw).hexdigest() != artifact["sha256"]:
                    self._send_json(500, {"error": {"code": "ARTIFACT_INTEGRITY_FAILURE", "message": "Stored artifact hash did not match its ledger entry"}})
                    return
                self.send_response(200)
                self.send_header("Content-Type", artifact["media_type"])
                self.send_header("Content-Length", str(len(raw)))
                self.send_header("Cache-Control", "private, no-store")
                self.send_header("X-Content-Type-Options", "nosniff")
                if artifact["media_type"].startswith("text/html"):
                    self.send_header("Content-Security-Policy", "default-src 'none'; style-src 'unsafe-inline'; img-src data:; base-uri 'none'; form-action 'none'; frame-ancestors 'none'")
                self.end_headers()
                self.wfile.write(raw)
                return
            self._send_json(404, {"error": {"code": "NOT_FOUND", "message": "Route not found"}})

        def do_POST(self):  # noqa: N802
            if urlsplit(self.path).path != "/v1/executions":
                self._send_json(404, {"error": {"code": "NOT_FOUND", "message": "Route not found"}})
                return
            if not self._require_auth():
                return
            content_type = self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
            if content_type != "application/json":
                self._send_json(415, {"error": {"code": "UNSUPPORTED_MEDIA_TYPE", "message": "Content-Type must be application/json"}})
                return
            try:
                length = int(self.headers.get("Content-Length", "-1"))
            except ValueError:
                self._send_json(400, {"error": {"code": "INVALID_CONTENT_LENGTH", "message": "Content-Length must be an integer"}})
                return
            if length < 0:
                self._send_json(411, {"error": {"code": "LENGTH_REQUIRED", "message": "Content-Length is required"}})
                return
            if length > MAX_BODY_BYTES:
                self._send_json(413, {"error": {"code": "BODY_TOO_LARGE", "message": "Request body exceeds the configured limit"}})
                return
            try:
                request = json.loads(self.rfile.read(length).decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                self._send_json(400, {"error": {"code": "INVALID_JSON", "message": "Request body must be UTF-8 JSON"}})
                return
            status, response = service.execute_request(request)
            self._send_json(status, response)

        def log_message(self, fmt, *args):
            print("[za3im-http] " + (fmt % args))

    return Handler


def serve() -> None:
    host = os.getenv("ZA3IM_API_HOST", "127.0.0.1")
    port = int(os.getenv("ZA3IM_API_PORT", "8080"))
    api_token = os.getenv("ZA3IM_API_TOKEN", "").strip()
    if host not in {"127.0.0.1", "localhost", "::1"} and not api_token:
        raise SystemExit("Refusing non-loopback bind without ZA3IM_API_TOKEN; this runtime is not a production multi-tenant service.")
    store = ExecutionStore(os.getenv("ZA3IM_DB_PATH", "za3im_state.sqlite3"), os.getenv("ZA3IM_ARTIFACT_DIR", "za3im_artifacts"))
    provider = OpenAIResponsesClient()
    service = Za3imService(store, provider)
    server = ThreadingHTTPServer((host, port), make_handler(service, api_token))
    print(f"Za3im runtime listening at http://{host}:{port}; model={provider.model}; provider_configured={bool(provider.api_key)}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    serve()
