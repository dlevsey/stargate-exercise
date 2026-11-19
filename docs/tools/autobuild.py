"""Starts sphinx-autobuild, the program behind watch.sh, with one correction.

watch.sh watches some files by their own name: README.md, the study document, Program.cs, every
file the study document links to (tools/watch_paths.py says why). When such a file is removed or
renamed, the watcher finds nothing at its place at every look, about once a second, and reports
"deleted" every time, for as long as the file stays away. sphinx-autobuild starts a build for
every report. So without this script both sites would be built over and over, and the page in
the browser would reload every few seconds, until the file is back or watch.sh is stopped.
(A file inside a watched folder is reported once. Seen with watchfiles 1.3.0 and
sphinx-autobuild 2025.8.25, on 2026-11-17.)

The correction: a report starts a build only when the path looks different from the last time
a report about it started one. "Looks" means: it is there or not and, when it is there, which
file it is, its time stamp and its size. So

- a file that is gone starts one build, however often it is reported;
- its return starts one build, whether the watcher tells of it once ("added") or twice (an old
  "deleted" that is looked at late, during a build for example, and then "added");
- a file that is saved starts a build every time, as before.

It takes the same arguments as "python -m sphinx_autobuild".
"""
import os
import sys

import sphinx_autobuild.__main__
from sphinx_autobuild.filter import IgnoreFilter

GONE = None


def looks(path):
    """What can be seen of a path without reading it; GONE when nothing is there."""
    try:
        found = os.stat(path)
    except OSError:
        return GONE
    return (found.st_ino, found.st_mtime_ns, found.st_size)


class OneBuildForAChange(IgnoreFilter):
    """Says which reported paths start no build: the rules of sphinx-autobuild, and one more."""

    def __init__(self, regular, regex_based):
        super().__init__(regular, regex_based)
        self.built = {}     # path -> how it looked when a report about it last started a build

    def __call__(self, filename, /):
        """True when this report starts no build. The watcher asks once for every report."""
        if super().__call__(filename):
            return True
        now = looks(filename)
        if filename in self.built and self.built[filename] == now:
            return True     # nothing to see that the last build has not seen
        self.built[filename] = now
        return False


def main(arguments):
    # sphinx-autobuild makes its rules from the class named IgnoreFilter in its starting file.
    # tools/test_autobuild.py checks that this name is still there.
    sphinx_autobuild.__main__.IgnoreFilter = OneBuildForAChange
    sphinx_autobuild.__main__.main(arguments)


if __name__ == "__main__":
    main(sys.argv[1:])
