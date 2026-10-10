# Za3im

Za3im is intended to become an Algerian-market AI execution platform. Users describe outcomes; Za3im combines local context, model capabilities, tools and reusable experiences to produce verifiable deliverables.

## What actually runs in this revision

A narrow local vertical slice validates an Algerian business profile, has a concrete OpenAI Responses API client behind a fail-closed live-request gate, and renders unpublished HTML and promotional-copy drafts through the tested service path. Contact buttons are emitted only for explicitly preferred channels; phone numbers are normalized before link creation, email is validated, social links require HTTPS, public text is HTML-escaped, and unsafe anchor schemes fail verification. SQLite stores execution/event/artifact metadata and artifact downloads recheck SHA-256. Deterministic tests use a fake provider; live GPT remains disabled.

Not implemented: Algerian knowledge connectors, agent-framework adapters, website deployment, video generation, advertising integrations, payments/credits, portable experience export/import, production tenant authentication, distributed execution, and live-provider verification.

## Run locally

Requirements: Python 3.11+.

    python -m venv .venv
    . .venv/bin/activate
    pip install -e .
    python -m za3im_runtime.api

Live GPT requests are disabled by default and are deliberately deferred until the finished product passes its acceptance gates. Starting the local server does not require an API key; draft execution returns LIVE_GPT_DISABLED (503) without making a provider request. Tests use a deterministic fake provider and mocked HTTP responses only. Never commit API keys.

The server defaults to 127.0.0.1:8080, stores SQLite state in za3im_state.sqlite3, and artifacts in za3im_artifacts/. A non-loopback bind is refused unless ZA3IM_API_TOKEN is set. This shared bearer token is not production multi-tenant authentication; do not expose this MVP directly to the public internet.

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| ZA3IM_API_HOST | 127.0.0.1 | Bind address |
| ZA3IM_API_PORT | 8080 | HTTP port |
| ZA3IM_API_TOKEN | empty | Optional shared bearer token |
| ZA3IM_DB_PATH | za3im_state.sqlite3 | SQLite ledger |
| ZA3IM_ARTIFACT_DIR | za3im_artifacts | Local artifact directory |
| OPENAI_API_KEY | empty | Required only at finished-product live-validation time |
| ZA3IM_ENABLE_LIVE_GPT | false | Safety gate; leave false during development and testing |
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

The first workflow requires website.generate-draft, marketing.copy.generate and website.contact-channels.render, explicitly allows provider.openai.responses and artifact.write, requires api.openai.com in the egress allowlist, and blocks restricted data from hosted-model egress.

Example using the synthetic profile request:

    curl -sS http://127.0.0.1:8080/v1/executions \
      -H 'Content-Type: application/json' \
      --data-binary @examples/execution-request.example.json

When a token is configured, send Authorization: Bearer $ZA3IM_API_TOKEN on protected routes. A successful response returns HTML and Markdown artifact IDs. Exact idempotent retries replay stored results; the same tenant/key with a different request returns 409. A process restart marks leftover running tasks interrupted rather than blindly repeating provider work.

## Run checks

    python -m unittest discover -s tests -v
    python -m compileall -q za3im_runtime tests

The tests use mocked provider HTTP and a fake provider while exercising opt-in contact rendering, link-scheme rejection, the local HTTP server and SQLite implementation. Live GPT is deliberately disabled by default in the runtime and is not required for intermediate development. Only after the finished-product acceptance checklist is met should the dedicated live-validation environment set ZA3IM_ENABLE_LIVE_GPT=true and provide OPENAI_API_KEY. The tests do not prove a live OpenAI request, deployment, customer billing, production security, or distributed execution. GitHub Actions runs deterministic checks on pushes and pull requests.

## Evidence and implementation status

- [Implementation evidence ledger](IMPLEMENTATION_STATUS.md)
- [Implementation policy: checked means implemented and evidenced](docs/IMPLEMENTATION_POLICY.md)
- [Implementation-grounded architecture](ZA3IM_PLATFORM_ARCHITECTURE_v0.3.md)
- [Example/evidence labels](examples/README.md)

The v0.2 document is retained as historical target architecture. Use v0.3 and the evidence ledger for current behavior.
