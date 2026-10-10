# Za3im Platform Architecture

**Version:** 0.2  
**Status:** Proposed architecture; implementation and production behavior are not yet verified  
**Research date:** 10 October 2026

## 1. Decision summary

Za3im is a conversational entry point to an AI execution and experience platform for the Algerian market. A user describes an outcome; Za3im retrieves relevant, governed context, plans the work, invokes suitable model and tool capabilities, creates deliverables, verifies them, and—only with suitable authorization—publishes or operates them. Completed workflows can be packaged as reusable experiences for other users.

The platform must not be designed as a collection of independent agents competing for control. It must be one governed system with replaceable execution engines.

Core decisions:

1. **One control plane owns authoritative state.** Identity, tenants, task state, approvals, permissions, budget, credits, artifacts, experience versions and audit records are owned by Za3im.
2. **Integrate, do not merge.** DeerFlow, Agent Zero, OpenManus, OpenHands, Browser Use, Skyvern and future tools are separate candidates behind adapters.
3. **Make every engine available; do not run every engine on every task.** Route by capability, measured reliability, policy, latency and cost. Parallel execution is opt-in and budgeted.
4. **OpenAI GPT API is the initial model provider, not the platform boundary.** Keep a provider-neutral interface so approved hosted and local models can be added without rewriting workflows.
5. **Success requires evidence.** Worker self-reports are not proof. Validate files, tests, state changes, deployment outcomes, and required invariants.
6. **Experiences are portable assets.** Separate a reusable definition from each tenant's configured instance, data, credentials, external account grants and execution records.
7. **Reuse before replacing or adding infrastructure.** Audit current Za3im code and related repositories before selecting duplicate workflow, gateway, database, storage or evaluation systems.
8. **External side effects fail closed.** Publishing, spending advertising money, sending messages, making purchases and submitting official documents require scoped authorization and appropriate confirmation.

## 2. Product model

Za3im is not merely a chat assistant or a directory of business tools. It is a natural-language way to create, connect, run, and share digital capabilities. The prepared Algerian knowledge base is treated as USER_REPORTED existing project context until an inventory verifies coverage, provenance, freshness, rights and integration status.

An example request—create a website for a barber shop and prepare a launch—may become a dependency plan: discover missing business details; retrieve applicable Algerian context; create the site and assets; test responsiveness and links; generate promotional material; prepare deployment and optional analytics or advertising integrations; request approval for external publication or spending; package the reusable workflow; and present evidence, outstanding actions and actual cost.

This is an illustrative target, not a claim that the current platform can already complete every step.

### Core entities

| Entity | Responsibility |
|---|---|
| Tenant / User | Identity and isolation boundary |
| Project | Persistent work context for a business or objective |
| Task / Plan | Requested outcome, acceptance criteria and dependency graph |
| Execution | One durable attempt with budget, status, idempotency and audit events |
| Capability | Typed, versioned operation with declared permissions |
| Engine | Replaceable implementation of one or more capabilities |
| Artifact | Content-addressed output with provenance and access policy |
| ExperienceDefinition | Versioned shareable package containing behavior, schemas, dependencies, permissions and tests |
| ExperienceInstance | One tenant's configuration and state for a definition |
| ConnectorGrant | Revocable, scoped authorization to an external service |
| EvidenceRecord | Source, trace, test or verification record supporting a claim |
| CreditLedgerEntry | Append-only reservation, charge, release or refund event |

## 3. Logical architecture

The target flow is:

User → Za3im chat/workspace → API and identity boundary → control plane → durable execution runtime → capability registry and adapters → worker engines/tools → artifacts → verification → user-visible outcome.

Cross-cutting services are the model-provider gateway, Algerian context/data services, policy and approval service, artifact/experience registry, usage and credit ledger, and observability/audit pipeline.

This is a logical boundary, not a mandate to deploy every component as a separate microservice. Start with a modular monolith when feasible; split processes when security isolation, independent scaling or reliability actually requires it.

### Control plane

The control plane owns plan approval, capability selection, tenant and connector scope, policy checks, budgets, retries, deadlines, cancellation, task-state transitions, billing reconciliation, artifacts and final reporting. Workers can perform bounded internal planning but cannot bypass these controls to use unregistered tools or create untracked jobs.

### Engine adapter contract

Every engine adapter must implement equivalent operations for: describing capabilities; validating a request; starting an execution; reporting status and events; cancellation; collecting outputs; health checks; and conformance reporting. Translate engine-specific statuses and artifacts into the common Za3im contract. Native worker state may be retained for diagnostics, but is not the authoritative cross-platform record.

### Model-provider gateway

Centralize server-side credentials, model allowlists, provider capability declarations, tenant rate and cost limits, timeouts, retry policy, request correlation, usage capture and data classification. LiteLLM is an option, not a mandatory dependency: compare it with the existing code and a thin first-party adapter before deciding. Never put provider keys in browsers, experience packages, prompts or client-exported files.

## 4. Candidate open-source roles

These are candidates, not confirmed integrations. Pin an immutable upstream commit and verify its current license, runtime, dependencies, network access, telemetry, and security profile before use.

| Candidate | Potential role | Gate before activation |
|---|---|---|
| DeerFlow — github.com/bytedance/deer-flow | Long-horizon research and multi-stage artifact work | Pin version, inspect privilege model, adapter tests |
| Agent Zero — github.com/agent0ai/agent-zero | General computer/terminal workspace | Per-job isolation and minimal filesystem/network access |
| OpenManus — github.com/FoundationAgents/OpenManus | Manus-inspired agent and comparison implementation | Prove distinct value, compatibility and safe execution |
| OpenHands — github.com/OpenHands/software-agent-sdk | Coding, repository edits, tests and patches | Ephemeral workspaces, diff review, no production secrets by default |
| Browser Use — github.com/browser-use/browser-use | Browser interaction and extraction | Domain/session scope and action-level validation |
| Skyvern — github.com/Skyvern-AI/skyvern | Repeatable structured browser workflows | AGPL-3.0 commercial-use review, security and comparative tests |
| LiteLLM — github.com/BerriAI/litellm | Optional multi-provider model gateway | Verify exact license scope, admin isolation and metering behavior |
| Temporal — github.com/temporalio/temporal | Durable workflows, retries and recovery | First prove existing m0-durable-run or other infrastructure is insufficient |
| E2B — github.com/e2b-dev/e2b | Ephemeral code/computer-use sandboxes | Compare hosted terms/costs and self-hosted isolation requirements |
| MCP — modelcontextprotocol.io | Tool and context interoperability | Authenticate servers, scope tools, validate outputs |
| A2A — a2a-protocol.org | Interoperability with separately deployed agents | Add only when independent agent-to-agent communication is required |
| OpenTelemetry — opentelemetry.io | Traces, metrics and logs | Redact secrets and minimize sensitive prompt content |

Licensing must be evaluated at the exact commit and component path. Some projects have additional enterprise or hosted-service terms. AGPL and other reciprocal licenses require legal review for the intended integration and distribution model; do not infer commercial permission solely from public source availability.

### Routing policy

Route by task capability and measured performance, not by name or GitHub popularity. Research-heavy multi-step tasks may use DeerFlow; coding tasks may use OpenHands; computer-workspace tasks may use Agent Zero; browser tasks can choose between Browser Use and Skyvern based on conformance. Keep OpenManus in the candidate/evaluation pool unless it earns a distinct production role.

Do not run overlapping engines in parallel by default. Duplication can inflate costs, produce conflicting browser actions, repeat external side effects and expand the attack surface. A second engine may verify an output when the risk or uncertainty justifies the expense.

For every engine, record upstream URL, immutable commit, build digest, license, runtime and dependencies, declared capabilities, allowed network, secrets, data flow, SBOM/vulnerability evidence, security review, conformance results and status: candidate, sandbox-only, staging, production or disabled. Moving main branches are not production dependencies.

## 5. Common execution contract

The JSON Schemas under schemas/ define an initial v0.1 envelope and are not a substitute for API authentication, authorization or application-level validation. Evolve them through explicit versioning and compatibility rules.

### Request

Every request should identify its schema version, execution/task/tenant/project IDs, objective, acceptance criteria, capability requirements, context/artifact references, allowed provider and connector scopes, budget, deadline, step/tool limits, approval mode, data classification, idempotency key and trace ID. Pass references to private context rather than embedding long-lived secrets.

### Result

Every result reports status; artifact references and content hashes; validation outcomes; engine/model version; relevant events; observed side effects; known and unknown usage/cost; structured errors and retryability; and outstanding approval requirements. A result saying “done” is insufficient without required artifacts or a defined policy-approved success condition.

### Task lifecycle

Use explicit, durable states such as: DRAFT → PLANNED → AWAITING_APPROVAL → QUEUED → RUNNING → VERIFYING → SUCCEEDED. Alternative terminal states include FAILED, CANCELLED and EXPIRED. A job can enter AWAITING_APPROVAL from execution when a policy gate requires user confirmation. Every transition is validated and recorded. Retries create attempt records and must not duplicate non-idempotent actions.

### Acceptance and verification

Each task must have machine-checkable acceptance criteria where possible. Examples include site build success, route/link checks, artifact schema validation, deployment health, test suite result or external provider confirmation. Record evidence with source/version, execution ID, timestamp, state digest where appropriate, and verdict. Unknown is not pass. Verification should be performed outside the same agent's unsupported self-attestation for consequential outcomes.

## 6. Portable experiences

A distributable experience definition contains a versioned manifest, user-facing entry point, workflow graph or declarative steps, typed input/output schemas, dependencies and version constraints, capability IDs, permission requests, migration rules and acceptance tests. The package should be inspectable before installation and signed or integrity-checked when distributed.

Separate four objects:
1. Definition: reusable instructions, workflow and schemas.
2. Instance: a tenant's configured installation.
3. Execution: a particular run and its trace.
4. Artifacts: files/data generated by that run.

Default export excludes credentials, session cookies, private customer data, billing information, connected-account IDs, and execution history. Installation requires the receiving user to grant their own credentials and approve required permissions. Dependency versions and migration behavior must be explicit. Imported packages run in a restricted environment before promotion.

MCP Apps, MCP server bundles and Agent Skills solve parts of the ecosystem; do not claim novelty merely for packaging a UI or prompt. Validate the actual gap: reproducible behavior, versioned state, portable dependency declarations, permission preservation and testable compatibility across hosts.

## 7. Algerian context and data governance

Treat the existing Algerian data and service corpus as USER_REPORTED until each dataset is inventoried. Store provenance, owning party, source URL/reference, jurisdiction/wilaya coverage, applicable date, retrieval/ingestion time, update cadence, permitted uses, transformation history, confidence/status and known gaps.

For legal, regulatory, price, population and document requirements, show the source and effective date where applicable. A language model's fluent answer is not an authoritative legal source. Stale or contradictory sources should surface as a conflict/unknown requiring review.

Use synthetic data during early development. Before production, assess applicable Algerian personal-data obligations and each provider's processing/retention arrangements. Do not imply that API usage guarantees local data residency or zero storage. Minimize data sent to models and tools, apply access controls, and define deletion/retention policies.

## 8. Security and side-effect gates

- Enforce tenant isolation in every data access and artifact download.
- Keep provider credentials in a server-side secret manager; grant minimum scopes and support revocation.
- Isolate agent workspaces and restrict filesystem, process, network, browser and package-install privileges.
- Treat prompts, webpages, documents, tool output and imported experience packages as untrusted input.
- Restrict egress to approved destinations where practical; defend against SSRF, prompt injection, exfiltration and malicious packages.
- Separate generation from execution. Require explicit authorization and appropriate confirmation for publishing, ad spend, message sending, purchases and official submissions.
- Make consequential actions idempotent where possible; otherwise use a durable intent/confirmation/reconciliation record.
- Keep a tamper-evident audit trail without logging secrets or unnecessary sensitive content.
- Provide cancellation, revocation, rollback or compensating action where the external system supports it.

## 9. Usage accounting and payments

Maintain an append-only credit ledger. A task reserves an estimated budget before execution; observed usage is reconciled afterward; unused reservation is released; failures and refunds follow explicit policy. Use idempotency keys for reservations, charges, refunds and payment webhooks. Do not trust agent-reported usage when a provider or runtime meter is available.

Keep internal compute/model costs separate from the user-facing price. Define per-tenant, per-task and per-engine caps; handle provider cost uncertainty; and avoid charging twice on retries. Support for CIB, Edahabia, BaridiMob, bank transfer or subscriptions is a product/payment integration decision requiring current provider and compliance verification, not an assumption that every option is available.

## 10. Reuse-first inventory

Before choosing new frameworks, inspect and record capability, tests, license, maturity and integration cost for:
- current Za3im implementation and deployment;
- m0-durable-run (workflow/API/retry capabilities);
- Software-res (evidence validation and CI/resilience checks);
- Llms-mcp-android (provider/tool/agent integration patterns);
- Opportunity-Packs (capability/strategy package structure);
- prepared Algerian datasets, services and connectors.

These are audit targets, not claims that each one already provides the stated capability. Adopt, wrap, extend or reject each based on repository evidence. Avoid duplicating durable execution, evidence validation, model gateways, schemas or registries without a written decision.

## 11. Implementation sequence

**Phase 0 — Inventory and freeze contracts.** Identify source repository/revision, runtime, deployment, data stores, available tests, current interfaces and prepared datasets. Map existing components to the entities and interfaces above. Produce a gap table.

**Phase 1 — Contract and control-plane vertical slice.** Implement tenant/task/attempt records, request/result validation, capability registry, policy gate, artifact metadata, idempotency and trace IDs. Add tests for illegal transitions and duplicate operations.

**Phase 2 — GPT provider and one worker.** Connect the OpenAI API server-side through a provider adapter and integrate one execution engine through the common contract. Use synthetic data, bounded cost and a sandbox. Keep other candidates registered but disabled.

**Phase 3 — End-to-end business experience.** Generate one concrete deliverable; store artifacts; run tests; present a preview; request approval before external publication; record evidence and cost.

**Phase 4 — Portability and comparative engines.** Export/import the experience in another compatible runtime; run the same test corpus against candidate engines; enable another engine only if it provides measurable incremental value.

**Phase 5 — Payments and scale.** Add credit ledger and payment methods after reconciliation, refund, abuse and security tests. Scale worker services based on measured resource and isolation needs.

## 12. Release gates

A feature is not production-ready until:
- request/result schemas and migration compatibility tests pass;
- tenant isolation and cross-tenant artifact access tests pass;
- repeated requests and retry tests prove idempotency or safe reconciliation;
- cancellation, timeout, worker crash and resume tests pass;
- prompt injection and untrusted package tests cover tool boundaries;
- permissions and approval gates reject unauthorized side effects;
- costs are bounded and reconciled;
- required artifacts and source evidence can be inspected;
- observability redacts secrets;
- license and supply-chain review are recorded;
- a rollback or disable procedure exists.

Initial experiment targets should be fixed before running benchmarks: verified task success, cost per successful task, recovery rate, artifact validity/portability, human intervention rate, latency, and safety violations. Do not set a performance claim based solely on popularity, internal demonstrations or agent self-evaluation.

## 13. Open decisions

1. Which current repository/branch/revision is the authoritative Za3im implementation?
2. What runtime and existing durable-run interfaces can be reused?
3. Which prepared Algerian data assets have verified source/date/coverage and a usable API?
4. Which single end-to-end experience should be the first acceptance case?
5. What hosting and tenant isolation model can current resources sustain?
6. Which payment provider and merchant arrangements are available and compliant?
7. What exact licenses and pinned commits will be approved for each engine?
8. What data retention, deletion, and audit policy applies to user inputs and generated artifacts?

## 14. Status summary

- **ESTABLISHED:** The repository needs an architecture and stable integration contracts before many engines are wired together.
- **USER_REPORTED:** Algerian datasets/services are already prepared; their current state still needs an inventory.
- **PROPOSED:** The control plane, adapters, experience package, ledger, and release gates described here.
- **UNKNOWN:** Current implementation coverage, actual engine performance, production cost, legal compliance status and market willingness to pay.
- **NOT CLAIMED:** No candidate engine is integrated, no deployment is proven, and no production security guarantee is established by this specification.
