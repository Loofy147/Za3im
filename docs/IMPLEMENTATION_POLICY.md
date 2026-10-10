# Za3im implementation and evidence policy

## Binding rule

A checked item must be implemented, connected to the system path it claims to serve, and verified with evidence. A file, example, design, mocked test, or registry row alone never satisfies implementation status.

## Allowed status vocabulary

- PROPOSED: design only; no executable path.
- IMPLEMENTED: code exists and is wired to the intended runtime path.
- UNIT_TESTED: implementation passes deterministic local unit tests.
- INTEGRATION_TESTED: cooperating real components passed a named integration test in a recorded environment.
- LIVE_VERIFIED: an actual provider/external system was invoked; redacted evidence, version, timestamp and outcome are recorded.
- PRODUCTION_READY: all security, reliability, operations, compliance, cost and rollback gates for the deployment target pass.
- CANDIDATE_DISABLED: evaluated for possible adoption but unavailable to execution.
- BLOCKED / UNKNOWN / NOT_RUN: state blockers honestly; no inferred success.

These statuses are gates, not a marketing scale. A unit test using a fake cannot be upgraded to live evidence by repetition.

## Minimum evidence record

For each claimed capability, record capability ID/version; source repository and immutable commit; contract and dependency versions; execution/test identifier; environment; command; expected and actual result; artifact hash/log reference; status; known failures; reviewer/decision where relevant.

## Change discipline

1. Add a failing test for new logic or a reproduced failure (RED).
2. Implement the smallest behavior that satisfies it (GREEN).
3. Refactor only while tests remain green.
4. Run focused and complete test suites.
5. Record exact revision and results.
6. Update the implementation ledger and only then change status.
7. Keep proposals and examples explicitly disconnected unless the runtime loads and validates them.
8. Failed, skipped, unavailable and negative tests remain visible.

## Non-negotiable boundaries

- Never call an unintegrated engine in a production route.
- Never call a fake provider response a live provider test.
- Never call an estimate an actual bill.
- Never call a manifest a portable experience runtime.
- Never call a tenant ID in JSON authentication.
- Never claim an exactly-once external effect from a successful build.
- Unknown is not pass.
