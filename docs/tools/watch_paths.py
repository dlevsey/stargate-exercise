"""Prints what watch.sh watches besides source/, one path per line.

WSL is not told when a program on Windows saves a file, so the watcher has to look at the
time stamp of every file under the folders it watches, about once a second. bin/ and obj/
hold hundreds of files that never matter here, and node_modules/ holds tens of thousands,
so the repository is not watched as a whole. The list names the useful places one by one:

- in each C# project: every folder except bin/ and obj/, and the .cs and .csproj files next to them;
- the Markdown files of the repository (its README files);
- every other file that a page shows with ``repo-code``;
- the study document, and every other file of the repository it links to (the second site
  shows each of them on a page).

A file or folder that is created later inside a listed folder is noticed. A new folder
directly inside a C# project is not, and neither is a new project or a new Markdown file
outside the listed folders: start watch.sh again after adding one.
"""
import re
from urllib.parse import unquote

from common import COMPANION_DOC, DOCS, REPO, SKIPPED_FOLDERS, SOURCE, csharp_projects, repo_walk, require_repo

GENERATED = ("api", "diagrams", "http", "project")   # folders under source/ that prebuild.py fills
REPO_CODE = re.compile(r"^[ \t]*`{3,}\{repo-code\}[ \t]+(\S.*?)[ \t]*$", re.M)
LINK = re.compile(r"\]\(([^)\s#]+)")                  # the address of a Markdown link, up to "#"
SCHEME = re.compile(r"^[A-Za-z][A-Za-z0-9+.\-]*:")    # "https:", "mailto:"


def study_document_files():
    """The study document and the files of the repository it links to.

    A quick look for links is enough here. tools/gen_companion.py reads the document properly,
    but it cannot run before the first build, and watch.sh needs the list before that.
    """
    if not COMPANION_DOC.is_file():
        return []
    text = COMPANION_DOC.read_text(encoding="utf-8-sig", errors="replace")
    repo = REPO.resolve()
    wanted = [COMPANION_DOC]
    for written in sorted(set(LINK.findall(text))):
        if SCHEME.match(written) or written.startswith("//"):
            continue    # another site
        target = (COMPANION_DOC.parent / unquote(written)).resolve()
        if target.is_relative_to(repo) and target.is_file():
            wanted.append(target)
    return wanted


def watch_paths():
    wanted = []
    for project in csharp_projects():
        for entry in sorted(project.iterdir()):
            if entry == DOCS:
                continue    # this docs project sits inside a C# project: watching it would rebuild without end
            if entry.is_dir() and entry.name not in SKIPPED_FOLDERS and not entry.name.startswith("."):
                wanted.append(entry)
            elif entry.suffix in (".cs", ".csproj"):
                wanted.append(entry)
    # The Markdown files that tools/prebuild.py copies into the site (repo_documents there).
    wanted += [here / name for here, names in repo_walk() for name in names if name.lower().endswith(".md")]

    for page in sorted(SOURCE.rglob("*.md")):
        if page.relative_to(SOURCE).parts[0] not in GENERATED:
            wanted += [REPO / shown for shown in REPO_CODE.findall(page.read_text(encoding="utf-8"))]
    wanted += study_document_files()

    existing = sorted({path.resolve() for path in wanted if path.exists()})
    # Leave out what a listed folder already covers.
    return [path for path in existing if not any(other in path.parents for other in existing)]


if __name__ == "__main__":
    require_repo()
    print("\n".join(str(path) for path in watch_paths()))
