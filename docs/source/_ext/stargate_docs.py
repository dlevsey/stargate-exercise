"""Small additions the Stargate docs site needs on top of Sphinx.

1. ``repo-code``: show part of a file from the repository. The file is read every
   time the site is built, so the excerpt can never differ from the real code.
   With ``:block:`` it shows one whole method or class, found by its first line.
2. The names after "Subclassed by" become links.
3. A C# name on a hand-written page that does not exist in the code (renamed,
   removed, mistyped) is reported as a warning. The strict build stops on warnings.
4. C# names in the generated code reference that could not be linked are listed
   once at the end of a build.
5. A record that has a body is labelled "record". Doxygen reports it as a class.
6. The "Contents" list of a code-reference page shows the names that stand in the headings
   of that page. Breathe puts Doxygen's long names there.
7. Links into the second site, the dev docs (tools/gen_companion.py makes its pages):
   a link written as (companion:heading) leads to that heading, and under every type of the
   code reference a line names the parts of the dev docs that mention the type.
"""
import html
import json
import os
import re
from collections import Counter
from pathlib import Path
from urllib.parse import unquote
from xml.etree import ElementTree

from docutils import nodes
from sphinx import addnodes
from sphinx.directives.code import LiteralInclude
from sphinx.util import logging

logger = logging.getLogger(__name__)

LANGUAGES = {
    ".cs": "csharp", ".ts": "typescript", ".js": "javascript", ".html": "html", ".css": "css", ".scss": "scss",
    ".json": "json", ".md": "markdown", ".yml": "yaml", ".yaml": "yaml", ".sh": "bash", ".ps1": "powershell",
    ".csproj": "xml", ".props": "xml", ".targets": "xml", ".xml": "xml", ".slnx": "xml", ".sql": "sql",
}


# Text in which a curly brace does not open or close a block: a // comment, or a string in
# double quotes, single quotes or backticks (all on one line).
NOT_CODE = re.compile(r"""//.*$|"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|`(?:\\.|[^`\\])*`""")


def block_length(lines, start_text):
    """How many lines the block that starts at ``start_text`` has.

    The block runs from the first line that contains ``start_text`` to the line where the curly
    braces opened since then are all closed again. Returns None when no line contains the text,
    and 0 when the braces never close.
    """
    start = None
    depth = 0
    opened = False
    for number, line in enumerate(lines):
        if start is None:
            if start_text not in line:
                continue
            start = number
        for character in NOT_CODE.sub("", line):
            if character == "{":
                depth += 1
                opened = True
            elif character == "}":
                depth -= 1
        if opened and depth <= 0:
            return number - start + 1
    return None if start is None else 0


class RepoCode(LiteralInclude):
    """``literalinclude`` for a file in the repository, named by its path from the repository root.

    Example (in a Markdown page)::

        ```{repo-code} api/Controllers/PersonController.cs
        :start-at: public async Task<IActionResult> GetPeople
        :block:
        ```

    Differences from ``literalinclude``: the path starts at the repository root, the language comes
    from the file extension, the line numbers shown are the real ones, shared indentation is removed,
    and the path is shown above the code. Add ``:no-caption:`` to hide the path.

    ``:block:`` (with ``:start-at:``) shows a whole method, class or other ``{ ... }`` block: it ends
    at the closing brace that matches the first opening brace, so no end marker is needed.
    """

    option_spec = {**LiteralInclude.option_spec,
                   "no-caption": lambda argument: True, "block": lambda argument: True}

    def run(self):
        def problem(text):
            return [self.state.document.reporter.warning(f"repo-code: {text}", line=self.lineno)]

        repo = Path(self.config.stargate_repo).resolve()
        relative = self.arguments[0].strip()
        target = (repo / relative).resolve()
        if not target.is_relative_to(repo) or not target.is_file():
            return problem(f"there is no file {relative!r} in the repository ({repo})")

        if "block" in self.options:
            start_text = self.options.get("start-at")
            if not start_text or {"end-at", "end-before", "lines"} & set(self.options):
                return problem(":block: needs :start-at: and cannot be combined with :end-at:, :end-before: or :lines:")
            length = block_length(target.read_text(encoding="utf-8-sig").splitlines(), start_text)
            if length == 0:
                return problem(f"no closing brace found for the block that starts at {start_text!r} in {relative}")
            if length:  # None: the start text is missing, and literalinclude reports that itself
                self.options["lines"] = f"1-{length}"  # counted from the start-at line

        # A path that starts with "/" is taken from the Sphinx source folder; "../" leads out of it.
        self.arguments[0] = "/" + Path(os.path.relpath(target, self.env.srcdir)).as_posix()
        self.options.setdefault("language", LANGUAGES.get(target.suffix.lower(), "text"))
        self.options.setdefault("dedent", None)  # None = remove the indentation all lines share
        if not {"linenos", "lineno-start", "lineno-match"} & set(self.options):
            self.options["lineno-match"] = True

        result = super().run()
        if not result or not isinstance(result[0], nodes.literal_block):
            return result
        code = result[0]
        text = code.astext().rstrip() + "\n"  # an excerpt that stops before a marker often ends in an empty line
        code.rawsource = text
        code[:] = [nodes.Text(text)]
        first = code.get("highlight_args", {}).get("linenostart", 1)
        # Shown by "python -m sphinx -v": a quick way to see which lines every excerpt picked.
        logger.verbose("repo-code %s:%d-%d", relative, first, first + len(code.astext().splitlines()) - 1)
        if "no-caption" in self.options or "caption" in self.options:
            return result
        wrapper = nodes.container("", literal_block=True, classes=["literal-block-wrapper", "repo-code"])
        wrapper += nodes.caption("", "", nodes.literal(relative, relative))
        wrapper += code
        return [wrapper]


def subclass_links(app, doctree):
    """Breathe writes "Subclassed by A, B" as plain text for C#. Make each name a normal C# reference."""
    for paragraph in list(doctree.findall(nodes.paragraph)):
        if not paragraph.children or not paragraph.children[0].astext().startswith("Subclassed by"):
            continue
        fresh = [nodes.Text("Subclassed by ")]
        for name in paragraph.astext()[len("Subclassed by "):].split(", "):
            fresh.append(addnodes.pending_xref(
                "", nodes.literal(name, name.split(".")[-1]), refdomain="cs", reftype="type",
                reftarget=name.replace("::", "."), refexplicit=True, refwarn=False))
            fresh.append(nodes.Text(", "))
        paragraph.children = []
        paragraph += fresh[:-1]


def unresolved_csharp_name(app, env, node, contnode):
    """Called by Sphinx for every reference that nothing could resolve."""
    if node.get("refdomain") != "cs":
        return None
    target = node.get("reftarget") or contnode.astext()
    if node.get("refdoc", "").startswith("api/"):
        # Generated page: a name from a signature that is neither Stargate's nor a listed .NET name.
        app.env.stargate_unlinked[target] += 1
    else:
        logger.warning(
            "C# name not found in the code: %s (renamed or removed? Check the spelling, or see "
            "'Linking to code' on the 'Using this site' page)", target,
            location=node, type="stargate", subtype="missing_csharp_name")
    return None


def start_counting(app):
    app.env.stargate_unlinked = Counter()


def report_unlinked(app, exception):
    unlinked = getattr(app.env, "stargate_unlinked", None)
    if exception is None and unlinked:
        names = ", ".join(f"{name} ({count})" for name, count in sorted(unlinked.items()))
        logger.info("Names in the code reference without a link (%d). To link a .NET name, add it to "
                    "sphinx_csharp_external_type_map in conf.py: %s", len(unlinked), names)


# "record", "record class" or "record struct" in a declaration such as "public sealed record Name(".
def contents_names(app, doctree):
    """Give every entry of the "Contents" list the name that stands in its heading on the page.

    Breathe names an entry the way Doxygen does: "StargateAPI::Business::Data::Person" for a
    class, "A::Box-1-g" for the generic type Box<T>, "OrderQuery()" for a record without a
    body. The list is narrow, so the end of such a name, the part that tells one type from the
    next, did not fit. This writes "Person", "Box" and "OrderQuery" instead. A method
    keeps its brackets: "Handle()".

    It has to run after Breathe has made the page and before Sphinx collects the entries.
    setup() says how that is arranged.
    """
    for signature in doctree.findall(addnodes.desc_signature):
        name = signature.next_node(addnodes.desc_name)
        if name is None or not signature.get("_toc_name") or signature.parent.get("domain") != "cs":
            continue
        brackets = "()" if signature.parent.get("objtype") == "function" else ""
        signature["_toc_name"] = name.astext() + brackets


RECORD = re.compile(r"^[ \t]*(?:[a-z]+\s+)*?(record(?:\s+(?:class|struct))?)\s+\w")


def records_in_the_xml(xml_dir, repo):
    """The classes and structs in Doxygen's XML that the code declares as records.

    Doxygen has no word for a record, but it says in which file and on which line every type is
    declared, so the declaration itself is looked up. Returns for example
    {"Shop.Orders.OrderSummary": "record"}.
    """
    found, lines = {}, {}
    index = Path(xml_dir) / "index.xml"
    if not index.is_file():
        return found
    for compound in ElementTree.parse(index).getroot().iter("compound"):
        if compound.get("kind") not in ("class", "struct"):
            continue
        definition = ElementTree.parse(Path(xml_dir) / f"{compound.get('refid')}.xml").getroot().find("compounddef")
        location = definition.find("location")
        source_file = Path(repo) / location.get("file", "")
        if source_file not in lines:
            lines[source_file] = source_file.read_text(encoding="utf-8-sig").splitlines() if source_file.is_file() else []
        number = int(location.get("line", "0"))
        declared = RECORD.match(lines[source_file][number - 1]) if 0 < number <= len(lines[source_file]) else None
        if declared:
            # Doxygen names a generic C# type by its number of type parameters: "A::Box-1-g" is A.Box<T>.
            name = re.sub(r"-\d+-g(?=::|$)", "", definition.findtext("compoundname"))
            found[name.replace("::", ".")] = " ".join(declared.group(1).split())
    return found


def label_records(app):
    """Give a record that reached Sphinx as a class or struct its own keyword back.

    A record without a body reaches Sphinx as a method, and the C# extension turns that into a
    record by itself. A record with a body is rewritten for Doxygen (tools/cs_doxygen_filter.py,
    rule 4) and reaches Sphinx as a class or struct. This wraps the method of the C# extension
    that draws a class or struct heading: when the type is a record, the entry is filed as a
    record and the keyword in its heading is replaced.
    """
    from sphinx_csharp import csharp, parser, render   # imported here so the rest works without them

    records = records_in_the_xml(app.config.breathe_projects[app.config.breathe_default_project],
                                 app.config.stargate_repo)
    if not hasattr(csharp.CSharpType, "stargate_original"):
        csharp.CSharpType.stargate_original = csharp.CSharpType.handle_signature

    def handle_signature(self, sig, signode):
        full_name = csharp.CSharpType.stargate_original(self, sig, signode)
        keyword = records.get(parser.remove_arity(full_name))   # "A.Box-1" -> "A.Box"
        if keyword:
            self.change_objtype(signode, "record")
            for annotation in signode.findall(addnodes.desc_annotation):
                if annotation.astext().split() == [self.keyword]:
                    annotation.replace_self(render.keywords(keyword))
                    break
        return full_name

    csharp.CSharpType.handle_signature = handle_signature


# ---- the second site: the dev docs --------------------------------------------------------

TYPE_ENTRIES = ("class", "record", "interface", "enum", "struct")
MENTIONS_SHOWN = 6     # under one type, at most this many parts of the dev docs are named


def companion_map(app):
    """What tools/gen_companion.py wrote down about the dev docs: which heading is on which
    page, and which sections name which C# type. None when that site is not built."""
    if not hasattr(app, "stargate_companion_data"):
        path = Path(app.config.stargate_companion_map) if app.config.stargate_companion_map else None
        app.stargate_companion_data = json.loads(path.read_text(encoding="utf-8")) if path and path.is_file() else None
    return app.stargate_companion_data


def is_page_title(companion, anchor):
    return companion["pages"][anchor["page"]]["slugs"][0] == anchor["id"]


def companion_address(app, docname, companion, slug):
    """The address of a heading of the dev docs, for a link on the page `docname`.
    Without a heading it is the start page."""
    start = "../" * docname.count("/") + app.config.stargate_companion_url
    if not slug:
        return start + "index.html"
    anchor = companion["anchors"][slug]
    return start + anchor["page"] + ".html" + ("" if is_page_title(companion, anchor) else "#" + anchor["id"])


def companion_links(app, doctree, docname):
    """Make [text](companion:heading) a link to that heading of the dev docs.

    The heading is named the way a link inside the study document names it: its text in small
    letters, with "-" for every space and without punctuation. "## 3. Patterns" is
    (companion:3-patterns). "companion:" alone is the start page.

    A heading that the document does not have is a warning, like a C# name that does not exist,
    and the text is shown without a link. The same goes, without a warning, for every such link
    when there is no study document.
    """
    companion = companion_map(app)
    for node in list(doctree.findall(nodes.reference)):
        address = html.unescape(node.get("refuri", ""))     # the Markdown parser stores "&" as "&amp;"
        if not address.lower().startswith("companion:"):
            continue
        slug = unquote(address[len("companion:"):]).lstrip("#")
        if companion is not None and (not slug or slug in companion["anchors"]):
            node["refuri"] = companion_address(app, docname, companion, slug)
            node["internal"] = True
            node["classes"].append("companion-link")
            continue
        if companion is not None:
            logger.warning("The link (%s) names a heading that the study document (%s) does not have (renamed or "
                           "removed? See 'Linking to the dev docs' on the 'Using this site' page)",
                           address, companion["document"], location=node, type="stargate", subtype="companion_link")
        elif not getattr(app, "stargate_companion_told", False):
            app.stargate_companion_told = True
            logger.info("There is no study document, so links written as (companion:...) are shown as plain text.")
        node.replace_self(node.children)


def companion_mentions(app, doctree, docname):
    """Under every type of the code reference, name the parts of the dev docs that mention it.

    tools/gen_companion.py counts, for every section of the study document, how often it names a
    type in code font. The sections that name the type most often come first. To leave these
    lines out, set stargate_companion_backlinks to False in conf.py.
    """
    companion = companion_map(app)
    if companion is None or not app.config.stargate_companion_backlinks:
        return
    for entry in list(doctree.findall(addnodes.desc)):
        if entry.get("domain") != "cs" or entry.get("objtype") not in TYPE_ENTRIES:
            continue
        signature, content = entry.children[0], entry.children[-1]
        if not signature.get("ids") or not isinstance(content, addnodes.desc_content):
            continue
        name = signature["ids"][0].partition("-")[2]    # "class-StargateAPI.Business.Data.Person"
        counted = sorted(companion["mentions"].get(name, []), key=lambda pair: -pair[1])
        sections = [slug for slug, _ in counted if slug in companion["anchors"]]
        if not sections:
            continue
        line = nodes.paragraph(classes=["companion-mentions"])
        line += nodes.inline("", "In the dev docs: ", classes=["companion-mentions-label"])
        for position, slug in enumerate(sections[:MENTIONS_SHOWN]):
            anchor = companion["anchors"][slug]
            # A heading inside a page is named together with the heading above it:
            # "Appendix A: Types declared in this codebase › StargateAPI.Business.Data".
            alone = is_page_title(companion, anchor) or not anchor["trail"]
            label = anchor["title"] if alone else f"{anchor['trail']} › {anchor['title']}"
            if position:
                line += nodes.Text(" · ")
            line += nodes.reference("", label, refuri=companion_address(app, docname, companion, slug),
                                    internal=True, classes=["companion-link"])
        if len(sections) > MENTIONS_SHOWN:
            line += nodes.Text(f" · and {len(sections) - MENTIONS_SHOWN} more")
        # After the description of the type, before the lists of its members or values.
        lists = (index for index, child in enumerate(content.children)
                 if isinstance(child, (addnodes.desc, addnodes.index))
                 or isinstance(child, nodes.container) and "breathe-sectiondef" in child.get("classes", [])
                 or isinstance(child, nodes.paragraph) and child.astext() == "Values:")
        content.insert(next(lists, len(content.children)), line)


# Doxygen names the sections of a type for C++. These are the C# words for them.
SECTION_TITLES = {
    "Public Functions": "Constructors and methods",
    "Public Static Functions": "Static methods",
    "Protected Functions": "Protected methods",
    "Protected Static Functions": "Protected static methods",
    "Private Functions": "Private methods",
    "Private Static Functions": "Private static methods",
    "Public Members": "Fields",
    "Public Static Attributes": "Static fields",
    "Protected Attributes": "Protected fields",
    "Private Members": "Private fields",
    "Private Static Attributes": "Private static fields",
}


def csharp_section_titles(app, doctree):
    """Gives the sections inside a type their C# title ("Public Functions" -> "Constructors and methods")."""
    for title in doctree.findall(nodes.rubric):
        if "breathe-sectiondef-title" in title.get("classes", []) and title.astext() in SECTION_TITLES:
            title.children = [nodes.Text(SECTION_TITLES[title.astext()])]


def setup(app):
    app.connect("doctree-read", csharp_section_titles)
    app.add_config_value("stargate_repo", "", "env", types=[str])
    app.add_config_value("stargate_companion_map", "", "html", types=[str])
    app.add_config_value("stargate_companion_url", "companion/", "html", types=[str])
    app.add_config_value("stargate_companion_backlinks", True, "html", types=[bool])
    app.add_directive("repo-code", RepoCode)
    app.connect("builder-inited", start_counting)
    app.connect("builder-inited", label_records)
    app.connect("doctree-read", subclass_links)
    # Sphinx collects the entries of the "Contents" list in a "doctree-read" handler of its own,
    # with the usual priority of 500. A lower number runs earlier.
    app.connect("doctree-read", contents_names, priority=400)
    app.connect("missing-reference", unresolved_csharp_name, priority=900)  # after every real resolver
    app.connect("build-finished", report_unlinked)
    # Both run while a page is written, so they follow the study document without Sphinx
    # having to read the pages of this site again.
    app.connect("doctree-resolved", companion_links)
    app.connect("doctree-resolved", companion_mentions)
    return {"version": "1.0", "parallel_read_safe": True, "parallel_write_safe": False}
