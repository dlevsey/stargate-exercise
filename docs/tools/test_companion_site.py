"""Builds a small study document into a real site and looks at the pages that come out.

The other checks try one step each. This one runs the steps the way ./build.sh and ./watch.sh
run them, on a sample that has one of everything: links between pages, links to repository
files, links to the first site, class names in code font, an excerpt that no longer matches.
Of the first site it only needs the list of names (objects.inv), which is written by hand here.

It runs Sphinx a handful of times, which takes about four seconds.

Run with:  ./test.sh
"""
import os
import subprocess
import sys
import tempfile
import unittest
import zlib
from html.parser import HTMLParser
from pathlib import Path

from common import DOCS

STUDY = """\
# Sample study guide

Start with [the map](#1-map), [the patterns](#2-patterns) or [a detail](#details).

## 1. Map

`Order` is a class and `Order.Close()` is its method. `Result<Order>` is generic, and
`NotAName` is nothing the code has.

See [the program](src/App/Program.cs#L2-L3), [a file that is gone](src/App/Gone.cs#L1),
[the security guide](docs:guide/security), [the entry of the class](docs:Order) and
[a search](https://example.org/find?a=1&b=2).

**[`src/App/Program.cs`](src/App/Program.cs#L2-L3)** · lines 2–3

```csharp
line 2
line three
```

### Details

More text. Back to [the map](#1-map).

## 2. Patterns

Text of patterns. [Details](#details) are on another page.

## 3. Front end

In the web app `Order` is a TypeScript type: see [the model](src/Web/order.ts).
"""
PROGRAM = "line 1\nline 2\nline 3\nline 4\nline 5\n"
MODEL = "export interface Order {\n  id: string;\n}\n"

# The names the first site would list: name, kind, priority, address, shown as ("-" is the name itself).
FIRST_SITE = [
    ("Shop.Orders", "cs:namespace", 1, "api/Shop.Orders.html#namespace-Shop.Orders", "-"),
    ("Shop.Orders.Order", "cs:class", 1, "api/Shop.Orders.html#class-Shop.Orders.Order", "-"),
    ("Shop.Orders.Order.Close", "cs:function", 1, "api/Shop.Orders.html#function-Shop.Orders.Order.Close", "-"),
    ("Shop.Orders.Result-1", "cs:record", 1, "api/Shop.Orders.html#record-Shop.Orders.Result-1", "Result<T>"),
    ("guide/security", "std:doc", -1, "guide/security.html", "Security"),
    ("index", "std:doc", -1, "index.html", "Sample docs"),
]


class Links(HTMLParser):
    """Collects the links of a piece of HTML: (text, address, classes)."""

    def __init__(self):
        super().__init__()
        self.found, self.current = [], None

    def handle_starttag(self, tag, attributes):
        if tag == "a":
            attributes = dict(attributes)
            self.current = ["", attributes.get("href"), (attributes.get("class") or "").split()]

    def handle_data(self, data):
        if self.current is not None:
            self.current[0] += data

    def handle_endtag(self, tag):
        if tag == "a" and self.current is not None:
            self.found.append((self.current[0].strip(), self.current[1], self.current[2]))
            self.current = None


def links(html_text):
    parser = Links()
    parser.feed(html_text)
    return parser.found


def article(page):
    """The text of a page without the columns left and right of it."""
    return page[page.index("<article"):page.index("</article>")]


class Sample:
    """A folder with a small repository and a build folder, and the tools run on them."""

    def __init__(self):
        self.folder = tempfile.TemporaryDirectory(prefix="stargate-docs-test-")
        root = Path(self.folder.name)
        self.repo, self.build = root / "repo", root / "build"
        self.document = self.repo / "study.md"
        self.site = self.build / "html" / "companion"
        self.environment = {**os.environ, "STARGATE_REPO": str(self.repo), "STARGATE_DOCS_BUILD": str(self.build),
                            "STARGATE_COMPANION_DOC": str(self.document), "PYTHONDONTWRITEBYTECODE": "1"}
        for name, text in (("study.md", STUDY), ("src/App/Program.cs", PROGRAM), ("src/Web/order.ts", MODEL)):
            path = self.repo / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        lines = "".join(f"{name} {kind} {priority} {address} {shown}\n" for name, kind, priority, address, shown in FIRST_SITE)
        (self.build / "html").mkdir(parents=True)
        (self.build / "html" / "objects.inv").write_bytes(
            b"# Sphinx inventory version 2\n# Project: Sample\n# Version: \n"
            b"# The remainder of this file is compressed using zlib.\n" + zlib.compress(lines.encode("utf-8")))

    def run(self, script, *arguments):
        """Run one of the tools. Returns (exit code, everything it printed)."""
        done = subprocess.run([sys.executable, str(DOCS / "tools" / script), *arguments], cwd=DOCS, env=self.environment,
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")
        return done.returncode, done.stdout

    def page(self, name):
        return (self.site / name).read_text(encoding="utf-8")


class BuiltSite(unittest.TestCase):
    """One strict build, as ./build.sh does it, and then a look at its pages."""

    @classmethod
    def setUpClass(cls):
        sample = Sample()
        cls.addClassCleanup(sample.folder.cleanup)
        cls.cut = sample.run("gen_companion.py")
        cls.built = sample.run("build_companion.py", "--strict")
        cls.pages = {path.relative_to(sample.site).as_posix(): path.read_text(encoding="utf-8")
                     for path in sample.site.rglob("*.html")} if sample.site.is_dir() else {}

    def links_in(self, name, whole_page=False):
        """The links of a page: {text: [address, ...]}."""
        self.assertIn(name, self.pages)
        found = {}
        for text, address, _ in links(self.pages[name] if whole_page else article(self.pages[name])):
            found.setdefault(text, []).append(address)
        return found

    def test_the_document_is_cut_and_what_is_wrong_in_it_is_said(self):
        code, said = self.cut
        self.assertEqual(code, 0, said)
        self.assertIn("4 pages from study.md, 2 pages that show a repository file", said)
        self.assertIn("note: line 10: the link (src/App/Gone.cs#L1) does not lead to a text file in the repository", said)
        self.assertIn("note: line 14: the excerpt of src/App/Program.cs (lines 2–3) no longer matches the file", said)

    def test_the_strict_build_passes(self):
        code, said = self.built
        self.assertEqual(code, 0, said)
        self.assertIn("6 pages written in", said)
        self.assertNotIn("WARNING", said)
        self.assertLessEqual({"index.html", "1-map.html", "2-patterns.html", "3-front-end.html",
                              "files/src/App/Program.cs.html", "files/src/Web/order.ts.html"}, set(self.pages))

    def test_a_heading_has_the_id_that_links_in_the_document_use(self):
        page = article(self.pages["1-map.html"])
        self.assertIn('<section id="1-map">', page)
        self.assertIn('<section id="details">', page)

    def test_a_link_to_a_heading_leads_to_the_page_it_is_on_now(self):
        start = self.links_in("index.html")
        self.assertEqual(start["the map"], ["1-map.html"])                 # the title of a page: no "#..."
        self.assertEqual(start["the patterns"], ["2-patterns.html"])
        self.assertEqual(start["a detail"], ["1-map.html#details"])
        self.assertEqual(self.links_in("1-map.html")["the map"], ["#1-map"])   # on the same page
        self.assertEqual(self.links_in("2-patterns.html")["Details"], ["1-map.html#details"])

    def test_a_link_to_a_repository_file_leads_to_the_page_that_shows_it(self):
        found = self.links_in("1-map.html")
        self.assertEqual(found["the program"], ["files/src/App/Program.cs.html#L2-L3"])
        self.assertEqual(found["src/App/Program.cs"], ["files/src/App/Program.cs.html#L2-L3"])     # the caption of the excerpt
        self.assertEqual(self.links_in("3-front-end.html")["the model"], ["files/src/Web/order.ts.html"])
        classes = {text: classes for text, _, classes in links(article(self.pages["1-map.html"]))}
        self.assertIn("source-link", classes["the program"])

    def test_a_link_to_a_file_that_is_gone_is_plain_text(self):
        self.assertNotIn("a file that is gone", self.links_in("1-map.html"))
        self.assertIn("a file that is gone", article(self.pages["1-map.html"]))

    def test_the_page_of_a_file_has_every_line_and_says_who_points_at_it(self):
        page = article(self.pages["files/src/App/Program.cs.html"])
        for number in range(1, 6):
            self.assertIn(f'id="L-{number}"', page)
        self.assertNotIn('id="L-6"', page)
        found = self.links_in("files/src/App/Program.cs.html")
        self.assertEqual(found["1. Map"], ["../../../1-map.html"])
        self.assertEqual(found["lines 2–3"], ["#L2-L3"])

    def test_links_to_the_first_site(self):
        found = self.links_in("1-map.html")
        self.assertEqual(found["the security guide"], ["../guide/security.html"])
        self.assertEqual(found["the entry of the class"], ["../api/Shop.Orders.html#class-Shop.Orders.Order"])

    def test_a_class_name_in_code_font_leads_to_the_code_reference(self):
        found = self.links_in("1-map.html")
        self.assertEqual(found["Order"], ["../api/Shop.Orders.html#class-Shop.Orders.Order"])
        self.assertEqual(found["Order.Close()"], ["../api/Shop.Orders.html#function-Shop.Orders.Order.Close"])
        self.assertEqual(found["Result<Order>"], ["../api/Shop.Orders.html#record-Shop.Orders.Result-1"])
        self.assertNotIn("NotAName", found)
        classes = {text: classes for text, _, classes in links(article(self.pages["1-map.html"]))}
        self.assertIn("code-reference", classes["Order"])

    def test_in_a_part_about_the_web_app_the_name_is_the_typescript_type(self):
        self.assertNotIn("Order", self.links_in("3-front-end.html"))
        self.assertIn("Order", article(self.pages["3-front-end.html"]))

    def test_an_address_with_an_ampersand_is_written_once(self):
        self.assertEqual(self.links_in("1-map.html")["a search"], ["https://example.org/find?a=1&b=2"])
        self.assertIn('href="https://example.org/find?a=1&amp;b=2"', self.pages["1-map.html"])

    def test_an_excerpt_that_no_longer_matches_gets_a_note(self):
        page = article(self.pages["1-map.html"])
        self.assertIn("stale-excerpt", page)
        self.assertIn("This excerpt no longer matches src/App/Program.cs (lines 2–3).", page)
        self.assertLess(page.index("This excerpt no longer matches"), page.index("<pre"))     # above the code
        self.assertNotIn("stale-excerpt", self.pages["2-patterns.html"])

    def test_the_start_page_says_what_the_site_is_made_from(self):
        page = article(self.pages["index.html"])
        self.assertIn("These pages are one file", page)
        self.assertIn("companion-origin", page)
        self.assertEqual(self.links_in("index.html")["Stargate docs"], ["../index.html"])
        self.assertNotIn("These pages are one file", self.pages["1-map.html"])

    def test_every_page_has_the_switch_between_the_two_sites(self):
        for name, to_docs, to_companion in (
                ("index.html", "../index.html", "#"),
                ("1-map.html", "../index.html", "index.html"),
                ("files/src/App/Program.cs.html", "../../../../index.html", "../../../index.html")):
            with self.subTest(page=name):
                page = self.pages[name]
                switch = page[page.index('<nav class="site-switch"'):]
                switch = switch[:switch.index("</nav>")]
                self.assertEqual([(text, address) for text, address, _ in links(switch)],
                                 [("Stargate docs", to_docs), ("Dev docs", to_companion)])
                self.assertEqual([text for text, _, classes in links(switch) if "current" in classes], ["Dev docs"])
                self.assertNotIn("site-switch", article(page))


class QuickBuilds(unittest.TestCase):
    """The build that ./watch.sh runs after every change: quick, and it never stops the watcher."""

    def test_what_happens_from_one_change_to_the_next(self):
        sample = Sample()
        self.addCleanup(sample.folder.cleanup)
        state = sample.build / "companion" / "built.txt"

        def step(script, *arguments, expect=0):
            code, said = sample.run(script, *arguments)
            self.assertEqual(code, expect, said)
            return said

        with self.subTest("the first build writes every page"):
            step("gen_companion.py")
            said = step("build_companion.py")
            self.assertIn("6 pages written in", said)
            self.assertNotIn("WARNING", said)
            self.assertTrue(state.is_file())
            self.assertIn("Text of patterns.", sample.page("2-patterns.html"))

        with self.subTest("nothing changed: nothing is built"):
            written = (sample.site / "index.html").stat().st_mtime_ns
            step("gen_companion.py")
            said = step("build_companion.py")
            self.assertIn("nothing it is made from has changed (6 pages)", said)
            self.assertNotIn("its last build said", said)
            self.assertEqual((sample.site / "index.html").stat().st_mtime_ns, written)

        with self.subTest("a repository file that a page shows changed: built again"):
            (sample.repo / "src" / "App" / "Program.cs").write_text(PROGRAM + "line 6\n", encoding="utf-8")
            step("gen_companion.py")
            self.assertIn("6 pages written in", step("build_companion.py"))
            self.assertIn('id="L-6"', sample.page("files/src/App/Program.cs.html"))

        with self.subTest("a link to a heading that does not exist: a warning, and the build goes on"):
            sample.document.write_text(STUDY + "\nSee [nothing](#no-such-heading). A new sentence.\n", encoding="utf-8")
            step("gen_companion.py")
            said = step("build_companion.py")
            self.assertIn("WARNING: The link (#no-such-heading) names a heading that the study document does not have "
                          "(near line 33 of study.md)", said)
            self.assertIn("6 pages written in", said)
            self.assertIn("A new sentence.", sample.page("3-front-end.html"))

        with self.subTest("the warning is shown again while nothing changes"):
            said = step("build_companion.py")
            self.assertIn("nothing it is made from has changed (6 pages)", said)
            self.assertIn("its last build said:", said)
            self.assertIn("The link (#no-such-heading) names a heading", said)

        with self.subTest("Sphinx cannot run: said, and the pages of the last build stay"):
            said = step("build_companion.py", "--an-option-sphinx-does-not-have")
            self.assertIn("WARNING: the dev docs could not be built (see above). The pages of its last build stay.",
                          said)
            self.assertIn("A new sentence.", sample.page("3-front-end.html"))

        with self.subTest("the strict build stops at the warning"):
            said = step("build_companion.py", "--strict", expect=1)
            self.assertIn("The link (#no-such-heading) names a heading that the study document does not have", said)
            self.assertNotIn("pages written in", said)
            self.assertFalse(state.exists())

        with self.subTest("the study document is removed: the second site goes away"):
            sample.document.unlink()
            self.assertIn("the dev docs is left out", step("gen_companion.py"))
            self.assertIn("there is no study document, so there is no second site", step("build_companion.py"))
            self.assertFalse(sample.site.exists())


if __name__ == "__main__":
    unittest.main()
