"""Checks the HTTP endpoints page (tools/gen_endpoints.py).

Run with:  ./test.sh
"""
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import gen_endpoints
from gen_endpoints import kind


class Kinds(unittest.TestCase):
    def test_a_type_in_plain_words(self):
        self.assertEqual(kind({"type": "string"}), "string")
        self.assertEqual(kind({"type": "string", "format": "date-time"}), "date and time")
        self.assertEqual(kind({"type": "array", "items": {"$ref": "#/components/schemas/Duty"}}), "list of [Duty](#duty)")
        self.assertEqual(kind({"enum": ["A", "B"]}), "one of `A`, `B`")

    def test_may_be_empty_in_both_versions_of_openapi(self):
        self.assertEqual(kind({"type": "string", "nullable": True}), "string or null")       # OpenAPI 3.0
        self.assertEqual(kind({"type": ["null", "string"]}), "string or null")                # OpenAPI 3.1
        self.assertEqual(kind({"type": "string", "nullable": False}), "string")


class Page(unittest.TestCase):
    def page(self, description, types=()):
        with tempfile.TemporaryDirectory(prefix="stargate-docs-test-") as folder:
            root = Path(folder)
            (root / "openapi.json").write_text(json.dumps(description), encoding="utf-8")
            with mock.patch.multiple(gen_endpoints, SOURCE=root / "source", documented_types=lambda: set(types),
                                     OPENAPI_URL="http://localhost:1/swagger/v1/swagger.json"), \
                    contextlib.redirect_stdout(io.StringIO()):
                gen_endpoints.main(root / "openapi.json", root / "saved-on.txt")
            return (root / "source" / "http" / "index.md").read_text(encoding="utf-8")

    def description(self, responses, **body):
        return {"openapi": "3.0.1", "paths": {"/Person": {"post": {"tags": ["Person"], "responses": responses, **body}}}}

    def test_the_page_says_where_the_description_comes_from(self):
        page = self.page(self.description({"200": {"description": "Success"}}))
        self.assertIn("publishes at `/swagger/v1/swagger.json` (1 endpoints, OpenAPI 3.0.1)", page)
        self.assertIn("### POST /Person", page)

    def test_a_group_links_to_its_controller_only_when_the_code_has_one(self):
        description = self.description({"200": {"description": "Success"}})
        self.assertIn("Handled by {cs:type}`PersonController`.", self.page(description, types=["Shop.Controllers.PersonController"]))
        self.assertNotIn("Handled by", self.page(description, types=["Shop.Controllers.OrderController"]))

    def test_a_description_without_any_answer_shape_gets_a_note(self):
        self.assertIn("names no data shape for any answer", self.page(self.description({"200": {"description": "Success"}})))
        with_shape = {"200": {"description": "Success", "content": {"application/json": {"schema": {"type": "string"}}}}}
        self.assertNotIn("names no data shape", self.page(self.description(with_shape)))

    def test_whether_the_body_is_required_is_only_said_when_the_description_says_it(self):
        content = {"content": {"application/json": {"schema": {"type": "string"}}}}
        responses = {"200": {"description": "Success"}}
        self.assertIn("| request body | JSON | string | not said |", self.page(self.description(responses, requestBody=content)))
        self.assertIn("| request body | JSON | string | yes |",
                      self.page(self.description(responses, requestBody={**content, "required": True})))


if __name__ == "__main__":
    unittest.main()
