# Za3im implementation status and evidence ledger

Revision: source foundation v0.1, 2026-10-10. The status here refers to code and deterministic CI evidence; the real provider call has not run.

## Verdict

NOT PRODUCTION READY. The narrow business-presence draft workflow is implemented and tested locally with a deterministic fake provider. A concrete OpenAI Responses API client is implemented but not live-verified. No other candidate agent is integrated. No customer payment or credit charging works yet.

## Implemented and locally tested

| Item | Status | Evidence |
|---|---|---|
| Request schema validation | UNIT_TESTED | Rejects malformed requests before claim/provider access |
| Business profile schema validation | UNIT_TESTED | Invalid profile rejected before provider call |
| Runtime configuration | UNIT_TESTED | Eight configuration tests cover defaults, parsing, malformed values, safe bind policy and cost/token/time limits; runtime-wiring integration test proves validated settings reach HTTP, provider and service boundaries |
| Executable capability registry | UNIT_TESTED | Four tests validate metadata, IDs, separation of disabled candidates and stable business-presence workflow requirements |
| Provider/repository ports | UNIT_TESTED | Four runtime-conformance tests confirm OpenAI client, synthetic provider and SQLite adapter satisfy shared Protocol contracts; idempotency conflict is one shared type |
| Schema/example conformance | UNIT_TESTED | Four tests validate each Draft 2020-12 schema plus synthetic request, nested business profile and result fixtures |
| Built wheel contents | CI_VERIFIED | CI builds za3im-runtime and inspects the wheel for configuration, registry, ports, provider, service, store and all three schemas |
| OpenAI Responses client | UNIT_TESTED / LIVE_NOT_RUN | Mocked transport validates endpoint, JSON mode, output parsing, request ID and token usage |
| Website draft generation | UNIT_TESTED | Static HTML generated from validated model copy; Arabic RTL support; HTML text escaping |
| Contact-channel renderer | UNIT_TESTED | Registered `website.contact-channels.render`; preference-gated phone/WhatsApp/email/social links, escaped public address, unsafe-scheme rejection, malformed-number rejection, and explicit provider-input allowlist excluding contact/reference fields; six feature regressions passed in CI run [#24](https://github.com/Loofy147/Za3im/actions/runs/38064114962) on source revision `2fc14cac3adc5f4783cada2e372d8cf04710f01a` |
| Promotional-copy artifact | UNIT_TESTED | Markdown draft produced alongside the HTML |
| SQLite execution/event/artifact ledger | UNIT_TESTED | Transactional idempotency claim, durable rows and event references |
| Idempotency | UNIT_TESTED | Exact retry replays result; same key with modified request gets 409 |
| Same-process concurrency | UNIT_TESTED | Concurrent same-key calls invoke fake provider once |
| Restart recovery | UNIT_TESTED | Stale running record becomes interrupted and is not blindly replayed |
| Budget preflight | UNIT_TESTED | Configured upper-bound estimate can block a provider request |
| Artifact integrity | UNIT_TESTED | SHA-256 is recorded and rechecked when artifact is downloaded |
| Optional bearer token | UNIT_TESTED | Unauthorized protected call receives 401 when token is configured |
| Local HTTP flow | UNIT_TESTED | Test starts a real local HTTP server and calls health, execute and artifact routes |
| Event/evidence references | UNIT_TESTED | Returned event references point to persisted events |
| Wheel contents | LOCALLY_VERIFIED | Local wheel built with pip wheel --no-deps --no-build-isolation; runtime modules and schemas included |
| CI workflow | PASS | GitHub Actions run [#47](https://github.com/Loofy147/Za3im/actions/runs/38074690875) passed compile, 44 deterministic tests and built-wheel content checks on executable/test revision `549eb2d7a6a1afc52cf72c53d6bafd60c2935928` and CI configuration revision `96e15c9f73bafa8e0b8a5d22999463766a6c93f2` |

Local test command: python -m unittest discover -s tests -v  
GitHub Actions run [#47](https://github.com/Loofy147/Za3im/actions/runs/38074690875) passed on the source-foundation change: compile succeeded, all 44 deterministic tests passed in 1.525 seconds, and a built wheel was verified to contain the runtime modules and all three JSON Schemas. The code/test revision used in that run was `549eb2d7a6a1afc52cf72c53d6bafd60c2935928`; the added wheel inspection step was at `96e15c9f73bafa8e0b8a5d22999463766a6c93f2`. Subsequent changes through `71daa455b3a483402aba5503e947480c8a301554` were documentation-only. Live GPT remained disabled and no provider request was sent.

## Foundation iteration: failures and corrections

- CI run [#29](https://github.com/Loofy147/Za3im/actions/runs/38074240586) was the intentional RED run for configuration tests before config.py existed.
- CI run [#32](https://github.com/Loofy147/Za3im/actions/runs/38074324050) exposed 11 runtime failures after the refactor removed os although atomic artifact writes still use it. Restoring the import at 854dca715314e3aa905b3137371c6c682d36ff7f returned the suite to green in run [#33](https://github.com/Loofy147/Za3im/actions/runs/38074386398).
- Registry test runs [#34–#37](https://github.com/Loofy147/Za3im/actions/runs/38074420259) exposed an over-restrictive test regex for the valid registry version za3im.capabilities/0.2; the test was corrected and run [#38](https://github.com/Loofy147/Za3im/actions/runs/38074481337) passed.
- Port conformance runs [#40–#41](https://github.com/Loofy147/Za3im/actions/runs/38074537267) failed while the shared idempotency exception was not yet migrated into the port module; the store and service were then wired to the shared contract and run [#42](https://github.com/Loofy147/Za3im/actions/runs/38074565167) passed.

These failures are retained as history, not counted as successful verification. Current feature status uses passing evidence only.

## OpenAI integration status

The client is wired to POST https://api.openai.com/v1/responses, OPENAI_API_KEY, and configurable ZA3IM_OPENAI_MODEL (default gpt-6-luna). Live requests are disabled by default through ZA3IM_ENABLE_LIVE_GPT=false. The service returns LIVE_GPT_DISABLED before claiming an execution or touching the network.

- Implemented: executable client and error mapping; explicit ZA3IM_ENABLE_LIVE_GPT fail-closed gate (default false).
- Tested: mocked HTTP response/contract; with live GPT disabled and a configured test key, the injected transport is not called; the service rejects the request before creating an execution record.
- Not established: real API key/model entitlement, a successful live call, actual latency, output quality, current account-specific rate, and invoice reconciliation.
- No secret was supplied or written to this repository; no billable live request was made, and no live request is expected before the finished product passes acceptance.
- Future finished-product validation only: set ZA3IM_ENABLE_LIVE_GPT=true in a controlled environment with an explicitly authorized key after all release gates pass.

## Accounting

Input/output rates default to GPT-6 Luna standard text-token rates as checked on the [official model page](https://developers.openai.com/api/docs/models/gpt-6-luna) on 2026-10-10: $0.10 input / $0.50 output per million tokens. They are configurable assumptions. The estimate omits some possible billing nuances and is not a guaranteed spend cap. actual_provider_cost_usd remains null; customer credits are not charged. Credit ledger, refunds and payment integrations are not implemented.

## Not implemented / disabled

| Capability | Status | Evidence required before promotion |
|---|---|---|
| Live OpenAI smoke test | DEFERRED_UNTIL_FINISHED_PRODUCT | Do not run during development. Only after finished-product acceptance: an explicitly authorized low-budget request, redacted response ID, model ID, returned usage and failure behavior |
| Prepared Algerian knowledge connectors | NOT_INTEGRATED | Inventory source, date, coverage, rights and API; test a real query and provenance/freshness |
| DeerFlow / Agent Zero / OpenManus / OpenHands | CANDIDATE_DISABLED | Pinned revision, license/security review, adapter and contract/conformance tests |
| Browser Use / Skyvern | CANDIDATE_DISABLED | Same as above plus isolated session, domain control and side-effect validation; Skyvern needs AGPL legal review |
| Website deployment | NOT_IMPLEMENTED | Real connector, scoped auth, approval, post-deploy smoke test and rollback |
| Video generation | NOT_IMPLEMENTED | Real generation path, artifact storage, format/content tests and usage accounting |
| Ads/social accounts | NOT_IMPLEMENTED | OAuth, scoped permissions, preview and human approval, budget cap and real sandbox tests |
| Portable experience install/export | EXAMPLE_ONLY | Runtime package parser, integrity/signature policy, dependency resolution, migration and cross-runtime tests |
| MCP/A2A | NOT_INTEGRATED | Authenticated transport and capability-level authorization tests |
| Tenant authentication/authorization | NOT_PRODUCTION_READY | Trusted principal maps to tenant; cross-tenant object access tests; revocation |
| Credit charging/payments | NOT_IMPLEMENTED | Append-only credit ledger, idempotent payment events, reconciliation/refund tests and current local provider arrangements |
| Distributed orchestration | NOT_IMPLEMENTED | Durable queue/coordination, multi-process tests and safe crash recovery |
| m0-durable-run integration | NOT_INTEGRATED | Choose stable revision; preserve one authoritative run ledger; end-to-end integration test |
| Software-res validation integration | NOT_INTEGRATED | Concrete invocation plus adversarial fixtures and evidence retention |
| Production deployment/security | NOT_READY | Threat model, tenant isolation, secrets, egress, load, monitoring, rollback, retention and operational runbook |

## Security and operating limits

Use this build on localhost or a trusted private network only. The optional bearer token is shared-secret protection, not identity or tenant isolation. Request tenant_id is untrusted request data until the platform derives it from a verified principal. Artifact authorization needs tenant-scoped checks before public multi-user exposure.

Only local draft artifacts are produced; no publication, advertising, customer messaging or payments occur. Artifact/event files are durable on the local machine but are not tamper-proof or replicated.

## Promotion rules

Do not set LIVE_VERIFIED without a real provider or connector execution and retrievable evidence. Do not set PRODUCTION_READY before production identity, tenant isolation, secret management, spending controls, CI evidence on the release commit, data governance, licensing/supply-chain review, rollback and operational monitoring pass explicit tests.
