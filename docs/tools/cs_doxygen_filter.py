#!/usr/bin/env python3
"""Rewrites modern C# into a form Doxygen understands.

tools/prebuild.py calls rewrite() on a copy of every C# file before Doxygen reads
it. The real file is never changed, and the number of lines never changes either,
so the line numbers Doxygen reports are the real ones.

Declarations. Doxygen 1.18 does not understand four things that Stargate's code
uses, so they are rewritten into an older form that means the same:

1. A type that ends with `;` and has no body gets ` { }`.
   Doxygen silently drops such types.            class Program;  ->  class Program { }
2. Arguments passed to a base constructor are removed.
   Doxygen garbles the base name otherwise.      : Base(message)  ->  : Base
3. A primary constructor becomes an ordinary constructor inside the body, so
   the page lists it with its parameters.        class A(IDep dep) { ... }  ->  class A { public A(IDep dep) { } ... }
4. A record that has a body is written as a `record class` (or `record struct`),
   with rule 3 applied to its parameters. Doxygen takes any other record for a
   method and loses the members in its body.     record R(int X) { ... }  ->  record class R { public R(int X) { } ... }
   A record without a body, such as `record R(int X);`, is left alone: the C#
   extension for Sphinx shows it as a record with its parameters.

/// comments. Four tags come out wrong or without a link, so they are rewritten too:

5. <see cref="X"/> and <seealso cref="X"/> become a link made by the C# extension
   for Sphinx, the same kind the guide pages use. Doxygen writes the short form as
   plain text. Generic arguments and parameter lists are left out of the name that
   is looked up:                                 cref="Box{T}.Put(T)"  ->  Box.Put
   Doxygen ends a summary at such a link, in the middle of the sentence, so
   <summary> is written as <para>: the same text, as an ordinary first paragraph.
   The tag has to start and end on one line. Between two " signs the name is
   written without a link (quote_signs() says why). rewrite_see() explains the
   exact spelling of a link.
6. <see href="URL">text</see> becomes an ordinary web link.
7. <paramref name="x"/> and <typeparamref name="T"/> become <c>x</c>. Doxygen adds
   a stray space after them otherwise.
8. A comment that is only <inheritdoc/> is removed. Doxygen then copies the comment
   of the interface member or base member by itself, in full.

To see what Doxygen is given for one file:  python3 tools/cs_doxygen_filter.py <file.cs>
The checks:  ./test.sh   (test_cs_doxygen_filter.py for the rules, test_comment_links.py
runs Doxygen itself on links in awkward places).
"""
import html
import re
import sys

MODIFIERS = r"(?:(?:public|internal|private|protected|sealed|abstract|static|partial|readonly|ref|file|unsafe|new)\s+)*"
PARENS = r"\((?:[^()]|\([^()]*\))*\)"  # a parenthesised list, with one level of parentheses inside it
KEYWORD = r"(?:record\s+(?:class|struct)|class|struct|interface|record)"
# A type declaration, from the start of its line to the first `{` or `;`.
DECLARATION = re.compile(rf"^[ \t]*{MODIFIERS}{KEYWORD}\s+\w+[^;{{}}]*[;{{]", re.M)
# The start of that declaration: keyword, name, optional <T>, optional primary-constructor parameters.
HEAD = re.compile(rf"[ \t]*{MODIFIERS}(?P<keyword>{KEYWORD})\s+(?P<name>\w+)"
                  rf"(?P<generics>\s*<[^<>]*(?:<[^<>]*>[^<>]*)*>)?(?P<params>\s*{PARENS})?")
BASE_CALL = re.compile(rf"(?<=[\w>])\s*{PARENS}")
COMMENT = re.compile(r"//[^\n]*|/\*.*?\*/", re.S)


def newlines_of(text):
    """Only the line breaks of a piece of text, so that removing it does not move later lines."""
    return "\n" * text.count("\n")


def base_list_start(header):
    """Position of the `:` that starts the base list, or -1."""
    depth = 0
    for position, char in enumerate(header):
        depth += char in "(<[" or -(char in ")>]")
        if char == ":" and depth == 0:
            return position
    return -1


def rewrite_declaration(match):
    text = match.group(0)
    header, end = text[:-1], text[-1]
    if header.count("(") != header.count(")"):
        return text  # something unusual, such as a `;` inside a default value: leave it as it is

    constructor = ""
    head = HEAD.match(header)
    if head and head.group("keyword") == "record":
        if end == ";":
            return text  # rule 4: a record without a body is fine as it is
        header = header[:head.end("keyword")] + " class" + header[head.end("keyword"):]
        head = HEAD.match(header)
    if head and head.group("params"):
        parameters = " ".join(COMMENT.sub(" ", head.group("params")).split())
        constructor = f" public {head.group('name')}{parameters} {{ }}"
        header = header[:head.start("params")] + newlines_of(head.group("params")) + header[head.end("params"):]

    colon = base_list_start(header)
    if colon >= 0:
        where = re.search(r"\bwhere\b", header[colon:])
        stop = colon + where.start() if where else len(header)
        bases = BASE_CALL.sub(lambda call: newlines_of(call.group(0)), header[colon:stop])
        header = header[:colon] + bases + header[stop:]

    if end == ";":
        return header + " {" + constructor + " }"
    return header + "{" + constructor


# ---- /// comments -------------------------------------------------------------------------------

# A documentation comment: lines that follow each other and start with exactly three slashes.
DOC_COMMENT = re.compile(r"^[ \t]*///(?!/)[^\n]*(?:\n[ \t]*///(?!/)[^\n]*)*", re.M)
DOC_LINE = re.compile(r"(?P<lead>[ \t]*///)(?P<text>.*)")
# <see cref="X"/>, <see cref="X">text</see>, and the same with seealso or href.
# "head" is what stands directly before the tag: opening brackets or an opening quote.
# "tail" is what follows the tag without a space: 's or s (a plural), then closing punctuation.
# "next" is the character after that; it is looked at, not taken.
SEE = re.compile(r"(?P<head>[(\[{']*)"
                 r'<see(?P<also>also)?\s+(?P<kind>cref|href)\s*=\s*"(?P<target>[^"]+)"\s*'
                 r"(?:/>|>(?P<text>[^<]*)</see(?:also)?>)"
                 r"(?P<tail>(?:'?s(?!\w))?[,;:!?)\]}']*)(?=(?P<next>.?))")
PARAMREF = re.compile(r'<(?:type)?paramref\s+name\s*=\s*"(?P<name>[^"]+)"\s*/>')
INHERITDOC_ONLY = re.compile(r"^(?P<before>(?:.*\n)?)[ \t]*///[ \t]*<inheritdoc[ \t]*/>[ \t]*(?=\n(?![ \t]*///))", re.M)
GENERIC_ARGUMENTS = re.compile(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}|&lt;.*&gt;")
PLAIN_NAME = re.compile(r"[^\W\d]\w*(?:\.[^\W\d]\w*)*\Z")   # Name or Name.Name.Name


def cref_name(cref):
    """The name a cref points at, as the site looks names up:  M:Box{T}.Put(T) -> Box.Put"""
    name = re.sub(r"^[A-Z]:", "", cref.strip()).split("(")[0]
    return GENERIC_ARGUMENTS.sub("", name).strip()


def quote_signs(text):
    """How many " signs in `text` open or close a quoted phrase for Doxygen.

    Doxygen 1.18 (src/doctokenizer.l, WORD1) takes everything from one " sign to the next
    as plain text, over several lines too: tags and commands in between are printed as they
    are written. A " sign written as '"', as \\" or as &quot; does not count. So a " sign
    that has no partner, such as the sign for inches, is best written as &quot;.
    """
    return text.count('"') - text.count("'\"'") - text.count('\\"')


def rewrite_see(match, in_quoted_phrase):
    """Rules 5 and 6, for one tag."""
    text = html.unescape(match.group("text") or "").strip()
    head, tail = match.group("head"), match.group("tail")
    also = "\\sa " if match.group("also") else ""
    is_web_link = match.group("kind") == "href"
    name = match.group("target") if is_web_link else cref_name(match.group("target"))
    if not name:
        return match.group(0)
    if in_quoted_phrase:
        # quote_signs() says why: here a link would be printed as the commands it is made of.
        # The text or the name is all that can be shown.
        return head + (match.group("text") or name) + tail
    if is_web_link:
        shown = html.escape(text, quote=False) if text else name
        return f'{also}{head}<a href="{name}">{shown}</a>{tail}'
    if not PLAIN_NAME.match(name):
        return match.group(0)   # an operator, an indexer, ...: left to Doxygen, which prints the name
    if text:
        shown = text.replace("\\", "\\\\").replace("`", "\\`").replace("<", "\\<")
        name = f"{shown} <{name}>"
    if tail.startswith("s"):
        tail = "\\ " + tail     # reStructuredText wants "\ " between a link and a letter
    # \verbatim embed:rst:inline ... \endverbatim: Breathe hands what is in between to Sphinx as
    # it is, inside the sentence. :cs:obj: is the C# extension's "a type or member with this name".
    #
    # The spelling is this exact for a reason: two programs read it, and each is strict in its
    # own way. test_cs_doxygen_filter.py checks every point below, and test_comment_links.py
    # tries the result with Doxygen itself.
    #
    # Doxygen reads a comment in several steps, and each step decides by its own rules where such
    # a block ends. When one of them misses the end, the rest of the file counts as comment and
    # its types vanish from the site without a message. Doxygen 1.18 (src/scanner.l, state
    # "Comment") sees the end only when \endverbatim stands alone: after a space, and before a
    # space, a full stop or the end of the line. So:
    #   - the text ends with "\ " (reStructuredText for "nothing"), which gives the space before;
    #   - punctuation that follows the tag is taken inside ("tail"), so no space shows before it;
    #   - anything else that follows gets a space in front.
    #
    # Breathe 5.1 reads the text only when a space follows "embed:rst:inline"; without it the
    # build stops with "UnknownStateError: text". That space is shown on the page, where it
    # merges with the space that normally stands before a link. An opening bracket or quote
    # directly before the tag ("head") is taken inside, so that the space lands in front of it.
    link = f"\\verbatim embed:rst:inline {head}:cs:obj:`{name}`{tail}\\ \\endverbatim"
    if match.group("next") not in ("", " ", "\t", "."):
        link += " "
    return also + link


def rewrite_comment(match):
    """Rules 5 to 7, for one comment."""
    quotes = 0    # the " signs up to the place we are at, as Doxygen counts them (see quote_signs)
    lines = []
    for line in match.group(0).split("\n"):
        lead, text = DOC_LINE.match(line).group("lead", "text")
        pieces, position = [], 0
        for tag in SEE.finditer(text):
            before = text[position:tag.start()]
            quotes += quote_signs(before)
            written = rewrite_see(tag, in_quoted_phrase=quotes % 2 == 1)
            if "\\endverbatim" not in written:    # Doxygen does not look for " signs inside a link
                quotes += quote_signs(written)
            pieces += [before, written]
            position = tag.end()
        quotes += quote_signs(text[position:])
        text = "".join(pieces) + text[position:]
        text = text.replace("<summary>", "<para>").replace("</summary>", "</para>")        # rule 5, last part
        text = PARAMREF.sub(lambda reference: f"<c>{reference.group('name')}</c>", text)   # rule 7
        lines.append(lead + text)
    return "\n".join(lines)


def remove_lone_inheritdoc(match):
    """Rule 8: only when the line above is not part of the same comment."""
    before = match.group("before")
    return match.group(0) if before.lstrip().startswith("///") else before


def rewrite(source):
    source = DECLARATION.sub(rewrite_declaration, source)
    source = INHERITDOC_ONLY.sub(remove_lone_inheritdoc, source)
    return DOC_COMMENT.sub(rewrite_comment, source)


if __name__ == "__main__":
    with open(sys.argv[1], encoding="utf-8-sig") as source_file:
        sys.stdout.write(rewrite(source_file.read()))
