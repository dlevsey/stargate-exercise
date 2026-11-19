"""Checks the popup texts for .NET names (tools/dotnet_xml_previews.py).

The checks write a small documentation file of their own, in the format the .NET SDK ships,
so they need neither the SDK nor a built site.

Run with:  ./test.sh
"""
import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import dotnet_xml_previews
from dotnet_xml_previews import (PREFIX, Library, collect, dotnet_installations, fragment, links_in_site, local_path,
                                 page_name, read_members, read_xml, render, restored_packages, save, short, shown_type,
                                 split_top, version_key)

SAMPLE = """<?xml version="1.0"?>
<doc>
  <assembly><name>Sample</name></assembly>
  <members>
    <member name="T:System.Text.Box`1">
      <summary>Holds one <typeparamref name="T"/> value.
        See <see cref="T:System.Text.Tool"/> and <see cref="T:Shop.Order"/>.</summary>
      <typeparam name="T">What it holds.</typeparam>
    </member>
    <member name="M:System.Text.Box`1.#ctor(`0)">
      <summary>Makes a box.</summary>
      <param name="value">The first value.</param>
    </member>
    <member name="M:System.Text.Box`1.Put(`0)">
      <summary>Puts a value in.</summary>
      <param name="value">The value.</param>
      <returns><see langword="true"/> when it fits.</returns>
      <exception cref="T:System.ArgumentNullException"><paramref name="value"/> is <see langword="null"/>.</exception>
    </member>
    <member name="M:System.Text.Box`1.Put(`0,System.Int32[])">
      <summary>Puts a value in at several places.</summary>
      <param name="value">The value.</param>
      <param name="places">Where.</param>
    </member>
    <member name="M:System.Text.Box`1.Map``1(System.Func{`0,``0})">
      <summary>Makes a box of another kind.</summary>
      <typeparam name="TResult">What the new box holds.</typeparam>
      <param name="map">Turns a value into the new kind.</param>
      <returns>The new box.</returns>
    </member>
    <member name="P:System.Text.Box`1.Count">
      <summary>How many values it holds.</summary>
      <value>A number.</value>
    </member>
    <member name="P:System.Text.Box`1.Item(System.Int32)">
      <summary>The value at a place.</summary>
      <param name="index">The place.</param>
    </member>
    <member name="M:System.Text.Box`1.op_Equality(System.Text.Box{`0},System.Text.Box{`0})">
      <summary>Compares two boxes.</summary>
    </member>
    <member name="M:System.Text.Box`1.System#IDisposable#Dispose">
      <summary>Written for an interface only.</summary>
    </member>
    <member name="T:System.Text.Box`1.Enumerator">
      <summary>Walks through a box.</summary>
    </member>
    <member name="T:System.Text.Tool">
      <summary>A tool. See <see cref="T:System.Text.Other">the other one</see>.</summary>
    </member>
    <member name="F:System.Text.Tool.Limit">
      <summary>The largest size.</summary>
    </member>
    <member name="E:System.Text.Tool.Changed">
      <summary>Raised after a change.</summary>
    </member>
    <member name="T:System.Text.Other">
      <summary>Another. See <see cref="T:System.Text.Fourth"/>.</summary>
    </member>
    <member name="T:System.Text.Fourth">
      <summary>The fourth. See <see cref="T:System.Text.Fifth"/>.</summary>
    </member>
    <member name="T:System.Text.Fifth">
      <summary>The fifth.</summary>
    </member>
    <member name="N:System.Text">
      <summary>An entry for a namespace is not read.</summary>
    </member>
  </members>
</doc>
"""
XML_FILE = Path("/dotnet/packs/Microsoft.NETCore.App.Ref/10.0.0/ref/net10.0/System.Text.xml")
BOX, TOOL = "system.text.box-1", "system.text.tool"


def library():
    types, members = {}, {}
    read_members(SAMPLE, XML_FILE, types, members)
    return Library(types, members)


class TemporaryFolder(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory(prefix="stargate-docs-test-")
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)

    def write(self, name, text):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path


class Names(unittest.TestCase):
    def test_version_folders_sort_by_number(self):
        versions = ["10.0.9", "10.0.15", "9.0.11", "10.0.0-preview.3"]
        self.assertEqual(sorted(versions, key=version_key), ["9.0.11", "10.0.0-preview.3", "10.0.9", "10.0.15"])

    def test_the_name_in_a_learn_address(self):
        for doc_id, name in (
                ("T:System.Guid", "System.Guid"),
                ("T:System.Collections.Generic.Dictionary`2", "System.Collections.Generic.Dictionary-2"),
                ("M:System.Guid.NewGuid", "System.Guid.NewGuid"),
                ("M:System.String.Join(System.String,System.String[])", "System.String.Join"),
                ("M:System.Linq.Enumerable.Select``2(System.Collections.Generic.IEnumerable{``0},System.Func{``0,``1})",
                 "System.Linq.Enumerable.Select"),
                ("M:System.Collections.Generic.List`1.#ctor(System.Int32)", "System.Collections.Generic.List-1.-ctor"),
                ("P:System.Collections.Generic.List`1.Item(System.Int32)", "System.Collections.Generic.List-1.Item")):
            with self.subTest(doc_id=doc_id):
                self.assertEqual(page_name(doc_id), name)

    def test_the_name_of_one_overload_on_a_learn_page(self):
        for doc_id, name in (
                ("M:System.String.Join(System.String,System.String[])", "system-string-join(system-string-system-string())"),
                ("M:System.Guid.NewGuid", "system-guid-newguid"),
                ("M:System.Collections.Generic.List`1.Add(`0)", "system-collections-generic-list-1-add(-0)"),
                ("M:System.Collections.Generic.List`1.#ctor(System.Int32)", "system-collections-generic-list-1-ctor(system-int32)"),
                ("M:System.Linq.Enumerable.Select``2(System.Collections.Generic.IEnumerable{``0},System.Func{``0,``1})",
                 "system-linq-enumerable-select-2(system-collections-generic-ienumerable((-0))-system-func((-0-1)))"),
                ("M:System.Int32.TryParse(System.String,System.Int32@)", "system-int32-tryparse(system-string-system-int32@)"),
                ("F:System.StringComparison.Ordinal", "system-stringcomparison-ordinal")):
            with self.subTest(doc_id=doc_id):
                self.assertEqual(fragment(doc_id), name)

    def test_the_short_name_shown_in_a_popup(self):
        self.assertEqual(short("T:System.Guid"), "Guid")
        self.assertEqual(short("T:System.Collections.Generic.Dictionary`2", ["TKey", "TValue"]), "Dictionary<TKey, TValue>")
        self.assertEqual(short("T:System.Collections.Generic.Dictionary`2"), "Dictionary<T1, T2>")
        self.assertEqual(short("T:System.Collections.Generic.List`1"), "List<T>")
        self.assertEqual(short("M:System.Linq.Enumerable.Select``2(System.Func{``0,``1})"), "Select")
        self.assertEqual(short("M:System.Guid.#ctor(System.String)"), "(constructor)")

    def test_parameters_are_split_at_the_commas_outside_brackets(self):
        self.assertEqual(split_top("A{B,C},D[]"), ["A{B,C}", "D[]"])
        self.assertEqual(split_top("System.Int32[0:,0:],System.String"), ["System.Int32[0:,0:]", "System.String"])
        self.assertEqual(split_top("System.String"), ["System.String"])
        self.assertEqual(split_top(""), [])

    def test_the_type_of_a_parameter_as_code_shows_it(self):
        self.assertEqual(shown_type("System.Func{``0,System.String[]}@", ["TSource"]), "ref Func<TSource, String[]>")
        self.assertEqual(shown_type("`0", (), ["T"]), "T")
        self.assertEqual(shown_type("System.Collections.Generic.IDictionary{`0,`1}", (), ["TKey", "TValue"]),
                         "IDictionary<TKey, TValue>")
        self.assertEqual(shown_type("System.Int32[0:,0:]"), "Int32[,]")
        self.assertEqual(shown_type("``1"), "T2")     # no name known for it

    @unittest.skipIf(os.name == "nt", "the folders are named the Windows way already")
    def test_a_windows_folder_is_found_from_inside_wsl(self):
        self.assertEqual(local_path("C:\\Users\\name\\.nuget\\packages\\"), Path("/mnt/c/Users/name/.nuget/packages"))
        self.assertEqual(local_path("D:/packages"), Path("/mnt/d/packages"))
        self.assertEqual(local_path("/home/name/.nuget/packages/"), Path("/home/name/.nuget/packages"))


class Text(unittest.TestCase):
    def test_documentation_xml_becomes_simple_html(self):
        link = f'<a href="{PREFIX}System.Guid"><code>'
        for xml, expected in (
                ('See <see cref="T:System.Guid"/>.', f"See {link}Guid</code></a>."),
                ('See <see cref="T:System.Guid">a unique id</see>.', f"See {link}a unique id</code></a>."),
                ('See <see cref="M:System.Guid.NewGuid"/>.', f'See <a href="{PREFIX}System.Guid.NewGuid"><code>NewGuid</code></a>.'),
                # A type that is not Microsoft's has no page on Learn.
                ('See <see cref="T:Shop.Order"/>.', "See <code>Order</code>."),
                ('<see langword="null"/> or <paramref name="x"/> of <typeparamref name="T"/>',
                 "<code>null</code> or <code>x</code> of <code>T</code>"),
                ("Use <c>x.Y</c>.", "Use <code>x.Y</code>."),
                ("<para>One.</para>\n      <para>Two.</para>", "<p>One.</p> <p>Two.</p>"),
                ('<list type="bullet"><item><description>One</description></item></list> and\n   more',
                 "One and more"),
                ("a &lt; b &amp; c", "a &lt; b &amp; c")):
            with self.subTest(xml=xml):
                self.assertEqual(render(xml), expected)

    def test_the_first_folder_wins_when_two_describe_the_same_type(self):
        with tempfile.TemporaryDirectory(prefix="stargate-docs-test-") as work:
            for folder, text in (("first", "From the first."), ("second", "From the second.")):
                Path(work, folder).mkdir()
                Path(work, folder, "Sample.xml").write_text(
                    f'<doc><members><member name="T:System.Thing"><summary>{text}</summary></member></members></doc>',
                    encoding="utf-8")
            types, _ = read_xml([Path(work, "first"), Path(work, "second")])
        self.assertIn("From the first.", types["system.thing"][1])


class Popups(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.library = library()

    def test_what_answers_a_link(self):
        for name, page in (
                (BOX, BOX),                                     # a type
                (BOX + ".put", BOX + ".put"),                   # a member
                ("system.text", "system.text"),                 # a namespace
                (TOOL + ".undocumented", TOOL),                 # a member without text: its type
                (BOX + ".enumerator", BOX + ".enumerator"),     # a type inside a type
                ("system.nothing.here", None)):
            with self.subTest(name=name):
                self.assertEqual(self.library.page_for(name), page)

    def test_a_type(self):
        page = self.library.article(BOX)
        self.assertTrue(page.startswith(
            "<article><h1>Box&lt;T&gt;</h1><p><code>System.Text.Box`1</code></p>"
            f'<p>Holds one <code>T</code> value. See <a href="{PREFIX}System.Text.Tool"><code>Tool</code></a> '
            "and <code>Order</code>.</p><p><code>T</code>: What it holds.</p><h2>Methods</h2><dl>"), page)
        # One entry for a name, with a mark for each overload that a link can name.
        self.assertIn('<dt><span id="system-text-box-1-put(-0)"></span><span id="system-text-box-1-put(-0-system-int32())"></span>'
                      f'<a href="{PREFIX}System.Text.Box-1.Put"><code>Put</code></a> (2 overloads)</dt><dd>Puts a value in.</dd>',
                      page)
        self.assertIn(f'<dt><span id="system-text-box-1-ctor(-0)"></span><a href="{PREFIX}System.Text.Box-1.-ctor">'
                      "<code>(constructor)</code></a></dt><dd>Makes a box.</dd>", page)
        self.assertLess(page.index("(constructor)"), page.index("<code>Map</code>"))
        self.assertLess(page.index("<code>Map</code>"), page.index("<code>Put</code>"))
        self.assertIn("<h2>Properties</h2><dl>", page)
        self.assertIn("<code>Count</code></a></dt><dd>How many values it holds.</dd>", page)
        self.assertNotIn("<h2>Fields</h2>", page)
        # Operators and members written for an interface only are left out.
        self.assertNotIn("op_Equality", page)
        self.assertNotIn("Dispose", page)
        self.assertTrue(page.endswith(
            "<p><small>Text from System.Text.xml, the documentation file shipped in Microsoft.NETCore.App.Ref. "
            "Remarks and examples are only on the full page.</small></p></article>"), page)

    def test_fields_and_events_of_a_type(self):
        page = self.library.article(TOOL)
        self.assertIn(f'<h2>Fields</h2><dl><dt><span id="system-text-tool-limit"></span><a href="{PREFIX}System.Text.Tool.Limit">'
                      "<code>Limit</code></a></dt><dd>The largest size.</dd></dl><h2>Events</h2>", page)

    def test_a_method_with_two_overloads(self):
        page = self.library.article(BOX + ".put")
        owner = f'<a href="{PREFIX}System.Text.Box-1"><code>Box&lt;T&gt;</code></a>'
        self.assertEqual(
            page,
            "<article><h1>Box&lt;T&gt;.Put method</h1><p>2 overloads.</p>"
            '<section id="system-text-box-1-put(-0)"><h2>Box&lt;T&gt;.Put(T)</h2><p>Puts a value in.</p>'
            "<p><strong>Parameters</strong></p><dl><dt><code>value</code> <code>T</code></dt><dd>The value.</dd></dl>"
            "<p><strong>Returns:</strong> <code>true</code> when it fits.</p>"
            f'<p><strong>Exceptions</strong></p><dl><dt><a href="{PREFIX}System.ArgumentNullException">'
            "<code>ArgumentNullException</code></a></dt><dd><code>value</code> is <code>null</code>.</dd></dl>"
            f"<p><small>Method of {owner}</small></p></section>"
            '<section id="system-text-box-1-put(-0-system-int32())"><h2>Box&lt;T&gt;.Put(T, Int32[])</h2>'
            "<p>Puts a value in at several places.</p>"
            "<p><strong>Parameters</strong></p><dl><dt><code>value</code> <code>T</code></dt><dd>The value.</dd>"
            "<dt><code>places</code> <code>Int32[]</code></dt><dd>Where.</dd></dl>"
            f"<p><small>Method of {owner}</small></p></section>"
            "<p><small>Text from System.Text.xml, the documentation file shipped in Microsoft.NETCore.App.Ref. "
            "Remarks and examples are only on the full page.</small></p></article>")

    def test_a_method_with_a_type_parameter_of_its_own(self):
        page = self.library.article(BOX + ".map")
        self.assertIn("<h1>Box&lt;T&gt;.Map method</h1>", page)
        self.assertNotIn("overloads", page)
        self.assertIn('<section id="system-text-box-1-map-1(system-func((-0-0)))">'
                      "<h2>Box&lt;T&gt;.Map&lt;TResult&gt;(Func&lt;T, TResult&gt;)</h2>", page)
        self.assertIn("<p><strong>Type parameters</strong></p><dl><dt><code>TResult</code></dt><dd>What the new box holds.</dd></dl>"
                      "<p><strong>Parameters</strong></p><dl><dt><code>map</code> <code>Func&lt;T, TResult&gt;</code></dt>", page)

    def test_a_constructor_a_property_an_indexer_a_field_and_an_event(self):
        for name, title, heading, also in (
                (BOX + ".-ctor", "Box&lt;T&gt; constructor", "Box&lt;T&gt;(T)", "<small>Constructor of "),
                (BOX + ".count", "Box&lt;T&gt;.Count property", "Box&lt;T&gt;.Count", "<p><strong>Value:</strong> A number.</p>"),
                (BOX + ".item", "Box&lt;T&gt;.Item property", "Box&lt;T&gt;.Item[Int32]",
                 "<dt><code>index</code> <code>Int32</code></dt><dd>The place.</dd>"),
                (TOOL + ".limit", "Tool.Limit field", "Tool.Limit", "<small>Field of "),
                (TOOL + ".changed", "Tool.Changed event", "Tool.Changed", "<small>Event of ")):
            with self.subTest(name=name):
                page = self.library.article(name)
                self.assertIn(f"<article><h1>{title}</h1>", page)
                self.assertIn(f"<h2>{heading}</h2>", page)
                self.assertIn(also, page)

    def test_a_namespace_lists_its_types(self):
        page = self.library.article("system.text")
        self.assertTrue(page.startswith(
            "<article><h1>System.Text namespace</h1><p>5 of its types have documentation on this machine.</p><dl>"
            f'<dt><a href="{PREFIX}System.Text.Box-1"><code>Box&lt;T&gt;</code></a></dt><dd>Holds one <code>T</code> value.'), page)
        self.assertNotIn("Enumerator", page)    # a type inside a type is listed with that type


class Collecting(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.library = library()

    def test_a_popup_inside_a_popup_has_its_text_too_two_popups_deep(self):
        pages, answers, missing = collect(self.library, {BOX: {""}})
        # Box names Tool, Tool names Other, Other names Fourth. Fourth would be a third popup inside.
        self.assertEqual(sorted(pages), [BOX, "system.text.other", TOOL])
        self.assertEqual(answers, {name: name for name in pages})
        self.assertEqual(missing, set())

    def test_a_member_without_text_is_answered_by_its_type(self):
        pages, answers, _ = collect(self.library, {TOOL + ".undocumented": {""}})
        self.assertEqual(answers[TOOL + ".undocumented"], TOOL)
        self.assertIn(TOOL, pages)
        self.assertNotIn(TOOL + ".undocumented", pages)

    def test_the_types_of_a_namespace_are_not_saved_for_the_namespace_alone(self):
        pages, _, _ = collect(self.library, {"system.text": {""}})
        self.assertEqual(sorted(pages), ["system.text"])

    def test_a_name_without_any_text_is_reported(self):
        pages, answers, missing = collect(self.library, {"system.nothing": {""}, TOOL + ".limit": {""}})
        self.assertEqual(missing, {"system.nothing"})
        self.assertNotIn("system.nothing", answers)
        self.assertIn(TOOL + ".limit", pages)


class Sites(TemporaryFolder):
    def test_the_learn_addresses_a_site_links_to(self):
        self.write("site/index.html",
                   f'<a href="{PREFIX}System.Guid">a</a> <a href="{PREFIX}system.guid?view=net-10.0#system-guid-newguid">b</a> '
                   f'<a href="{PREFIX}">the start page of the API browser</a> <a href="https://example.org/dotnet/api/x">c</a> '
                   f'<a href="{PREFIX}system.string.join?view=net-10.0&amp;viewFallbackFrom=net-9.0">d</a>')
        self.write("site/api/page.html", f'<a href="{PREFIX}System.Guid.NewGuid#system-guid-newguid">e</a>')
        self.write("site/_static/popup.html", f'<a href="{PREFIX}system.hidden">not a page of the site</a>')
        self.write("site/companion/index.html", f'<a href="{PREFIX}system.text.json">the other site</a>')
        site = self.root / "site"
        first = {"system.guid": {"", "view=net-10.0"}, "system.guid.newguid": {""},
                 "system.string.join": {"view=net-10.0&viewFallbackFrom=net-9.0"}}
        self.assertEqual(links_in_site(site, skip=[site / "companion"]), first)
        self.assertEqual(links_in_site(site), {**first, "system.text.json": {""}})
        self.assertEqual(links_in_site(site / "companion"), {"system.text.json": {""}})

    def test_the_saved_files_and_the_list_the_page_script_reads(self):
        site = self.root / "site"
        self.write("site/_static/reference-previews/old.json", "{}")
        linked = {TOOL: {"", "view=net-10.0"}, TOOL + ".undocumented": {"view=net-10.0"}}
        save(site, {TOOL: "<article>Tool</article>"}, {TOOL: TOOL, TOOL + ".undocumented": TOOL}, linked, "2026-01-02T03:04:05+00:00")
        folder = site / "_static" / "reference-previews"
        manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
        # An address is listed without "?view=..." and with every "?view=..." it is linked with.
        self.assertEqual(sorted(manifest), [PREFIX + TOOL, PREFIX + TOOL + ".undocumented",
                                            PREFIX + TOOL + ".undocumented?view=net-10.0", PREFIX + TOOL + "?view=net-10.0"])
        self.assertEqual(len(set(manifest.values())), 1)
        self.assertEqual(sorted(path.name for path in folder.glob("*.json")), sorted(["manifest.json", manifest[PREFIX + TOOL]]))
        self.assertEqual(json.loads((folder / manifest[PREFIX + TOOL]).read_text(encoding="utf-8")),
                         {"url": PREFIX + TOOL, "html": "<article>Tool</article>", "fetchedAt": "2026-01-02T03:04:05+00:00"})


class Packages(TemporaryFolder):
    def assets(self, project, **more):
        content = {
            "targets": {"net10.0": {
                "Some.Package/1.2.3": {"type": "package", "compile": {"lib/net8.0/Some.Package.dll": {"related": ".xml"}}},
                "Other.Folder/2.0.0": {"type": "package", "compile": {"lib/net10.0/Other.Folder.dll": {"related": ".pdb;.xml"}}},
                "No.Docs/1.0.0": {"type": "package", "compile": {"lib/net8.0/No.Docs.dll": {}}},
                "Not.On.Disk/1.0.0": {"type": "package", "compile": {"lib/net8.0/Not.On.Disk.dll": {"related": ".xml"}}},
                "Other.Project/1.0.0": {"type": "project", "compile": {"bin/placeholder/Other.Project.dll": {"related": ".xml"}}},
            }},
            "libraries": {"Some.Package/1.2.3": {"path": "some.package/1.2.3"}, "Other.Folder/2.0.0": {"path": "other.folder/2.0.0"},
                          "No.Docs/1.0.0": {"path": "no.docs/1.0.0"}, "Not.On.Disk/1.0.0": {"path": "not.on.disk/1.0.0"}},
            "packageFolders": {str(self.root / "named-in-the-file") + os.sep: {}},
            **more,
        }
        self.write(f"{project}/obj/project.assets.json", json.dumps(content))
        return self.root / project

    def test_the_packages_that_other_packages_bring_along(self):
        project = self.assets("src/App")
        self.write("cache/some.package/1.2.3/lib/net8.0/Some.Package.xml", "<doc/>")
        self.write("named-in-the-file/other.folder/2.0.0/lib/net10.0/Other.Folder.xml", "<doc/>")
        self.write("cache/no.docs/1.0.0/lib/net8.0/No.Docs.xml", "<doc/>")     # the assets file does not name it
        found = restored_packages([project, self.root / "src" / "NeverRestored"], [self.root / "cache"])
        self.assertEqual(found, {
            "some.package/1.2.3": self.root / "cache" / "some.package" / "1.2.3" / "lib" / "net8.0",
            "other.folder/2.0.0": self.root / "named-in-the-file" / "other.folder" / "2.0.0" / "lib" / "net10.0",
        })

    def xml_folders(self, pinned=(), in_project=(), framework="net10.0", installations=None):
        if pinned:
            self.write("repo/Directory.Packages.props", "<Project><ItemGroup>" + "".join(
                f'<PackageVersion Include="{name}" Version="{version}" />' for name, version in pinned) + "</ItemGroup></Project>")
        project = self.write(
            "repo/src/App/App.csproj",
            f"<Project><PropertyGroup><TargetFramework>{framework}</TargetFramework></PropertyGroup><ItemGroup>"
            + "".join(f'<PackageReference Include="{name}" Version="{version}" />' for name, version in in_project)
            + "</ItemGroup></Project>").parent
        with mock.patch.dict(os.environ, {"NUGET_PACKAGES": str(self.root / "packages")}), \
                mock.patch.multiple(dotnet_xml_previews, REPO=self.root / "repo", csharp_projects=lambda: [project],
                                    dotnet_installations=lambda: installations or [self.root / "dotnet"]):
            return dotnet_xml_previews.xml_folders()

    def test_the_newest_reference_pack_and_the_pinned_packages(self):
        for version in ("10.0.9", "10.0.15", "9.0.11"):
            framework = "net9.0" if version.startswith("9") else "net10.0"
            self.write(f"dotnet/packs/Microsoft.NETCore.App.Ref/{version}/ref/{framework}/System.Runtime.xml", "<doc/>")
        self.write("packages/microsoft.entityframeworkcore/10.0.15/lib/net10.0/Microsoft.EntityFrameworkCore.xml", "<doc/>")
        self.write("packages/older.package/3.0.0/lib/net8.0/Older.Package.xml", "<doc/>")
        self.write("packages/older.package/3.0.0/lib/net6.0/Older.Package.xml", "<doc/>")
        found, not_found = self.xml_folders([("Microsoft.EntityFrameworkCore", "10.0.15"), ("Older.Package", "3.0.0"),
                                             ("Never.Downloaded", "1.0.0")])
        self.assertEqual(found, [
            self.root / "dotnet/packs/Microsoft.NETCore.App.Ref/10.0.15/ref/net10.0",
            self.root / "packages/microsoft.entityframeworkcore/10.0.15/lib/net10.0",
            self.root / "packages/older.package/3.0.0/lib/net8.0",      # no folder for net10.0: the newest it has
        ])
        self.assertEqual(len(not_found), 1)
        self.assertIn("Microsoft.AspNetCore.App.Ref for net10.0", not_found[0])

    def test_a_pack_for_an_older_framework_comes_from_the_installation_that_has_it(self):
        # WSL has .NET 10 only; the Windows installation, which Visual Studio uses, also has .NET 8.
        self.write("wsl/packs/Microsoft.NETCore.App.Ref/10.0.15/ref/net10.0/System.Runtime.xml", "<doc/>")
        self.write("windows/packs/Microsoft.NETCore.App.Ref/10.0.15/ref/net10.0/System.Runtime.xml", "<doc/>")
        self.write("windows/packs/Microsoft.NETCore.App.Ref/8.0.34/ref/net8.0/System.Runtime.xml", "<doc/>")
        self.write("windows/packs/Microsoft.AspNetCore.App.Ref/8.0.34/ref/net8.0/Microsoft.AspNetCore.Mvc.Core.xml", "<doc/>")
        found, not_found = self.xml_folders(framework="net8.0", installations=[self.root / "wsl", self.root / "windows"])
        self.assertEqual(found, [self.root / "windows/packs/Microsoft.NETCore.App.Ref/8.0.34/ref/net8.0",
                                 self.root / "windows/packs/Microsoft.AspNetCore.App.Ref/8.0.34/ref/net8.0"])
        self.assertEqual(not_found, [])

    def test_a_pack_is_also_looked_for_in_the_package_folders(self):
        # A build downloads a reference pack as a NuGet package when the installation does not have it.
        self.write("dotnet/packs/Microsoft.NETCore.App.Ref/8.0.20/ref/net8.0/System.Runtime.xml", "<doc/>")
        self.write("packages/microsoft.netcore.app.ref/8.0.27/ref/net8.0/System.Runtime.xml", "<doc/>")
        self.write("named-in-the-file/microsoft.aspnetcore.app.ref/8.0.27/ref/net8.0/Microsoft.AspNetCore.Mvc.Core.xml", "<doc/>")
        self.assets("repo/src/App", targets={})
        found, not_found = self.xml_folders(framework="net8.0")
        self.assertEqual(found, [self.root / "packages/microsoft.netcore.app.ref/8.0.27/ref/net8.0",      # newer than 8.0.20
                                 self.root / "named-in-the-file/microsoft.aspnetcore.app.ref/8.0.27/ref/net8.0"])
        self.assertEqual(not_found, [])

    def test_a_version_written_in_a_project_file_counts_as_pinned(self):
        self.write("packages/some.mapper/2.1.35/lib/net461/Some.Mapper.xml", "<doc/>")    # the old .NET Framework
        self.write("packages/some.mapper/2.1.35/lib/net7.0/Some.Mapper.xml", "<doc/>")
        self.write("packages/some.mapper/2.1.35/lib/net9.0/Some.Mapper.xml", "<doc/>")    # newer than the project
        self.write("packages/only.standard/1.0.0/lib/netstandard2.0/Only.Standard.xml", "<doc/>")
        found, _ = self.xml_folders(in_project=[("Some.Mapper", "2.1.35"), ("Only.Standard", "1.0.0")], framework="net8.0")
        self.assertEqual(found, [self.root / "packages/some.mapper/2.1.35/lib/net7.0",
                                 self.root / "packages/only.standard/1.0.0/lib/netstandard2.0"])

    def test_a_project_that_was_never_restored_is_reported_with_what_to_do(self):
        _, not_found = self.xml_folders(in_project=[("Some.Mapper", "2.1.35")])
        self.assertEqual(len(not_found), 3)        # the two reference packs, and the packages of the project
        self.assertIn("the packages of App", not_found[2])
        self.assertIn("dotnet restore", not_found[2])

        self.assets("repo/src/App")
        _, not_found = self.xml_folders(in_project=[("Some.Mapper", "2.1.35")])
        self.assertEqual(len(not_found), 2)

    def test_where_dotnet_is_installed(self):
        for name in ("root/dotnet", "wsl/dotnet", "windows/dotnet.exe"):
            self.write(name, "")
        programs = {"dotnet": str(self.root / "wsl" / "dotnet"), "dotnet.exe": str(self.root / "windows" / "dotnet.exe")}
        with mock.patch.object(dotnet_xml_previews.shutil, "which", programs.get), \
                mock.patch.object(dotnet_xml_previews, "WINDOWS_DOTNET", self.root / "not-there"):
            with mock.patch.dict(os.environ, {"DOTNET_ROOT": str(self.root / "root")}):
                self.assertEqual(dotnet_installations(), [self.root / "root", self.root / "wsl", self.root / "windows"])
            with mock.patch.dict(os.environ, {"DOTNET_ROOT": str(self.root / "wsl")}):     # the same folder twice
                self.assertEqual(dotnet_installations(), [self.root / "wsl", self.root / "windows"])
            with mock.patch.dict(os.environ, {"DOTNET_ROOT": str(self.root / "gone")}):    # a folder that is not there
                self.assertEqual(dotnet_installations(), [self.root / "wsl", self.root / "windows"])


class Main(TemporaryFolder):
    """The build step: which sites get popups, and that an unchanged run does nothing."""

    def setUp(self):
        super().setUp()
        self.site = self.root / "build" / "html"
        self.write("xml/System.Text.xml", SAMPLE)
        patched = mock.patch.multiple(dotnet_xml_previews, BUILD=self.root / "build",
                                      xml_folders=lambda: ([self.root / "xml"], ["Some.Pack (not installed)"]))
        patched.start()
        self.addCleanup(patched.stop)

    def run_main(self):
        said = io.StringIO()
        with contextlib.redirect_stdout(said):
            dotnet_xml_previews.main(self.site)
        return said.getvalue()

    def saved(self, site):
        manifest = json.loads((site / "_static" / "reference-previews" / "manifest.json").read_text(encoding="utf-8"))
        return sorted(address[len(PREFIX):] for address in manifest)

    def test_without_a_built_site_it_says_so(self):
        with self.assertRaises(SystemExit) as stopped, contextlib.redirect_stdout(io.StringIO()):
            dotnet_xml_previews.main(self.site)
        self.assertIn("No built site in", str(stopped.exception))

    def test_one_site(self):
        self.write("build/html/index.html", f'<a href="{PREFIX}System.Text.Tool?view=net-10.0">Tool</a>')
        said = self.run_main()
        self.assertTrue(said.startswith("-- Popup texts for .NET names\n"), said)
        self.assertIn("   note: documentation XML not found for Some.Pack (not installed)\n", said)
        # Tool, and what its popup names two popups deep: Other and Fourth.
        self.assertRegex(said, r"   Stargate docs: 3 \.NET popups saved \(\d+ KB\) for 1 linked names, from 1 folders of documentation XML\n")
        self.assertNotIn("dev docs", said)
        self.assertEqual(self.saved(self.site), ["system.text.fourth", "system.text.other", TOOL, TOOL + "?view=net-10.0"])

    def test_an_unchanged_run_reads_nothing(self):
        self.write("build/html/index.html", f'<a href="{PREFIX}System.Text.Tool">Tool</a>')
        self.run_main()
        with mock.patch.object(dotnet_xml_previews, "read_xml", side_effect=AssertionError("the XML was read again")):
            self.assertIn("   .NET popups unchanged (3 saved)\n", self.run_main())
            # Another link on a page: the popups are made again.
            self.write("build/html/index.html", f'<a href="{PREFIX}System.Text.Fifth">Fifth</a>')
            with self.assertRaises(AssertionError):
                self.run_main()

    def test_both_sites_get_their_own_popups(self):
        self.write("build/html/index.html", f'<a href="{PREFIX}System.Text.Fifth">Fifth</a>')
        self.write("build/html/companion/index.html",
                   f'<a href="{PREFIX}System.Text.Tool.Limit">Limit</a> <a href="{PREFIX}system.nothing">nothing</a>')
        said = self.run_main()
        self.assertRegex(said, r"   Stargate docs: 1 \.NET popups saved \(\d+ KB\) for 1 linked names")
        # The popup of a member names its type (Tool), and that one names Other.
        self.assertRegex(said, r"   dev docs: 3 \.NET popups saved \(\d+ KB\) for 2 linked names")
        self.assertIn("   1 linked .NET names have no XML text and open as normal links: system.nothing\n", said)
        # A link on a page of the second site does not count for the first.
        self.assertEqual(self.saved(self.site), ["system.text.fifth"])
        self.assertEqual(self.saved(self.site / "companion"), ["system.text.other", TOOL, TOOL + ".limit"])
        self.assertIn("   .NET popups unchanged (1, 3 saved)\n", self.run_main())


if __name__ == "__main__":
    unittest.main()
