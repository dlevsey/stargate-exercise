"""Checks for cs_doxygen_filter.py: what each rule writes. Run with:  ./test.sh"""
import itertools
import re
import unittest

from cs_doxygen_filter import rewrite


class FilterTests(unittest.TestCase):
    def same_line_count(self, before, after):
        self.assertEqual(before.count("\n"), after.count("\n"), "the filter must not add or remove lines")

    def test_type_without_a_body_gets_one(self):
        self.assertEqual(rewrite("public partial class Program;\n"), "public partial class Program { }\n")

    def test_base_constructor_arguments_are_removed(self):
        before = "public sealed class Db(DbContextOptions<Db> options)\n    : DbContext(options), IShopData\n{\n"
        after = rewrite(before)
        self.assertIn(": DbContext, IShopData", after)
        self.same_line_count(before, after)

    def test_primary_constructor_becomes_a_constructor(self):
        before = "public sealed class OrderService(IShopData dbContext)\n{\n    public void Run() { }\n}\n"
        after = rewrite(before)
        self.assertEqual(
            after,
            "public sealed class OrderService\n{ public OrderService(IShopData dbContext) { }\n"
            "    public void Run() { }\n}\n")

    def test_parameters_on_several_lines_keep_the_line_count(self):
        before = ("public sealed class InvoiceService(\n    IShopData dbContext,\n    IClock clock)\n"
                  "{\n    private int x;\n}\n")
        after = rewrite(before)
        self.assertIn("{ public InvoiceService( IShopData dbContext, IClock clock) { }", after)
        self.same_line_count(before, after)
        self.assertEqual(after.splitlines()[4], "    private int x;")

    def test_exception_with_primary_constructor_and_no_body(self):
        before = ("public sealed class TransientException(\n    string message,\n    Exception? inner = null)\n"
                  "    : ProviderException(message, inner);\n")
        after = rewrite(before)
        self.assertIn(": ProviderException { public TransientException( string message, Exception? inner = null) { } }", after)
        self.same_line_count(before, after)

    def test_generic_class_with_constraint(self):
        before = "public class Box<T>(T value) : Base<T>(value) where T : class\n{\n}\n"
        after = rewrite(before)
        self.assertEqual(after, "public class Box<T> : Base<T> where T : class\n{ public Box(T value) { }\n}\n")

    def test_tuple_type_argument_in_base_list_is_kept(self):
        before = "public class Pairs : List<(int Left, int Right)>\n{\n}\n"
        self.assertEqual(rewrite(before), before)

    def test_record_without_a_body_and_ordinary_code_are_untouched(self):
        before = ("public sealed record OrderQuery(\n    Guid CustomerId,\n    DateOnly WorkDate);\n\n"
                  "public abstract record Shape(string Name);\n\n"
                  "public enum Scope { A, B }\n\npublic sealed class Plain\n{\n    public int Value { get; }\n}\n")
        self.assertEqual(rewrite(before), before)

    def test_record_with_a_body_becomes_a_record_class(self):
        before = ("public sealed record ActionResult(Status Status, string? ErrorCode = null)\n{\n"
                  "    public static ActionResult Success() => new(Status.Success);\n}\n")
        self.assertEqual(
            rewrite(before),
            "public sealed record class ActionResult\n{ public ActionResult(Status Status, string? ErrorCode = null) { }\n"
            "    public static ActionResult Success() => new(Status.Success);\n}\n")

    def test_generic_record_with_parameters_on_several_lines(self):
        before = ("public sealed record Result<T>(\n    Outcome Outcome,\n    T? Value = default)\n{\n"
                  "    public static Result<T> NotFound() => new(Outcome.NotFound);\n}\n")
        after = rewrite(before)
        self.assertTrue(after.startswith("public sealed record class Result<T>\n"))
        self.assertIn("{ public Result( Outcome Outcome, T? Value = default) { }", after)
        self.same_line_count(before, after)
        self.assertEqual(after.splitlines()[4], "    public static Result<T> NotFound() => new(Outcome.NotFound);")

    def test_record_with_only_a_body(self):
        before = "public sealed record Settings\n{\n    public int Size { get; init; }\n}\n"
        self.assertEqual(rewrite(before), "public sealed record class Settings\n{\n    public int Size { get; init; }\n}\n")

    def test_record_struct_and_record_class_keep_their_keyword(self):
        before = ("public readonly record struct Money(decimal Amount)\n{\n    public bool IsZero => Amount == 0;\n}\n\n"
                  "public record class Named(string Name)\n{\n}\n")
        after = rewrite(before)
        self.assertIn("public readonly record struct Money\n{ public Money(decimal Amount) { }\n", after)
        self.assertIn("public record class Named\n{ public Named(string Name) { }\n", after)

    def test_record_that_inherits(self):
        before = "public sealed record Circle(string Name, double Radius) : Shape(Name)\n{\n    public double Area => 3 * Radius;\n}\n"
        self.assertEqual(
            rewrite(before),
            "public sealed record class Circle : Shape\n{ public Circle(string Name, double Radius) { }\n"
            "    public double Area => 3 * Radius;\n}\n")

    def test_nested_record_keeps_its_indentation(self):
        before = ("public sealed class Outer\n{\n    private sealed record Row(\n        int Status,\n        string? Code = null)\n"
                  "    {\n        public static Row Ok() => new(0);\n    }\n}\n")
        after = rewrite(before)
        self.assertIn("    private sealed record class Row\n", after)
        self.assertIn("    { public Row( int Status, string? Code = null) { }\n", after)
        self.same_line_count(before, after)

    def test_a_variable_named_record_is_not_a_declaration(self):
        before = ("foreach (var record in records)\n{\n    record.Check();\n}\n"
                  "var result = records.Select(\n    record => record.Id);\n")
        self.assertEqual(rewrite(before), before)

    def test_unusual_declaration_is_left_alone(self):
        before = 'public class Odd(string text = "a;b")\n{\n}\n'
        self.assertEqual(rewrite(before), before)


def link(inside):
    """A link as the filter writes it. `inside` is what Sphinx is given: brackets, the role, punctuation."""
    return "\\verbatim embed:rst:inline " + inside + "\\ \\endverbatim"


class CommentTests(unittest.TestCase):
    def test_see_cref_becomes_a_link_and_summary_a_paragraph(self):
        self.assertEqual(
            rewrite('    /// <summary>Uses a <see cref="Order"/> here.</summary>\n'),
            "    /// <para>Uses a " + link(":cs:obj:`Order`") + " here.</para>\n")

    def test_summary_on_its_own_lines(self):
        self.assertEqual(rewrite("/// <summary>\n/// Text.\n/// </summary>\n"), "/// <para>\n/// Text.\n/// </para>\n")

    def test_prefix_generic_arguments_and_parameters_are_left_out_of_the_name(self):
        before = ('/// <see cref="M:A.Box{T}.Put(T)"/> <see cref="Box{TKey, List{T}}"/> '
                  '<see cref="T:A.B.Result{T}"/> <see cref="Box&lt;T&gt;"/>\n')
        self.assertEqual(
            rewrite(before),
            "/// " + " ".join(link(f":cs:obj:`{name}`") for name in ("A.Box.Put", "Box", "A.B.Result", "Box")) + "\n")

    def test_see_with_its_own_text(self):
        self.assertEqual(rewrite('/// The <see cref="Order">order</see> of a day\n'),
                         "/// The " + link(":cs:obj:`order <Order>`") + " of a day\n")
        # ` and < mean something in a link, so they get a backslash.
        self.assertEqual(rewrite('/// <see cref="Box{T}">a Box&lt;T&gt; of `T`</see>\n'),
                         "/// " + link(":cs:obj:`a Box\\<T> of \\`T\\` <Box>`") + "\n")

    def test_punctuation_next_to_a_link_is_taken_inside(self):
        before = '/// <see cref="A"/>, <see cref="B"/>; (<see cref="C"/>) <see cref="D"/>\'s <see cref="E"/>s.\n'
        self.assertEqual(
            rewrite(before),
            "/// " + link(":cs:obj:`A`,") + " " + link(":cs:obj:`B`;") + " " + link("(:cs:obj:`C`)") + " "
            + link(":cs:obj:`D`'s") + " " + link(":cs:obj:`E`\\ s") + ".\n")

    def test_anything_else_after_a_link_gets_a_space(self):
        self.assertEqual(
            rewrite('/// A <see cref="A"/>-based <see cref="B"/>.Name <see cref="C"/></summary>\n'),
            "/// A " + link(":cs:obj:`A`") + " -based " + link(":cs:obj:`B`") + ".Name " + link(":cs:obj:`C`") + " </para>\n")
        self.assertEqual(rewrite('/// See <see cref="A"/>\n'), "/// See " + link(":cs:obj:`A`") + "\n")

    def test_every_link_stands_the_way_doxygen_and_breathe_need_it(self):
        """rewrite_see() in cs_doxygen_filter.py explains the two conditions checked here."""
        befores = ["", " ", "(", "[", "{", "'", '"', "x", "/", "*", "-", ">", ".", ",", "&lt;"]
        afters = ["", " ", ".", ",", ";", ":", "!", "?", ")", "]", "}", "'", '"', "s", "'s", "x", "/", "*", "-",
                  "<b>", "&gt;", "</summary>"]
        tags = ['<see cref="A.Box{T}.Put(T)"/>', '<see cref="A">some `odd` text</see>', '<seealso cref="A"/>']
        links = 0
        for before, after, tag in itertools.product(befores, afters, tags):
            line = f"/// Text {before}{tag}{after} more {before}{tag}{after}"
            written = rewrite(line + "\n")
            with self.subTest(line=line):
                self.assertEqual(written.count("\n"), 1)
                starts = re.findall(r"\\verbatim(?: embed:rst:inline [(\[{']*:cs:obj:`)?", written)
                ends = re.findall(r"(..)\\endverbatim(.?)", written)
                self.assertEqual(len(starts), len(ends))
                for start in starts:
                    self.assertTrue(start.endswith(":cs:obj:`"), "Breathe needs a space after 'inline', then the link")
                for before_end, after_end in ends:
                    self.assertEqual(before_end, "\\ ", "Doxygen needs a space before \\endverbatim")
                    self.assertIn(after_end, ("", " ", "."), "Doxygen needs a space, a full stop or the line end after it")
                links += len(starts)
        self.assertGreater(links, 1500, "most of these lines should have got their links")

    def test_seealso(self):
        self.assertEqual(rewrite('/// <seealso cref="IWorker.Work(int)"/>\n'),
                         "/// \\sa " + link(":cs:obj:`IWorker.Work`") + "\n")
        self.assertEqual(rewrite('/// <seealso href="https://example.org/a">A page</seealso>\n'),
                         '/// \\sa <a href="https://example.org/a">A page</a>\n')

    def test_see_href_becomes_a_web_link(self):
        self.assertEqual(
            rewrite('/// Read (<see href="https://example.org/a?b=1&amp;c=2">it\'s a page</see>), or <see href="https://example.org/b?c=1&amp;d=2"/>.\n'),
            '/// Read (<a href="https://example.org/a?b=1&amp;c=2">it\'s a page</a>), '
            'or <a href="https://example.org/b?c=1&amp;d=2">https://example.org/b?c=1&amp;d=2</a>.\n')

    # Doxygen prints everything between two " signs as it is written, tags and commands included
    # (quote_signs() in cs_doxygen_filter.py). The next four tests are about that.

    def test_link_inside_a_quoted_phrase_becomes_plain_text(self):
        self.assertEqual(
            rewrite('/// The "<see cref="A"/>" and "big <see cref="B">bee</see> thing", then <see cref="C"/>.\n'),
            '/// The "A" and "big bee thing", then ' + link(":cs:obj:`C`") + ".\n")
        self.assertEqual(
            rewrite('/// Read "<see href="https://example.org/a">this</see>" or "<see href="https://example.org/b?c=1&amp;d=2"/>".\n'),
            '/// Read "this" or "https://example.org/b?c=1&amp;d=2".\n')

    def test_quoted_phrase_over_several_lines(self):
        self.assertEqual(
            rewrite('/// The "big\n/// <see cref="A"/>\n/// thing" and <see cref="B"/>.\n'),
            '/// The "big\n/// A\n/// thing" and ' + link(":cs:obj:`B`") + ".\n")

    def test_quote_signs_that_do_not_start_a_phrase(self):
        # '"', \" and &quot; do not, and neither does a " sign in a link's own text.
        self.assertEqual(
            rewrite('/// A \'"\' sign, <see cref="A"/>, an escaped \\" sign, <see cref="B">6" pipe</see> and <see cref="C"/>.\n'),
            "/// A '\"' sign, " + link(":cs:obj:`A`,") + ' an escaped \\" sign, ' + link(':cs:obj:`6" pipe <B>`')
            + " and " + link(":cs:obj:`C`") + ".\n")
        self.assertEqual(
            rewrite('/// A 6&quot; pipe and <see cref="A"/>.\n'),
            "/// A 6&quot; pipe and " + link(":cs:obj:`A`") + ".\n")

    def test_after_a_quote_sign_without_a_partner_links_are_plain_text(self):
        # Only until the comment ends: the next comment starts counting again.
        self.assertEqual(
            rewrite('/// A 6" pipe and <see cref="A"/>.\n/// <param name="x">The <see cref="B"/>.</param>\n\n/// <see cref="C"/>\n'),
            '/// A 6" pipe and A.\n/// <param name="x">The B.</param>\n\n/// ' + link(":cs:obj:`C`") + "\n")

    def test_tags_that_are_left_to_doxygen(self):
        before = ('/// <see cref="operator +(Box, Box)"/> <see cref="this[int]"/> <see langword="null"/>\n'
                  '/// <inheritdoc cref="Other"/>\n')
        self.assertEqual(rewrite(before), before)

    def test_paramref_and_typeparamref_become_code(self):
        self.assertEqual(rewrite('/// When <paramref name="count"/> of <typeparamref name="T"/> is 0.\n'),
                         "/// When <c>count</c> of <c>T</c> is 0.\n")

    def test_comment_that_is_only_inheritdoc_is_removed(self):
        before = "public class A : I\n{\n    /// <inheritdoc/>\n    public int Run() => 1;\n\n    /// <inheritdoc />\n    public int Stop() => 2;\n}\n"
        self.assertEqual(rewrite(before), "public class A : I\n{\n\n    public int Run() => 1;\n\n\n    public int Stop() => 2;\n}\n")

    def test_inheritdoc_next_to_other_lines_stays(self):
        before = ("    /// <inheritdoc/>\n    /// <remarks>More.</remarks>\n    public int Run() => 1;\n\n"
                  "    /// <remarks>More.</remarks>\n    /// <inheritdoc/>\n    public int Stop() => 2;\n")
        self.assertEqual(rewrite(before), before)

    def test_only_documentation_comments_are_touched(self):
        before = ('public class A\n{\n    // <see cref="X"/> in an ordinary comment, <summary>\n'
                  '    //// <see cref="X"/> after four slashes\n'
                  '    private string text = "<see cref=\\"X\\"/> <summary> <paramref name=\\"x\\"/>";\n}\n')
        self.assertEqual(rewrite(before), before)

    def test_comments_keep_the_line_count(self):
        before = ("namespace A;\n\n/// <summary>\n/// A <see cref=\"B\"/>,\n/// on <see cref=\"C\">several</see> lines.\n/// </summary>\n"
                  "/// <seealso cref=\"D\"/>\npublic sealed class E(int x) : F(x)\n{\n    /// <inheritdoc/>\n    public int G() => 1;\n}\n")
        after = rewrite(before)
        self.assertEqual(before.count("\n"), after.count("\n"))
        self.assertEqual(after.splitlines()[10], "    public int G() => 1;")


if __name__ == "__main__":
    unittest.main()
