# Za3im Architecture v0.2 package

This package captures the proposed architecture and the first version of its portable contracts. It is documentation and example material, not a running implementation.

## Contents

- `ZA3IM_PLATFORM_ARCHITECTURE_v0.2.md` — system architecture, integration strategy, security, billing, phases, and release gates.
- `schemas/za3im-execution-request.schema.json` — proposed normalized request contract.
- `schemas/za3im-execution-result.schema.json` — proposed normalized result contract.
- `examples/engine-registry.yaml` — candidate integration registry; all engine enablement is disabled pending conformance and review.
- `examples/experience-manifest.yaml` — illustrative portable experience manifest.
- `examples/execution-request.example.json` — synthetic execution request used for schema validation.
- `examples/execution-result.example.json` — synthetic normalized result record.

## Current status

- **ESTABLISHED:** this is an initial architecture and contract proposal.
- **NOT IMPLEMENTED:** listed agent engines are candidates, not connected integrations.
- **NOT VERIFIED:** production security, runtime compatibility, payment operations, and deployment are not yet established by this document.
- **NEXT:** inventory the existing Za3im codebase and related reusable projects, then implement one complete, testable vertical workflow.

See the architecture specification for the target design, decisions, risks, and acceptance gates.
