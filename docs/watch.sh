#!/usr/bin/env bash
# Builds both sites, shows them at http://localhost:8770 (the dev docs is under
# /companion/), and builds again whenever a file they are made from is saved: a C# file, a
# repository document, the study document, or a page of this site.
# The page in the browser reloads by itself. Ctrl+C stops it.
#
#   ./watch.sh         port 8770
#   ./watch.sh 8780    another port
#
# Unlike ./build.sh, this one carries on when something is wrong: it prints the warning and
# keeps showing the last pages that could be built.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/tools/env.sh"
need_tools
PORT="${1:-8770}"
need_free_port "$PORT"

# What to watch besides source/. tools/watch_paths.py explains how the list is made.
paths="$(python tools/watch_paths.py)"
watch=()
while IFS= read -r path; do
    [ -n "$path" ] && watch+=(--watch "$path")
done <<< "$paths"

# WSL is not told when a program on Windows saves a file, so the watcher looks at the time
# stamp of every watched file again and again ("polling"). Once a second is quick enough.
export WATCHFILES_POLL_DELAY_MS="${WATCHFILES_POLL_DELAY_MS:-1000}"

# Print every message at once, also when the output goes to a file or through "tee".
export PYTHONUNBUFFERED=1

# tools/autobuild.py starts sphinx-autobuild, the program that watches, builds and serves.
# It adds one correction: a watched file that is removed starts one build, not one a second.
# The options are those of sphinx-autobuild:
#
# -a            write every page again at every build, not only the pages that changed.
#               A link is worked out while its page is written, so this is what makes a
#               renamed method show up as a warning on every page that still uses the old
#               name. It costs about a second and a half per build. With many more pages,
#               remove it and rely on ./build.sh for the complete check.
# --host        localhost: only this computer can reach the site. Each served page also gets a
#               small script that connects back to this name to learn about a new build, so
#               open the site as http://localhost:PORT (the address printed below).
# --pre-build   runs before every build: C# files -> XML, generated pages, repository documents,
#               the pages of the dev docs
# --post-build  run after every build that worked, in this order: the second site (the study
#               companion; skipped when nothing it is made from has changed), then the popup
#               texts for .NET names
# --ignore      the pages the pre-build step writes. Sphinx reads them in the same build, and
#               without this line their change would start a second, pointless build.
# --re-ignore   temporary files that editors write next to the file being saved
exec python tools/autobuild.py -b html -a -d "$STARGATE_DOCS_BUILD/doctrees" \
    --host localhost --port "$PORT" \
    --pre-build "python tools/prebuild.py" \
    --post-build "python tools/build_companion.py" \
    --post-build "python tools/dotnet_xml_previews.py" \
    --ignore "$DOCS/source/api" \
    --ignore "$DOCS/source/diagrams" \
    --ignore "$DOCS/source/http" \
    --ignore "$DOCS/source/project" \
    --re-ignore '(~|\.tmp|\.TMP|\.swp|\.swx)$' \
    "${watch[@]}" \
    source "$STARGATE_DOCS_BUILD/html"
