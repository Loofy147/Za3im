"""Read-only catalog of candidate context/data sources.

This module stores source locators and epistemic status only. It does not fetch URLs,
ingest data, query an external provider, or turn a source reference into verified facts.
"""
from __future__ import annotations

import json
from importlib.resources import files
from urllib.parse import urlsplit

from jsonschema import Draft202012Validator, FormatChecker


CONTEXT_CATALOG_VERSION = "za3im.context.catalog/0.1"
CONTEXT_SOURCE_SCHEMA_VERSION = "za3im.context.source/0.1"


class ContextCatalogError(ValueError):
    """The committed context source catalog failed its contract."""


class ContextCatalog:
    """Load and validate the bundled source metadata without network access."""

    def __init__(self):
        source_text = files("za3im_runtime").joinpath("context_sources.json").read_text(encoding="utf-8")
        schema_text = files("schemas").joinpath("context-source.schema.json").read_text(encoding="utf-8")
        try:
            registry = json.loads(source_text)
            schema = json.loads(schema_text)
        except json.JSONDecodeError as exc:
            raise ContextCatalogError(f"Invalid JSON in context catalog resource: {exc.msg}") from None

        Draft202012Validator.check_schema(schema)
        validator = Draft202012Validator(schema, format_checker=FormatChecker())
        if not isinstance(registry, dict) or registry.get("registry_version") != CONTEXT_CATALOG_VERSION:
            raise ContextCatalogError("Context catalog registry_version is missing or unsupported")
        if registry.get("mode") != "metadata_only_no_ingestion_no_external_requests":
            raise ContextCatalogError("Context catalog must remain metadata-only until a connector is implemented")
        sources = registry.get("sources")
        if not isinstance(sources, list):
            raise ContextCatalogError("Context catalog sources must be an array")

        by_id: dict[str, dict] = {}
        for index, source in enumerate(sources):
            if not isinstance(source, dict):
                raise ContextCatalogError(f"Context source at index {index} must be an object")
            errors = sorted(validator.iter_errors(source), key=lambda error: list(map(str, error.absolute_path)))
            if errors:
                error = errors[0]
                raise ContextCatalogError(
                    f"Invalid context source at index {index} ({error.json_path}): {error.message}"
                )
            source_id = source["source_id"]
            if source_id in by_id:
                raise ContextCatalogError(f"Duplicate context source ID: {source_id}")

            parsed = urlsplit(source["source_uri"])
            if (
                parsed.scheme.lower() != "https"
                or not parsed.hostname
                or parsed.username is not None
                or parsed.password is not None
            ):
                raise ContextCatalogError(f"Context source {source_id} must use an HTTPS URL without credentials")

            if source["status"] == "source_only":
                if source["data_state"] != "not_ingested" or source["connector_state"] != "not_implemented":
                    raise ContextCatalogError(f"Source-only record {source_id} contradicts its ingestion/connector state")
                if source["queryable"] or source["content_sha256"] is not None:
                    raise ContextCatalogError(f"Source-only record {source_id} cannot be queryable or claim an ingested-data digest")
            if source["queryable"]:
                if (
                    source["status"] != "verified_source_data"
                    or source["data_state"] != "ingested_verified"
                    or source["connector_state"] != "implemented"
                    or source["license_status"] != "recorded"
                    or source["content_sha256"] is None
                ):
                    raise ContextCatalogError(
                        f"Queryable source {source_id} must have verified ingested data, an implemented connector, recorded rights and a content digest"
                    )
            by_id[source_id] = json.loads(json.dumps(source))

        self._sources = tuple(by_id[source_id] for source_id in sorted(by_id))
        self._by_id = by_id
        self._domains = frozenset(schema["properties"]["domain"]["enum"])

    def list_sources(self, *, domain: str | None = None) -> dict:
        """Return source metadata only; no network request or data retrieval occurs."""
        if domain is not None and domain not in self._domains:
            raise ValueError(f"Unknown context source domain: {domain}")
        result = [
            json.loads(json.dumps(source))
            for source in self._sources
            if domain is None or source["domain"] == domain
        ]
        return {
            "registry_version": CONTEXT_CATALOG_VERSION,
            "mode": "metadata_only_no_ingestion_no_external_requests",
            "source_count": len(result),
            "queryable_source_count": sum(1 for source in result if source["queryable"]),
            "sources": result,
        }

    def get_source(self, source_id: str) -> dict | None:
        source = self._by_id.get(source_id)
        return json.loads(json.dumps(source)) if source is not None else None
