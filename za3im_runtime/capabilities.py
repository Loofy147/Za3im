"""Executable capability registry and explicit workflow composition.

This module is the runtime source of truth. YAML examples and candidate manifests are
reference-only and cannot activate a capability.
"""
from __future__ import annotations

import re
from typing import Final


CAPABILITY_REGISTRY_VERSION: Final[str] = "za3im.capabilities/0.2"

IMPLEMENTED_CAPABILITIES: Final[dict[str, dict[str, str]]] = {
    "website.generate-draft": {
        "status": "implemented_contract_tested_live_gpt_disabled_until_finished_product",
        "description": "Generate an unpublished static HTML website draft from a validated business profile.",
        "version": "0.1.0",
    },
    "marketing.copy.generate": {
        "status": "implemented_unit_tested_live_provider_not_verified",
        "description": "Generate and store draft promotional copy alongside the website artifact.",
        "version": "0.1.0",
    },
    "website.contact-channels.render": {
        "status": "implemented_unit_tested_live_gpt_disabled_until_finished_product",
        "description": "Render explicitly preferred business contact channels with validated links and escaped public details.",
        "version": "0.1.0",
    },
}

# Workflow composition is explicit and independent from the full registry. Registering a
# future capability does not silently make it mandatory for this workflow.
BUSINESS_PRESENCE_REQUIRED_CAPABILITIES: Final[frozenset[str]] = frozenset({
    "website.generate-draft",
    "marketing.copy.generate",
    "website.contact-channels.render",
})

# Candidate entries are discoverable but are not executable adapters.
CANDIDATE_CAPABILITY_IDS: Final[tuple[str, ...]] = (
    "agent.deer-flow",
    "agent.agent-zero",
    "agent.openmanus",
    "agent.openhands",
    "browser.browser-use",
    "browser.skyvern",
    "experience.export-import",
    "ads.manage",
    "video.generate",
    "deployment.publish",
    "credits.bill",
)

_CAPABILITY_ID = re.compile(r"^[a-z][a-z0-9]*(?:[.-][a-z0-9]+)*$")


def validate_capability_registry() -> None:
    """Fail fast when workflow composition and executable registry drift."""
    if not BUSINESS_PRESENCE_REQUIRED_CAPABILITIES:
        raise ValueError("The business-presence workflow must declare at least one capability")
    if not BUSINESS_PRESENCE_REQUIRED_CAPABILITIES.issubset(IMPLEMENTED_CAPABILITIES):
        missing = sorted(BUSINESS_PRESENCE_REQUIRED_CAPABILITIES - set(IMPLEMENTED_CAPABILITIES))
        raise ValueError("Workflow references unregistered capabilities: " + ", ".join(missing))
    if set(CANDIDATE_CAPABILITY_IDS) & set(IMPLEMENTED_CAPABILITIES):
        raise ValueError("A capability cannot be both implemented and candidate-disabled")
    if len(CANDIDATE_CAPABILITY_IDS) != len(set(CANDIDATE_CAPABILITY_IDS)):
        raise ValueError("Candidate capability IDs must be unique")
    for capability_id, metadata in IMPLEMENTED_CAPABILITIES.items():
        if not _CAPABILITY_ID.fullmatch(capability_id):
            raise ValueError(f"Invalid capability ID: {capability_id}")
        if not all(isinstance(metadata.get(key), str) and metadata[key].strip() for key in ("status", "description", "version")):
            raise ValueError(f"Incomplete metadata for implemented capability: {capability_id}")
        if not metadata["status"].startswith("implemented"):
            raise ValueError(f"Registry entry must have an implemented status: {capability_id}")
    for capability_id in CANDIDATE_CAPABILITY_IDS:
        if not _CAPABILITY_ID.fullmatch(capability_id):
            raise ValueError(f"Invalid candidate capability ID: {capability_id}")


validate_capability_registry()
