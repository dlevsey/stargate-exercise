"""Checks where the scripts take their settings from (tools/env.sh and local.env).

Run with:  ./test.sh
"""
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ENV_SH = Path(__file__).resolve().parent / "env.sh"
SETTINGS = ("STARGATE_REPO", "STARGATE_DOCS_BUILD", "STARGATE_DOCS_TOOLS")


class Settings(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory(prefix="stargate-docs-test-")
        self.addCleanup(folder.cleanup)
        self.project = Path(folder.name).resolve() / "repo" / "docs-site"
        (self.project / "tools").mkdir(parents=True)
        shutil.copy(ENV_SH, self.project / "tools" / "env.sh")

    def settings(self, local_env=None, **given):
        """What the scripts end up with: {name: value}."""
        if local_env is not None:
            (self.project / "local.env").write_text(local_env, encoding="utf-8")
        environment = {name: value for name, value in os.environ.items() if name not in SETTINGS}
        environment.update(given, HOME="/home/someone")
        environment.pop("XDG_DATA_HOME", None)
        script = 'source "$1/tools/env.sh"; printf "%s\\n" "$STARGATE_REPO" "$STARGATE_DOCS_BUILD" "$STARGATE_DOCS_TOOLS"'
        printed = subprocess.run(["bash", "-c", script, "bash", str(self.project)], env=environment,
                                 capture_output=True, text=True, check=True).stdout.splitlines()
        return dict(zip(SETTINGS, printed))

    def test_without_settings_the_repository_is_the_folder_above_the_project(self):
        self.assertEqual(self.settings(), {
            "STARGATE_REPO": str(self.project.parent),
            "STARGATE_DOCS_BUILD": str(self.project / "_build"),
            "STARGATE_DOCS_TOOLS": "/home/someone/.local/share/stargate-docs",
        })

    def test_a_line_in_local_env_is_used(self):
        found = self.settings("# a comment\nSTARGATE_REPO=/from/local/env\n")
        self.assertEqual(found["STARGATE_REPO"], "/from/local/env")

    def test_a_home_folder_sign_in_local_env_is_filled_in(self):
        found = self.settings("STARGATE_DOCS_BUILD=~/.cache/stargate-docs\n")
        self.assertEqual(found["STARGATE_DOCS_BUILD"], "/home/someone/.cache/stargate-docs")

    def test_a_value_given_with_the_command_wins_over_local_env(self):
        found = self.settings("STARGATE_REPO=/from/local/env\nSTARGATE_DOCS_BUILD=/build/from/local/env\n",
                              STARGATE_REPO="/from/the command line")
        self.assertEqual(found["STARGATE_REPO"], "/from/the command line")
        self.assertEqual(found["STARGATE_DOCS_BUILD"], "/build/from/local/env")     # not given, so local.env counts


if __name__ == "__main__":
    unittest.main()
