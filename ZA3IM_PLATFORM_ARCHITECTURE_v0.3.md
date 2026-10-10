# Za3im Platform Architecture v0.3 — implementation-grounded

Date: 2026-10-10  
Status: A local vertical slice is implemented and tested with a fake provider. Live GPT requests are disabled by a fail-closed runtime gate until the finished product is accepted. No real OpenAI request has been run. This is not production-ready.

## Product objective

Za3im is intended to be a conversational production platform for Algeria: turn user intent into completed, inspectable deliverables; combine prepared local context, model providers, tools and agents; and eventually package experiences for reuse. The current implementation proves only the initial website-draft and promotional-copy workflow.

## Implemented path

HTTP request -> request schema and business-profile validation -> capability, egress, data-classification and budget gates -> SQLite execution claim and idempotency fingerprint -> concrete OpenAI Responses API client (live call NOT RUN) -> generated JSON validation -> escaped static website draft and promotional Markdown -> structure checks and SHA-256 hashes -> persisted usage/verification events -> artifact download with hash recheck and CSP.

## Boundaries

- api.py: local HTTP transport, body bounds, optional shared token, routes and artifact response headers.
- service.py: request/profile validation, capability admission, data/egress/budget checks, execution, artifact generation and response validation.
- provider.py: one concrete OpenAI Responses API client. Do not abstract it until a second real provider/target demonstrates a shared contract.
- store.py: SQLite execution, idempotency, event and artifact ledger; transactional claim; unique tenant/idempotency key; startup recovery does not auto-replay interrupted provider work.
- schemas/: versioned request, result and business-profile schemas.
- examples/engine-registry.yaml: reference-only candidate inventory; it is not loaded by the runtime.
- examples/experience-manifest.yaml: design example only; runtime does not yet install/export/import experience packages.

## Runtime invariants

1. Request and nested business profile must validate before provider access.
2. The supported workflow requires website.generate-draft and marketing.copy.generate.
3. Request policy must explicitly allow provider.openai.responses, artifact.write, and the api.openai.com domain.
4. Restricted data is rejected for hosted-model egress.
5. Same tenant + idempotency key + same body replays a stored run; same key with a different canonical body returns 409.
6. Concurrent same-key requests are tested within one process; this does not establish distributed locking.
7. Cost checks use configured rates and conservative bounds. Rates are estimates, not invoice-level guarantees.
8. Expected model output has exactly six fields; malformed output fails rather than creating artifacts.
9. Generated text is HTML escaped. Output remains an unpublished local draft.
10. Artifact metadata records SHA-256; hashes are recalculated before download.
11. No deployment, video, advertising account, messaging, payment, or other external side effect is performed.
12. Unknown capability candidates do not become integrated just because they are listed in a registry file.

## HTTP surface

| Method | Path | Current behavior |
|---|---|---|
| GET | /healthz | Local process health and provider-key configured boolean |
| GET | /v1/capabilities | Runtime-backed status list |
| POST | /v1/executions | Validates and executes the first draft workflow |
| GET | /v1/executions/{id} | Retrieves persisted execution state |
| GET | /v1/artifacts/{id} | Rechecks hash then returns artifact, with HTML CSP |

Default bind is loopback. A non-loopback bind requires ZA3IM_API_TOKEN; the shared token does not establish tenant identity or tenant-scoped authorization. Public deployment is prohibited until that is replaced.

## Provider pricing and evidence

The provider calls POST https://api.openai.com/v1/responses with OPENAI_API_KEY held server-side. The default model is gpt-6-luna. The official [model page](https://developers.openai.com/api/docs/models/gpt-6-luna) lists the Responses endpoint and standard prices of $0.10 input / $0.50 output per million text tokens, checked 2026-10-10. The local rate estimator is configurable and incomplete; actual cost remains null without invoice reconciliation. A mocked HTTP response proves client parsing only, not live-provider connectivity or model access.

## Existing project reuse audit

- m0-durable-run/main contains a tested SQLite Run/envelope core. HTTP idempotency exists on feature/m0-1-http-agent-api; its current main agent executor is a stub, and real provider execution is not established. Za3im has not integrated M0 and currently duplicates some local durable-run behavior. Resolve this explicitly before either store is treated as canonical.
- Software-res includes evidence validation and CI patterns; Za3im does not call its validator yet.
- Llms-mcp-android includes capability executor, approval and durable effect work for its native Android runtime; it is not a server runtime dependency here.
- Opportunity-Packs documents that the Opscotch official runtime gate is closed; its packs are not active Za3im capabilities.

## Candidate engines (not integrated)

DeerFlow, Agent Zero, OpenManus, OpenHands, Browser Use and Skyvern remain disabled candidates. Their licenses, pinned commits, runtime compatibility, threat surfaces and distinct value must be reviewed. Overlapping engines should not run together by default. Add an adapter only after passing shared request/result contracts, sandbox, policy, cancellation, error/recovery, cost-accounting and conformance tests.

## Not implemented

Prepared Algerian context/data connectors; real browser/agent integrations; video generation; deploy/publish connectors; advertising/social-account integration; customer messages; actual customer credit billing; CIB/Edahabia/BaridiMob/bank payment flows; experience package signing/export/import/migration; MCP/A2A integration; trusted identity/tenant authorization; distributed execution; production monitoring, deletion and retention policy; external-effect reconciliation.

## Release gates

- Run CI against the exact revision.
- Keep live GPT requests disabled during product development. Only after the complete product passes its functional, security, data-governance, cost-control and rollback acceptance gates may a dedicated finished-product validation environment enable ZA3IM_ENABLE_LIVE_GPT and run an explicitly authorized low-budget smoke test. Capture redacted evidence and provider usage.
- Integrate one real, source-backed Algerian context path and test freshness/provenance.
- Decide whether to integrate M0 or replace the duplicate store; document migration and restart/replay tests.
- Add one real external connector only after scoped credentials, approval, idempotency/reconciliation and rollback checks.
- Implement tenant identity and artifact authorization before any untrusted multi-user deployment.
- Only mark a capability integrated after executable code, tests and a recorded conformance result.

No statement in this document is a production-readiness claim.
