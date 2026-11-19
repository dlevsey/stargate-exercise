"""Saves popup text for the .NET names the sites link to.

A link to learn.microsoft.com points at another website, so a hover popup cannot
load it. This script reads the XML documentation files that ship with the .NET
SDK and with NuGet packages (the same text Visual Studio shows in IntelliSense)
and saves small JSON files into the built sites. No network.

Three kinds of address get a popup:

    .../dotnet/api/system.guid                    a type: its summary and a list of its members
    .../dotnet/api/system.guid.newguid            a member: every overload with its parameters
    .../dotnet/api/system.collections.generic     a namespace: a list of its types

An address may go on with "?view=net-10.0" and with "#...", the name Learn gives to one
overload on the page of a member. The popup then shows that overload only.

Both sites get their own files: the Stargate docs, and the dev docs when it is built.

Run it after Sphinx has written the HTML, because it reads the pages to see
which .NET names they link to. build.sh and watch.sh both do that.
"""
import datetime
import hashlib
import html
import json
import os
import re
import shutil
import sys
from pathlib import Path

from common import BUILD, REPO, csharp_projects

PREFIX = "https://learn.microsoft.com/en-us/dotnet/api/"
LEARN_LINK = re.compile(r'href="' + re.escape(PREFIX) + r'([^"]*)"')
MEMBER = re.compile(r'<member name="([^"]+)">(.*?)</member>', re.S)
KINDS = [("M", "Methods"), ("P", "Properties"), ("F", "Fields"), ("E", "Events")]
KIND_OF_MEMBER = {"M": "Method", "P": "Property", "F": "Field", "E": "Event"}
ROUNDS = 3   # a popup opened from inside a popup has its text too, two popups deep


# ---- finding the XML documentation files on this machine ----------------------------------------

def version_key(text):
    """Sort key for version folders, so that 10.0.15 comes after 10.0.9."""
    return tuple(int(part) if part.isdigit() else 0 for part in re.split(r"[.-]", text))


def target_framework():
    """The framework the projects build for (for example net10.0), or None."""
    for project in csharp_projects():
        for project_file in project.glob("*.csproj"):
            found = re.search(r"<TargetFramework>([^<]+)</TargetFramework>", project_file.read_text(encoding="utf-8-sig"))
            if found:
                return found.group(1).strip()
    return None


def newest(folders, version_of):
    folders = sorted(folders, key=lambda folder: version_key(version_of(folder)))
    return folders[-1] if folders else None


def local_path(text):
    """A folder as obj/project.assets.json names it, as a path on this machine.

    Visual Studio on Windows writes C:\\Users\\name\\.nuget\\packages\\ there. From inside WSL
    that same folder is /mnt/c/Users/name/.nuget/packages.
    """
    windows = re.match(r"^([A-Za-z]):[\\/]*(.*)$", text)
    if windows and os.name != "nt":
        return Path("/mnt", windows.group(1).lower(), *re.split(r"[\\/]+", windows.group(2).strip("\\/")))
    return Path(text)


def restored_packages(projects, caches):
    """The documentation XML of every NuGet package the projects are built with: {package: folder}.

    A project file names a few packages, and those bring others along:
    Microsoft.EntityFrameworkCore.Sqlite brings Microsoft.Data.Sqlite.Core, for one. The whole
    list is in obj/project.assets.json, which Visual Studio and "dotnet restore" write. A
    project without that file adds nothing here.

    A package is looked for in `caches` first and then in the folders the file itself names.
    """
    found = {}
    for project in projects:
        try:
            assets = json.loads((project / "obj" / "project.assets.json").read_text(encoding="utf-8-sig"))
        except (OSError, ValueError):
            continue
        roots = [*caches, *(local_path(folder) for folder in assets.get("packageFolders", {}))]
        for target in assets.get("targets", {}).values():
            for library, entry in target.items():
                package = assets.get("libraries", {}).get(library, {}).get("path", library.lower())
                if entry.get("type") != "package" or package in found:
                    continue
                for compiled, details in entry.get("compile", {}).items():
                    if ".xml" not in details.get("related", ""):
                        continue    # this file has no documentation beside it
                    folder = next((root / package / Path(compiled).parent for root in roots
                                   if (root / package / compiled).with_suffix(".xml").is_file()), None)
                    if folder:
                        found[package] = folder
                        break
    return found


# Where Windows keeps .NET, as WSL sees that folder. Used when dotnet.exe is not on the PATH of WSL.
WINDOWS_DOTNET = Path("/mnt/c/Program Files/dotnet")


def dotnet_installations():
    """The folders .NET is installed in, as far as this machine shows them.

    Inside WSL there can be two: the one of WSL itself, and the one of Windows, which Visual
    Studio uses. The second one matters when a project is built for a version of .NET that
    only Windows has.
    """
    wanted = [os.environ.get("DOTNET_ROOT")]
    for program in ("dotnet", "dotnet.exe"):
        path = shutil.which(program)
        wanted.append(Path(path).resolve().parent if path else None)
    if os.name != "nt":
        wanted.append(WINDOWS_DOTNET)
    found = []
    for folder in wanted:
        if folder and Path(folder).is_dir() and Path(folder) not in found:
            found.append(Path(folder))
    return found


def package_folders(projects):
    """NuGet's package folders: the one of this user first, then the ones the projects were restored into."""
    found = [Path(os.environ.get("NUGET_PACKAGES") or Path.home() / ".nuget" / "packages")]
    for project in projects:
        try:
            assets = json.loads((project / "obj" / "project.assets.json").read_text(encoding="utf-8-sig"))
        except (OSError, ValueError):
            continue
        found += [local_path(folder) for folder in assets.get("packageFolders", {})]
    return list(dict.fromkeys(found))


def pinned_packages(projects):
    """(name, version) of every package the repository names with a version.

    The version is either in Directory.Packages.props, one file for all projects, or in the
    project file itself.
    """
    files = [REPO / "Directory.Packages.props", *(file for project in projects for file in sorted(project.glob("*.csproj")))]
    pinned = []
    for file in files:
        if file.is_file():
            pinned += re.findall(r'<Package(?:Version|Reference)\s+Include="([^"]+)"\s+Version="([^"]+)"',
                                 file.read_text(encoding="utf-8-sig"))
    return list(dict.fromkeys(pinned))


def library_folder(lib, framework):
    """The folder of a package that fits the framework: the same one, or else the newest older one.

    A package has one folder per framework it was built for: lib/net8.0, lib/net6.0,
    lib/netstandard2.0, and lib/net461 for the old .NET Framework, which never fits here.
    """
    if (lib / framework).is_dir():
        return lib / framework
    wanted = version_key(framework[3:]) if re.fullmatch(r"net\d+\.\d+", framework) else None
    fitting = [folder for folder in lib.glob("net[0-9]*.[0-9]*")
               if wanted is None or version_key(folder.name[3:]) <= wanted]
    return newest(fitting, lambda f: f.name[3:]) or newest(lib.glob("netstandard[0-9]*"), lambda f: f.name[11:])


def xml_folders():
    """Folders that hold documentation XML. Earlier folders win when two describe the same type.

    Returns (folders found, descriptions of what was not found).
    """
    framework = target_framework() or "net*"
    projects = csharp_projects()
    found, not_found = [], []

    # 1. The reference packs of .NET itself: System.* and Microsoft.AspNetCore.*
    #    They are in a .NET installation, or in a package folder when a build had to download them.
    installations, caches = dotnet_installations(), package_folders(projects)
    for pack in ("Microsoft.NETCore.App.Ref", "Microsoft.AspNetCore.App.Ref"):
        candidates = [folder for root in installations for folder in (root / "packs" / pack).glob(f"*/ref/{framework}")]
        candidates += [folder for cache in caches for folder in (cache / pack.lower()).glob(f"*/ref/{framework}")]
        folder = newest(candidates, lambda f: f.parent.parent.name)
        if folder:
            found.append(folder)
        else:
            looked = ", ".join(str(root / "packs") for root in installations) or "no .NET installation was found"
            not_found.append(f"{pack} for {framework} (looked in: {looked}; and in the NuGet package folders)")

    # 2. NuGet packages, in the versions the repository names
    packages = caches[0]
    have = set()   # "microsoft.entityframeworkcore/10.0.15"
    for name, version in pinned_packages(projects):
        folder = library_folder(packages / name.lower() / version / "lib", framework)
        if folder and any(folder.glob("*.xml")):
            found.append(folder)
            have.add(f"{name.lower()}/{version}")

    # 3. The packages those bring along, and named ones that are only in another package folder
    #    (the one of Windows, when Visual Studio restored the packages and this script runs in WSL)
    for package, folder in restored_packages(projects, [packages]).items():
        if package not in have:
            found.append(folder)
            have.add(package)

    for project in projects:
        assets = project / "obj" / "project.assets.json"
        if not assets.is_file() and any("<PackageReference" in file.read_text(encoding="utf-8-sig")
                                        for file in project.glob("*.csproj")):
            not_found.append(f"the packages of {project.name} ({assets} is missing, so the list of its packages is not "
                             "known); open the solution in Visual Studio once, or run 'dotnet restore', so the "
                             "packages are downloaded")
    return found, not_found


# ---- names ---------------------------------------------------------------------------------------

def page_name(doc_id):
    """Documentation id -> the name Learn uses in its address (T:System.Guid -> System.Guid)."""
    name = doc_id[2:].split("(")[0]
    name = re.sub(r"``\d+", "", name)
    return re.sub(r"`(\d+)", r"-\1", name).replace("#", "-")


def fragment(doc_id):
    """Documentation id of a member -> the name Learn gives it on a page: what follows "#" in a link.

    M:System.String.Join(System.String,System.String[]) -> system-string-join(system-string-system-string())
    """
    text = doc_id[2:].lower().replace("{", "((").replace("}", "))").replace("[", "(").replace("]", ")")
    return re.sub(r"[^a-z0-9()*@]+", "-", text).strip("-")


def type_parameters(body):
    """The names of the type parameters a type or a method documents, in order: ["TKey", "TValue"]."""
    return re.findall(r'<typeparam name="([^"]+)"', body)


def short(doc_id, names=()):
    """T:System.Collections.Generic.Dictionary`2 -> Dictionary<TKey, TValue>

    `names` are the names of its type parameters. Without them it is Dictionary<T1, T2>.
    """
    name = re.sub(r"``\d+", "", doc_id[2:].split("(")[0]).split(".")[-1].replace("#ctor", "(constructor)")

    def shown(match):
        count = int(match.group(1))
        known = list(names[:count]) if len(names) >= count else ["T" if count == 1 else f"T{i + 1}" for i in range(count)]
        return "<" + ", ".join(known) + ">"

    return re.sub(r"`(\d+)", shown, name)


def split_top(text):
    """Split at the commas that are not inside brackets: "A{B,C},D[]" -> ["A{B,C}", "D[]"]."""
    parts, depth, current = [], 0, ""
    for character in text:
        depth += character in "{[(" 
        depth -= character in "}])"
        if character == "," and depth == 0:
            parts.append(current)
            current = ""
        else:
            current += character
    return parts + [current] if current or parts else []


def shown_type(text, method_names=(), type_names=()):
    """The type of a parameter as a documentation id writes it -> as C# code shows it.

    System.Func{``0,System.String[]}@ -> ref Func<TSource, String[]>

    ``0 is the first type parameter of the method and `0 the first of its type; `method_names`
    and `type_names` say what they are called.
    """
    def named(names):
        return lambda match: names[int(match.group(1))] if int(match.group(1)) < len(names) else f"T{int(match.group(1)) + 1}"

    by_reference = text.endswith("@")
    text = re.sub(r"``(\d+)", named(method_names), text.rstrip("@"))
    text = re.sub(r"`(\d+)", named(type_names), text)
    text = re.sub(r"[A-Za-z_][\w.]*", lambda match: match.group(0).rpartition(".")[2], text)   # System.Guid -> Guid
    text = re.sub(r"\[[^\]]*\]", lambda match: "[" + "," * match.group(0).count(",") + "]", text)   # [0:,0:] -> [,]
    text = re.sub(r",(?![\],])", ", ", text.replace("{", "<").replace("}", ">"))
    return ("ref " if by_reference else "") + text


# ---- turning documentation XML into popup HTML -------------------------------------------------

def link(doc_id, text=None):
    text = html.escape(text or short(doc_id))
    is_member = doc_id[:2] in ("M:", "P:", "F:", "E:")
    if is_member or doc_id.startswith(("T:System", "T:Microsoft")):
        return f'<a href="{PREFIX}{html.escape(page_name(doc_id))}"><code>{text}</code></a>'
    return f"<code>{text}</code>"


def render(xml):
    """The inside of a <summary> or similar element, as simple HTML."""
    xml = re.sub(r'<see(?:also)? cref="([^"]+)"\s*>(.*?)</see(?:also)?>', lambda m: link(m.group(1), m.group(2)), xml, flags=re.S)
    xml = re.sub(r'<see(?:also)? cref="([^"]+)"\s*/>', lambda m: link(m.group(1)), xml)
    xml = re.sub(r'<see langword="([^"]+)"\s*/>', r"<code>\1</code>", xml)
    xml = re.sub(r'<(?:paramref|typeparamref) name="([^"]+)"\s*/>', r"<code>\1</code>", xml)
    xml = re.sub(r"<(/?)c>", r"<\1code>", xml)
    xml = re.sub(r"<(/?)para>", r"<\1p>", xml)
    return re.sub(r"\s+", " ", re.sub(r"<(?!/?(?:code|p|a)[ >])[^>]+>", "", xml)).strip()


def part(body, tag):
    found = re.search(rf"<{tag}>(.*?)</{tag}>", body, re.S)
    return render(found.group(1)) if found else ""


def named_parts(body, tag, attribute):
    """[(name, text as HTML)] for elements such as <param name="x">text</param> or <param name="x"/>."""
    found = re.findall(rf'<{tag} {attribute}="([^"]+)"\s*(?:/>|>(.*?)</{tag}>)', body, re.S)
    return [(name, render(text)) for name, text in found]


def source_note(xml_file):
    pack = next((p for p in xml_file.parts if p.endswith(".Ref") or p.startswith("microsoft.")), xml_file.parent.name)
    return (f"<p><small>Text from {html.escape(xml_file.name)}, the documentation file shipped in {html.escape(pack)}. "
            "Remarks and examples are only on the full page.</small></p>")


def read_xml(folders):
    """Every documented type, and the documented members of each type. The first folder wins."""
    types, members = {}, {}
    for xml_file in (f for folder in folders for f in sorted(folder.glob("*.xml"))):
        read_members(xml_file.read_text(encoding="utf-8", errors="replace"), xml_file, types, members)
    return types, members


def read_members(text, xml_file, types, members):
    for doc_id, body in MEMBER.findall(text):
        if doc_id[0] == "T":
            types.setdefault(page_name(doc_id).lower(), (doc_id, body, xml_file))
        elif doc_id[0] in "MPFE":
            owner = page_name(doc_id).rsplit(".", 1)[0].lower()
            members.setdefault(owner, {}).setdefault(doc_id, body)


class Library:
    """What the documentation XML describes, and the popup text for each name.

    A name is the part of a Learn address after ".../dotnet/api/", in small letters:
    "system.guid" (a type), "system.guid.newguid" (a member), "system.collections.generic"
    (a namespace).
    """

    def __init__(self, types, members):
        self.types = types        # name -> (documentation id, its XML text, the file it is from)
        self.members = members    # name of a type -> {documentation id of a member: its XML text}
        self.member_pages = {}    # name of a member -> the documentation ids of its overloads
        for found in members.values():
            for doc_id in found:
                self.member_pages.setdefault(page_name(doc_id).lower(), []).append(doc_id)
        self.namespaces = {}      # name of a namespace -> the names of its types
        for name in types:
            parent = name.rpartition(".")[0]
            if parent and parent not in types:      # a type inside a type is listed with that type
                self.namespaces.setdefault(parent, []).append(name)

    def page_for(self, name):
        """The name whose page answers a link to `name`, or None when there is no text for it.

        A member without text of its own (a constructor nobody documented, say) is answered by
        the page of its type.
        """
        if name in self.types or name in self.member_pages or name in self.namespaces:
            return name
        owner = name.rpartition(".")[0]
        return owner if owner in self.types else None

    def article(self, name):
        if name in self.types:
            return self.type_article(name)
        if name in self.member_pages:
            return self.member_article(name)
        return self.namespace_article(name)

    def type_article(self, name):
        doc_id, body, xml_file = self.types[name]
        parts = [f"<article><h1>{html.escape(short(doc_id, type_parameters(body)))}</h1>"
                 f"<p><code>{html.escape(doc_id[2:])}</code></p><p>{part(body, 'summary')}</p>"]
        for parameter, text in named_parts(body, "typeparam", "name"):
            parts.append(f"<p><code>{html.escape(parameter)}</code>: {text}</p>")
        for letter, heading in KINDS:
            grouped = {}
            for member_id, member_body in self.members.get(name, {}).items():
                plain_name = member_id.split("(")[0].replace("#ctor", "")
                if member_id[0] == letter and "op_" not in member_id and "#" not in plain_name:
                    grouped.setdefault(short(member_id), []).append((member_id, member_body))
            if grouped:
                parts.append(f"<h2>{heading}</h2><dl>")
                for member, overloads in sorted(grouped.items()):
                    count = f" ({len(overloads)} overloads)" if len(overloads) > 1 else ""
                    # A link such as .../system.stringcomparison#system-stringcomparison-ordinal names one
                    # entry of this list. The page script finds it by these marks.
                    marks = "".join(f'<span id="{html.escape(fragment(member_id))}"></span>' for member_id, _ in overloads)
                    parts.append(f"<dt>{marks}{link(overloads[0][0], member)}{count}</dt>"
                                 f"<dd>{part(overloads[0][1], 'summary')}</dd>")
                parts.append("</dl>")
        parts.append(source_note(xml_file) + "</article>")
        return "".join(parts)

    def member_article(self, name):
        overloads = self.member_pages[name]
        first = overloads[0]
        # M:System.Collections.Generic.List`1.Add(`0) -> T:System.Collections.Generic.List`1
        owner_id = "T:" + re.sub(r"``\d+", "", first[2:].split("(")[0]).rsplit(".", 1)[0]
        owner = self.types.get(page_name(owner_id).lower())
        owner_names = type_parameters(owner[1]) if owner else []
        owner_name = short(owner_id, owner_names)
        constructor = first[2:].split("(")[0].endswith("#ctor")
        kind = "Constructor" if constructor else KIND_OF_MEMBER[first[0]]
        title = f"{owner_name} constructor" if constructor else f"{owner_name}.{short(first)} {kind.lower()}"
        parts = [f"<article><h1>{html.escape(title)}</h1>"]
        if len(overloads) > 1:
            parts.append(f"<p>{len(overloads)} overloads.</p>")
        bodies = self.members[page_name(owner_id).lower()]
        for doc_id in overloads:
            parts.append(member_section(doc_id, bodies[doc_id], kind, owner_id, owner_name, owner_names))
        parts.append((source_note(owner[2]) if owner else "") + "</article>")
        return "".join(parts)

    def namespace_article(self, name):
        names = sorted(self.namespaces[name])
        written = self.types[names[0]][0][2:].rpartition(".")[0]    # with its capital letters
        parts = [f"<article><h1>{html.escape(written)} namespace</h1>"
                 f"<p>{len(names)} of its types have documentation on this machine.</p><dl>"]
        for type_name in names:
            doc_id, body, _ = self.types[type_name]
            parts.append(f"<dt>{link(doc_id, short(doc_id, type_parameters(body)))}</dt><dd>{part(body, 'summary')}</dd>")
        parts.append("</dl><p><small>A list made from the documentation files of the .NET SDK and of the NuGet packages. "
                     "The full page also says what the namespace is for.</small></p></article>")
        return "".join(parts)


def member_section(doc_id, body, kind, owner_id, owner_name, owner_names):
    """One overload of a member: its heading, summary, parameters, result and exceptions."""
    method_names = type_parameters(body)
    name, bracket, rest = doc_id[2:].partition("(")
    types = [shown_type(text, method_names, owner_names) for text in split_top(rest.rpartition(")")[0])]
    simple = name.rsplit(".", 1)[-1]                              # Add, #ctor, Select``2, Item
    arity = re.search(r"``(\d+)$", simple)
    if arity:
        count = int(arity.group(1))
        known = method_names[:count] if len(method_names) >= count else [f"T{i + 1}" for i in range(count)]
        simple = simple[:arity.start()] + "<" + ", ".join(known) + ">"
    if kind == "Constructor":
        heading = f"{owner_name}({', '.join(types)})"
    elif kind == "Method":
        heading = f"{owner_name}.{simple}({', '.join(types)})"
    else:
        heading = f"{owner_name}.{simple}" + (f"[{', '.join(types)}]" if bracket else "")    # an indexer: Item[Int32]

    out = [f'<section id="{html.escape(fragment(doc_id))}"><h2>{html.escape(heading)}</h2>']
    summary = part(body, "summary")
    if summary:
        out.append(f"<p>{summary}</p>")
    for title, found in (("Type parameters", named_parts(body, "typeparam", "name")),
                         ("Parameters", named_parts(body, "param", "name"))):
        if not found:
            continue
        out.append(f"<p><strong>{title}</strong></p><dl>")
        with_types = title == "Parameters" and len(found) == len(types)
        for position, (parameter, text) in enumerate(found):
            its_type = f" <code>{html.escape(types[position])}</code>" if with_types else ""
            out.append(f"<dt><code>{html.escape(parameter)}</code>{its_type}</dt><dd>{text}</dd>")
        out.append("</dl>")
    for title, tag in (("Returns", "returns"), ("Value", "value")):
        text = part(body, tag)
        if text:
            out.append(f"<p><strong>{title}:</strong> {text}</p>")
    exceptions = re.findall(r'<exception cref="([^"]+)"\s*(?:/>|>(.*?)</exception>)', body, re.S)
    if exceptions:
        out.append("<p><strong>Exceptions</strong></p><dl>")
        out += [f"<dt>{link(cref)}</dt><dd>{render(text)}</dd>" for cref, text in exceptions]
        out.append("</dl>")
    out.append(f"<p><small>{kind} of {link(owner_id, owner_name)}</small></p></section>")
    return "".join(out)


# ---- the build step -----------------------------------------------------------------------------

def pages_of(site, skip=()):
    """The HTML pages of a built site, without its _static folder and without the folders in `skip`."""
    for folder, folders, files in os.walk(site):
        folders[:] = [name for name in folders if name != "_static" and Path(folder, name) not in skip]
        for name in files:
            if name.endswith(".html"):
                yield Path(folder, name)


def links_in_site(site, skip=()):
    """The Learn addresses that the pages of a site link to: {name: {what follows "?", ...}}.

    The name is the part between ".../dotnet/api/" and "?" or "#", in small letters. What follows
    "?" (such as "view=net-10.0") is kept, because the page script compares addresses with it.
    It is "" for an address without "?". What follows "#" names a part of the page and is not
    needed here: a saved page has all its parts.
    """
    wanted = {}
    for page in pages_of(site, skip):
        for address in LEARN_LINK.findall(page.read_text(encoding="utf-8")):
            name, _, query = html.unescape(address).partition("#")[0].partition("?")
            if name.strip("/"):    # ".../dotnet/api/" alone is the start page of the API browser, not a name
                wanted.setdefault(name.strip("/").lower(), set()).add(query)
    return wanted


def collect(library, linked):
    """The popup pages for the names in `linked`, and for the types those pages link to.

    Returns (pages, answers, missing): pages is {name: HTML}; answers is {name: the name of the
    page that answers a link to it}; missing are the linked names without any text.
    """
    pages, answers, missing = {}, {}, set()
    queue = sorted(linked)
    for _ in range(ROUNDS):
        following = []
        for name in queue:
            if name in answers:
                continue
            page = library.page_for(name)
            if page is None:
                missing.add(name)
                continue
            answers[name] = page
            if page in pages:
                continue
            pages[page] = library.article(page)
            answers[page] = page
            if page in library.namespaces:
                continue    # a namespace lists hundreds of types; their popups are not saved for that alone
            for address in LEARN_LINK.findall(pages[page]):
                target = html.unescape(address).partition("#")[0].partition("?")[0].lower()
                if target in library.types and target not in answers:
                    following.append(target)
        queue = following
    return pages, answers, missing & set(linked)


def save(site, pages, answers, linked, saved_at):
    """Write the pages and the list of addresses into one site. Returns the size in KB."""
    out = site / "_static" / "reference-previews"
    out.mkdir(parents=True, exist_ok=True)
    for old in out.glob("*.json"):
        old.unlink()
    files = {}
    for name, page in sorted(pages.items()):
        files[name] = hashlib.sha256(name.encode()).hexdigest()[:24] + ".json"
        (out / files[name]).write_text(json.dumps({"url": PREFIX + name, "html": page, "fetchedAt": saved_at}),
                                       encoding="utf-8")
    # The page script compares addresses in small letters and with what follows "?", so an
    # address is listed once for every "?view=..." it is linked with.
    manifest = {}
    for name, page in sorted(answers.items()):
        for query in sorted({""} | linked.get(name, set())):
            manifest[PREFIX + name + ("?" + query if query else "")] = files[page]
    (out / "manifest.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    return sum(f.stat().st_size for f in out.glob("*.json")) // 1024


def main(first=BUILD / "html"):
    print("-- Popup texts for .NET names", flush=True)
    if not (first / "index.html").is_file():
        sys.exit(f"No built site in {first}. Run ./build.sh first.")
    companion = first / "companion"
    sites = {"Stargate docs": first}
    if (companion / "index.html").is_file():
        sites["dev docs"] = companion
    linked = {title: links_in_site(site, skip=[companion] if site == first else []) for title, site in sites.items()}
    folders, not_found = xml_folders()
    for missing in not_found:
        print(f"   note: documentation XML not found for {missing}")

    # Reading a few hundred XML files takes seconds, so skip it when nothing that matters has changed.
    state_file = BUILD / "dotnet-previews.state.json"
    state = {"folders": [str(folder) for folder in folders],
             "linked": {title: sorted(f"{name}?{query}" for name, queries in found.items() for query in queries)
                        for title, found in linked.items()}}
    manifests = [site / "_static" / "reference-previews" / "manifest.json" for site in sites.values()]
    if all(manifest.is_file() for manifest in manifests) and state_file.is_file() \
            and json.loads(state_file.read_text(encoding="utf-8")) == state:
        saved = ", ".join(str(len(set(json.loads(manifest.read_text(encoding="utf-8")).values()))) for manifest in manifests)
        print(f"   .NET popups unchanged ({saved} saved)")
        return

    library = Library(*read_xml(folders))
    saved_at = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")  # shown in the popup's footer
    for title, site in sites.items():
        pages, answers, missing = collect(library, linked[title])
        size = save(site, pages, answers, linked[title], saved_at)
        print(f"   {title}: {len(pages)} .NET popups saved ({size} KB) for {len(linked[title])} linked names, "
              f"from {len(folders)} folders of documentation XML")
        if missing:
            print(f"   {len(missing)} linked .NET names have no XML text and open as normal links: "
                  + ", ".join(sorted(missing)[:8]) + (" ..." if len(missing) > 8 else ""))
    state_file.write_text(json.dumps(state), encoding="utf-8")


if __name__ == "__main__":
    main()
