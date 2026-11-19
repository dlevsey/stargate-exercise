#!/usr/bin/env bash
# One-time set-up for the Stargate docs site. Safe to run again at any time.
#
#   1. Checks that the programs it relies on are there. It never uses sudo and installs
#      nothing system-wide: when something is missing it says which command installs it.
#   2. Creates a private Python environment and installs exactly the package versions
#      listed in requirements.txt.
#   3. Downloads Doxygen 1.18.0 from Doxygen's release page on GitHub and compares the
#      download with a known fingerprint before using it.
#
# 2 and 3 go into one folder outside the project (default: ~/.local/share/stargate-docs).
# The project may sit on a Windows drive (/mnt/c/...), and WSL reads the thousands of small
# files of a Python environment from there very slowly. To remove the tools, delete that folder.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/tools/env.sh"

DOXYGEN_VERSION="1.18.0"
DOXYGEN_URL="https://github.com/doxygen/doxygen/releases/download/Release_1_18_0/doxygen-1.18.0.linux.bin.tar.gz"
DOXYGEN_SHA256="14fa81bdc34171edb5f1f02b1d60e74802f0439b77fa44e592565d517d72df90"
PYTHON_FOR_SETUP="${PYTHON:-python3}"    # another Python:  PYTHON=python3.13 ./setup.sh

# stop "what is wrong" "what to do" ...
stop() {
    echo >&2
    echo "setup.sh stopped: $1" >&2
    shift
    for line in "$@"; do echo "    $line" >&2; done
    exit 1
}

echo "== 1. Checking this machine"
[ "$(uname -s)" = "Linux" ] || stop "this script is made for Linux." "On Windows, run it inside WSL."
command -v "$PYTHON_FOR_SETUP" >/dev/null || stop "Python was not found ($PYTHON_FOR_SETUP)." "Install it:  sudo apt install python3 python3-venv"
"$PYTHON_FOR_SETUP" -c 'import sys; sys.exit(sys.version_info < (3, 12))' ||
    stop "Python 3.12 or newer is needed; $PYTHON_FOR_SETUP is $("$PYTHON_FOR_SETUP" -c 'import platform; print(platform.python_version())')." \
         "Install a newer one and name it:  PYTHON=python3.12 ./setup.sh"
"$PYTHON_FOR_SETUP" -c 'import venv, ensurepip' 2>/dev/null ||
    stop "this Python cannot create environments (the venv module is missing)." "Install it:  sudo apt install python3-venv"
command -v dot >/dev/null || stop "Graphviz was not found. It draws the diagrams." "Install it:  sudo apt install graphviz"
for program in curl tar sha256sum; do
    command -v "$program" >/dev/null || stop "$program was not found." "Install it:  sudo apt install $program"
done
echo "   $("$PYTHON_FOR_SETUP" --version), $(dot -V 2>&1 | sed 's/^dot - //'): fine"

echo "== 2. Python packages -> $VENV"
mkdir -p "$STARGATE_DOCS_TOOLS"
[ -x "$VENV/bin/python" ] || "$PYTHON_FOR_SETUP" -m venv "$VENV"
echo "   installing the versions in requirements.txt (the first time takes a minute or two)"
# One download that stalls makes pip give up on all of them, with a long Python error that ends
# in "Read timed out". Trying again is cheap, because pip keeps every file that has arrived.
# --timeout 60: wait a minute for a slow connection, where pip would wait 15 seconds.
attempt=1
until "$VENV/bin/python" -m pip install --quiet --disable-pip-version-check --timeout 60 \
          --requirement "$DOCS/requirements.txt"; do
    [ "$attempt" -lt 3 ] ||
        stop "the Python packages could not be installed (tried $attempt times)." \
             "The reason is in pip's own message above; its last line says most." \
             "If it speaks of a time-out or a connection: check the internet connection and run" \
             "./setup.sh again. The files that have arrived are kept, so it carries on from there."
    attempt=$((attempt + 1))
    echo "   that did not work; the reason is in the lines above. Trying again (attempt $attempt of 3)"
done
echo "   $("$VENV/bin/python" -m sphinx --version)"

echo "== 3. Doxygen $DOXYGEN_VERSION -> $STARGATE_DOCS_TOOLS/doxygen"
if [ -n "${DOXYGEN:-}" ]; then
    echo "   skipped: DOXYGEN is set, so the builds use $DOXYGEN"
elif [ "$("$STARGATE_DOCS_TOOLS/doxygen" --version 2>/dev/null | cut -d' ' -f1)" = "$DOXYGEN_VERSION" ]; then
    echo "   already there"
else
    [ "$(uname -m)" = "x86_64" ] ||
        stop "Doxygen's ready-made Linux program is for x86_64 processors; this machine is $(uname -m)." \
             "Build or install Doxygen $DOXYGEN_VERSION yourself, then put this line in local.env:" \
             "DOXYGEN=/path/to/doxygen"
    work="$(mktemp -d "$STARGATE_DOCS_TOOLS/download.XXXXXX")"
    trap 'rm -rf "$work"' EXIT
    echo "   downloading about 115 MB from github.com/doxygen/doxygen"
    # A large download sometimes breaks off half-way. --retry tries again, and --continue-at -
    # carries on from the part that already arrived instead of starting over.
    curl --fail --location --progress-bar --retry 5 --retry-all-errors --continue-at - \
         --output "$work/doxygen.tar.gz" "$DOXYGEN_URL" ||
        stop "the download failed." "Check the internet connection and run ./setup.sh again."
    echo "$DOXYGEN_SHA256  $work/doxygen.tar.gz" | sha256sum --check --status ||
        stop "the downloaded file is not the one this script expects (its SHA-256 fingerprint differs)." \
             "Nothing from it was used. Run ./setup.sh again; if it keeps happening, the file on GitHub changed."
    # The archive also holds manuals and two other programs. Only Doxygen itself is taken out.
    tar -xzf "$work/doxygen.tar.gz" -C "$work" "doxygen-$DOXYGEN_VERSION/bin/doxygen"
    install -m 755 "$work/doxygen-$DOXYGEN_VERSION/bin/doxygen" "$STARGATE_DOCS_TOOLS/doxygen"
    echo "   Doxygen $("$STARGATE_DOCS_TOOLS/doxygen" --version | cut -d' ' -f1) installed"
fi

echo "== Done"
# The tools know how to look for C# projects (tools/common.py), so they are asked.
if "$VENV/bin/python" -c 'import sys; sys.path.insert(0, "tools"); import common; sys.exit(0 if common.csharp_projects() else 1)'; then
    echo "   Repository: $STARGATE_REPO"
    echo "   Next:  ./build.sh   and then   ./serve.sh      (or ./watch.sh while you work on the code)"
else
    echo "   One thing is still missing: no C# project (.csproj file) was found under $STARGATE_REPO"
    echo "   Tell the scripts where the repository is:  cp local.env.example local.env   and edit the STARGATE_REPO line."
fi
