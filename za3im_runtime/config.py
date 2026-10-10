"""Validated, single-source runtime configuration for Za3im.

Secrets are deliberately excluded from repr output. Parsing is pure: it never mutates
the provided mapping or performs network/file-system operations.
"""
from __future__ import annotations

import ipaddress
import math
import os
from dataclasses import dataclass, field
from typing import Mapping


class ConfigurationError(ValueError):
    """Raised when runtime settings are missing, invalid, or unsafe."""


def _read_int(env: Mapping[str, str], key: str, default: int) -> int:
    raw = env.get(key, str(default)).strip()
    try:
        return int(raw)
    except (TypeError, ValueError):
        raise ConfigurationError(f"{key} must be an integer") from None


def _read_float(env: Mapping[str, str], key: str, default: float) -> float:
    raw = env.get(key, str(default)).strip()
    try:
        value = float(raw)
    except (TypeError, ValueError):
        raise ConfigurationError(f"{key} must be a finite number") from None
    if not math.isfinite(value):
        raise ConfigurationError(f"{key} must be a finite number")
    return value


def _read_bool(env: Mapping[str, str], key: str, default: bool = False) -> bool:
    raw = env.get(key, "true" if default else "false").strip().lower()
    if raw in {"1", "true", "yes"}:
        return True
    if raw in {"0", "false", "no"}:
        return False
    raise ConfigurationError(f"{key} must be one of true/false, yes/no, or 1/0")


def _is_loopback_host(host: str) -> bool:
    if host.lower() == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


@dataclass(frozen=True, slots=True)
class RuntimeConfig:
    """Runtime settings, validated once before service startup.

    Defaults intentionally bind to loopback and leave live GPT disabled. Non-loopback
    use still has only shared-token protection and is NOT production multi-tenant auth.
    """

    api_host: str = "127.0.0.1"
    api_port: int = 8080
    api_token: str = field(default="", repr=False)
    api_max_body_bytes: int = 1024 * 1024
    db_path: str = "za3im_state.sqlite3"
    artifact_dir: str = "za3im_artifacts"
    openai_api_key: str = field(default="", repr=False)
    openai_model: str = "gpt-6-luna"
    live_gpt_enabled: bool = False
    provider_timeout_seconds: float = 35.0
    max_output_tokens: int = 1200
    input_price_per_million: float = 0.10
    output_price_per_million: float = 0.50

    def __post_init__(self) -> None:
        if not isinstance(self.api_host, str) or not self.api_host.strip():
            raise ConfigurationError("ZA3IM_API_HOST must be a non-empty host")
        if not isinstance(self.api_port, int) or isinstance(self.api_port, bool) or not 1 <= self.api_port <= 65535:
            raise ConfigurationError("ZA3IM_API_PORT must be between 1 and 65535")
        if not isinstance(self.api_token, str):
            raise ConfigurationError("ZA3IM_API_TOKEN must be a string")
        if not isinstance(self.api_max_body_bytes, int) or isinstance(self.api_max_body_bytes, bool) or not 1 <= self.api_max_body_bytes <= 16 * 1024 * 1024:
            raise ConfigurationError("ZA3IM_API_MAX_BODY_BYTES must be between 1 and 16777216")
        if not isinstance(self.db_path, str) or not self.db_path.strip():
            raise ConfigurationError("ZA3IM_DB_PATH must be a non-empty path")
        if not isinstance(self.artifact_dir, str) or not self.artifact_dir.strip():
            raise ConfigurationError("ZA3IM_ARTIFACT_DIR must be a non-empty path")
        if not isinstance(self.openai_api_key, str):
            raise ConfigurationError("OPENAI_API_KEY must be a string")
        if not isinstance(self.openai_model, str) or not self.openai_model.strip():
            raise ConfigurationError("ZA3IM_OPENAI_MODEL must be non-empty")
        if not isinstance(self.live_gpt_enabled, bool):
            raise ConfigurationError("ZA3IM_ENABLE_LIVE_GPT must be an explicit boolean")
        if not isinstance(self.provider_timeout_seconds, (int, float)) or isinstance(self.provider_timeout_seconds, bool) or not math.isfinite(self.provider_timeout_seconds) or not 0.1 <= self.provider_timeout_seconds <= 120:
            raise ConfigurationError("ZA3IM_OPENAI_TIMEOUT_SECONDS must be between 0.1 and 120")
        if not isinstance(self.max_output_tokens, int) or isinstance(self.max_output_tokens, bool) or not 64 <= self.max_output_tokens <= 4096:
            raise ConfigurationError("ZA3IM_MAX_OUTPUT_TOKENS must be between 64 and 4096")
        for key, value in (
            ("ZA3IM_OPENAI_INPUT_USD_PER_MILLION", self.input_price_per_million),
            ("ZA3IM_OPENAI_OUTPUT_USD_PER_MILLION", self.output_price_per_million),
        ):
            if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value) or value <= 0:
                raise ConfigurationError(f"{key} must be a finite positive number")
        if not _is_loopback_host(self.api_host) and not self.api_token.strip():
            raise ConfigurationError("ZA3IM_API_TOKEN is required for non-loopback binds")
        if not _is_loopback_host(self.api_host) and len(self.api_token.strip()) < 32:
            raise ConfigurationError("ZA3IM_API_TOKEN must contain at least 32 characters for non-loopback binds")

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "RuntimeConfig":
        source = os.environ if env is None else env
        return cls(
            api_host=source.get("ZA3IM_API_HOST", "127.0.0.1").strip(),
            api_port=_read_int(source, "ZA3IM_API_PORT", 8080),
            api_token=source.get("ZA3IM_API_TOKEN", "").strip(),
            api_max_body_bytes=_read_int(source, "ZA3IM_API_MAX_BODY_BYTES", 1024 * 1024),
            db_path=source.get("ZA3IM_DB_PATH", "za3im_state.sqlite3").strip(),
            artifact_dir=source.get("ZA3IM_ARTIFACT_DIR", "za3im_artifacts").strip(),
            openai_api_key=source.get("OPENAI_API_KEY", "").strip(),
            openai_model=source.get("ZA3IM_OPENAI_MODEL", "gpt-6-luna").strip(),
            live_gpt_enabled=_read_bool(source, "ZA3IM_ENABLE_LIVE_GPT", False),
            provider_timeout_seconds=_read_float(source, "ZA3IM_OPENAI_TIMEOUT_SECONDS", 35.0),
            max_output_tokens=_read_int(source, "ZA3IM_MAX_OUTPUT_TOKENS", 1200),
            input_price_per_million=_read_float(source, "ZA3IM_OPENAI_INPUT_USD_PER_MILLION", 0.10),
            output_price_per_million=_read_float(source, "ZA3IM_OPENAI_OUTPUT_USD_PER_MILLION", 0.50),
        )
