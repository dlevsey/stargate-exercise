"""Checks, with Doxygen itself, that links in /// comments do not make it lose code.

cs_doxygen_filter.py writes a link in a spelling that depends on how Doxygen reads a comment
(rewrite_see() explains it). When Doxygen misses the end of such a link, it takes the rest of
the file for comment text, and the types in it vanish without a message.

Stargate's own code has no /// comments yet, so a build would not notice if another version of
Doxygen read that spelling differently. This check would: it puts links in every awkward place
of small C# files, runs Doxygen on them, and looks whether every type, member and link is
still there.

Run with:  ./test.sh      It is skipped when Doxygen is not installed (./setup.sh installs it).
"""
import os
import tempfile
import unittest
from pathlib import Path
from xml.etree import ElementTree

import cs_doxygen_filter
from common import TOOLS
from prebuild import doxygen_on

DOXYGEN = Path(os.environ.get("DOXYGEN") or TOOLS / "doxygen")
SEE = '<see cref="Holder"/>'

# What is tried -> the lines of one comment. sample() says where the comment is put.
COMMENTS = {
    "a plain sentence": [
        f"<summary>A {SEE} here.</summary>",
        "<remarks>More.</remarks>"],
    "punctuation after the link": [
        f"<summary>A {SEE}, b {SEE}; c {SEE}: d {SEE}! e {SEE}? f {SEE}'s g {SEE}s h.</summary>",
        '<remarks>More "q".</remarks>'],
    "brackets and quotes around the link": [
        f"<summary>A ({SEE}) b [{SEE}] c {{{SEE}}} d '{SEE}' e ({SEE}, {SEE}) f ('{SEE}').</summary>",
        "<remarks>More.</remarks>"],
    "awkward neighbours": [
        f"<summary>A {SEE}/b {SEE}> c {SEE}-d {SEE}* e {SEE}{SEE} f pre{SEE}post g {SEE}.Name h {SEE}</summary>",
        "<remarks>More.</remarks>"],
    "inside a quoted phrase": [
        f'<summary>A "{SEE}" and "quoted {SEE} phrase", then {SEE}.</summary>',
        "<remarks>More.</remarks>"],
    "at the start and the end of a line": [
        "<summary>A", f"{SEE} plus {SEE}", SEE, "end.</summary>",
        "<remarks>More.</remarks>"],
    "a link with its own text": [
        '<summary>A <see cref="Holder">odd `tick` \\ and "quote" text</see>, plus <see cref="Holder">it\'s</see>.</summary>',
        "<remarks>More.</remarks>"],
    "a quoted phrase over several lines": [
        '<summary>The "big', f'{SEE} thing" and {SEE}.</summary>',
        "<remarks>More.</remarks>"],
    "a quote sign without a partner": [
        f'<summary>A <see cref="Holder">6" pipe</see> fits a 6" hole, {SEE} too.</summary>',
        "<remarks>More.</remarks>"],
    "a quote sign written as &quot;": [
        f"<summary>A pipe fits a 6&quot; hole, {SEE} too.</summary>",
        "<remarks>More.</remarks>"],
    "seealso": [
        "<summary>Text.</summary>",
        '<seealso cref="Holder"/>',
        '<seealso cref="Holder.Work(int)">Work of Holder</seealso>',
        '<seealso href="https://example.org/a">A page</seealso>'],
    "generic names and prefixes": [
        '<summary>A <see cref="T:Probe.Box{T}"/>, <see cref="Box{TKey, List{T}}.Put(T)"/>, <see cref="M:A.B.C(System.String)"/>.</summary>',
        "<remarks>More.</remarks>"],
    "web links and the other tags": [
        '<summary>A (<see href="https://example.org/a?b=1&amp;c=2">page</see>), <see href="https://example.org/b"/>.</summary>',
        f'<remarks>Uses <paramref name="x"/>, <typeparamref name="T"/>, <see langword="null"/> and {SEE}.</remarks>'],
    "in a list and in an example": [
        "<summary>Text.</summary>",
        "<remarks>",
        '<list type="bullet">',
        f"<item><description>One {SEE}.</description></item>",
        f"<item><description>{SEE}</description></item>",
        "</list>",
        f"<example>Call {SEE}:<code>new Holder().Work(1);</code></example>",
        "</remarks>"],
    "a comment of one line": [
        f"<summary>A {SEE}, here.</summary>"],
    "nothing but a link": [
        SEE],
    "the link ends the comment": [
        "<summary>Text.</summary>",
        f"See {SEE}"],
}
# Added to the comment of every method.
ON_METHODS = [
    f'<param name="x">The {SEE} value.</param>',
    f"<returns>A {SEE}</returns>",
    f'<exception cref="System.Exception">When {SEE}.</exception>',
]
# What Doxygen has to find in every sample: type -> its members.
EXPECTED = {"Holder": {"Work", "After"}, "Holder::Inner": {"Deep"}, "Second": set(), "Third": {"Last"}}


def sample(namespace, comment, block_namespace):
    """A C# file with `comment` on a type, on a method, on a type inside a type and on its
    method, with code after each of them. That code is what Doxygen loses when it goes wrong."""
    def doc(indent, lines):
        return [indent + "/// " + line for line in lines]

    on_method = comment + ON_METHODS
    body = [
        *doc("", comment), "public sealed class Holder", "{",
        *doc("    ", on_method), "    public int Work(int x) => x;", "",
        *doc("    ", comment), "    public sealed class Inner", "    {",
        *doc("        ", on_method), "        public int Deep(int x) => x;", "    }", "",
        "    /// <summary>Plain.</summary>", "    public int After() => 2;", "}", "",
        "/// <summary>Plain.</summary>", "public sealed class Second { }", "",
        *doc("", comment), "public sealed class Third", "{",
        *doc("    ", on_method), "    public int Last(int x) => x;", "}",
    ]
    if block_namespace:
        lines = [f"namespace {namespace}", "{", *("    " + line if line else line for line in body), "}"]
    else:
        lines = [f"namespace {namespace};", "", *body]
    return "\n".join(lines) + "\n"


@unittest.skipUnless(DOXYGEN.is_file(), f"Doxygen is not installed ({DOXYGEN})")
class CommentLinksThroughDoxygen(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Write every sample, rewritten as in a build, and run Doxygen once over all of them."""
        cls.cases = {}       # namespace -> (what is tried, number of links the filter wrote)
        cls.members = {}     # "Probe1::Holder" -> names of its members
        cls.links = {}       # namespace -> the links Doxygen passed on, as text
        cls.texts = {}       # namespace -> all the text Doxygen wrote for it
        with tempfile.TemporaryDirectory(prefix="stargate-docs-test-") as work:
            code, out = Path(work) / "code", Path(work) / "out"
            code.mkdir()
            out.mkdir()
            for number, (tried, comment) in enumerate(COMMENTS.items(), start=1):
                for block_namespace in (False, True):
                    namespace = f"Probe{number}{'Block' if block_namespace else ''}"
                    rewritten = cs_doxygen_filter.rewrite(sample(namespace, comment, block_namespace))
                    (code / f"{namespace}.cs").write_text(rewritten, encoding="utf-8", newline="\n")
                    style = "namespace with braces" if block_namespace else "namespace with a semicolon"
                    cls.cases[namespace] = (f"{tried} ({style})", rewritten.count("\\endverbatim"))
            cls.exit_code, cls.said = doxygen_on(DOXYGEN, code, out)

            index = ElementTree.parse(out / "xml" / "index.xml").getroot()
            for compound in index.iter("compound"):
                if compound.get("kind") != "class":
                    continue
                name = compound.findtext("name")
                cls.members[name] = {member.findtext("name") for member in compound.iter("member")}
                described = ElementTree.parse(out / "xml" / f"{compound.get('refid')}.xml").getroot()
                namespace = name.split("::")[0]
                cls.links.setdefault(namespace, []).extend(v.text or "" for v in described.iter("verbatim"))
                cls.texts[namespace] = cls.texts.get(namespace, "") + "".join(described.itertext())

    def test_doxygen_ran(self):
        self.assertEqual(self.exit_code, 0, self.said)

    def test_no_type_and_no_member_is_lost(self):
        for namespace, (tried, _) in self.cases.items():
            for type_name, members in EXPECTED.items():
                with self.subTest(tried=tried, type=type_name):
                    self.assertIn(f"{namespace}::{type_name}", self.members, "Doxygen lost this type")
                    self.assertLessEqual(members, self.members[f"{namespace}::{type_name}"], "Doxygen lost a member")

    def test_every_link_arrives_as_it_was_written(self):
        for namespace, (tried, written) in self.cases.items():
            with self.subTest(tried=tried):
                arrived = self.links.get(namespace, [])
                self.assertEqual(len(arrived), written, "links written by the filter and links in Doxygen's XML")
                for text in arrived:
                    self.assertRegex(text, r"\Aembed:rst:inline [(\[{']*:cs:obj:`.+`.*\\ \Z")
                # A link that Doxygen did not understand shows up as the commands it is made of.
                self.assertNotIn("verbatim", self.texts[namespace], "a link was printed as text")

    def test_doxygen_has_nothing_to_say(self):
        self.assertEqual(self.said, "", "Doxygen printed a message about the samples")


if __name__ == "__main__":
    unittest.main()
