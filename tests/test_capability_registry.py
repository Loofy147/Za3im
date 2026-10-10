from __future__ import annotations

import re
import unittest

from za3im_runtime.capabilities import (
    BUSINESS_PRESENCE_REQUIRED_CAPABILITIES,
    CANDIDATE_CAPABILITY_IDS,
    CAPABILITY_REGISTRY_VERSION,
    IMPLEMENTED_CAPABILITIES,
    validate_capability_registry,
)


class CapabilityRegistryTests(unittest.TestCase):
    def test_every_business_presence_requirement_is_registered(self):
        validate_capability_registry()
        self.assertTrue(BUSINESS_PRESENCE_REQUIRED_CAPABILITIES)
        self.assertTrue(BUSINESS_PRESENCE_REQUIRED_CAPABILITIES.issubset(IMPLEMENTED_CAPABILITIES))

    def test_registering_future_capabilities_does_not_expand_workflow_requirements(self):
        self.assertEqual(
            BUSINESS_PRESENCE_REQUIRED_CAPABILITIES,
            frozenset({
                "website.generate-draft",
                "marketing.copy.generate",
                "website.contact-channels.render",
            }),
        )

    def test_registry_metadata_is_complete_and_capability_ids_are_normalized(self):
        self.assertRegex(CAPABILITY_REGISTRY_VERSION, r"^za3im\.capabilities/[0-9]+$")
        for capability_id, metadata in IMPLEMENTED_CAPABILITIES.items():
            with self.subTest(capability_id=capability_id):
                self.assertRegex(capability_id, r"^[a-z][a-z0-9]*(?:[.-][a-z0-9]+)*$")
                self.assertTrue(metadata["version"].strip())
                self.assertTrue(metadata["status"].strip())
                self.assertTrue(metadata["description"].strip())

    def test_candidate_registry_never_claims_candidates_are_implemented(self):
        self.assertFalse(set(CANDIDATE_CAPABILITY_IDS) & set(IMPLEMENTED_CAPABILITIES))
        for capability_id in CANDIDATE_CAPABILITY_IDS:
            with self.subTest(capability_id=capability_id):
                self.assertRegex(capability_id, r"^[a-z][a-z0-9]*(?:[.-][a-z0-9]+)*$")


if __name__ == "__main__":
    unittest.main(verbosity=2)
