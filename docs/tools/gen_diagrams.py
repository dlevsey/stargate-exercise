"""Writes the data model page and the projects page from files in the repository.

The data model comes from the model snapshot: the file named ...ModelSnapshot.cs that Entity
Framework Core writes beside the migrations. It lists every table with its columns, keys,
indexes and relationships, in one regular format, and EF Core writes it again whenever a
migration is added. So a new table appears here after "add a migration" and a rebuild.

The projects page comes from the .csproj files: what each project is built for, which
packages it uses in which version, and which other projects it uses.
"""
import re
from xml.etree import ElementTree

from common import REPO, SOURCE, csharp_files, documented_types, generated_note, is_test_project, project_files, write_if_changed

# One "modelBuilder.Entity("Full.Name", b => { ... });" block of a snapshot. The same entity has
# two: the first with its columns, a later one with its relationships.
ENTITY_BLOCK = re.compile(r'modelBuilder\.Entity\("([^"]+)",\s*b\s*=>\s*\{(.*?)^\s*\}\);', re.S | re.M)
CALL = re.compile(r'\.(\w+)(?:<([^>(]+)>)?\(([^()]*(?:\([^()]*\)[^()]*)*)\)')   # .Name<T>(arguments)
TEXTS = re.compile(r'"([^"]*)"')


def short(full_name):
    return full_name.rsplit(".", 1)[-1]


def read_snapshot(text):
    """A model snapshot -> ({entity: {...}}, [relationship, ...]). Names are full names, as the file writes them."""
    entities, relationships = {}, []
    for full_name, body in ENTITY_BLOCK.findall(text):
        entity = entities.setdefault(full_name, {"table": short(full_name), "columns": [], "key": [], "indexes": []})
        for statement in body.split(";"):
            calls = [(name, type_, arguments) for name, type_, arguments in CALL.findall(" ".join(statement.split()))]
            if not calls:
                continue
            (first, first_type, first_arguments), names = calls[0], {name for name, _, _ in calls}
            given = TEXTS.findall(first_arguments)
            if first == "Property" and given:
                column_type = next((TEXTS.findall(a) for n, _, a in calls if n == "HasColumnType"), [""])
                entity["columns"].append({
                    "name": given[0], "type": first_type or "", "column_type": (column_type or [""])[0],
                    # A value type such as int cannot be empty; a string or a "?" type can, unless IsRequired() says no.
                    "required": "IsRequired" in names or not (first_type or "").endswith("?") and first_type not in ("string", "byte[]"),
                    "generated": "ValueGeneratedOnAdd" in names,
                })
            elif first == "HasKey":
                entity["key"] = given
            elif first == "HasIndex":
                entity["indexes"].append({"columns": given, "unique": "IsUnique" in names})
            elif first == "ToTable" and given:
                entity["table"] = given[0]
            elif first == "HasOne" and given:
                to_one = "WithOne" in names
                key = next((TEXTS.findall(a) for n, _, a in calls if n == "HasForeignKey"), [])
                # With WithOne, the first text of HasForeignKey names the entity that holds the column.
                holder, columns = (key[0], key[1:]) if to_one and len(key) > 1 else (full_name, key)
                on_delete = next((a.rsplit(".", 1)[-1] for n, _, a in calls if n == "OnDelete"), "")
                relationships.append({"child": holder, "parent": given[0], "columns": columns, "to_one": to_one,
                                      "on_delete": on_delete, "required": "IsRequired" in names})
    return entities, relationships


# What the database does when a row is deleted that other rows point at. The other values of
# EF Core's DeleteBehavior (the ones that start with "Client") also say what EF Core does with
# the objects it has loaded; they are shown by name only.
ON_DELETE = {
    "Cascade": "the rows that point at it are deleted too",
    "SetNull": "the column of the rows that point at it is emptied",
    "Restrict": "the database refuses while rows still point at it",
    "NoAction": "the database refuses while rows still point at it",
}


def marks(entity, name, foreign):
    found = (["PK"] if name in entity["key"] else []) + (["FK"] if name in foreign else [])
    if any(index["unique"] and index["columns"] == [name] for index in entity["indexes"]):
        found.append("UQ")
    return found


def escaped(text):
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def on_delete(name):
    return f"{ON_DELETE[name]} (`{name}`)" if name in ON_DELETE else f"`{name}`" if name else "not said"


def table_node(full_name, entity, foreign, linked):
    rows = [f'<TR><TD COLSPAN="3" BGCOLOR="#1f4e79" ALIGN="LEFT"><FONT COLOR="white"><B>{escaped(entity["table"])}</B></FONT></TD></TR>']
    for column in entity["columns"]:
        mark = " ".join(marks(entity, column["name"], foreign))
        rows.append(
            f'<TR><TD ALIGN="LEFT" PORT="{column["name"]}"><FONT COLOR="#8a5a00" POINT-SIZE="9">{mark} </FONT></TD>'
            f'<TD ALIGN="LEFT">{escaped(column["name"])}</TD>'
            f'<TD ALIGN="LEFT" PORT="{column["name"]}.out"><FONT COLOR="#666666">{escaped(column["type"])}</FONT></TD></TR>'
        )
    link = ""
    if full_name in linked:
        namespace = full_name.rsplit(".", 1)[0]
        link = f'URL="../api/{namespace}.html#{linked[full_name]}" target="_top" tooltip="Open {short(full_name)}" '
    return (
        f'  "{full_name}" [{link}label=<<TABLE BORDER="1" COLOR="#8a94a3" '
        f'CELLBORDER="0" CELLSPACING="0" CELLPADDING="3" BGCOLOR="white">{"".join(rows)}</TABLE>>];'
    )


def model_graph(entities, relationships, linked):
    lines = [
        "digraph model {",
        '  graph [rankdir=LR bgcolor="transparent" nodesep=0.35 ranksep=1.1 fontname="Helvetica"];',
        '  node [shape=plain fontname="Helvetica" fontsize=10];',
        '  edge [color="#55606e" dir=both arrowhead=tee fontname="Helvetica" fontsize=8];',
    ]
    foreign = {}
    for relationship in relationships:
        foreign.setdefault(relationship["child"], set()).update(relationship["columns"])
    lines += [table_node(name, entity, foreign.get(name, set()), linked) for name, entity in sorted(entities.items())]
    for relationship in relationships:
        child, parent = relationship["child"], relationship["parent"]
        if child not in entities or parent not in entities or not relationship["columns"]:
            continue
        to = (entities[parent]["key"] or ["Id"])[0]
        # The end at the table that holds the column: a single bar for "one", a crow's foot for "many".
        # Each row has two places a line can touch: its first cell (named after the column) and its
        # last cell (".out"). A line leaves on the right of its row and arrives on the left of the
        # key's row; without that, lines start on the left and go around their own table.
        lines.append(f'  "{child}":"{relationship["columns"][0]}.out":e -> "{parent}":"{to}":w '
                     f'[arrowtail={"tee" if relationship["to_one"] else "crow"}];')
    return "\n".join(lines + ["}"])


def data_model_page():
    snapshots = [path for path in csharp_files() if path.name.endswith("ModelSnapshot.cs")]
    note = generated_note("gen_diagrams.py")
    if not snapshots:
        write_if_changed(SOURCE / "diagrams" / "data-model.md", note + (
            "# Data model\n\n"
            "There is no model snapshot in the repository (a file named `...ModelSnapshot.cs`, which Entity Framework\n"
            "Core writes when the first migration is added), so there is nothing to draw the tables from yet.\n"))
        return 0, 0
    types = documented_types()
    parts, table_count, relationship_count = ["# Data model", ""], 0, 0
    for snapshot in snapshots:
        entities, relationships = read_snapshot(snapshot.read_text(encoding="utf-8-sig"))
        table_count, relationship_count = table_count + len(entities), relationship_count + len(relationships)
        # The address of a class in the code reference, for the ones that have an entry there.
        linked = {name: f"class-{name}" for name in entities if name in types}
        foreign = {}
        for relationship in relationships:
            foreign.setdefault(relationship["child"], set()).update(relationship["columns"])
        parts += [
            f"Generated from `{snapshot.relative_to(REPO).as_posix()}`: {len(entities)} tables and {len(relationships)} relationships.",
            "",
            "That file is the *model snapshot*: the description of the tables that Entity Framework Core keeps beside the",
            "migrations and writes again each time a migration is added. It says what the database looks like once every",
            "migration has run. The entity classes are a different source; a class that was changed after the last",
            "migration can say something else than this page.",
            "",
            "## How the tables relate",
            "",
            "The line ends tell how many rows can be on that side: a bar is one, a crow's foot is many.",
            "`PK` is the primary key, `FK` a column that points at another table, `UQ` a column whose values must be unique.",
            "Click a table to open its class.",
            "",
            "```{graphviz}", ":align: center", "", model_graph(entities, relationships, linked), "```", "",
            "## Relationships", "",
            "| Table | Column | Points at | Rows that may point at the same row | Must point at a row | When that row is deleted |",
            "|---|---|---|---|---|---|",
        ]
        for relationship in relationships:
            child, parent = entities.get(relationship["child"]), entities.get(relationship["parent"])
            parts.append(
                f'| `{child["table"] if child else short(relationship["child"])}` | {", ".join(f"`{c}`" for c in relationship["columns"])} '
                f'| `{parent["table"] if parent else short(relationship["parent"])}` | {"at most one" if relationship["to_one"] else "any number"} '
                f'| {"yes" if relationship["required"] else "no"} | {on_delete(relationship["on_delete"])} |')
        parts += ["", "## Tables", ""]
        for name, entity in sorted(entities.items()):
            parts += [f'### {entity["table"]}', ""]
            if name in linked:
                parts += [f"Class: {{cs:type}}`{name}`.", ""]
            parts += ["| Column | C# type | Column type | Must have a value | Notes |", "|---|---|---|---|---|"]
            for column in entity["columns"]:
                notes = marks(entity, column["name"], foreign.get(name, set()))
                notes = [{"PK": "primary key", "FK": "points at another table", "UQ": "unique"}[mark] for mark in notes]
                if column["generated"]:
                    notes.append("value made by the database")
                parts.append(f'| `{column["name"]}` | `{column["type"]}` | `{column["column_type"] or "?"}` '
                             f'| {"yes" if column["required"] else "no"} | {", ".join(notes)} |')
            parts.append("")
    write_if_changed(SOURCE / "diagrams" / "data-model.md", note + "\n".join(parts))
    return table_count, relationship_count


def read_project(project_file):
    """What one .csproj file says: the target framework, the packages and the projects it uses."""
    root = ElementTree.parse(project_file).getroot()

    def value(name):
        return next((element.text.strip() for element in root.iter(name) if element.text), "")

    packages = []
    for reference in root.iter("PackageReference"):
        name = reference.get("Include") or reference.get("Update") or ""
        version = reference.get("Version") or reference.findtext("Version") or ""
        if name:
            packages.append((name, version.strip()))
    uses = [re.split(r"[\\/]", reference.get("Include", ""))[-1].removesuffix(".csproj") for reference in root.iter("ProjectReference")]
    return {"name": project_file.stem, "path": project_file.relative_to(REPO).as_posix(), "sdk": root.get("Sdk", ""),
            "framework": value("TargetFramework") or value("TargetFrameworks"), "packages": sorted(packages, key=lambda p: p[0].lower()),
            "uses": sorted(uses), "tests": is_test_project(project_file)}


def projects_page():
    projects = [read_project(project_file) for project_file in project_files()]
    references = [(project["name"], used) for project in projects for used in project["uses"]]
    parts = [
        "# Projects and packages", "",
        f"Generated from the {len(projects)} project {'file' if len(projects) == 1 else 'files'} (`.csproj`) in the repository. "
        "A project file says which version of .NET the code is built for and which packages it uses. "
        "A *package* is a library that is downloaded from NuGet, the package source of .NET.", "",
        "| Project | File | Built for | Kind |", "|---|---|---|---|",
    ]
    for project in projects:
        kind = "tests" if project["tests"] else "web application" if project["sdk"].endswith(".Web") else "library or program"
        parts.append(f'| `{project["name"]}` | `{project["path"]}` | `{project["framework"] or "?"}` | {kind} |')
    if references:
        dot = [
            "digraph projects {",
            '  graph [rankdir=TB bgcolor="transparent" ranksep=0.7];',
            '  node [shape=box style="rounded,filled" fillcolor="white" color="#8a94a3" fontname="Helvetica" fontsize=11 margin="0.25,0.12"];',
            '  edge [color="#55606e"];',
        ]
        dot += [f'  "{project["name"]}";' for project in projects]
        dot += [f'  "{a}" -> "{b}";' for a, b in references] + ["}"]
        parts += ["", "## Which project uses which", "", "An arrow means \"uses\".", "",
                  "```{graphviz}", ":align: center", "", "\n".join(dot), "```"]
    for project in projects:
        parts += ["", f'## {project["name"]}', ""]
        if project["uses"]:
            parts += ["Uses " + ", ".join(f"`{used}`" for used in project["uses"]) + ".", ""]
        if not project["packages"]:
            parts += ["No packages."]
            continue
        parts += ["| Package | Version |", "|---|---|"]
        for name, version in project["packages"]:
            address = f"https://www.nuget.org/packages/{name}" + (f"/{version}" if re.fullmatch(r"[\w.\-+]+", version) else "")
            parts.append(f'| [{name}]({address}) | {f"`{version}`" if version else "set elsewhere"} |')
    write_if_changed(SOURCE / "diagrams" / "projects.md", generated_note("gen_diagrams.py") + "\n".join(parts) + "\n")
    return len(projects), sum(len(project["packages"]) for project in projects)


def main():
    tables, relationships = data_model_page()
    projects, packages = projects_page()
    print(f"   {tables} tables ({relationships} relationships), {projects} projects ({packages} packages)")


if __name__ == "__main__":
    main()
