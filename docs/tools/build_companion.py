"""Builds the second site, the dev docs, into the folder companion/ of the first site.

Two things have happened before this runs:

- tools/gen_companion.py has cut the study document into pages (a step of tools/prebuild.py);
- the first site is built. Its list of names (objects.inv) is what turns a class name in the
  dev docs into a link to the code reference.

    python tools/build_companion.py            for ./watch.sh: quick, and it never stops the watcher
    python tools/build_companion.py --strict   for ./build.sh: from nothing, and a warning is an error

Anything else on the command line is handed to Sphinx as it is.

Without --strict, and with nothing for Sphinx on the command line, the build is skipped when
nothing the site is made from has changed. Otherwise every page is written again. A link is worked out while its page is written, so
that is what keeps every link right. It takes about five seconds.
"""
import hashlib
import json
import shutil
import subprocess
import sys
import time

from common import BUILD, COMPANION, DOCS, REPO, SOURCE

OUT = BUILD / "html" / "companion"
STATE = COMPANION / "built.txt"          # what the last build was made from (see made_from)
WARNINGS = COMPANION / "warnings.txt"    # what Sphinx had to say during the last build


def stamp(path):
    """The time a file was saved and its size: enough to see that it was saved again."""
    try:
        found = path.stat()
    except OSError:
        return [str(path), None, None]
    return [str(path), found.st_mtime_ns, found.st_size]


def made_from(document_map):
    """Everything the built site depends on, boiled down to one short text.

    The same text as at the last build means that a new build would write the same pages.
    """
    inventory = BUILD / "html" / "objects.inv"
    own = [path
           for folder, pattern in ((DOCS / "companion", "*.py"), (DOCS / "tools", "*.py"), (SOURCE / "_ext", "*.py"),
                                   (SOURCE / "_static", "*"), (SOURCE / "_templates", "*"))
           for path in sorted(folder.rglob(pattern)) if path.is_file()]
    parts = {
        "pages": [stamp(path) for path in sorted((COMPANION / "pages").rglob("*.md"))],
        "map": stamp(COMPANION / "map.json"),
        "repository files shown": [stamp(REPO / path) for path in sorted(document_map["files"])],
        # The first site writes this file again at every build, so the time it was saved says
        # nothing. Its content changes when a C# name or a page of the first site comes or goes.
        "names of the first site": hashlib.sha256(inventory.read_bytes()).hexdigest() if inventory.is_file() else None,
        "this project": [stamp(path) for path in own],
    }
    return hashlib.sha256(json.dumps(parts, sort_keys=True).encode("utf-8")).hexdigest()


def main(arguments):
    strict = "--strict" in arguments
    for_sphinx = [argument for argument in arguments if argument != "--strict"]
    print("-- Dev docs: pages -> HTML (Sphinx)", flush=True)

    map_file = COMPANION / "map.json"
    if not map_file.is_file():
        shutil.rmtree(OUT, ignore_errors=True)
        STATE.unlink(missing_ok=True)
        print("   there is no study document, so there is no second site", flush=True)
        return 0
    document_map = json.loads(map_file.read_text(encoding="utf-8"))
    count = len(document_map["pages"]) + len(document_map["files"])
    now = made_from(document_map)

    command = [sys.executable, "-m", "sphinx", "-b", "html", "-c", str(DOCS / "companion"),
               "-d", str(COMPANION / "doctrees")]
    if strict:
        # From nothing, as build.sh does for the first site: Sphinx only reports a problem while
        # it reads a page, and it skips pages that did not change since the last build.
        shutil.rmtree(COMPANION / "doctrees", ignore_errors=True)
        shutil.rmtree(OUT, ignore_errors=True)
        STATE.unlink(missing_ok=True)
        WARNINGS.unlink(missing_ok=True)
        command += ["-W", "--keep-going"]    # a warning counts as an error; list every warning, not only the first
    else:
        unchanged = (OUT / "index.html").is_file() and STATE.is_file() and STATE.read_text(encoding="utf-8") == now
        if unchanged and not for_sphinx:    # an option for Sphinx is a wish to see Sphinx run
            print(f"   nothing it is made from has changed ({count} pages)", flush=True)
            said = WARNINGS.read_text(encoding="utf-8", errors="replace").strip() if WARNINGS.is_file() else ""
            if said:
                print("   its last build said:\n" + said, flush=True)
            return 0
        # -a: write every page.  -q: print warnings only.  -w: keep the warnings, to show them again (above).
        command += ["-a", "-q", "-w", str(WARNINGS)]

    started = time.monotonic()
    exit_code = subprocess.run([*command, *for_sphinx, str(COMPANION / "pages"), str(OUT)], cwd=DOCS).returncode
    if exit_code != 0:
        if strict:
            return exit_code
        print("   WARNING: the dev docs could not be built (see above). The pages of its last build stay.",
              flush=True)
        return 0    # the watcher goes on with its next step
    STATE.write_text(now, encoding="utf-8")
    print(f"   {count} pages written in {time.monotonic() - started:.1f} s", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
