from __future__ import annotations

import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_DIR = ROOT / "schemas"
EXAMPLE_DIR = ROOT / "examples"


def load_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as stream:
        value = json.load(stream)
    if not isinstance(value, dict):
        raise AssertionError(f"{path.name} must contain a JSON object")
    return value


class ContractFixtureTests(unittest.TestCase):
    def setUp(self):
        self.request_schema = load_json(SCHEMA_DIR / "za3im-execution-request.schema.json")
        self.profile_schema = load_json(SCHEMA_DIR / "business-profile.schema.json")
        self.result_schema = load_json(SCHEMA_DIR / "za3im-execution-result.schema.json")

    def test_all_committed_json_schemas_are_valid_draft_2020_12_schemas(self):
        for path, schema in (
            ("request", self.request_schema),
            ("business profile", self.profile_schema),
            ("result", self.result_schema),
        ):
            with self.subTest(schema=path):
                Draft202012Validator.check_schema(schema)

    def test_synthetic_request_and_nested_business_profile_match_contracts(self):
        request = load_json(EXAMPLE_DIR / "execution-request.example.json")
        Draft202012Validator(
            self.request_schema,
            format_checker=FormatChecker(),
        ).validate(request)
        Draft202012Validator(
            self.profile_schema,
            format_checker=FormatChecker(),
        ).validate(request["input_payload"]["business_profile"])

    def test_synthetic_result_matches_result_contract(self):
        result = load_json(EXAMPLE_DIR / "execution-result.example.json")
        Draft202012Validator(
            self.result_schema,
            format_checker=FormatChecker(),
        ).validate(result)

    def test_example_fixtures_are_explicitly_synthetic_not_live_evidence(self):
        request = load_json(EXAMPLE_DIR / "execution-request.example.json")
        result = load_json(EXAMPLE_DIR / "execution-result.example.json")
        self.assertEqual(request["metadata"]["test_case"], "synthetic")
        self.assertIn("Synthetic schema fixture only", result["summary"])
        self.assertEqual(result["engine"]["model_provider"], "synthetic")


if __name__ == "__main__":
    unittest.main(verbosity=2)
