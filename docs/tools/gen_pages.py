"""Writes one code-reference page per namespace, from Doxygen's XML.

Each page holds one directive (``doxygennamespace`` or ``doxygenclass``). Sphinx
fills it in from the XML at build time, so the text of a page never has to be
edited: change the C# file and rebuild.
"""
import re
from xml.etree import ElementTree

from common import BUILD, SOURCE, generated_note, remove_other_files, write_if_changed

MEMBER_OPTIONS = "   :members:\n   :private-members:\n   :protected-members:\n   :undoc-members:\n"


def main(xml_dir=BUILD / "doxygen" / "xml", out_dir=SOURCE / "api"):
    note = generated_note("gen_pages.py")
    namespaces, outside = {}, []
    # index.xml lists everything Doxygen found; each namespace has a file named after its id.
    for compound in ElementTree.parse(xml_dir / "index.xml").getroot().iter("compound"):
        name = compound.findtext("name")
        if compound.get("kind") in ("class", "struct", "interface") and "::" not in name:
            outside.append(name)  # a type that is not inside any namespace, such as Program
        if compound.get("kind") != "namespace":
            continue
        text = (xml_dir / f"{compound.get('refid')}.xml").read_text(encoding="utf-8")
        classes = re.findall(r"<innerclass [^>]*>(.*?)</innerclass>", text)
        member_count = len(re.findall(r"<memberdef ", text))
        namespaces[name] = (classes, member_count)

    written, pages = [], []
    for name, (classes, member_count) in sorted(namespaces.items()):
        if not classes and not member_count:
            continue  # a namespace that only groups other namespaces
        dotted = name.replace("::", ".")
        has_children = any(other.startswith(name + "::") for other in namespaces)
        lines = [f"# {dotted}", "", "```{eval-rst}"]
        if has_children:
            # doxygennamespace would repeat the child namespaces here, so list this namespace's own types.
            lines += [f".. doxygenclass:: {c}\n{MEMBER_OPTIONS}" for c in classes]
        else:
            lines += [f".. doxygennamespace:: {name}\n{MEMBER_OPTIONS}"]
        lines += ["```", ""]
        page = out_dir / f"{dotted}.md"
        write_if_changed(page, note + "\n".join(lines))
        written.append(page)
        pages.append(dotted)

    if outside:
        page = out_dir / "no-namespace.md"
        write_if_changed(page, note + (
            "# Types outside a namespace\n\n"
            "These types are declared without a `namespace` line, so they belong to no namespace.\n\n"
            "```{eval-rst}\n" + "".join(f".. doxygenclass:: {c}\n{MEMBER_OPTIONS}\n" for c in sorted(outside)) + "```\n"
        ))
        written.append(page)
        pages.append("no-namespace")

    index = out_dir / "index.md"
    write_if_changed(index, note + (
        "# Code reference (C#)\n\n"
        "One page per namespace, generated from the C# files of the projects in the repository. Every class, record,\n"
        "interface and enum is listed with all of its members, private ones included, because this site is for studying\n"
        "the code. Descriptions come from the `///` comments in the code; a type without them shows its signature only.\n\n"
        "```{toctree}\n:maxdepth: 1\n\n" + "\n".join(pages) + "\n```\n"
    ))
    remove_other_files(out_dir, written + [index])
    print(f"   {len(pages)} pages")


if __name__ == "__main__":
    main()
