"""Cuts the study document into the pages of the second site, the "dev docs".

The study document is one long Markdown file (COMPANION_DOC in common.py) that is written to be
read on its own, for example on GitHub. This step only reads it. It writes

- the pages, into <build folder>/companion/pages, and
- a "map", <build folder>/companion/map.json, that tells the Sphinx extensions of both sites
  where everything went.

How the document is cut into pages
----------------------------------
1. The text up to the first "##" heading is the start page: title, introduction and, when it
   comes first, the table of contents. Every other "##" section is a page.
2. A page larger than LIMIT is cut again, one heading level down. Sub-sections that look like
   chapters get a page each: those with a numbered title ("Pattern 7: ...") and those that have
   sub-sections themselves. Short sections in front of the first chapter stay on the page.
   When none looks like a chapter, every sub-section gets a page. This is repeated until every
   page is small enough or has no headings left to cut at.

A page holds the lines of the document exactly as they are. Only the "#" signs of the headings
change, so that every page starts with one "#" heading. Links are not rewritten here: the
extension source/_ext/stargate_companion.py does that while Sphinx builds, with the map.

What else is worked out here
----------------------------
- A link such as (#2-solution-map) names a heading the way GitHub does. The map
  says on which page each heading is now.
- A link to a file of the repository, such as (api/Program.cs#L6-L21), gets a
  page that shows that file as it is today (pages/files/...).
- A code excerpt that says where it was copied from ("**[`path`](path#L3-L9)** · lines 3–9") is
  compared with the file. When they differ, the page shows a note above the excerpt.
- Which sections name which C# type, and how often: the first site uses that for its links back.

Run by tools/prebuild.py.  On its own:  python tools/gen_companion.py
"""
import json
import re
import shutil
from bisect import bisect_right
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import unquote

import code_names
from common import BUILD, COMPANION, COMPANION_DOC, REPO, remove_other_files, write_if_changed

LIMIT = 150_000        # bytes of Markdown. A larger page is cut again.
NAME_LENGTH = 80       # the longest name of a page file, in characters
LARGEST_FILE = 400_000  # bytes. A larger repository file gets no page of its own.
RESERVED = {"index", "search", "genindex", "files", "objects"}   # names Sphinx and this step use themselves
CONTENTS = {"contents", "table of contents"}
WEB_FILES = {".ts", ".html", ".scss", ".css"}

NUMBERED = re.compile(r"^\w+ \d+[:.]")                           # "Pattern 7: ...", "Step 2. ..."
SCHEME = re.compile(r"^[A-Za-z][A-Za-z0-9+.\-]*:")               # "https:", "mailto:"
LINE_FRAGMENT = re.compile(r"^L(\d+)(?:-L?(\d+))?$")             # "L6", "L6-L21"
CAPTION = re.compile(r"^\*\*\[`([^`]+)`\]\(([^)\s]+)\)\*\* · (lines? .+)$")
RANGE = re.compile(r"(\d+)(?:\s*[–-]\s*(\d+))?")
# A line that stands for lines left out of an excerpt: "// ... lines 7–26 omitted ...".
LEFT_OUT = re.compile(r"^\s*(?://|#|--|<!--|/\*)\s*\.\.\. .+ \.\.\.\s*(?:-->|\*/)?\s*$")
# A table row that gives the number of lines of a file: "| name | [`path`](path) | 22 |".
LINE_COUNT_ROW = re.compile(r"^\|[^|]*\|\s*\[`([^`]+)`\]\(([^)#\s]+)\)\s*\|\s*([\d,]+)\s*\|\s*$")
TYPESCRIPT_TYPE = re.compile(
    r"^\s*export\s+(?:declare\s+)?(?:abstract\s+)?(?:interface|type|class|enum)\s+([A-Za-z_$][\w$]*)", re.M)


class DocumentProblem(Exception):
    """The document cannot be cut into pages. The text says what to change."""


@dataclass(eq=False)
class Section:
    line: int            # the line of its heading, counted from 0
    heading_end: int     # the first line after the heading
    level: int           # 1 for "#", 2 for "##", ...
    title: str           # the heading as plain text
    source: str          # the heading as it is written, without the "#" signs
    slug: str            # how a link names it: (#slug)
    end: int = 0         # the first line after the section
    parent: "Section" = None
    children: list = field(default_factory=list)


@dataclass(eq=False)
class Page:
    docname: str         # the name of the page: "index", "3-patterns/pattern-1-layered-modular-monolith"
    section: Section     # the section it starts with
    start: int           # its first line in the document
    end: int             # the first line that is no longer on it
    children: list = field(default_factory=list)


def markdown_tokens(text):
    """The document as the list of pieces ("tokens") that the Markdown parser of the site sees."""
    from markdown_it.renderer import RendererHTML
    from myst_parser.config.main import MdParserConfig
    from myst_parser.parsers.mdit import create_md_parser

    return create_md_parser(MdParserConfig(), RendererHTML).parse(text)


def plain_text(inline):
    """The text of a heading without its markup: "`Program.cs` and [more](x)" -> "Program.cs and more"."""
    return "".join(child.content if child.type in ("text", "code_inline") else " " if child.type == "softbreak" else ""
                   for child in inline.children or [])


def github_slug(title, used):
    """The name GitHub gives a heading: lower case, punctuation removed, spaces as hyphens.
    A second heading with the same text gets "-1" at the end, a third "-2"."""
    slug = re.sub(r"[^\w\- ]", "", title.strip().lower()).replace(" ", "-") or "section"
    count = used.get(slug, 0)
    used[slug] = count + 1
    return slug if count == 0 else f"{slug}-{count}"


def read_sections(tokens, line_count):
    """Every heading of the document as a Section, in reading order, each knowing its parent
    and children. Also returns {slug: line} for headings inside a list or a quote: those do
    not start a section, but a link may still name them."""
    sections, inside, used = [], {}, {}
    for position, token in enumerate(tokens):
        if token.type != "heading_open":
            continue
        inline = tokens[position + 1]
        title = " ".join(plain_text(inline).split())
        slug = github_slug(title, used)
        if token.level == 0:
            sections.append(Section(token.map[0], token.map[1], int(token.tag[1]), title, inline.content.strip(), slug))
        else:
            inside[slug] = token.map[0]
    open_sections = []
    for section in sections:
        while open_sections and open_sections[-1].level >= section.level:
            open_sections.pop().end = section.line
        if open_sections:
            section.parent = open_sections[-1]
            section.parent.children.append(section)
        open_sections.append(section)
    for section in open_sections:
        section.end = line_count
    return sections, inside


def page_children(section, size, limit, start_page):
    """The sub-sections of `section` that get a page of their own. Always the last ones:
    what stays on the page of `section` is its text up to the first of them."""
    children = section.children
    if start_page:
        first_is_contents = bool(children) and children[0].title.lower() in CONTENTS
        return children[1:] if first_is_contents else children
    if size(section) <= limit or not children:
        return []
    chapters = [bool(NUMBERED.match(child.title)) or bool(child.children) for child in children]
    return children[chapters.index(True):] if any(chapters) else children


def page_name(slug, taken):
    """A file name for the page of a section, different from the names in `taken`."""
    base = slug
    if len(base) > NAME_LENGTH:
        base = base[:NAME_LENGTH + 1].rpartition("-")[0] or base[:NAME_LENGTH]    # cut between two words
    base = base.strip("-_.") or "section"
    name, number = base, 1
    while name in taken:
        number += 1
        name = f"{base}-{number}"
    taken.add(name)
    return name


def plan(title_section, size, limit=LIMIT):
    """Decides which sections start a page. Returns the pages in reading order."""
    pages = []

    def cut(section, docname, start_page=False):
        children = page_children(section, size, limit, start_page)
        page = Page(docname, section, 0 if start_page else section.line, children[0].line if children else section.end)
        pages.append(page)
        taken = set(RESERVED) if start_page else set()
        for child in children:
            name = page_name(child.slug, taken)
            page.children.append(cut(child, name if start_page else f"{docname}/{name}"))
        return page

    cut(title_section, "index", start_page=True)
    return pages


def as_markdown_text(text):
    """`text` with the characters that mean something in Markdown made harmless."""
    return re.sub(r"([\\`*_\[\]<>])", r"\\\1", text)


def lines_label(first, last):
    return f"line {first}" if first == last else f"lines {first}–{last}"


def listing_name(repo_path, taken):
    """The page that shows a repository file: "files/api/Program.cs". A name that
    starts with a dot is rewritten, because web servers tend to hide such files."""
    parts = ["dot-" + part[1:] if part.startswith(".") else part for part in repo_path.split("/")]
    name, number = "files/" + "/".join(parts), 1
    while name.lower() in taken:
        number += 1
        name = f"files/{'/'.join(parts)}-{number}"
    taken.add(name.lower())
    return name


def excerpt_parts(code):
    """The pieces of an excerpt, cut at the lines that stand for lines left out."""
    parts, current = [], []
    for line in code.splitlines():
        if LEFT_OUT.match(line):
            parts.append(current)
            current = []
        else:
            current.append(line.strip())
    parts.append(current)
    return [trimmed for trimmed in (trim(part) for part in parts) if trimmed]


def trim(lines):
    """`lines` without the empty lines at its start and end."""
    lines = list(lines)
    while lines and not lines[0]:
        lines.pop(0)
    while lines and not lines[-1]:
        lines.pop()
    return lines


def build(text, doc_path, repo, names=None, limit=LIMIT):
    """Works everything out for the document `text`, which lies at `doc_path` in the repository `repo`.

    `names` knows the C# names of the code (code_names.CodeNames). Returns (pages, map, notes):
    pages is {file name: text}, map is the dictionary that becomes map.json, and notes are
    lines for the person who runs the build.
    """
    repo, doc_path = Path(repo).resolve(), Path(doc_path)
    doc_folder = doc_path.resolve().parent
    names = names or code_names.CodeNames()
    lines = text.splitlines()
    tokens = markdown_tokens("\n".join(lines) + "\n")
    sections, inside = read_sections(tokens, len(lines))
    notes = []

    titles = [section for section in sections if section.level == 1]
    if len(titles) != 1 or sections[0].level != 1:
        raise DocumentProblem(
            f"{doc_path.name} needs exactly one title: a line that starts with one \"#\", before every other "
            f"heading. It has {len(titles)} such lines"
            + ("" if not titles else f" (lines {', '.join(str(s.line + 1) for s in titles)})") + ".")

    offsets = [0]
    for line in lines:
        offsets.append(offsets[-1] + len(line.encode("utf-8")) + 1)
    pages = plan(sections[0], lambda section: offsets[section.end] - offsets[section.line], limit)

    section_lines = [section.line for section in sections]
    page_lines = [page.start for page in pages]

    def section_at(line):
        return sections[max(bisect_right(section_lines, line) - 1, 0)]

    def page_at(line):
        return pages[bisect_right(page_lines, line) - 1]

    # ---- where every heading went -----------------------------------------------------------------
    anchors = {}
    for section in sections:
        trail = section.parent.title if section.parent and section.parent.level > 1 else ""
        anchors[section.slug] = {"page": page_at(section.line).docname, "id": section.slug,
                                 "title": section.title, "trail": trail}
    for slug, line in inside.items():
        anchors[slug] = dict(anchors[section_at(line).slug])

    # ---- one walk over the document: links, excerpts, names in code font ----------------------------
    targets = {}           # the path of a link as written -> the file's path in the repository, or None
    file_text = {}         # path in the repository -> its lines
    cited = {}             # path in the repository -> {slug of the citing section: [(first, last), ...]}
    web_or_csharp = {}     # slug -> [links to files of the web app, links to C# files]
    page_links = {}        # page -> the headings its own text links to
    mentions = {}          # C# type -> {section that names it: how often}
    code_spans = []        # (slug, text) for every name in code font, kept for the TypeScript rule
    excerpts = []          # (page, number of the code block on that page, caption line, path, ranges, code)
    blocks_on_page = {}
    caption = None
    missing = {}           # the path of a link that leads to no text file -> (its place in notes, [(line, link), ...])

    def target_of(written):
        if written not in targets:
            path = unquote(written)
            target = (repo / path.lstrip("/") if path.startswith("/") else doc_folder / path).resolve()
            found = None
            if target.is_relative_to(repo) and target.is_file() and target.stat().st_size <= LARGEST_FILE:
                raw = target.read_bytes()
                if b"\0" not in raw:
                    try:
                        relative = target.relative_to(repo).as_posix()
                        file_text.setdefault(relative, raw.decode("utf-8-sig").splitlines())
                        found = relative
                    except UnicodeDecodeError:
                        pass
            targets[written] = found
        return targets[written]

    for position, token in enumerate(tokens):
        if token.type in ("fence", "code_block"):
            if token.type == "fence" and token.info.strip().startswith("{"):
                continue    # a directive, not a code block
            page = page_at(token.map[0])
            number = blocks_on_page.get(page.docname, 0)
            blocks_on_page[page.docname] = number + 1
            if caption and token.map[0] - caption[0] <= 6:
                excerpts.append((page, number, *caption, token.content))
            caption = None
            continue
        if token.type != "inline" or not token.map:
            continue
        line = token.map[0]
        section, page = section_at(line), page_at(line)
        in_heading = tokens[position - 1].type == "heading_open"
        found = CAPTION.match(token.content.strip())
        caption = None
        if found:
            ranges = [(int(first), int(last or first)) for first, last in RANGE.findall(found.group(3))]
            # The file is the one the caption links to. The text of the link may be a shorter name for it.
            caption = (line, found.group(2).partition("#")[0], ranges)
        depth = 0
        for child in token.children or []:
            if child.type == "link_open":
                depth += 1
                href = child.attrGet("href") or ""
                if href.startswith("#"):
                    page_links.setdefault(page.docname, set()).add(unquote(href[1:]))
                elif href and not SCHEME.match(href) and not href.startswith("//"):
                    written, _, fragment = href.partition("#")
                    repo_path = target_of(written)
                    if repo_path is None:
                        if written not in missing:
                            missing[written] = (len(notes), [])
                            notes.append(None)      # written below, when every link to the file is known
                        missing[written][1].append((line + 1, href))
                        continue
                    numbers = LINE_FRAGMENT.match(fragment)
                    where = cited.setdefault(repo_path, {}).setdefault(section.slug, [])
                    if numbers:
                        first, last = int(numbers.group(1)), int(numbers.group(2) or numbers.group(1))
                        if (first, last) not in where:
                            where.append((first, last))
                        if last > len(file_text[repo_path]):
                            notes.append(f"line {line + 1}: the link ({href}) points past the end of the file, "
                                         f"which has {len(file_text[repo_path])} lines")
                    kind = Path(repo_path).suffix.lower()
                    if kind in WEB_FILES or kind == ".cs":
                        web_or_csharp.setdefault(section.slug, [0, 0])[0 if kind in WEB_FILES else 1] += 1
            elif child.type == "link_close":
                depth -= 1
            elif child.type == "code_inline" and depth == 0 and not in_heading:
                code_spans.append((section.slug, child.content))

    # A file that is gone is said once, however many links name it.
    for written, (place, links) in missing.items():
        if len(links) == 1:
            notes[place] = (f"line {links[0][0]}: the link ({links[0][1]}) does not lead to a text file in the repository; "
                            "it is shown as plain text")
            continue
        on = sorted({number for number, _ in links})     # the lines of the document that hold those links
        shown = ", ".join(str(number) for number in on[:5]) + (f" and {len(on) - 5} more" if len(on) > 5 else "")
        notes[place] = (f"{'line' if len(on) == 1 else 'lines'} {shown}: {len(links)} links to {unquote(written)} "
                        "do not lead to a text file in the repository; they are shown as plain text")

    # ---- sections about the web app: there, a name such as Order means the TypeScript type ---------
    typescript_names = sorted({name for path, content in file_text.items() if path.endswith(".ts")
                               for name in TYPESCRIPT_TYPE.findall("\n".join(content))})
    typescript_sections = []
    for section in sections:
        counted = section
        while counted and counted.slug not in web_or_csharp:
            counted = counted.parent
        if counted and web_or_csharp[counted.slug][0] > web_or_csharp[counted.slug][1]:
            typescript_sections.append(section.slug)
    typescript = {"names": typescript_names, "sections": typescript_sections}

    for slug, written in code_spans:
        name = names.resolve(written)
        owner = names.owner(name) if name and not code_names.means_typescript(written, slug, typescript) else None
        if owner:
            counted = mentions.setdefault(owner, {})
            counted[slug] = counted.get(slug, 0) + 1

    # ---- excerpts that no longer match their file -----------------------------------------------------
    stale = {}
    numbered = {}          # page -> {number of the code block: its line ranges}, for the line numbers beside it
    for page, number, line, written, ranges, code in excerpts:
        repo_path = target_of(written)
        if repo_path is None:
            continue    # reported above, where the caption's link was read
        numbered.setdefault(page.docname, {})[str(number)] = [list(pair) for pair in ranges]
        content = file_text[repo_path]
        wanted = [trim(row.strip() for row in content[first - 1:last]) for first, last in ranges]
        if excerpt_parts(code) != [part for part in wanted if part]:
            label = " and ".join(lines_label(first, last) for first, last in ranges)
            stale.setdefault(page.docname, {})[str(number)] = (
                f"This excerpt no longer matches {repo_path} ({label}). "
                "The file has changed since this text was written, so line numbers near here may be off too.")
            notes.append(f"line {line + 1}: the excerpt of {repo_path} ({label}) no longer matches the file")
    for number, row in enumerate(lines, start=1):
        counted = LINE_COUNT_ROW.match(row)
        if counted and counted.group(1) == unquote(counted.group(2)) and target_of(counted.group(2)):
            now, then = len(file_text[target_of(counted.group(2))]), int(counted.group(3).replace(",", ""))
            if now != then:
                notes.append(f"line {number}: {counted.group(1)} has {now} lines now; the document says {then}. "
                             "Line numbers in links to it may be off")

    # ---- the pages ------------------------------------------------------------------------------------------
    files = {}
    taken = set()
    for repo_path in sorted(cited):
        files[repo_path] = listing_name(repo_path, taken)

    heading_at = {section.line: section for section in sections}
    written_pages = {}
    for page in pages:
        shift = 0 if page.docname == "index" else page.section.level - 1
        offset = page.start - 2      # line n of the page is line n + offset of the document
        out = [f"% Generated by tools/gen_companion.py from {doc_path.name} (line n here is line n "
               f"{'+' if offset >= 0 else '-'} {abs(offset)} there). Do not edit: the next build overwrites this file.", ""]
        number = page.start
        while number < page.end:
            heading = heading_at.get(number)
            if heading:
                out.append("#" * max(heading.level - shift, 1) + " " + heading.source)
                out += [""] * (heading.heading_end - number - 1)
                number = heading.heading_end
            else:
                out.append(lines[number])
                number += 1
        if page.children:
            # The list of the pages below this one. It is hidden when the text itself links to each of them.
            linked = page_links.get(page.docname, set())
            hidden = all(child.section.slug in linked for child in page.children)
            out += [""] if hidden else ["", "**This part continues on these pages:**", ""]
            out += ["```{toctree}", ":hidden:" if hidden else ":maxdepth: 1", ""]
            out += ["/" + child.docname for child in page.children]
            out += ["```"]
        written_pages[page.docname + ".md"] = "\n".join(out) + "\n"

    by_slug = {section.slug: section for section in sections}
    for repo_path, docname in files.items():
        out = ["---", "orphan: true", "---",
               "% Generated by tools/gen_companion.py. Do not edit: the next build overwrites this file.", "",
               f"# `{repo_path}`", "",
               "This is the file as it is in the repository now. The dev docs links here.", "",
               f"```{{source-listing}} {repo_path}", "```", "",
               "## Where the dev docs points into this file", ""]
        for slug, ranges in cited[repo_path].items():
            section = by_slug[slug]
            trail = section.parent.title + " › " if section.parent and section.parent.level > 1 else ""
            entry = f"- [{as_markdown_text(trail + section.title)}](#{slug})"
            if ranges:
                entry += ": " + ", ".join(
                    f"[{lines_label(first, last)}](#L{first}{'' if first == last else f'-L{last}'})"
                    for first, last in sorted(ranges))
            out.append(entry)
        written_pages[docname + ".md"] = "\n".join(out) + "\n"

    page_sections = {page.docname: [] for page in pages}
    for section in sections:
        page_sections[page_at(section.line).docname].append(section.slug)
    document_map = {
        "title": sections[0].title,
        "document": doc_path.name,
        "pages": {page.docname: {"slugs": page_sections[page.docname], "first_line": page.start + 1}
                  for page in pages},
        "anchors": anchors,
        "links": targets,
        "files": files,
        "stale": stale,
        "excerpts": numbered,
        "typescript": typescript,
        # [section, how often it names the type], in the order of the document
        "mentions": {owner: [[slug, count] for slug, count in counted.items()] for owner, counted in mentions.items()},
    }
    return written_pages, document_map, notes


def main(strict=False):
    """Write the pages and the map. Returns the number of pages.

    A document that cannot be cut into pages stops a strict run (./build.sh). Otherwise the
    problem is printed and the pages of the last run stay, so ./watch.sh carries on.
    """
    pages_folder, map_file = COMPANION / "pages", COMPANION / "map.json"
    if not COMPANION_DOC.is_file():
        shutil.rmtree(pages_folder, ignore_errors=True)
        map_file.unlink(missing_ok=True)
        print(f"   no study document at {COMPANION_DOC}: the dev docs is left out")
        return 0
    names = code_names.from_doxygen(BUILD / "doxygen" / "xml")
    try:
        try:
            text = COMPANION_DOC.read_text(encoding="utf-8-sig")
        except UnicodeDecodeError as problem:
            raise DocumentProblem(f"{COMPANION_DOC.name} is not saved as UTF-8 ({problem}).")
        pages, document_map, notes = build(text, COMPANION_DOC, REPO, names)
    except DocumentProblem as problem:
        if strict:
            raise SystemExit(f"The dev docs cannot be built: {problem}")
        print(f"   WARNING: the dev docs cannot be built, so it stays as it was: {problem}")
        return 0
    changed = sum(write_if_changed(pages_folder / name, content) for name, content in pages.items())
    remove_other_files(pages_folder, [pages_folder / name for name in pages])
    write_if_changed(map_file, json.dumps(document_map, indent=1, ensure_ascii=False, sort_keys=True) + "\n")
    listings = len(document_map["files"])
    print(f"   {len(pages) - listings} pages from {COMPANION_DOC.name}, {listings} pages that show a repository file "
          f"({changed} written)")
    for note in notes:
        print(f"   note: {note}")
    return len(pages)


if __name__ == "__main__":
    main()
