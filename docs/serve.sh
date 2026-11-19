#!/usr/bin/env bash
# Shows the sites that ./build.sh made, at http://localhost:8770. Ctrl+C stops it.
#
#   ./serve.sh         port 8770
#   ./serve.sh 8780    another port
#
# The popups load pages in the background, and browsers only allow that for pages that come
# from a web server. That is why the HTML files are not simply opened from the folder.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/tools/env.sh"
PORT="${1:-8770}"

if [ ! -f "$STARGATE_DOCS_BUILD/html/index.html" ]; then
    echo "There is no built site yet in $STARGATE_DOCS_BUILD/html. Run ./build.sh first." >&2
    exit 1
fi
need_free_port "$PORT"

echo "Stargate docs:  http://localhost:$PORT      (Ctrl+C stops)"
if [ -f "$STARGATE_DOCS_BUILD/html/companion/index.html" ]; then
    echo "Dev docs: http://localhost:$PORT/companion/"
fi
# 127.0.0.1: only this computer can reach the site, not other machines on the network.
exec python3 -m http.server "$PORT" --bind 127.0.0.1 --directory "$STARGATE_DOCS_BUILD/html"
