# Za3im Architecture v0.2 package

This repository captures the proposed architecture and first version of Za3im's portable execution contracts. It is documentation and example material, not a running implementation.

## Contents

- [Platform architecture](ZA3IM_PLATFORM_ARCHITECTURE_v0.2.md) — system boundaries, engines, security, billing, phases and release gates.
- [Execution request schema](schemas/za3im-execution-request.schema.json) — normalized adapter request.
- [Execution result schema](schemas/za3im-execution-result.schema.json) — normalized result, artifacts, verification and accounting.
- [Business profile schema](schemas/business-profile.schema.json) — illustrative input for a reusable business-presence experience.
- [Candidate engine registry](examples/engine-registry.yaml) — candidate integrations, all disabled pending review.
- [Experience manifest](examples/experience-manifest.yaml) — illustrative portable experience package.
- [Synthetic request](examples/execution-request.example.json) and [synthetic result](examples/execution-result.example.json) — example records for contract tests.

## Current status

- **ESTABLISHED:** this is an initial architecture and contract proposal.
- **USER_REPORTED:** Algerian datasets and services are already prepared; coverage, provenance, freshness and integration need an inventory.
- **NOT IMPLEMENTED:** listed engines are candidates, not connected integrations.
- **NOT VERIFIED:** production security, engine compatibility, payments, deployment and runtime performance have not been proven by this documentation.
- **NEXT:** inventory the existing Za3im codebase and reusable repositories, then implement one complete, testable vertical workflow.

Read the architecture specification for the target design, decisions, risks, acceptance gates and open questions.
