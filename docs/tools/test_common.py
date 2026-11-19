"""Checks how the tools find the C# projects and files of a repository (tools/common.py).

Run with:  ./test.sh
"""
import contextlib
import io
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import common

TEST_PROJECT = ('<Project Sdk="Microsoft.NET.Sdk"><ItemGroup>'
                '<PackageReference Include="Microsoft.NET.Test.Sdk" Version="17.8.0" /></ItemGroup></Project>')


class Discovery(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory(prefix="stargate-docs-test-")
        self.addCleanup(folder.cleanup)
        self.repo = Path(folder.name).resolve() / "repo"
        docs = self.repo / "docs-site"
        patched = mock.patch.multiple(common, REPO=self.repo, DOCS=docs, BUILD=docs / "_build")
        patched.start()
        self.addCleanup(patched.stop)
        self.forget()
        self.addCleanup(self.forget)

    def forget(self):
        """The lists are worked out once per run; a check needs them worked out again."""
        for remembered in (common.project_files, common.csharp_projects, common.csharp_files):
            remembered.cache_clear()

    def write(self, name, text=""):
        path = self.repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def sample(self):
        self.write("package/api/Api.csproj", '<Project Sdk="Microsoft.NET.Sdk.Web"></Project>')
        self.write("package/api/Program.cs")
        self.write("package/api/Controllers/PersonController.cs")
        self.write("package/api/bin/Debug/net8.0/Built.cs")          # build output
        self.write("package/api/obj/Generated.cs")
        self.write("package/api/.vs/Settings.cs")                    # a folder whose name starts with a dot
        self.write("package/api/Tools/Tool.csproj", "<Project></Project>")      # a project inside a project
        self.write("package/api/Tools/Tool.cs")
        self.write("package/tests/Api.Tests/Api.Tests.csproj", TEST_PROJECT)
        self.write("package/tests/Api.Tests/PersonTests.cs")
        self.write("node_modules/some-package/Sample.csproj", "<Project></Project>")
        self.write("docs-site/sample/Sample.csproj", "<Project></Project>")     # the docs project itself
        self.write("package/README.md", "# Overview\n")

    def names(self, paths):
        return [path.relative_to(self.repo).as_posix() for path in paths]

    def test_projects_are_found_wherever_they_are(self):
        self.sample()
        self.assertEqual(self.names(common.project_files()), [
            "package/api/Api.csproj", "package/api/Tools/Tool.csproj", "package/tests/Api.Tests/Api.Tests.csproj"])

    def test_a_test_project_stays_out_of_the_code_reference(self):
        self.sample()
        self.assertEqual(self.names(common.csharp_projects()), ["package/api", "package/api/Tools"])
        self.assertEqual(self.names(common.csharp_files()), [
            "package/api/Controllers/PersonController.cs", "package/api/Program.cs", "package/api/Tools/Tool.cs"])

    def test_test_projects_are_included_on_request(self):
        self.sample()
        with mock.patch.dict(os.environ, {"STARGATE_DOCS_TESTS": "1"}):
            self.assertEqual(self.names(common.csharp_projects()),
                             ["package/api", "package/api/Tools", "package/tests/Api.Tests"])
            self.assertIn("package/tests/Api.Tests/PersonTests.cs", self.names(common.csharp_files()))

    def test_the_files_of_a_left_out_project_are_not_read_through_the_project_around_it(self):
        self.write("app/App.csproj", "<Project></Project>")
        self.write("app/Program.cs")
        self.write("app/Tests/App.Tests.csproj", TEST_PROJECT)      # a test project inside the application's folder
        self.write("app/Tests/ProgramTests.cs")
        self.assertEqual(self.names(common.csharp_files()), ["app/Program.cs"])

    def test_how_a_test_project_is_recognised(self):
        for text, expected in (
            (TEST_PROJECT, True),
            ("<Project><PropertyGroup><IsTestProject>true</IsTestProject></PropertyGroup></Project>", True),
            ('<Project><ItemGroup><PackageReference Include="xunit" Version="2.6.0" /></ItemGroup></Project>', True),
            ('<Project Sdk="Microsoft.NET.Sdk.Web"><ItemGroup><PackageReference Include="Dapper" Version="2.1.35" />'
             "</ItemGroup></Project>", False),
        ):
            with self.subTest(text=text):
                self.assertEqual(common.is_test_project(self.write("some/Some.csproj", text)), expected)

    def test_a_repository_without_a_project_stops_with_what_to_do(self):
        self.write("README.md", "# Nothing here yet\n")
        with self.assertRaises(SystemExit) as stopped:
            common.require_repo()
        self.assertIn("there is no project (.csproj file) under", str(stopped.exception))
        self.assertIn("STARGATE_REPO", str(stopped.exception))

    def test_the_types_doxygen_found(self):
        index = self.write("xml/index.xml", """<doxygenindex>
            <compound refid="a" kind="class"><name>Shop::Data::Order</name></compound>
            <compound refid="b" kind="interface"><name>Shop::IClock</name></compound>
            <compound refid="c" kind="namespace"><name>Shop::Data</name></compound>
            <compound refid="d" kind="file"><name>Order.cs</name></compound></doxygenindex>""")
        self.assertEqual(common.documented_types(index.parent), {"Shop.Data.Order", "Shop.IClock"})
        self.assertEqual(common.documented_types(self.repo / "not-built-yet"), set())


if __name__ == "__main__":
    unittest.main()
