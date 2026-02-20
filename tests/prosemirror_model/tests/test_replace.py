import re

import pytest

from prosemirror.model import Slice
from prosemirror.test_builder import eq, out

doc = out["doc"]
blockquote = out["blockquote"]
h1 = out["h1"]
p = out["p"]
ul = out["ul"]
li = out["li"]


def rpl(doc_node, insert, expected):
    if insert is not None:
        slice = insert.slice(insert.tag["a"], insert.tag["b"])
    else:
        slice = Slice.empty
    result = doc_node.replace(doc_node.tag["a"], doc_node.tag["b"], slice)
    assert eq(result, expected), f"Expected {expected}, got {result}"


def bad(doc_node, insert, pattern):
    if insert is not None:
        slice = insert.slice(insert.tag["a"], insert.tag["b"])
    else:
        slice = Slice.empty
    with pytest.raises(Exception, match=re.compile(pattern, re.IGNORECASE)):
        doc_node.replace(doc_node.tag["a"], doc_node.tag["b"], slice)


class TestReplace:
    def test_joins_on_delete(self):
        rpl(doc(p("on<a>e"), p("t<b>wo")), None, doc(p("onwo")))

    def test_merges_matching_blocks(self):
        rpl(
            doc(p("on<a>e"), p("t<b>wo")),
            doc(p("xx<a>xx"), p("yy<b>yy")),
            doc(p("onxx"), p("yywo")),
        )

    def test_merges_when_adding_text(self):
        rpl(
            doc(p("on<a>e"), p("t<b>wo")),
            doc(p("<a>H<b>")),
            doc(p("onHwo")),
        )

    def test_can_insert_text(self):
        rpl(
            doc(p("before"), p("on<a><b>e"), p("after")),
            doc(p("<a>H<b>")),
            doc(p("before"), p("onHe"), p("after")),
        )

    def test_doesnt_merge_non_matching_blocks(self):
        rpl(
            doc(p("on<a>e"), p("t<b>wo")),
            doc(h1("<a>H<b>")),
            doc(p("onHwo")),
        )

    def test_can_merge_a_nested_node(self):
        rpl(
            doc(blockquote(blockquote(p("on<a>e"), p("t<b>wo")))),
            doc(p("<a>H<b>")),
            doc(blockquote(blockquote(p("onHwo")))),
        )

    def test_can_replace_within_a_block(self):
        rpl(
            doc(blockquote(p("a<a>bc<b>d"))),
            doc(p("x<a>y<b>z")),
            doc(blockquote(p("ayd"))),
        )

    def test_can_insert_a_lopsided_slice(self):
        rpl(
            doc(blockquote(blockquote(p("on<a>e"), p("two"), "<b>", p("three")))),
            doc(blockquote(p("aa<a>aa"), p("bb"), p("cc"), "<b>", p("dd"))),
            doc(blockquote(blockquote(p("onaa"), p("bb"), p("cc"), p("three")))),
        )

    def test_can_insert_a_deep_lopsided_slice(self):
        rpl(
            doc(
                blockquote(blockquote(p("on<a>e"), p("two"), p("three")), "<b>", p("x"))
            ),
            doc(blockquote(p("aa<a>aa"), p("bb"), p("cc")), "<b>", p("dd")),
            doc(blockquote(blockquote(p("onaa"), p("bb"), p("cc")), p("x"))),
        )

    def test_can_merge_multiple_levels(self):
        rpl(
            doc(
                blockquote(blockquote(p("hell<a>o"))),
                blockquote(blockquote(p("<b>a"))),
            ),
            None,
            doc(blockquote(blockquote(p("hella")))),
        )

    def test_can_merge_multiple_levels_while_inserting(self):
        rpl(
            doc(
                blockquote(blockquote(p("hell<a>o"))),
                blockquote(blockquote(p("<b>a"))),
            ),
            doc(p("<a>i<b>")),
            doc(blockquote(blockquote(p("hellia")))),
        )

    def test_can_insert_a_split(self):
        rpl(
            doc(p("foo<a><b>bar")),
            doc(p("<a>x"), p("y<b>")),
            doc(p("foox"), p("ybar")),
        )

    def test_can_insert_a_deep_split(self):
        rpl(
            doc(blockquote(p("foo<a>x<b>bar"))),
            doc(blockquote(p("<a>x")), blockquote(p("y<b>"))),
            doc(blockquote(p("foox")), blockquote(p("ybar"))),
        )

    def test_can_add_a_split_one_level_up(self):
        rpl(
            doc(blockquote(p("foo<a>u"), p("v<b>bar"))),
            doc(blockquote(p("<a>x")), blockquote(p("y<b>"))),
            doc(blockquote(p("foox")), blockquote(p("ybar"))),
        )

    def test_keeps_the_node_type_of_the_left_node(self):
        rpl(
            doc(h1("foo<a>bar"), "<b>"),
            doc(p("foo<a>baz"), "<b>"),
            doc(h1("foobaz")),
        )

    def test_keeps_the_node_type_even_when_empty(self):
        rpl(
            doc(h1("<a>bar"), "<b>"),
            doc(p("foo<a>baz"), "<b>"),
            doc(h1("baz")),
        )


class TestReplaceErrors:
    def test_doesnt_allow_the_left_side_to_be_too_deep(self):
        bad(
            doc(p("<a><b>")),
            doc(blockquote(p("<a>")), "<b>"),
            "deeper",
        )

    def test_doesnt_allow_a_depth_mismatch(self):
        bad(
            doc(p("<a><b>")),
            doc("<a>", p("<b>")),
            "inconsistent",
        )

    def test_rejects_a_bad_fit(self):
        bad(
            doc("<a><b>"),
            doc(p("<a>foo<b>")),
            "invalid content",
        )

    def test_rejects_unjoinable_content(self):
        bad(
            doc(ul(li(p("a")), "<a>"), "<b>"),
            doc(p("foo", "<a>"), "<b>"),
            "cannot join",
        )

    def test_rejects_an_unjoinable_delete(self):
        bad(
            doc(blockquote(p("a"), "<a>"), ul("<b>", li(p("b")))),
            None,
            "cannot join",
        )

    def test_check_content_validity(self):
        bad(
            doc(blockquote("<a>", p("hi")), "<b>"),
            doc(blockquote("hi", "<a>"), "<b>"),
            "invalid content",
        )
