"""What the second site, the dev docs, needs on top of Sphinx.

The pages of that site are cut from one long Markdown document by tools/gen_companion.py.
That step also writes a "map" (map.json): which heading is on which page, which repository
files the document links to, and so on. With the map, this extension does six things.

1. Every heading gets the id that links in the document use: the name GitHub gives it.
   "## 2. Solution map" becomes id="2-solution-map".
2. Links are rewritten, because the document was written as one file:
     (#2-solution-map)                        -> the page that heading is on now
     (api/Program.cs#L6-L21) -> the page that shows that file, at those lines
     (docs:guide/start-here)                  -> that page of the code reference (the first site)
     (docs:Person)                            -> the entry of that C# type in the code reference
   A link to a file that no longer exists is shown as plain text.
3. A C# name from the repository in code font, such as `CreatePersonHandler`, becomes a link to its entry in
   the code reference. tools/code_names.py decides what counts as a name.
4. A code excerpt that no longer matches the file it was copied from gets a note above it.
5. The directive ``source-listing`` shows a whole repository file with line numbers.
6. The start page says which file the site is made from, and links to the first site.
"""
import html
import json
import os
import re
from pathlib import Path
from urllib.parse import unquote

from docutils import nodes
from sphinx.directives.code import LiteralInclude
from sphinx.util import logging
from sphinx.util.inventory import InventoryFile
from sphinx.util.osutil import relative_uri

import code_names                      # tools/code_names.py
from gen_companion import LEFT_OUT     # tools/gen_companion.py: a line that stands for lines left out
from stargate_docs import LANGUAGES   # which language a file extension stands for

logger = logging.getLogger(__name__)

SCHEME = re.compile(r"^[A-Za-z][A-Za-z0-9+.\-]*:")     # "https:", "mailto:"
LINES = re.compile(r"^L\d+(?:-L?\d+)?$")               # "L6", "L6-L21": lines of a file
LISTING_LANGUAGES = {
    **LANGUAGES, ".editorconfig": "ini", ".ini": "ini", ".toml": "toml", ".prettierrc": "json",
    ".mjs": "javascript", ".cjs": "javascript", ".tsx": "tsx", ".jsx": "jsx", ".svg": "xml", ".config": "xml",
    ".py": "python", ".cshtml": "html", ".razor": "html", ".dockerfile": "docker", "dockerfile": "docker",
}


class Companion:
    """What every page needs to know: the map, and the names and pages of the code reference."""

    def __init__(self, app):
        self.map = json.loads(Path(app.config.stargate_companion_map).read_text(encoding="utf-8"))
        self.listings = set(self.map["files"].values())
        self.names, self.addresses, self.pages = code_names.CodeNames(), {}, {}
        inventory = Path(app.config.stargate_code_reference) / "objects.inv"
        if not inventory.is_file():
            logger.info("The code reference is not built yet (no %s), so this build has no links to it. "
                        "./build.sh builds both sites in the right order.", inventory)
            return
        with inventory.open("rb") as stream:
            found = InventoryFile.load(stream, "", lambda base, uri: uri)
        self.names, self.addresses = code_names.from_inventory(found)
        self.pages = {name: item.uri for name, item in found.get("std:doc", {}).items()}

    def code_reference(self, target):
        """Where "docs:<target>" leads in the code reference, or None.

        The target is a page ("guide/start-here", with or without "#heading"), a C# name
        ("Person", "CreatePersonHandler.Handle") or nothing at all: the start page.
        """
        page, _, fragment = target.partition("#")
        page = re.sub(r"\.(md|html)$", "", page.strip("/"))
        if not page:
            return "index.html"
        if page in self.pages:
            return self.pages[page] + ("#" + fragment if fragment else "")
        return self.addresses.get(self.names.resolve(unquote(target)))


def companion(app):
    if not hasattr(app, "stargate_companion"):
        app.stargate_companion = Companion(app)
    return app.stargate_companion


# ---- 1. headings ---------------------------------------------------------------------------------

def heading_ids(app, doctree):
    """Give the headings of a page the ids that the map lists for it, in the same order.

    Sphinx would name a heading after its text in its own way ("2. Solution map" becomes
    "solution-map"). The links in the document use GitHub's way ("2-solution-map"), and a
    link that comes from another page has to find that id.

    It has to run before Sphinx collects the "Contents" list of the page. setup() arranges that.
    """
    docname = app.env.docname
    page = companion(app).map["pages"].get(docname)
    if page is None:
        return      # a page that shows a repository file
    sections = list(doctree.findall(nodes.section))
    if len(sections) != len(page["slugs"]):
        logger.warning("The page has %d headings, but tools/gen_companion.py counted %d. Links to headings "
                       "of this page may miss.", len(sections), len(page["slugs"]),
                       location=docname, type="stargate", subtype="companion_headings")
        return
    for section, slug in zip(sections, page["slugs"]):
        for old in section["ids"]:
            doctree.ids.pop(old, None)
        for name in section["names"]:
            doctree.nameids[name] = slug
        section["ids"] = [slug]
        doctree.ids[slug] = section
    remembered(app.env)[docname] = list(page["slugs"])


def remembered(env):
    """Page -> the ids its headings got when it was last read. Kept between builds."""
    if not hasattr(env, "stargate_companion_ids"):
        env.stargate_companion_ids = {}
    return env.stargate_companion_ids


def pages_with_new_ids(app, env, added, changed, removed):
    """Pages to read again although their text is the same: those whose headings get other ids.

    That happens when a heading with the same text is added earlier in the document: GitHub
    then names the later one "summary-1" instead of "summary".
    """
    pages = companion(app).map["pages"]
    return [docname for docname, ids in remembered(env).items()
            if docname in pages and docname not in removed and ids != pages[docname]["slugs"]]


def forget_page(app, env, docname):
    remembered(env).pop(docname, None)


def merge_pages(app, env, docnames, other):
    """Needed when Sphinx reads pages with several processes (-j)."""
    for docname in docnames:
        if docname in remembered(other):
            remembered(env)[docname] = remembered(other)[docname]


# ---- 2. links ------------------------------------------------------------------------------------

def page_link(app, docname, target, fragment=""):
    """The address of the page `target`, as seen from the page `docname`."""
    address = relative_uri(app.builder.get_target_uri(docname), app.builder.get_target_uri(target))
    return address + ("#" + fragment if fragment or not address else "")


def rewrite_links(app, doctree, docname, data):
    pages, anchors, files = data.map["pages"], data.map["anchors"], data.map["files"]
    listing = docname in data.listings
    # A line of the page is this many lines further down in the study document.
    offset = pages[docname]["first_line"] - 3 if docname in pages else None
    code_reference = "../" * docname.count("/") + app.config.stargate_code_reference_url

    def warn(node, text, *arguments):
        where = f" (near line {node.line + offset} of {data.map['document']})" if node.line and offset is not None else ""
        logger.warning(text + where, *arguments, location=node, type="stargate", subtype="companion_link")

    for node in list(doctree.findall(nodes.reference)):
        if node.get("internal") or "refuri" not in node:
            continue
        # The Markdown parser stores the address the way it would stand in HTML ("&" as "&amp;").
        address = html.unescape(node["refuri"])
        if address.startswith("#"):
            fragment = unquote(address[1:])
            node["internal"] = True
            if listing and LINES.match(fragment):
                continue                                        # a line of the file on this page
            anchor = anchors.get(fragment)
            if anchor is None:
                warn(node, "The link (%s) names a heading that the study document does not have", address)
                continue
            first = pages[anchor["page"]]["slugs"][0]           # the title of that page
            same_page = anchor["page"] == docname
            node["refuri"] = page_link(app, docname, anchor["page"], anchor["id"] if same_page or anchor["id"] != first else "")
        elif address.lower().startswith("docs:"):
            found = data.code_reference(address[5:])
            if found is None:
                if data.addresses:
                    warn(node, "The link (%s) names no page and no C# name of the code reference", address)
                node.replace_self(node.children)
                continue
            node["refuri"], node["internal"] = code_reference + found, True
            node["classes"].append("code-reference")
        elif SCHEME.match(address) or address.startswith("//"):
            node["refuri"] = address                            # another site: left as it is
        else:
            written, _, fragment = address.partition("#")
            repo_path = data.map["links"].get(written)
            if repo_path is None:
                node.replace_self(node.children)                # no such file any more: plain text
                continue
            node["refuri"] = page_link(app, docname, files[repo_path], fragment if LINES.match(fragment) else "")
            node["internal"] = True
            node["classes"].append("source-link")


# ---- 3. names in code font -----------------------------------------------------------------------

def inside(node, kinds):
    parent = node.parent
    while parent is not None:
        if isinstance(parent, kinds):
            return parent
        parent = parent.parent
    return None


def link_code_names(app, doctree, docname, data):
    if not data.addresses or docname not in data.map["pages"]:
        return
    code_reference = "../" * docname.count("/") + app.config.stargate_code_reference_url
    for node in list(doctree.findall(nodes.literal)):
        if inside(node, (nodes.reference, nodes.title)):
            continue    # already a link, or part of a heading
        text = node.astext()
        address = data.addresses.get(data.names.resolve(text))
        if address is None:
            continue
        section = inside(node, nodes.section)
        if code_names.means_typescript(text, section["ids"][0] if section is not None else "", data.map["typescript"]):
            continue
        link = nodes.reference("", "", refuri=code_reference + address, internal=True, classes=["code-reference"])
        node.replace_self(link)
        link += node


# ---- 4. excerpts that no longer match ----------------------------------------------------------------

def mark_stale_excerpts(doctree, docname, data):
    stale = data.map["stale"].get(docname)
    if not stale:
        return
    blocks = list(doctree.findall(nodes.literal_block))
    for number, text in stale.items():
        if int(number) >= len(blocks):
            continue
        block = blocks[int(number)]
        if isinstance(block.parent, nodes.container) and block.parent.get("literal_block"):
            block = block.parent                                # a code block with a caption
        note = nodes.warning("", nodes.paragraph("", text), classes=["stale-excerpt"])
        block.parent.insert(block.parent.index(block), note)


# ---- 4b. line numbers beside an excerpt ---------------------------------------------------------------

def number_excerpts(doctree, docname, data):
    """Puts the line numbers of the real file beside every excerpt that says where it was copied from.

    The caption above an excerpt names the lines ("lines 22–43"), and the map carries them. An
    excerpt that leaves lines out ("// ... lines 49–72 omitted ...") is shown as one box per piece,
    because the numbers in one box can only count on without a gap. When the pieces of an excerpt
    do not fit the caption (the text was edited by hand), it keeps its look without numbers
    instead of showing wrong ones.
    """
    wanted = data.map.get("excerpts", {}).get(docname)
    if not wanted:
        return
    blocks = list(doctree.findall(nodes.literal_block))
    for number, ranges in wanted.items():
        if int(number) >= len(blocks):
            continue
        block = blocks[int(number)]
        pieces, gaps, current = [], [], []
        for line in block.astext().split("\n"):
            if LEFT_OUT.match(line):
                pieces.append(current)
                gaps.append(line.strip())
                current = []
            else:
                current.append(line)
        pieces.append(current)
        if len(pieces) != len(ranges):
            continue
        shown = []
        for position, (piece, (first, _)) in enumerate(zip(pieces, ranges)):
            while piece and not piece[0].strip():       # empty lines around a gap belong to no line of the file
                piece = piece[1:]
            while piece and not piece[-1].strip():
                piece = piece[:-1]
            if position:
                shown.append(nodes.paragraph("", gaps[position - 1].strip("/#-<>!* "), classes=["excerpt-gap"]))
            text = "\n".join(piece)
            part = nodes.literal_block(text, text, language=block.get("language", "text"), classes=list(block.get("classes", [])))
            part["linenos"] = True
            part["highlight_args"] = {"linenostart": first}
            shown.append(part)
        block.replace_self(shown)


# ---- 5. a whole file ---------------------------------------------------------------------------------

class SourceListing(LiteralInclude):
    """Shows a whole file of the repository, named by its path from the repository root::

        ```{source-listing} api/Program.cs
        ```

    Every line gets a number and can be linked to: "#L6" is line 6 and "#L6-L21" is lines 6
    to 21. (The page script source-lines.js marks those lines and scrolls to them.)
    """

    def run(self):
        repo = Path(self.config.stargate_repo).resolve()
        relative = self.arguments[0].strip()
        target = (repo / relative).resolve()
        if not target.is_relative_to(repo) or not target.is_file():
            return [self.state.document.reporter.warning(
                f"source-listing: there is no file {relative!r} in the repository ({repo})", line=self.lineno)]
        # A path that starts with "/" is taken from the Sphinx source folder; "../" leads out of it.
        self.arguments[0] = "/" + Path(os.path.relpath(target, self.env.srcdir)).as_posix()
        language = LISTING_LANGUAGES.get(target.suffix.lower()) or LISTING_LANGUAGES.get(target.name.lower(), "text")
        self.options.setdefault("language", language)
        self.options["linenos"] = True
        self.options["force"] = True    # colour what can be coloured, also when a file has syntax the highlighter does not know
        result = super().run()
        if result and isinstance(result[0], nodes.literal_block):
            # Pygments wraps every line in <span id="L-6">, which the links and the popups find.
            result[0].setdefault("highlight_args", {})["linespans"] = "L"
            result[0]["classes"].append("source-listing")
        return result


# ---- 6. the start page ---------------------------------------------------------------------------

def start_page_note(doctree, docname, data):
    """Under the title of the start page: which file this site is made from, and where the other site is.

    The note is added here and not to the page file, so the lines of a page stay the lines of
    the study document.
    """
    if docname != "index":
        return
    title = next(iter(doctree.findall(nodes.title)), None)
    if title is None:
        return
    document = data.map["document"]
    text = nodes.paragraph()
    text += nodes.Text("This site is made from ")
    text += nodes.literal(document, document)
    text += nodes.Text(" each time the docs are built. To change a page, edit that file. A name of one of "
                       "Stargate's own classes leads to its entry in the code reference, which is on the other site: ")
    text += nodes.reference("", "Stargate docs", refuri="docs:")    # rewrite_links() fills in the address
    text += nodes.Text(".")
    note = nodes.admonition("", nodes.title("", "These pages are one file"), text, classes=["note", "companion-origin"])
    title.parent.insert(title.parent.index(title) + 1, note)


def resolve_page(app, doctree, docname):
    """Runs for every page just before it is written."""
    data = companion(app)
    start_page_note(doctree, docname, data)    # first: its link is filled in by the next step
    rewrite_links(app, doctree, docname, data)
    link_code_names(app, doctree, docname, data)
    mark_stale_excerpts(doctree, docname, data)
    number_excerpts(doctree, docname, data)    # after the notes: it may put several boxes where one was


def setup(app):
    if "stargate_repo" not in app.config:
        app.add_config_value("stargate_repo", "", "env", types=[str])
    app.add_config_value("stargate_companion_map", "", "env", types=[str])
    app.add_config_value("stargate_code_reference", "", "html", types=[str])
    app.add_config_value("stargate_code_reference_url", "../", "html", types=[str])
    app.add_directive("source-listing", SourceListing)
    # Sphinx collects the "Contents" list of a page in a "doctree-read" handler of its own, with
    # the usual priority of 500. A lower number runs earlier.
    app.connect("doctree-read", heading_ids, priority=400)
    app.connect("env-get-outdated", pages_with_new_ids)
    app.connect("env-purge-doc", forget_page)
    app.connect("env-merge-info", merge_pages)
    app.connect("doctree-resolved", resolve_page)
    return {"version": "1.0", "parallel_read_safe": True, "parallel_write_safe": True}
