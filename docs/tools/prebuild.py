"""Everything that has to happen before Sphinx runs.

1. Doxygen reads the C# files and writes XML that describes every type and member.
2. Pages are generated from that XML, from the source files and from the API's OpenAPI description.
3. The Markdown files of the repository (its README files) are copied in, so they are part of the site.
4. The study document is cut into the pages of the second site, the dev docs.

build.sh runs this once. watch.sh runs it before every rebuild.
Pass --strict to make a type that Doxygen missed, or a study document that cannot be cut into
pages, an error instead of a note.
"""
import datetime
import filecmp
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from collections import Counter
from pathlib import Path
from xml.etree import ElementTree
from xml.sax.saxutils import escape

import cs_doxygen_filter
import gen_companion
import gen_diagrams
import gen_endpoints
import gen_pages
from common import (BUILD, COMPANION_DOC, DATA, DOCS, OPENAPI_URL, REPO, SOURCE, TOOLS, csharp_files, remove_other_files,
                    repo_walk, require_repo, write_if_changed)

TESTED_DOXYGEN = "1.18.0"
# A type declaration at the start of a line, such as "public class PersonController : ControllerBase".
TYPE_DECLARATION = re.compile(
    r"^[ \t]*((?:(?:public|internal|private|protected|file|static|sealed|abstract|partial|readonly|unsafe|new)\s+)*)"
    r"(?:record\s+(?:class|struct)|class|record|struct|interface|enum)\s+(\w+)", re.M)
# Words the check for missing types takes for a type by mistake, for example "of" when a line
# inside a /* ... */ comment starts with "class of ...". Add the word here to silence the false alarm.
NOT_A_TYPE = set()


def declared_types(texts):
    """How often each type name is declared in the C# texts.

    A partial type is written in parts, often in several files, and is still one type. All parts
    with the same name count as one declaration. (Two different partial types with one name, in
    two namespaces, therefore count as one as well.)
    """
    declared, partial = Counter(), set()
    for text in texts:
        for modifiers, name in TYPE_DECLARATION.findall(text):
            if "partial" in modifiers.split():
                partial.add(name)
            else:
                declared[name] += 1
    declared.update(partial)
    return declared


# ---- 1. C# -> XML ------------------------------------------------------------------------------

def find_doxygen():
    doxygen = os.environ.get("DOXYGEN") or str(TOOLS / "doxygen")
    if not Path(doxygen).is_file():
        sys.exit(f"Doxygen not found at {doxygen}. Run ./setup.sh once (or set DOXYGEN to a Doxygen {TESTED_DOXYGEN} program).")
    version = subprocess.run([doxygen, "--version"], capture_output=True, text=True, check=True).stdout.split()[0]
    if version != TESTED_DOXYGEN:
        print(f"   note: this is Doxygen {version}; the site was tested with {TESTED_DOXYGEN}. "
              "Older versions lose some modern C# types.")
    return doxygen


def quoted(value):
    """A value for a Doxygen settings file, safe when the path has spaces in it."""
    return '"' + str(value).replace("\\", "\\\\").replace('"', '\\"') + '"'


def doxygen_on(doxygen, code, out):
    """Run Doxygen with this project's settings on the C# files under `code`. The XML goes to out/xml.

    Returns Doxygen's exit code and what it said. In its messages the path of the temporary
    copy is cut off, so they read:  api/Program.cs:12: warning: ...
    (The line number is the one in the real file: the rewriting never adds or removes a line.)
    """
    settings = (DOCS / "Doxyfile").read_text(encoding="utf-8") + "\n".join([
        "",
        f"INPUT = {quoted(code)}",
        f"OUTPUT_DIRECTORY = {quoted(out)}",
        f"STRIP_FROM_PATH = {quoted(code)}",   # so the XML says api/Program.cs
        "",
    ])
    # "doxygen -" reads its settings from standard input, so no settings file with machine paths is written.
    result = subprocess.run([str(doxygen), "-"], input=settings, capture_output=True, text=True, cwd=out)
    said = (result.stdout + result.stderr).strip()
    for folder in {str(code), str(Path(code).resolve())}:
        said = said.replace(folder + os.sep, "")
    return result.returncode, said


# ---- 1b. base types keep their type arguments ---------------------------------------------------

BASE_TYPE = re.compile(r"(<basecompoundref\b[^>]*>)([^<]*)(</basecompoundref>)")


def last_part(name):
    """Shop.Common.Entity -> Entity"""
    return re.split(r"\.|::", name.strip())[-1]


def top_level_parts(text):
    """The parts of a list between its commas. A comma inside <>, () or [] does not end a part."""
    parts, depth, start = [], 0, 0
    for position, char in enumerate(text):
        if char in "<([":
            depth += 1
        elif char in ">)]":
            depth -= 1
        elif char == "," and depth == 0:
            parts.append(text[start:position])
            start = position + 1
    parts.append(text[start:])
    return [" ".join(part.split()) for part in parts if part.strip()]


def declared_bases(code, line, name):
    """The base types of the type `name` whose declaration covers `line` of the C# text `code`.

    A list of (name, type arguments) in the order written. The name is its last part only, and
    the type arguments are "" when there are none:
        class CreatePersonHandler : IRequestHandler<CreatePerson, CreatePersonResult>, IDisposable
    gives [("IRequestHandler", "CreatePerson, CreatePersonResult"), ("IDisposable", "")].
    """
    for match in cs_doxygen_filter.DECLARATION.finditer(code):
        first = code.count("\n", 0, match.start()) + 1
        if not first <= line <= first + match.group(0).count("\n"):
            continue
        header = match.group(0)[:-1]
        head = cs_doxygen_filter.HEAD.match(header)
        colon = cs_doxygen_filter.base_list_start(header)
        if not head or head.group("name") != name or colon < 0:
            continue
        bases = []
        for part in top_level_parts(re.split(r"\bwhere\b", header[colon + 1:])[0]):
            part = cs_doxygen_filter.BASE_CALL.sub("", part)   # Base<T>(argument) -> Base<T>
            base, opened, arguments = part.partition("<")
            bases.append((last_part(base), arguments.rstrip()[:-1].strip() if opened else ""))
        return bases
    return []


def with_type_arguments(xml, bases):
    """The text of one of Doxygen's XML files, with the type arguments of its base types put back.

    `bases` is what declared_bases() read from the code. A base type gets its arguments only when
    the XML and the code name it equally often. Otherwise it stays as Doxygen wrote it: a base
    type without its arguments says less, but nothing that is wrong.
    """
    declared = {}
    for name, arguments in bases:
        declared.setdefault(name, []).append(arguments)
    written = Counter(last_part(match.group(2)) for match in BASE_TYPE.finditer(xml))
    waiting = {name: list(arguments) for name, arguments in declared.items() if len(arguments) == written[name]}

    def restored(match):
        opening, text, closing = match.groups()
        queue = waiting.get(last_part(text))
        arguments = queue.pop(0) if queue else ""
        if not arguments:
            return match.group(0)
        return f"{opening}{text}&lt; {escape(arguments)} &gt;{closing}"   # Doxygen's own spelling: Base< T >

    return BASE_TYPE.sub(restored, xml)


def restore_type_arguments(xml_folder, code_folder):
    """Put the type arguments of base types back into Doxygen's XML. Returns how many files changed.

    For C#, Doxygen 1.18 writes the base type of
        class CreatePersonHandler : IRequestHandler<CreatePerson, CreatePersonResult>
    as IRequestHandler. Which request a handler answers is then missing from the page. So the
    arguments are read from the declaration, in the copy of the file that Doxygen read (the XML
    says which file and line), and added to the XML before Sphinx reads it.
    """
    changed = 0
    for xml_file in sorted(Path(xml_folder).glob("*.xml")):
        text = xml_file.read_text(encoding="utf-8")
        if "<basecompoundref" not in text:
            continue
        compound = ElementTree.fromstring(text).find("compounddef")
        location = compound.find("location") if compound is not None else None
        if location is None or not location.get("file") or not location.get("line"):
            continue
        source = Path(code_folder) / location.get("file")
        if not source.is_file():
            continue
        name = last_part(compound.findtext("compoundname", "").split("<")[0])
        bases = declared_bases(source.read_text(encoding="utf-8"), int(location.get("line")), name)
        fresh = with_type_arguments(text, bases)
        if fresh != text:
            xml_file.write_text(fresh, encoding="utf-8", newline="\n")
            changed += 1
    return changed


def run_doxygen():
    """Run Doxygen on a rewritten copy of the C# files and keep the XML files that changed.

    The copy lives in a temporary folder on the Linux side of WSL and is deleted afterwards.
    Doxygen is fast there: reading the same files straight from a Windows drive, through a
    filter program started once per file, took about fifteen times as long.
    """
    doxygen = find_doxygen()
    with tempfile.TemporaryDirectory(prefix="stargate-docs-") as work:
        code, out = Path(work) / "code", Path(work) / "out"
        out.mkdir()
        for source_file in csharp_files():
            copy = code / source_file.relative_to(REPO)
            copy.parent.mkdir(parents=True, exist_ok=True)
            # cs_doxygen_filter.py explains what is rewritten and why. The real file is only read.
            copy.write_text(cs_doxygen_filter.rewrite(source_file.read_text(encoding="utf-8-sig")),
                            encoding="utf-8", newline="\n")
        exit_code, said = doxygen_on(doxygen, code, out)
        if said:
            # A message about a /// comment. It does not stop the build; README.md, "When a build fails", says more.
            print("   Doxygen said:\n      " + said.replace("\n", "\n      "))
        if exit_code != 0 or not (out / "xml" / "index.xml").is_file():
            sys.exit(f"Doxygen failed (exit code {exit_code}).")
        restore_type_arguments(out / "xml", code)

        # Copy only the XML files that changed into the folder Sphinx reads. Sphinx re-reads a page when
        # a file it used has a newer time stamp, so untouched files keep rebuilds short.
        # Doxyfile.xml is a record of the settings above (temporary paths), which nothing reads.
        xml = BUILD / "doxygen" / "xml"
        xml.mkdir(parents=True, exist_ok=True)
        fresh = {f.name for f in (out / "xml").iterdir() if f.is_file() and f.name != "Doxyfile.xml"}
        changed = 0
        for name in sorted(fresh):
            if not (xml / name).is_file() or not filecmp.cmp(out / "xml" / name, xml / name, shallow=False):
                shutil.copyfile(out / "xml" / name, xml / name)
                changed += 1
        for old in xml.iterdir():
            if old.name not in fresh:
                old.unlink()
    return changed


def check_coverage(strict):
    """Compare the types declared in the C# files with the types Doxygen found."""
    declared = declared_types(source_file.read_text(encoding="utf-8-sig") for source_file in csharp_files())
    for word in NOT_A_TYPE:
        declared.pop(word, None)

    found, functions = Counter(), Counter()
    for compound in ElementTree.parse(BUILD / "doxygen" / "xml" / "index.xml").getroot().iter("compound"):
        kind, own_name = compound.get("kind"), compound.findtext("name").split("::")[-1]
        if kind in ("class", "struct", "interface"):
            found[own_name] += 1
        if kind in ("namespace", "class", "struct", "interface"):
            for member in compound.iter("member"):
                name = member.findtext("name").split("<")[0].strip()  # "Result< T >" -> "Result"
                if member.get("kind") == "enum":
                    found[name] += 1
                elif member.get("kind") == "function" and name != own_name:  # not a constructor
                    functions[name] += 1
    # Doxygen describes a record written on one line, such as "record Duty(string Rank, string Title);",
    # as a function with that name. The C# extension for Sphinx shows it as a record.
    for name in declared:
        found[name] += min(functions[name], max(declared[name] - found[name], 0))

    lost = sorted((declared - found).elements())
    print(f"   {sum((declared & found).values())} of {sum(declared.values())} declared types are in the XML")
    if lost:
        print("   MISSING from the code reference (Doxygen did not understand the declaration): " + ", ".join(lost))
        print("   See 'When a type is missing' in README.md.")
        if strict:
            sys.exit("Stopped because types are missing (strict mode).")


# ---- 2. the OpenAPI description -----------------------------------------------------------------

def from_windows(url):
    """Fetch an address with Windows' own curl, for when this script runs in WSL. None when that cannot be done.

    WSL has a network of its own: "localhost" in here is not the "localhost" of Windows. An API
    that Visual Studio runs on Windows is therefore out of reach for this script, but not for a
    Windows program, and WSL can start Windows programs. curl.exe is part of Windows.
    """
    curl = shutil.which("curl.exe")
    if not curl:
        return None
    try:
        result = subprocess.run([curl, "--silent", "--fail", "--connect-timeout", "1", "--max-time", "3", url],
                                capture_output=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return result.stdout.decode("utf-8", errors="replace") if result.returncode == 0 else None


def running_description():
    """The OpenAPI description of the running API. Raises OSError or ValueError when it cannot be had."""
    try:
        with urllib.request.urlopen(OPENAPI_URL, timeout=2) as response:
            text = response.read().decode("utf-8")
    except OSError:
        text = from_windows(OPENAPI_URL)
        if text is None:
            raise
    live = json.loads(text.lstrip("\ufeff"))
    if not isinstance(live, dict) or "paths" not in live:
        raise ValueError("the answer is not an OpenAPI description")
    return live


def refresh_openapi():
    """Replace data/openapi.json with the running API's description, when the API is running."""
    saved = DATA / "openapi.json"
    try:
        live = running_description()
    except (OSError, ValueError) as error:
        reason = getattr(error, "reason", error)
        if not saved.is_file():
            sys.exit(f"No saved OpenAPI description ({saved}) and the API did not answer at {OPENAPI_URL}: {reason}")
        print(f"   API not running at {OPENAPI_URL}; using the saved copy")
        return
    if write_if_changed(saved, json.dumps(live, indent=2, ensure_ascii=False) + "\n"):
        (DATA / "openapi.saved-on.txt").write_text(datetime.date.today().isoformat() + "\n", encoding="utf-8")
        print(f"   the API's description changed; saved a new copy in {saved.relative_to(DOCS)}")
    else:
        print("   the running API matches the saved copy")


# ---- 3. documents that live in the repository ---------------------------------------------------

MARKDOWN_LINK = re.compile(r"(!?)\[([^\]]*)\]\(([^)\s]+)\)")


def repo_documents():
    """The Markdown files of the repository, the ones nearest the top first.

    Every .md file counts, wherever it is, so a document that is added later shows up by itself.
    Not looked into: bin/, obj/, node_modules/ and folders whose name starts with a dot (see
    repo_walk in common.py). The study document is left out, because it has a site of its own.
    """
    found = [here / name for here, names in repo_walk() for name in names if name.lower().endswith(".md")]
    found = [f for f in found if f.resolve() != COMPANION_DOC]
    return sorted(found, key=lambda f: (len(f.relative_to(REPO).parts), f.as_posix()))


def sync_repo_docs():
    """Copy those documents into source/project/, keeping the folder layout so links between them still work."""
    out = SOURCE / "project"
    originals = repo_documents()
    copied = {f.resolve() for f in originals}
    written, titles = [], []

    for original in originals:
        relative = original.relative_to(REPO)
        text = original.read_text(encoding="utf-8-sig").replace("\r\n", "\n")

        def keep_or_flatten(match, folder=original.parent):
            """Links to other copied documents keep working. Links to other repository files become plain text."""
            image, label, target = match.groups()
            path = target.split("#")[0]
            if image or not path or re.match(r"[a-z][a-z0-9+.-]*:", path, re.I) or path.startswith("/"):
                return match.group(0)
            if (folder / path).resolve() in copied:
                return match.group(0)
            try:
                shown = (folder / path).resolve().relative_to(REPO).as_posix()
            except ValueError:
                shown = path
            return f"{label} (`{shown}`)"

        text = MARKDOWN_LINK.sub(keep_or_flatten, text)
        heading = re.search(r"^# +(.+)$", text, re.M)
        title = heading.group(1).strip() if heading else relative.stem
        note = (f"\n```{{admonition}} This page is a file in the repository\n:class: note\n"
                f"It is a copy of `{relative.as_posix()}`, made when the site was built. To change it, edit that file.\n```\n")
        if heading:
            text = text[:heading.end()] + "\n" + note + text[heading.end():]
        else:
            text = f"# {title}\n{note}\n{text}"
        page = out / relative
        write_if_changed(page, f"% Copied from {relative.as_posix()} by tools/prebuild.py. Do not edit this copy.\n\n{text}")
        written.append(page)
        titles.append((relative, title))

    entries = "\n".join(relative.with_suffix("").as_posix() for relative, _ in titles)
    index = out / "index.md"
    write_if_changed(index, (
        "% Generated by tools/prebuild.py. Do not edit this file: the next build overwrites it.\n\n"
        "# From the repository\n\n"
        "These pages are the Markdown files that live in the repository itself, such as the README files with the\n"
        "tasks and the rules of the exercise. They are copied in each time the site is built, so the site and the\n"
        "repository always say the same thing. A Markdown file that is added to the repository shows up here by itself.\n\n"
        "```{toctree}\n:maxdepth: 1\n\n" + entries + "\n```\n"
    ))
    remove_other_files(out, written + [index])
    return len(written)


# ---- the steps, in order ------------------------------------------------------------------------

def step(title, action):
    started = time.monotonic()
    print(f"-- {title}", flush=True)
    result = action()
    print(f"   done in {time.monotonic() - started:.1f} s", flush=True)
    return result


def main():
    strict = "--strict" in sys.argv[1:]
    require_repo()
    print(f"Stargate docs: reading {REPO}", flush=True)
    changed = step("C# files -> XML (Doxygen)", run_doxygen)
    print(f"   {changed} XML files changed")
    check_coverage(strict)
    step("Code reference pages", gen_pages.main)
    step("Diagrams", gen_diagrams.main)
    step("HTTP endpoints", lambda: (refresh_openapi(), gen_endpoints.main()))
    count = step("Markdown files of the repository", sync_repo_docs)
    print(f"   {count} documents copied from the repository")
    # Last, because it needs the C# names that Doxygen found (the first step).
    step("Dev docs: the study document -> pages", lambda: gen_companion.main(strict))


if __name__ == "__main__":
    main()
