"""Checks the links from the first site into the dev docs (source/_ext/stargate_docs.py):
a link written as (companion:heading), and the line under a type that names the parts of the
dev docs which mention it.

A page is put together by hand here, the way Sphinx hands it to those functions, so the checks
need no build.

Run with:  ./test.sh
"""
import sys
import types
import unittest

from docutils import nodes
from docutils.utils import new_document
from sphinx import addnodes

from common import SOURCE

sys.path.insert(0, str(SOURCE / "_ext"))
import stargate_docs  # noqa: E402  (source/_ext/stargate_docs.py)

LOGGER = "sphinx.stargate_docs"    # where the messages of that file go


def anchor(page, heading, title, trail=""):
    return {"page": page, "id": heading, "title": title, "trail": trail}


# What tools/gen_companion.py would write down about a small study document.
MAP = {
    "document": "study.md",
    "title": "Sample study guide",
    "pages": {
        "index": {"slugs": ["sample-study-guide"], "first_line": 1},
        "3-patterns": {"slugs": ["3-patterns", "notes"], "first_line": 40},
        "3-patterns/pattern-1-layers": {"slugs": ["pattern-1-layers", "why"], "first_line": 60},
        "appendix": {"slugs": ["appendix", "shoporders", "a", "b", "c", "d", "e"], "first_line": 90},
    },
    "anchors": {
        "sample-study-guide": anchor("index", "sample-study-guide", "Sample study guide"),
        "3-patterns": anchor("3-patterns", "3-patterns", "3. Patterns"),
        "notes": anchor("3-patterns", "notes", "Notes", "3. Patterns"),
        "pattern-1-layers": anchor("3-patterns/pattern-1-layers", "pattern-1-layers", "Pattern 1: Layers", "3. Patterns"),
        "why": anchor("3-patterns/pattern-1-layers", "why", "Why", "3. Patterns › Pattern 1: Layers"),
        "appendix": anchor("appendix", "appendix", "Appendix"),
        "shoporders": anchor("appendix", "shoporders", "Shop.Orders", "Appendix"),
        **{letter: anchor("appendix", letter, letter.upper(), "Appendix") for letter in "abcde"},
    },
    "mentions": {
        # In the order of the document. "gone" is a section that has no heading any more.
        "Shop.Orders.Order": [["3-patterns", 1], ["pattern-1-layers", 2], ["why", 4], ["shoporders", 2], ["gone", 9]],
        "Shop.Orders.Result-1": [["shoporders", 1]],
        "Shop.Orders.Busy": [[slug, 1] for slug in ("3-patterns", "notes", "why", "shoporders", "a", "b", "c", "d", "e")],
    },
}


def app(companion=MAP, backlinks=True):
    """What the functions read from Sphinx's application object."""
    config = types.SimpleNamespace(stargate_companion_map="", stargate_companion_url="companion/",
                                   stargate_companion_backlinks=backlinks)
    return types.SimpleNamespace(config=config, stargate_companion_data=companion)


def page_with_link(address, text="the text"):
    page = new_document("page")
    paragraph = nodes.paragraph("", "Before ")
    paragraph += nodes.reference("", text, refuri=address)
    paragraph += nodes.Text(" after.")
    page += paragraph
    return page, paragraph


class Addresses(unittest.TestCase):
    def test_a_heading_of_the_study_companion_seen_from_a_page(self):
        for docname, slug, address in (
                ("index", "", "companion/index.html"),
                ("index", "3-patterns", "companion/3-patterns.html"),                     # the title of a page
                ("index", "notes", "companion/3-patterns.html#notes"),                    # a heading further down
                ("guide/patterns", "pattern-1-layers", "../companion/3-patterns/pattern-1-layers.html"),
                ("api/Shop.Orders", "why", "../companion/3-patterns/pattern-1-layers.html#why"),
                ("a/b/c", "", "../../companion/index.html")):
            with self.subTest(docname=docname, slug=slug):
                self.assertEqual(stargate_docs.companion_address(app(), docname, MAP, slug), address)


class CompanionLinks(unittest.TestCase):
    def test_a_link_to_a_heading(self):
        for written, address in (
                ("companion:3-patterns", "../companion/3-patterns.html"),
                ("companion:notes", "../companion/3-patterns.html#notes"),
                ("companion:#notes", "../companion/3-patterns.html#notes"),      # with the "#" of a link inside the document
                ("Companion:why", "../companion/3-patterns/pattern-1-layers.html#why"),
                ("companion:", "../companion/index.html")):                     # the start page
            with self.subTest(written=written):
                page, paragraph = page_with_link(written)
                with self.assertNoLogs(LOGGER, level="INFO"):
                    stargate_docs.companion_links(app(), page, "guide/patterns")
                link = paragraph.children[1]
                self.assertIsInstance(link, nodes.reference)
                self.assertEqual(link["refuri"], address)
                self.assertTrue(link["internal"])
                self.assertIn("companion-link", link["classes"])

    def test_other_links_are_left_alone(self):
        for written in ("https://example.org/companion:3-patterns", "mailto:someone@example.org", "#3-patterns"):
            with self.subTest(written=written):
                page, paragraph = page_with_link(written)
                stargate_docs.companion_links(app(), page, "index")
                self.assertEqual(paragraph.children[1]["refuri"], written)
                self.assertNotIn("companion-link", paragraph.children[1]["classes"])

    def test_a_heading_that_does_not_exist_is_a_warning_and_the_text_stays(self):
        page, paragraph = page_with_link("companion:3-paterns")
        with self.assertLogs(LOGGER, level="WARNING") as said:
            stargate_docs.companion_links(app(), page, "guide/patterns")
        self.assertEqual(len(said.records), 1)
        self.assertIn("The link (companion:3-paterns) names a heading that the study document (study.md) does not have",
                      said.records[0].getMessage())
        self.assertEqual((said.records[0].type, said.records[0].subtype), ("stargate", "companion_link"))
        self.assertEqual(list(page.findall(nodes.reference)), [])
        self.assertEqual(paragraph.astext(), "Before the text after.")

    def test_without_the_study_document_the_text_stays_and_it_is_said_once(self):
        without = app(companion=None)
        with self.assertLogs(LOGGER, level="INFO") as said:
            for _ in range(3):
                page, paragraph = page_with_link("companion:3-patterns")
                stargate_docs.companion_links(without, page, "guide/patterns")
                self.assertEqual(list(page.findall(nodes.reference)), [])
                self.assertEqual(paragraph.astext(), "Before the text after.")
        self.assertEqual([record.levelname for record in said.records], ["INFO"])
        self.assertIn("There is no study document", said.records[0].getMessage())


def entry(name, kind="class", content=()):
    """An entry of the code reference, as the C# extension builds it."""
    found = addnodes.desc(domain="cs", objtype=kind)
    found += addnodes.desc_signature("", "", ids=[f"{kind}-{name}"])
    found += addnodes.desc_content("", *content)
    return found


def member(name):
    return entry(name, "function", [nodes.paragraph("", "What it does.")])


def mentions_in(page):
    return [node for node in page.findall(nodes.paragraph) if "companion-mentions" in node["classes"]]


class Mentions(unittest.TestCase):
    def page(self, *entries):
        page = new_document("page")
        page += list(entries)
        return page

    def test_the_line_names_the_sections_that_mention_the_type_most_first(self):
        described = entry("Shop.Orders.Order", content=[nodes.paragraph("", "An order."), member("Shop.Orders.Order.Close")])
        page = self.page(described)
        stargate_docs.companion_mentions(app(), page, "api/Shop.Orders")
        (line,) = mentions_in(page)
        # A heading that is the title of its page stands alone; another one says where it is.
        self.assertEqual(line.astext(), "In the dev docs: 3. Patterns › Pattern 1: Layers › Why · "
                                        "Pattern 1: Layers · Appendix › Shop.Orders · 3. Patterns")
        self.assertEqual([link["refuri"] for link in line.findall(nodes.reference)], [
            "../companion/3-patterns/pattern-1-layers.html#why", "../companion/3-patterns/pattern-1-layers.html",
            "../companion/appendix.html#shoporders", "../companion/3-patterns.html"])
        # After the description of the type, before its members.
        content = described.children[-1]
        self.assertEqual(content.index(line), 1)
        self.assertEqual(mentions_in(self.page(*content.children[2:])), [])     # nothing under the member

    def test_where_the_line_goes(self):
        values = nodes.paragraph("", "Values:")
        members = nodes.container("", classes=["breathe-sectiondef"])
        for tried, content, position in (
                ("an enum: before its values", [nodes.paragraph("", "A state."), values, member("Shop.Orders.Order.Open")], 1),
                ("a class: before the lists of its members", [nodes.paragraph("", "One."), nodes.paragraph("", "Two."), members], 2),
                ("no description", [member("Shop.Orders.Order.Close")], 0),
                ("nothing at all", [], 0)):
            with self.subTest(tried=tried):
                described = entry("Shop.Orders.Order", "enum", content)
                stargate_docs.companion_mentions(app(), self.page(described), "api/Shop.Orders")
                (line,) = mentions_in(described)
                self.assertEqual(described.children[-1].index(line), position)

    def test_a_generic_type_is_found_by_the_name_it_is_filed_under(self):
        page = self.page(entry("Shop.Orders.Result-1", "record"))
        stargate_docs.companion_mentions(app(), page, "api/Shop.Orders")
        self.assertEqual(mentions_in(page)[0].astext(), "In the dev docs: Appendix › Shop.Orders")

    def test_only_the_first_six_are_named(self):
        page = self.page(entry("Shop.Orders.Busy", "interface"))
        stargate_docs.companion_mentions(app(), page, "api/Shop.Orders")
        (line,) = mentions_in(page)
        self.assertEqual(len(list(line.findall(nodes.reference))), stargate_docs.MENTIONS_SHOWN)
        # The same number of mentions everywhere: the order of the document.
        self.assertTrue(line.astext().startswith("In the dev docs: 3. Patterns · 3. Patterns › Notes · "), line.astext())
        self.assertTrue(line.astext().endswith(" · Appendix › B · and 3 more"), line.astext())

    def test_no_line_where_there_is_nothing_to_say(self):
        for tried, described, settings in (
                ("a type that no section mentions", entry("Shop.Orders.Quiet"), {}),
                ("a member", member("Shop.Orders.Order"), {}),
                ("an entry of another language", addnodes.desc("", addnodes.desc_signature("", "", ids=["class-Shop.Orders.Order"]),
                                                               addnodes.desc_content(), domain="py", objtype="class"), {}),
                ("switched off in conf.py", entry("Shop.Orders.Order"), {"backlinks": False}),
                ("no study document", entry("Shop.Orders.Order"), {"companion": None})):
            with self.subTest(tried=tried):
                page = self.page(described)
                stargate_docs.companion_mentions(app(**settings), page, "api/Shop.Orders")
                self.assertEqual(mentions_in(page), [])


if __name__ == "__main__":
    unittest.main()
