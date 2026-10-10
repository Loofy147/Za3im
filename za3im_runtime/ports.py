"""Typed application ports shared by workflow orchestration and adapters.

Implementations may be local or remote, but they must satisfy these behavioral
contracts. The current verified adapters are SQLite and the OpenAI Responses client.
"""
from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable


class IdempotencyConflict(Exception):
    """A tenant/idempotency key was reused for a different canonical request."""


@runtime_checkable
class CopyProviderPort(Protocol):
    """Boundary for a provider that returns structured draft copy."""

    provider: str
    model: str
    live_enabled: bool

    def generate_copy(self, profile: dict, max_output_tokens: int = 1200) -> dict:
        """Return validated-by-caller content plus provider/model/usage metadata."""
        ...


@runtime_checkable
class ExecutionRepositoryPort(Protocol):
    """Durable execution, event and artifact metadata operations required by service."""

    artifact_dir: Path

    def claim(self, request: dict) -> tuple[dict, bool]:
        """Atomically claim a request or return its previously recorded execution."""
        ...

    def record_event(self, execution_id: str, event_type: str, payload: dict | None = None) -> str:
        """Append an event while the execution is running; return a stable reference."""
        ...

    def finish(
        self,
        execution_id: str,
        status: str,
        result: dict,
        error: dict | None = None,
        artifact_rows: list[dict] | None = None,
    ) -> dict:
        """Record terminal execution state, result/error and any artifact metadata."""
        ...

    def get_execution(self, execution_id: str) -> dict | None:
        """Read a persisted execution by ID."""
        ...

    def get_artifact(self, artifact_id: str) -> dict | None:
        """Read artifact metadata by ID."""
        ...

    def list_events(self, execution_id: str) -> list[dict]:
        """List persisted events for one execution."""
        ...
