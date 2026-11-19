"""Checks rules of the step that runs before Sphinx (tools/prebuild.py).

Run with:  ./test.sh
"""
import os
import tempfile
import unittest
from collections import Counter
from pathlib import Path

import cs_doxygen_filter
from common import TOOLS
from prebuild import declared_bases, declared_types, doxygen_on, restore_type_arguments, with_type_arguments

DOXYGEN = Path(os.environ.get("DOXYGEN") or TOOLS / "doxygen")


class DeclaredTypes(unittest.TestCase):
    """The count of declared types, which is compared with what Doxygen found."""

    def test_every_declaration_counts(self):
        texts = ["namespace One;\npublic class Person { }\n    internal sealed record Duty(string Title);\n",
                 "namespace Two;\npublic class Person { }\npublic enum Rank { A }\npublic interface IClock { }"]
        self.assertEqual(declared_types(texts), Counter(Person=2, Duty=1, Rank=1, IClock=1))

    def test_the_parts_of_a_partial_type_count_once(self):
        # Entity Framework Core writes a migration as two files that both say "partial class InitialCreate".
        # That is one class, and Doxygen describes it once.
        texts = ["    public partial class InitialCreate : Migration\n    {\n    }\n",
                 "    partial class InitialCreate\n    {\n    }\n",
                 "public class Other { }"]
        self.assertEqual(declared_types(texts), Counter(InitialCreate=1, Other=1))

    def test_a_word_in_a_comment_or_in_the_middle_of_a_line_is_not_a_declaration(self):
        self.assertEqual(declared_types(["var text = \"a class Person\";\n// the class Person\n"]), Counter())


HANDLERS = """namespace Shop.Orders;

public class CreateOrder : IRequest<CreateOrderResult>
{
}

[Serializable]
public class CreateOrderHandler
    : IRequestHandler<CreateOrder, CreateOrderResult>,
      IDisposable
{
    public class Inner : IComparable<Inner> { }
}

public class Page<T> : PageBase<T>, IPage where T : IComparable<T>
{
}

public class Plain : Shop.Common.Entity
{
}

public class Lookup : Shop.Common.Table<string, List<int>>, IHandle<Created>, IHandle<Removed>
{
}
"""


class DeclaredBases(unittest.TestCase):
    """The base types as the C# file names them: (name, type arguments), in the order written."""

    def test_the_type_arguments_of_a_base_type_are_read(self):
        self.assertEqual(declared_bases(HANDLERS, 3, "CreateOrder"), [("IRequest", "CreateOrderResult")])

    def test_a_declaration_over_several_lines_is_found_from_any_of_its_lines(self):
        expected = [("IRequestHandler", "CreateOrder, CreateOrderResult"), ("IDisposable", "")]
        for line in (8, 9, 10):
            self.assertEqual(declared_bases(HANDLERS, line, "CreateOrderHandler"), expected)

    def test_the_name_must_fit_too(self):
        # Doxygen names a line; the type that is declared there must be the one that is asked for.
        self.assertEqual(declared_bases(HANDLERS, 3, "SomethingElse"), [])
        self.assertEqual(declared_bases(HANDLERS, 12, "Inner"), [("IComparable", "Inner")])
        self.assertEqual(declared_bases(HANDLERS, 12, "CreateOrderHandler"), [])

    def test_what_comes_after_where_is_not_a_base_type(self):
        self.assertEqual(declared_bases(HANDLERS, 15, "Page"), [("PageBase", "T"), ("IPage", "")])

    def test_a_name_with_its_namespace_counts_by_its_last_part(self):
        self.assertEqual(declared_bases(HANDLERS, 19, "Plain"), [("Entity", "")])

    def test_type_arguments_can_hold_commas_and_further_type_arguments(self):
        self.assertEqual(declared_bases(HANDLERS, 23, "Lookup"),
                         [("Table", "string, List<int>"), ("IHandle", "Created"), ("IHandle", "Removed")])

    def test_what_is_handed_to_the_constructor_of_a_base_type_is_not_a_type_argument(self):
        code = "public class Derived(int size) : Base<int>(size), IThing\n{\n}\n"
        self.assertEqual(declared_bases(code, 1, "Derived"), [("Base", "int"), ("IThing", "")])

    def test_a_type_without_base_types_has_none(self):
        self.assertEqual(declared_bases("public class Person\n{\n}\n", 1, "Person"), [])


def base(text, attributes=' prot="public" virt="non-virtual"'):
    return f"    <basecompoundref{attributes}>{text}</basecompoundref>\n"


class WithTypeArguments(unittest.TestCase):
    """Doxygen's XML names a base type without its type arguments. They are put back."""

    def test_the_type_arguments_are_added_in_doxygens_spelling(self):
        self.assertEqual(with_type_arguments(base("IRequestHandler"), [("IRequestHandler", "CreateOrder, CreateOrderResult")]),
                         base("IRequestHandler&lt; CreateOrder, CreateOrderResult &gt;"))

    def test_a_base_type_without_type_arguments_stays_as_it_is(self):
        xml = base("IRequest") + base("IDisposable")
        self.assertEqual(with_type_arguments(xml, [("IRequest", "Result"), ("IDisposable", "")]),
                         base("IRequest&lt; Result &gt;") + base("IDisposable"))

    def test_a_base_type_doxygen_found_in_the_code_keeps_its_link(self):
        found = ' refid="class_shop_1_1_common_1_1_table" prot="public" virt="non-virtual"'
        self.assertEqual(with_type_arguments(base("Shop.Common.Table", found), [("Table", "string, List<int>")]),
                         base("Shop.Common.Table&lt; string, List&lt;int&gt; &gt;", found))

    def test_the_same_base_type_twice_gets_its_arguments_in_the_order_written(self):
        xml = base("IHandle") + base("IHandle")
        self.assertEqual(with_type_arguments(xml, [("IHandle", "Created"), ("IHandle", "Removed")]),
                         base("IHandle&lt; Created &gt;") + base("IHandle&lt; Removed &gt;"))

    def test_when_the_xml_and_the_code_do_not_name_it_equally_often_nothing_is_guessed(self):
        xml = base("IHandle")
        self.assertEqual(with_type_arguments(xml, [("IHandle", "Created"), ("IHandle", "Removed")]), xml)

    def test_a_base_type_that_already_has_type_arguments_is_left_alone(self):
        xml = base("IRequest&lt; Result &gt;")
        self.assertEqual(with_type_arguments(xml, [("IRequest", "Result")]), xml)

    def test_other_parts_of_the_file_are_not_touched(self):
        xml = "<compoundname>Shop::IRequest</compoundname>\n" + base("Other") + "<type>IRequest</type>\n"
        self.assertEqual(with_type_arguments(xml, [("IRequest", "Result")]), xml)


@unittest.skipUnless(DOXYGEN.is_file(), "Doxygen is not installed (./setup.sh installs it)")
class RestoredInDoxygensXml(unittest.TestCase):
    """The same with Doxygen itself: run it on a small file and look at the XML afterwards."""

    def test_the_xml_names_base_types_with_their_type_arguments(self):
        with tempfile.TemporaryDirectory() as work:
            code, out = Path(work) / "code", Path(work) / "out"
            (code / "Orders").mkdir(parents=True)
            out.mkdir()
            (code / "Orders" / "Handlers.cs").write_text(cs_doxygen_filter.rewrite(HANDLERS), encoding="utf-8", newline="\n")
            exit_code, said = doxygen_on(DOXYGEN, code, out)
            self.assertEqual((exit_code, said), (0, ""))

            def bases(name):
                text = (out / "xml" / f"class_shop_1_1_orders_1_1_{name}.xml").read_text(encoding="utf-8")
                return [line.split(">", 1)[1].split("</")[0] for line in text.splitlines() if "<basecompoundref" in line]

            # What Doxygen writes by itself. If a later version keeps the type arguments,
            # this line fails and the repair step can go.
            self.assertEqual(bases("create_order_handler"), ["IRequestHandler", "IDisposable"])

            restored = restore_type_arguments(out / "xml", code)
            self.assertEqual(bases("create_order"), ["IRequest&lt; CreateOrderResult &gt;"])
            self.assertEqual(bases("create_order_handler"),
                             ["IRequestHandler&lt; CreateOrder, CreateOrderResult &gt;", "IDisposable"])
            self.assertEqual(bases("create_order_handler_1_1_inner"), ["IComparable&lt; Inner &gt;"])
            self.assertEqual(bases("plain"), ["Shop.Common.Entity"])
            self.assertGreaterEqual(restored, 3)


if __name__ == "__main__":
    unittest.main()
