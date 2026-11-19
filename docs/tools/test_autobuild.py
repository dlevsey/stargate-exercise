"""Checks the correction that tools/autobuild.py makes to the watcher behind watch.sh.

The watcher reports a file that is watched by its own name, and then removed, again at every look
for as long as the file stays away. Without the correction every one of those reports starts a
build. The last two checks here run the real watcher on a small folder, which takes about five
seconds.
"""
import asyncio
import os
import tempfile
import time
import unittest
from pathlib import Path

import sphinx_autobuild.__main__
import sphinx_autobuild.filter
import watchfiles

import autobuild

SECOND = 1_000_000_000      # time stamps of files are counted in billionths of a second


class Reports(unittest.TestCase):
    """What the rules answer when the watcher reports a path: False = build, True = no build."""

    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.folder = Path(folder.name)
        self.page = self.folder / "README.md"
        self.page.write_text("one\n", encoding="utf-8")
        self.no_build = autobuild.OneBuildForAChange([str(self.folder / "out")], [r"\.tmp$"])

    def asked(self, path, times):
        return [self.no_build(str(path)) for _ in range(times)]

    def test_the_first_report_about_a_file_starts_a_build(self):
        self.assertEqual(self.asked(self.page, 1), [False])

    def test_more_reports_start_no_build_while_the_file_looks_the_same(self):
        self.assertEqual(self.asked(self.page, 4), [False, True, True, True])

    def test_a_file_that_was_saved_again_starts_a_build_again(self):
        self.asked(self.page, 2)
        self.page.write_text("one and a half\n", encoding="utf-8")          # another size
        self.assertEqual(self.asked(self.page, 2), [False, True])
        found = self.page.stat()
        os.utime(self.page, ns=(found.st_atime_ns, found.st_mtime_ns + 2 * SECOND))    # the same size, saved later
        self.assertEqual(self.asked(self.page, 2), [False, True])

    def test_a_file_that_is_gone_starts_one_build(self):
        self.page.unlink()
        self.assertEqual(self.asked(self.page, 4), [False, True, True, True])

    def test_a_file_that_was_reported_before_and_is_gone_now_starts_one_build(self):
        self.asked(self.page, 2)
        self.page.unlink()
        self.assertEqual(self.asked(self.page, 4), [False, True, True, True])

    def test_each_file_that_is_gone_starts_one_build(self):
        other = self.folder / "NOTES.md"
        self.page.unlink()
        self.assertEqual([self.no_build(str(path)) for path in (self.page, other, self.page, other)],
                         [False, False, True, True])

    def test_a_file_that_came_back_starts_one_build_and_so_does_its_next_removal(self):
        self.page.unlink()
        self.asked(self.page, 3)
        self.page.write_text("two\n", encoding="utf-8")
        # Two reports can tell of the return: a late one that still says "deleted", and "added".
        self.assertEqual(self.asked(self.page, 2), [False, True])
        self.page.unlink()
        self.assertEqual(self.asked(self.page, 3), [False, True, True])

    def test_a_file_that_came_back_looking_exactly_as_before_starts_a_build(self):
        # As when a file is taken out of the Recycle Bin: the same file, the same time stamp.
        self.asked(self.page, 2)
        before = self.page.stat()
        away = self.folder / "bin.md"
        self.page.rename(away)
        self.assertEqual(self.asked(self.page, 2), [False, True])
        away.rename(self.page)
        after = self.page.stat()
        self.assertEqual((before.st_ino, before.st_mtime_ns, before.st_size), (after.st_ino, after.st_mtime_ns, after.st_size))
        self.assertEqual(self.asked(self.page, 2), [False, True])

    def test_a_folder_that_is_gone_starts_one_build_as_well(self):
        folder = self.folder / "docs"
        folder.mkdir()
        self.assertEqual(self.asked(folder, 1), [False])
        folder.rmdir()
        self.assertEqual(self.asked(folder, 3), [False, True, True])

    def test_the_rules_of_sphinx_autobuild_still_hold(self):
        (self.folder / "out").mkdir()
        built = self.folder / "out" / "index.html"
        built.write_text("<p>page</p>\n", encoding="utf-8")
        temporary = self.folder / "README.md.tmp"
        temporary.write_text("half saved\n", encoding="utf-8")
        for path in (built, self.folder / "out" / "gone.html", temporary, self.folder / "gone.tmp"):
            with self.subTest(path=path.name):
                self.assertEqual(self.asked(path, 2), [True, True])


class TheProgramItCorrects(unittest.TestCase):
    def test_sphinx_autobuild_still_has_the_two_names_this_script_uses(self):
        # autobuild.py puts its own rules in the place of this class and then calls main().
        # Another version of sphinx-autobuild may arrange its files differently: then this check
        # fails, and tools/autobuild.py has to be looked at again.
        self.assertIs(sphinx_autobuild.__main__.IgnoreFilter, sphinx_autobuild.filter.IgnoreFilter)
        self.assertTrue(callable(sphinx_autobuild.__main__.main))
        self.assertTrue(issubclass(autobuild.OneBuildForAChange, sphinx_autobuild.filter.IgnoreFilter))


class TheRealWatcher(unittest.TestCase):
    """A file that is watched by its own name is removed and put back, with the real watcher."""

    def builds(self, look_every, build_takes, back_after):
        """Runs the watcher and returns (the builds that the removal started, the builds in all).

        look_every: milliseconds between two looks of the watcher at the file.
        build_takes: seconds. No report is looked at during a build, as in sphinx-autobuild.
        back_after: seconds from the start of the first build until the file is put back.
        """
        with tempfile.TemporaryDirectory() as folder:
            page = Path(folder) / "README.md"
            page.write_text("one\n", encoding="utf-8")
            no_build = autobuild.OneBuildForAChange([], [])
            builds = []

            async def watch():
                # The same call as in sphinx_autobuild/server.py.
                async for changes in watchfiles.awatch(page, watch_filter=lambda _, path: not no_build(path),
                                                       force_polling=True, poll_delay_ms=look_every):
                    builds.append(sorted({Path(path).name for _, path in changes}))
                    await asyncio.sleep(build_takes)

            async def builds_reach(count):
                end = time.monotonic() + 10
                while len(builds) < count and time.monotonic() < end:
                    await asyncio.sleep(0.01)

            async def steps():
                watcher = asyncio.create_task(watch())
                await asyncio.sleep(look_every / 1000 + 0.3)    # the watcher has had its first look
                page.unlink()
                await builds_reach(1)
                await asyncio.sleep(back_after)
                while_gone = len(builds)
                page.write_text("two\n", encoding="utf-8")
                await builds_reach(2)
                await asyncio.sleep(build_takes + 2 * look_every / 1000 + 0.3)  # would another build start?
                watcher.cancel()
                return while_gone

            while_gone = asyncio.run(steps())
        return while_gone, builds

    def test_a_removed_file_starts_one_build_and_its_return_one_more(self):
        # 0.8 seconds without the file are sixteen looks, and every look reports "deleted".
        while_gone, builds = self.builds(look_every=50, build_takes=0, back_after=0.8)
        self.assertEqual(while_gone, 1)
        self.assertEqual(builds, [["README.md"], ["README.md"]])

    def test_a_file_that_returns_during_the_build_of_its_removal_starts_one_more_build(self):
        # The reports made during a build are looked at when it ends. Here the file is back by
        # then, so the old report ("deleted") starts the build of the return. The watcher sees
        # the file at its next look and reports "added", which must not start another build.
        #   0.0 s  first build (the removal)     0.4 s  look: "deleted"      0.5 s  the file is back
        #   0.6 s  the build ends                0.8 s  look: "added"
        while_gone, builds = self.builds(look_every=400, build_takes=0.6, back_after=0.5)
        self.assertEqual(while_gone, 1)
        self.assertEqual(builds, [["README.md"], ["README.md"]])


if __name__ == "__main__":
    unittest.main()
