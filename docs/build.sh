#!/usr/bin/env bash
# Builds both sites from nothing and stops when anything is wrong: the Stargate docs, and the
# dev docs in the folder companion/ of it (when the repository has the study document).
# Use it before you rely on the sites. While you work on the code, ./watch.sh is the handier one.
#
#   ./build.sh        build
#   ./build.sh -v     the same, and Sphinx says more (for example which lines every code sample picked)
#
# Anything written after ./build.sh is handed to Sphinx as it is.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/tools/env.sh"
need_tools

stopped() {
    echo >&2
    echo "The build stopped: see the lines marked WARNING or ERROR above." >&2
    echo "README.md, section \"When a build fails\", explains each message and what to do." >&2
    exit 1
}

# 1. C# files -> XML, generated pages, copies of the repository's documents, and the pages of
#    the dev docs.  --strict: a type that Doxygen did not understand stops the build.
python tools/prebuild.py --strict

# 2. Start from nothing. Sphinx only reports a problem while it reads a page, and it skips
#    pages that did not change since the last build, so an old problem could stay hidden.
rm -rf -- "${STARGATE_DOCS_BUILD:?}/html" "${STARGATE_DOCS_BUILD:?}/doctrees"

# 3. Pages -> HTML.  -W: a warning counts as an error.  --keep-going: list every warning, not only the first.
echo "-- Pages -> HTML (Sphinx)"
python -m sphinx -b html -W --keep-going -d "$STARGATE_DOCS_BUILD/doctrees" "$@" source "$STARGATE_DOCS_BUILD/html" || stopped

# 4. The second site, into the folder companion/ of the first. It comes second because its
#    links to the code reference are worked out from the names the first site has just written.
python tools/build_companion.py --strict "$@" || stopped

# 5. Popup texts for .NET names, for both sites, taken from the documentation files of the
#    installed .NET SDK and of the NuGet packages.
python tools/dotnet_xml_previews.py

echo
echo "Built without problems: $STARGATE_DOCS_BUILD/html"
echo "Look at it with ./serve.sh"
