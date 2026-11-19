"""Paths and small helpers shared by the scripts in this folder."""
import functools
import json
import os
import re
import sys
from pathlib import Path
from xml.etree import ElementTree

# The docs project folder (the one that holds build.sh).
DOCS = Path(__file__).resolve().parent.parent

# The repository this site documents: the Stargate exercise (the folder that holds api/ and Stargate.slnx).
# local.env names it (local.env.example shows how). Without that, it is taken to be the folder
# above the docs project, which is right when this folder has been put inside the repository.
REPO = Path(os.environ.get("STARGATE_REPO") or DOCS.parent).resolve()

SOURCE = DOCS / "source"   # pages Sphinx reads (hand-written and generated)
DATA = DOCS / "data"       # saved inputs, such as the OpenAPI description

# Everything a build produces. Set STARGATE_DOCS_BUILD to put it somewhere else.
BUILD = Path(os.environ.get("STARGATE_DOCS_BUILD") or DOCS / "_build").resolve()

# Where setup.sh puts the Python packages and Doxygen: a folder in your WSL home, not the project
# folder. The project may sit on a Windows drive (/mnt/c/...), and WSL reads the thousands of small
# files of a Python environment from there very slowly. (tools/env.sh has the same defaults.)
TOOLS = Path(os.environ.get("STARGATE_DOCS_TOOLS")
             or Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share") / "stargate-docs").resolve()

# Where the running API publishes its OpenAPI description. Swashbuckle, the package the API uses
# for that, serves it at /swagger/v1/swagger.json. The port is the one of the "http" profile in
# Properties/launchSettings.json, which is what Visual Studio and "dotnet run" use.
OPENAPI_URL = os.environ.get("STARGATE_OPENAPI_URL") or "http://localhost:5204/swagger/v1/swagger.json"

# The second site, the "dev docs", is made from one long Markdown document. By default
# that is stargate-api-and-patterns.md in the repository. When the file does not exist, the
# second site is left out and everything else is built as usual.
COMPANION_DOC = Path(os.environ.get("STARGATE_COMPANION_DOC") or REPO / "stargate-api-and-patterns.md").resolve()
COMPANION = BUILD / "companion"   # its generated pages (pages/), its map (map.json) and Sphinx's working files

# Folders that are never looked into, wherever they are: compiler output, downloaded packages and
# test results. Folders whose name starts with a dot (.git, .vs) are skipped as well. Listing a
# folder on a Windows drive is slow from WSL, and these hold thousands of files that never matter here.
SKIPPED_FOLDERS = frozenset({"bin", "obj", "node_modules", "TestResults"})

# What makes a project a test project: it uses a test framework, or says so itself.
TEST_PROJECT = re.compile(r"Microsoft\.NET\.Test\.Sdk|<IsTestProject>\s*true|MSTest|xunit|nunit|TUnit", re.I)


def sites(current):
    """The two sites, for the switch at the top of the left column (source/_templates/site-switch.html).

    `current` says which site shows the switch: "docs" (the first site) or "companion" (the
    second). The second site is the folder companion/ inside the first, and every address is
    written from the start page of the site that shows the switch. Without a study document
    there is one site only: the list is empty, and no switch is shown.
    """
    map_file = COMPANION / "map.json"    # tools/gen_companion.py writes it when the study document exists
    if not map_file.is_file():
        return []
    to_docs, to_companion = ("", "companion/") if current == "docs" else ("../", "")
    return [
        {"title": "Stargate docs", "href": to_docs + "index.html", "current": current == "docs",
         "about": "Guides, diagrams, HTTP endpoints and the code reference"},
        {"title": "Dev docs", "href": to_companion + "index.html", "current": current == "companion",
         "about": json.loads(map_file.read_text(encoding="utf-8"))["title"]},
    ]


def repo_walk(start=None, leave_out=()):
    """os.walk over the repository (or one folder of it), without the folders that never matter.

    Left out: SKIPPED_FOLDERS, folders whose name starts with a dot, the folders in `leave_out`,
    and this docs project itself with its build folder (for when it sits inside the repository).
    Gives (folder, file names) pairs, both in alphabetical order.
    """
    closed = {DOCS, BUILD, *leave_out}
    for folder, sub_folders, names in os.walk(start or REPO):
        here = Path(folder)
        sub_folders[:] = sorted(name for name in sub_folders
                                if name not in SKIPPED_FOLDERS and not name.startswith(".") and here / name not in closed)
        yield here, sorted(names)


@functools.lru_cache(maxsize=None)
def project_files():
    """Every .csproj file in the repository, as a tuple. The list is made once per run."""
    return tuple(here / name for here, names in repo_walk() for name in names if name.endswith(".csproj"))


def is_test_project(project_file):
    """True for a project that holds tests (it uses xUnit, NUnit or MSTest, or says IsTestProject)."""
    return bool(TEST_PROJECT.search(Path(project_file).read_text(encoding="utf-8-sig")))


@functools.lru_cache(maxsize=None)
def csharp_projects():
    """The folders of the projects whose code the site documents, such as api.

    That is every folder in the repository with a .csproj file, wherever it is, so a project
    that is added later is picked up by itself. Test projects are left out: a list of test
    methods is not what a code reference is for. STARGATE_DOCS_TESTS=1 puts them in.
    """
    with_tests = os.environ.get("STARGATE_DOCS_TESTS") == "1"
    return tuple(sorted({f.parent for f in project_files() if with_tests or not is_test_project(f)}))


def require_repo():
    """Stop with a clear message when the repository is not where we expect it."""
    if not csharp_projects():
        sys.exit(
            f"Cannot find C# code to document: there is no project (.csproj file) under {REPO}.\n"
            "Say where the repository is: copy local.env.example to local.env and set the\n"
            "STARGATE_REPO line in it. For one run:  STARGATE_REPO=/path/to/stargate-exercise ./build.sh"
        )


@functools.lru_cache(maxsize=None)
def csharp_files():
    """Every hand-written .cs file in those projects, as a tuple. The list is made once per run.

    A folder inside a project that holds a project of its own (a test project next to the
    code, say) belongs to that other project: its files are not counted here a second time.
    """
    project_folders = {f.parent for f in project_files()}
    found = []
    for project in csharp_projects():
        for here, names in repo_walk(project, leave_out=project_folders - {project}):
            found += [here / name for name in names if name.endswith(".cs")]
    return tuple(sorted(found))


def documented_types(xml_dir=None):
    """The classes, structs and interfaces Doxygen found, by full name: {"StargateAPI.Controllers.PersonController", ...}.

    Generated pages use it to link a name only when the code reference has an entry for it.
    """
    index = (xml_dir or BUILD / "doxygen" / "xml") / "index.xml"
    if not index.is_file():
        return set()
    return {compound.findtext("name").replace("::", ".")
            for compound in ElementTree.parse(index).getroot().iter("compound")
            if compound.get("kind") in ("class", "struct", "interface")}


def generated_note(script):
    """First line of every generated page. A line that starts with % is a comment in MyST Markdown."""
    return f"% Generated by tools/{script}. Do not edit this file: the next build overwrites it.\n\n"


def write_if_changed(path, text):
    """Write a generated file only when its text is different.

    Sphinx re-reads a page when the file's modified time changes, so leaving
    unchanged files alone keeps rebuilds short. Returns True when it wrote.
    """
    path = Path(path)
    if path.is_file() and path.read_text(encoding="utf-8") == text:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return True


def remove_other_files(folder, keep, pattern="*.md"):
    """Delete generated files from an earlier build that this build did not produce."""
    keep = {Path(p).resolve() for p in keep}
    for old in Path(folder).rglob(pattern):
        if old.resolve() not in keep:
            old.unlink()
