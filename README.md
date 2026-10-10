# Za3im

Za3im is intended to become an Algerian-market AI execution platform. Users describe outcomes; Za3im combines local context, model capabilities, tools and reusable experiences to produce verifiable deliverables.

## What actually runs in this revision

A narrow local vertical slice accepts a validated Algerian business profile, calls the OpenAI Responses API to produce structured draft copy, renders an unpublished HTML website and a promotional-copy Markdown artifact, stores execution/events/artifact metadata in SQLite, and serves artifacts with SHA-256 rechecking.

Not implemented: Algerian knowledge connectors, agent-framework adapters, website deployment, video generation, advertising integrations, payments/credits, portable experience export/import, production tenant authentication, distributed execution, and live-provider verification.

## Run locally

Requirements: Python 3.11+.

    python -m venv .venv
    . .venv/bin/activate
    pip install -e .
    export OPENAI_API_KEY='YOUR_API_KEY'
    export ZA3IM_OPENAI_MODEL='gpt-6-luna'
    python -m za3im_runtime.api

A live request can incur OpenAI charges. Never commit API keys. Tests use a deterministic fake provider and do not make external API calls.

The server defaults to 127.0.0.1:8080, stores SQLite state in za3im_state.sqlite3, and artifacts in za3im_artifacts/. A non-loopback bind is refused unless ZA3IM_API_TOKEN is set. This shared bearer token is not production multi-tenant authentication; do not expose this MVP directly to the public internet.

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| ZA3IM_API_HOST | 127.0.0.1 | Bind address |
| ZA3IM_API_PORT | 8080 | HTTP port |
| ZA3IM_API_TOKEN | empty | Optional shared bearer token |
| ZA3IM_DB_PATH | za3im_state.sqlite3 | SQLite ledger |
| ZA3IM_ARTIFACT_DIR | za3im_artifacts | Local artifact directory |
| OPENAI_API_KEY | empty | Required for a real provider request |
| ZA3IM_OPENAI_MODEL | gpt-6-luna | OpenAI Responses API model |
| ZA3IM_MAX_OUTPUT_TOKENS | 1200 | Generation bound |
| ZA3IM_OPENAI_INPUT_USD_PER_MILLION | 0.10 | Configured estimate rate |
| ZA3IM_OPENAI_OUTPUT_USD_PER_MILLION | 0.50 | Configured estimate rate |

The default input/output rates match the GPT-6 Luna standard text-token rates shown on the [official model page](https://developers.openai.com/api/docs/models/gpt-6-luna), checked 2026-10-10. The estimator does not cover every token class, cached-input mode, optional tool charge, discount or invoice reconciliation. Rates must be rechecked when changing model or processing mode. Cost is an estimate, not a guaranteed bill cap.

## HTTP API

- GET /healthz — process status and a boolean indicating whether a provider key is configured.
- GET /v1/capabilities — actual MVP capabilities and candidates that remain disabled.
- POST /v1/executions — accepts a request validated by the execution JSON Schema.
- GET /v1/executions/{execution_id} — persisted execution status/result.
- GET /v1/artifacts/{artifact_id} — artifact download with integrity recheck.

The first workflow requires website.generate-draft and marketing.copy.generate, explicitly allows provider.openai.responses and artifact.write, requires api.openai.com in the egress allowlist, and blocks restricted data from hosted-model egress.

Example using the synthetic profile request:

    curl -sS http://127.0.0.1:8080/v1/executions \
      -H 'Content-Type: application/json' \
      --data-binary @examples/execution-request.example.json

When a token is configured, send Authorization: Bearer $ZA3IM_API_TOKEN on protected routes. A successful response returns HTML and Markdown artifact IDs. Exact idempotent retries replay stored results; the same tenant/key with a different request returns 409. A process restart marks leftover running tasks interrupted rather than blindly repeating provider work.

## Run checks

    python -m unittest discover -s tests -v
    python -m compileall -q za3im_runtime tests

The tests use mocked provider HTTP and a fake provider while exercising the local HTTP server and SQLite implementation. They do not prove a live OpenAI request, deployment, customer billing, production security, or distributed execution. GitHub Actions runs these deterministic checks on pushes and pull requests.

## Evidence and implementation status

- [Implementation evidence ledger](IMPLEMENTATION_STATUS.md)
- [Implementation policy: checked means implemented and evidenced](docs/IMPLEMENTATION_POLICY.md)
- [Implementation-grounded architecture](ZA3IM_PLATFORM_ARCHITECTURE_v0.3.md)
- [Example/evidence labels](examples/README.md)

The v0.2 document is retained as historical target architecture. Use v0.3 and the evidence ledger for current behavior.
