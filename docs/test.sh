#!/usr/bin/env bash
# Runs the checks of the tools in tools/ and of the extensions in source/_ext/. It takes about
# ten seconds and needs no build: every check brings a small sample of its own.
#
#   ./test.sh                 all checks
#   ./test.sh -v              the same, and every check is named
#   ./test.sh -k companion    only the checks with "companion" in their name
#
# Run it after changing a rule in one of the tools, and after installing another version of
# Doxygen, Sphinx or sphinx-autobuild: tools/test_comment_links.py runs Doxygen itself,
# tools/test_companion_site.py builds a small sample site with Sphinx, and
# tools/test_autobuild.py runs the file watcher behind watch.sh.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/tools/env.sh"
need_tools
exec python -m unittest discover -s tools "$@"
