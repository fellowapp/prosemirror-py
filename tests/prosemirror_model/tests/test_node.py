from typing import Literal

from prosemirror.model import Fragment, Schema
from prosemirror.test_builder import eq, out
from prosemirror.test_builder import test_schema as schema

doc = out["doc"]
blockquote = out["blockquote"]
p = out["p"]
li = out["li"]
ul = out["ul"]
em = out["em"]
strong = out["strong"]
code = out["code"]
a = out["a"]
br = out["br"]
hr = out["hr"]
img = out["img"]

custom_schema: Schema[
    Literal["doc", "paragraph", "text", "contact", "hard_break"], str
] = Schema(
    {
        "nodes": {
            "doc": {"content": "paragraph+"},
            "paragraph": {"content": "(text|contact)*"},
            "text": {
                "toDebugString": lambda _: "custom_text",
            },
            "contact": {
                "inline": True,
                "attrs": {"name": {}, "email": {}},
                "leafText": (
                    lambda node: f"{node.attrs['name']} <{node.attrs['email']}>"
                ),
            },
            "hard_break": {
                "toDebugString": lambda _: "custom_hard_break",
            },
        },
    }
)


class TestToString:
    def test_nesting(self):
        node = doc(ul(li(p("hey"), p()), li(p("foo"))))
        expected = 'doc(bullet_list(list_item(paragraph("hey"), paragraph), list_item(paragraph("foo"))))'  # noqa
        assert str(node) == expected

    def test_shows_inline_children(self):
        node = doc(p("foo", img, br, "bar"))
        assert str(node) == 'doc(paragraph("foo", image, hard_break, "bar"))'

    def test_shows_marks(self):
        node = doc(p("foo", em("bar", strong("quux")), code("baz")))
        expected = 'doc(paragraph("foo", em("bar"), em(strong("quux")), code("baz")))'
        assert str(node) == expected

    def test_has_default_tostring_method_text(self):
        assert str(schema.text("hello")) == '"hello"'

    def test_has_default_tostring_method_br(self):
        assert str(br()) == "hard_break"

    def test_nodespec_to_debug_string(self):
        assert str(custom_schema.text("hello")) == "custom_text"

    def test_respected_by_fragment(self):
        f = Fragment.from_array(
            [
                custom_schema.text("hello"),
                custom_schema.nodes["hard_break"].create_checked(),
                custom_schema.text("world"),
            ],
        )
        assert str(f) == "<custom_text, custom_hard_break, custom_text>"

    def test_should_respect_custom_leafText_spec(self):
        contact = custom_schema.nodes["contact"].create_checked(
            {"name": "Bob", "email": "bob@example.com"}
        )
        paragraph = custom_schema.nodes["paragraph"].create_checked(
            {}, [custom_schema.text("Hello "), contact]
        )

        assert contact.text_content, "Bob <bob@example.com>"
        assert paragraph.text_content, "Hello Bob <bob@example.com>"


class TestCut:
    @staticmethod
    def cut(doc, cut):
        assert eq(doc.cut(doc.tag.get("a", 0), doc.tag.get("b")), cut)

    def test_extracts_full_block(self):
        self.cut(doc(p("foo"), "<a>", p("bar"), "<b>", p("baz")), doc(p("bar")))

    def test_cuts_text(self):
        self.cut(doc(p("0"), p("foo<a>bar<b>baz"), p("2")), doc(p("bar")))

    def test_cuts_deeply(self):
        self.cut(
            doc(
                blockquote(
                    ul(li(p("a"), p("b<a>c")), li(p("d")), "<b>", li(p("e"))), p("3")
                )
            ),
            doc(blockquote(ul(li(p("c")), li(p("d"))))),
        )

    def test_works_from_the_left(self):
        self.cut(doc(blockquote(p("foo<b>bar"))), doc(blockquote(p("foo"))))

    def test_works_to_the_right(self):
        self.cut(doc(blockquote(p("foo<a>bar"))), doc(blockquote(p("bar"))))

    def test_preserves_marks(self):
        self.cut(
            doc(p("foo", em("ba<a>r", img, strong("baz"), br), "qu<b>ux", code("xyz"))),
            doc(p(em("r", img, strong("baz"), br), "qu")),
        )


class TestBetween:
    @staticmethod
    def between(doc, *nodes):
        i = 0

        def iteratee(node, pos, *args):
            nonlocal i

            if i == len(nodes):
                raise Exception(f"More nodes iterated than list ({node.type.name})")
            compare = node.text if node.is_text else node.type.name
            if compare != nodes[i]:
                raise Exception(f"Expected {nodes[i]!r}, got {compare!r}")
            i += 1
            if not node.is_text and doc.node_at(pos) != node:
                raise Exception(
                    f"Pos {pos} does not point at node {node!r} {doc.nodeAt(pos)!r}"
                )

        doc.nodes_between(doc.tag["a"], doc.tag["b"], iteratee)

    def test_iterates_over_text(self):
        self.between(doc(p("foo<a>bar<b>baz")), "paragraph", "foobarbaz")

    def test_descends_multiple_levels(self):
        self.between(
            doc(blockquote(ul(li(p("f<a>oo")), p("b"), "<b>"), p("c"))),
            "blockquote",
            "bullet_list",
            "list_item",
            "paragraph",
            "foo",
            "paragraph",
            "b",
        )

    def test_iterates_over_inline_nodes(self):
        self.between(
            doc(
                p(
                    em("x"),
                    "f<a>oo",
                    em("bar", img, strong("baz"), br),
                    "quux",
                    code("xy<b>z"),
                )
            ),
            "paragraph",
            "foo",
            "bar",
            "image",
            "baz",
            "hard_break",
            "quux",
            "xyz",
        )


class TestTextBetween:
    def test_passing_custom_function_as_leaf_text(self):
        d = doc(p("foo", img, br))

        def leaf_text(node):
            if node.type.name == "image":
                return "<image>"
            elif node.type.name == "hard_break":
                return "<break>"

        text = d.text_between(0, d.content.size, "", leaf_text)
        assert text == "foo<image><break>"

    def test_works_with_leafText(self):
        d = custom_schema.nodes["doc"].create_checked(
            {},
            [
                custom_schema.nodes["paragraph"].create_checked(
                    {},
                    [
                        custom_schema.text("Hello "),
                        custom_schema.nodes["contact"].create_checked(
                            {"name": "Alice", "email": "alice@example.com"}
                        ),
                    ],
                )
            ],
        )
        assert d.text_between(0, d.content.size) == "Hello Alice <alice@example.com>"

    def test_should_ignore_leafText_spec_when_passing_a_custom_leaf_text(self):
        d = custom_schema.nodes["doc"].create_checked(
            {},
            [
                custom_schema.nodes["paragraph"].create_checked(
                    {},
                    [
                        custom_schema.text("Hello "),
                        custom_schema.nodes["contact"].create_checked(
                            {"name": "Alice", "email": "alice@example.com"}
                        ),
                    ],
                )
            ],
        )
        assert (
            d.text_between(0, d.content.size, "", "<anonymous>") == "Hello <anonymous>"
        )


class TestTextContent:
    def test_whole_doc(self):
        assert doc(p("foo")).text_content == "foo"

    def test_text_node(self):
        assert schema.text("foo").text_content == "foo"

    def test_nested_element(self):
        node = doc(ul(li(p("hi")), li(p(em("a"), "b"))))
        assert node.text_content == "hiab"


class TestFrom:
    @staticmethod
    def from_(arg, expect):
        assert expect.copy(Fragment.from_(arg)).eq(expect)

    def test_wraps_single_node(self):
        self.from_(schema.node("paragraph"), doc(p()))

    def test_wraps_array(self):
        self.from_([schema.node("hard_break"), schema.text("foo")], p(br, "foo"))

    def test_preserves_a_fragment(self):
        self.from_(doc(p("foo")).content, doc(p("foo")))

    def test_accepts_null(self):
        self.from_(None, p())

    def test_joins_adjacent_text(self):
        self.from_([schema.text("a"), schema.text("b")], p("ab"))


class TestToJSON:
    @staticmethod
    def round_trip(doc):
        assert schema.node_from_json(doc.to_json()).eq(doc)

    def test_serialize_simple_node(self):
        self.round_trip(doc(p("foo")))

    def test_serialize_marks(self):
        self.round_trip(doc(p("foo", em("bar", strong("baz")), " ", a("x"))))

    def test_serialize_inline_leaf_nodes(self):
        self.round_trip(doc(p("foo", em(img, "bar"))))

    def test_serialize_block_leaf_nodes(self):
        self.round_trip(doc(p("a"), hr, p("b"), p()))

    def test_serialize_nested_nodes(self):
        self.round_trip(
            doc(blockquote(ul(li(p("a"), p("b")), li(p(img))), p("c")), p("d"))
        )
