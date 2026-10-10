# Za3im source foundation v0.1

Date: 2026-10-10  
Status: executable source and tests pass on revision `b6bb2eb58ac257b4f7c5e691d934544c8cec7c37` (CI run [#51](https://github.com/Loofy147/Za3im/actions/runs/38074819325)); merge is pending final PR-head and post-merge CI. Do not start context or dataset ingestion until the merged main revision passes CI.

## Objective

Stabilize the execution substrate before connecting Algerian law, wilaya, pricing, documents, service or other datasets. Context connectors must be consumers of stable configuration, contracts, capability policy, provider/persistence ports and evidence behavior; they must not establish those foundations independently.

## Source boundaries

```text
HTTP/API composition root
  ├── RuntimeConfig (validated settings)
  ├── OpenAIResponsesClient ── CopyProviderPort
  ├── ExecutionStore ───────── ExecutionRepositoryPort
  └── Za3imService
        ├── executable capability registry + workflow composition
        ├── request/profile/result JSON schemas
        ├── provider port
        └── repository port
```

- `config.py`: immutable configuration object; environment is parsed once before server startup. Invalid booleans/numbers/ranges and unsafe bind settings fail closed. Key/token fields are excluded from object representation.
- `capabilities.py`: executable registry and explicit workflow requirements. Example YAML is not loaded as executable policy.
- `ports.py`: shared contracts for structured-copy providers and execution repositories; common idempotency-conflict exception.
- `provider.py`: current OpenAI Responses adapter. Its live request gate defaults to false.
- `store.py`: current SQLite adapter for execution claims, idempotency, events and artifact metadata. It is single-instance, not a distributed queue.
- `service.py`: validation, policy admission, orchestration, output verification and artifact creation; it depends on the ports instead of importing the concrete store/provider implementation.
- `api.py`: composition root; passes validated settings to runtime components and supplies the HTTP body-size limit.
- `schemas/`: versioned external request, business profile and execution result contracts.
- `tests/`: runtime regression, configuration, registry, adapter-port and schema-fixture tests.

## Required invariants

1. Defaults bind the HTTP service to loopback; live GPT remains disabled.
2. Environment values are parsed and validated before the server starts; no per-module environment reads may silently override validated settings.
3. Secrets are not printed or included in configuration representations.
4. A workflow declares its required capabilities separately from the wider registry. Adding a capability cannot silently change existing workflow composition.
5. A capability becomes executable only when implemented, registered, authorized by the request and connected to a tested runtime path.
6. Provider input is minimized to copy-relevant business fields. Contact and reference-only fields stay local.
7. Same-key, same-body retries replay recorded state; key/body conflicts fail. Interrupted provider work is not automatically replayed.
8. Examples are synthetic fixtures. JSON schemas and committed request/result fixtures must be checked by CI.
9. No context source, dataset, agent engine, payment provider or publication connector is promoted based only on documentation or a manifest.
10. Live-provider evidence is deferred until the complete product passes acceptance. A fake or mocked provider is not live evidence.

## Current hard limits

- Tenant identity is not authenticated: request `tenant_id` remains untrusted metadata. The shared bearer token is not production tenant authorization.
- No distributed coordination, replicated persistence, durable external-effect reconciliation or exactly-once external effects.
- Protocol shape is runtime-tested; a whole-project static type checker is not yet a CI gate.
- Schema compatibility/migration policy, schema evolution tests and API contract versioning policy are incomplete.
- Production secrets manager, TLS termination, rate limits, monitoring, deletion/retention and operations/rollback remain incomplete.

## Foundation acceptance gate before context/data work

- [x] Executable/test revision `b6bb2eb58ac257b4f7c5e691d934544c8cec7c37` passes full CI run [#51](https://github.com/Loofy147/Za3im/actions/runs/38074819325); the final PR-head and post-merge main revisions still require their own CI runs.
- [x] Runtime configuration reaches server, provider, service and request-body limit through an integration test.
- [x] Capability registry invariants and workflow composition pass tests.
- [x] OpenAI provider and SQLite store satisfy the shared port contracts.
- [x] All JSON schemas validate as Draft 2020-12 schemas; committed synthetic request/result examples validate against them.
- [x] Live GPT remains off; no external calls are required in CI.
- [x] Implementation ledger records the exact tested source revision, test count, wheel inspection and resolved failures.

After the gate passes, the next stage is an inventory-first context/data architecture: dataset catalog, source/license/freshness/provenance records, typed connector contracts, retrieval contract, cache policy and evidence-bearing query results. Do not ingest datasets before this gate is closed.
