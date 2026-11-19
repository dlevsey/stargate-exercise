# Shared first lines of setup.sh, build.sh, watch.sh, serve.sh and test.sh.
# Those scripts read this file with "source"; it is not run on its own.
#
# It settles three folders and stores them in variables that the Python tools read too
# (tools/common.py has the same defaults):
#
#   STARGATE_REPO         the Stargate repository         default: the folder above this project
#   STARGATE_DOCS_TOOLS   where setup.sh puts the tools    default: ~/.local/share/stargate-docs
#   STARGATE_DOCS_BUILD   where a build puts its results   default: _build in this project
#
# To change one, write a line such as STARGATE_REPO=/path/to/stargate-exercise in a file named
# local.env next to build.sh (local.env.example shows how). Git ignores local.env.

DOCS="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$DOCS"

if [ -f "$DOCS/local.env" ]; then
    # A value given in front of a command (STARGATE_REPO=/somewhere ./build.sh) wins over the
    # same name in local.env. So what is set now is remembered and put back after the file.
    given="$(export -p)"
    set -a    # pass every variable the file sets on to the programs started below
    # shellcheck disable=SC1091
    . "$DOCS/local.env"
    set +a
    eval "$given"
    unset given
fi

export STARGATE_REPO="${STARGATE_REPO:-$(dirname "$DOCS")}"
export STARGATE_DOCS_TOOLS="${STARGATE_DOCS_TOOLS:-${XDG_DATA_HOME:-$HOME/.local/share}/stargate-docs}"
export STARGATE_DOCS_BUILD="${STARGATE_DOCS_BUILD:-$DOCS/_build}"
export PYTHONDONTWRITEBYTECODE=1    # keep __pycache__ folders out of the project

VENV="$STARGATE_DOCS_TOOLS/venv"

# Stop with a clear message when setup.sh has not been run yet.
# Afterwards "python" means the Python that setup.sh installed the packages into.
need_tools() {
    if [ ! -x "$VENV/bin/python" ]; then
        echo "The tools are not installed yet (looked in $STARGATE_DOCS_TOOLS)." >&2
        echo "Run ./setup.sh once, then try again." >&2
        exit 1
    fi
    export PATH="$VENV/bin:$PATH"
}

# Stop when something already answers on a port, instead of failing later with a long Python error.
need_free_port() {
    if (exec 3<>"/dev/tcp/127.0.0.1/$1") 2>/dev/null; then
        echo "Port $1 is already in use. Is ./watch.sh or ./serve.sh still running in another terminal?" >&2
        echo "Stop it there with Ctrl+C, or choose another port, for example:  $0 8780" >&2
        exit 1
    fi
}
