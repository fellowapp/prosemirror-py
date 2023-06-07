import pytest

from prosemirror.model import DOMSerializer
from prosemirror.model.from_dom import from_html
from prosemirror.schema.basic import schema
from prosemirror.test_builder import out

doc = out["doc"]
p = out["p"]
li = out["li"]
ul = out["ul"]
em = out["em"]
a = out["a"]
blockquote = out["blockquote"]
strong = out["strong"]
code = out["code"]
img = out["img"]
br = out["br"]
ul = out["ul"]
ol = out["ol"]
h1 = out["h1"]
h2 = out["h2"]
pre = out["pre"]

serializer = DOMSerializer.from_schema(schema)
_marks_copy = serializer.marks.copy()
del _marks_copy["em"]
no_em = DOMSerializer(serializer.nodes, _marks_copy)


@pytest.mark.parametrize(
    "desc,doc,html",
    [
        (
            "it can represent simple node",
            doc(p("hello")),
            "<p>hello</p>",
        ),
        (
            "it can represent a line break",
            doc(p("hi", br, "there")),
            "<p>hi<br>there</p>",
        ),
        (
            "it can represent an image",
            doc(p("hi", img({"alt": "x"}), "there")),
            '<p>hi<img src="img.png" alt="x">there</p>',
        ),
        (
            "it joins styles",
            doc(p("one", strong("two", em("three")), em("four"), "five")),
            "<p>one<strong>two</strong><em><strong>three</strong>four</em>five</p>",
        ),
        (
            "it can represent links",
            doc(
                p(
                    "a ",
                    a({"href": "foo"}, "big ", a({"href": "bar"}, "nested"), " link"),
                )
            ),
            '<p>a <a href="foo">big </a><a href="bar">nested</a>'
            '<a href="foo"> link</a></p>',
        ),
        (
            "it can represent an unordered list",
            doc(
                ul(li(p("one")), li(p("two")), li(p("three", strong("!")))), p("after")
            ),
            "<ul><li><p>one</p></li><li><p>two</p></li><li><p>three"
            "<strong>!</strong></p></li></ul><p>after</p>",
        ),
        (
            "it can represent an ordered list",
            doc(
                ol(li(p("one")), li(p("two")), li(p("three", strong("!")))), p("after")
            ),
            "<ol><li><p>one</p></li><li><p>two</p></li><li><p>three"
            "<strong>!</strong></p></li></ol><p>after</p>",
        ),
        (
            "it can represent a blockquote",
            doc(blockquote(p("hello"), p("bye"))),
            "<blockquote><p>hello</p><p>bye</p></blockquote>",
        ),
        (
            "it can represent headings",
            doc(h1("one"), h2("two"), p("text")),
            "<h1>one</h1><h2>two</h2><p>text</p>",
        ),
        (
            "it can represent inline code",
            doc(p("text and ", code("code that is ", em("emphasized"), "..."))),
            "<p>text and <code>code that is </code><em><code>emphasized</code>"
            "</em><code>...</code></p>",
        ),
        (
            "it can represent a code block",
            doc(blockquote(pre("some code")), p("and")),
            "<blockquote><pre><code>some code</code></pre></blockquote><p>and</p>",
        ),
        (
            "it supports leaf nodes in marks",
            doc(p(em("hi", br, "x"))),
            "<p><em>hi<br>x</em></p>",
        ),
        (
            "it doesn't collapse non-breaking spaces",
            doc(p("\u00a0 \u00a0hello\u00a0")),
            "<p>\u00a0 \u00a0hello\u00a0</p>",
        ),
    ],
)
def test_serializer_first(doc, html, desc):
    """Parser is not implemented, this is just testing serializer right now"""
    schema = doc.type.schema
    dom = DOMSerializer.from_schema(schema).serialize_fragment(doc.content)
    assert str(dom) == html, desc


@pytest.mark.parametrize(
    "desc,serializer,doc,expect",
    [
        (
            "it can omit a mark",
            no_em,
            p("foo", em("bar"), strong("baz")),
            "foobar<strong>baz</strong>",
        ),
        (
            "it doesn't split other marks for omitted marks",
            no_em,
            p("foo", code("bar"), em(code("baz"), "quux"), "xyz"),
            "foo<code>barbaz</code>quuxxyz",
        ),
        (
            "it can render marks with complex structure",
            DOMSerializer(
                serializer.nodes,
                {
                    **serializer.marks,
                    "em": lambda *_: ["em", ["i", {"data-emphasis": "true"}, 0]],
                },
            ),
            p(strong("foo", code("bar"), em(code("baz"))), em("quux"), "xyz"),
            "<strong>foo<code>bar</code></strong>"
            '<em><i data-emphasis="true"><strong><code>baz</code>'
            "</strong>quux</i></em>xyz",
        ),
    ],
)
def test_serializer(serializer, doc, expect, desc):
    assert str(serializer.serialize_fragment(doc.content)) == expect, desc


def test_html_is_escaped():
    assert (
        str(serializer.serialize_node(schema.text("<b>bold &</b>")))
        == "&lt;b&gt;bold &amp;&lt;/b&gt;"
    )


@pytest.mark.parametrize(
    "desc,doc,expect",
    [
        (
            "Basic text node",
            """<div><p>test</p></div>""",
            {
                "type": "doc",
                "content": [
                    {"type": "paragraph", "content": [{"type": "text", "text": "test"}]}
                ],
            },
        ),
        (
            "Styled(marks) nodes pt1",
            """<div><p>test <strong>some bolded text</strong></p></div>""",
            {
                "type": "doc",
                "content": [
                    {
                        "type": "paragraph",
                        "content": [
                            {"type": "text", "text": "test "},
                            {
                                "type": "text",
                                "marks": [{"type": "strong", "attrs": {}}],
                                "text": "some bolded text",
                            },
                        ],
                    }
                ],
            },
        ),
        (
            "Styled nodes pt2",
            """<div><p>test <strong>some bolded text</strong></p><p>another test """
            """<em>em</em></p></div>""",
            {
                "type": "doc",
                "content": [
                    {
                        "type": "paragraph",
                        "content": [
                            {"type": "text", "text": "test "},
                            {
                                "type": "text",
                                "marks": [{"type": "strong", "attrs": {}}],
                                "text": "some bolded text",
                            },
                        ],
                    },
                    {
                        "type": "paragraph",
                        "content": [
                            {"type": "text", "text": "another test "},
                            {
                                "type": "text",
                                "marks": [{"type": "em", "attrs": {}}],
                                "text": "em",
                            },
                        ],
                    },
                ],
            },
        ),
        (
            "Slightly more complex test, testing pre and tail text around elements",
            """<div><p>test <a href="www.google.ca">google</a>\nsome more text here"""
            """</p><img src="google.ca"/><p><strong>Hello</strong></p><h1>Test """
            """heading</h1><p><em>Test <strong>break</strong></em><br/>Another bit """
            """of testing data.</p></div>""",
            {
                "type": "doc",
                "content": [
                    {
                        "type": "paragraph",
                        "content": [
                            {"type": "text", "text": "test "},
                            {
                                "type": "text",
                                "marks": [
                                    {
                                        "type": "link",
                                        "attrs": {
                                            "href": "www.google.ca",
                                            "title": None,
                                        },
                                    }
                                ],
                                "text": "google",
                            },
                            {"type": "text", "text": " some more text here"},
                        ],
                    },
                    {
                        "type": "paragraph",
                        "content": [
                            {
                                "type": "image",
                                "attrs": {
                                    "src": "google.ca",
                                    "alt": None,
                                    "title": None,
                                },
                            }
                        ],
                    },
                    {
                        "type": "paragraph",
                        "content": [
                            {
                                "type": "text",
                                "marks": [{"type": "strong", "attrs": {}}],
                                "text": "Hello",
                            }
                        ],
                    },
                    {
                        "type": "heading",
                        "attrs": {"level": 1},
                        "content": [{"type": "text", "text": "Test heading"}],
                    },
                    {
                        "type": "paragraph",
                        "content": [
                            {
                                "type": "text",
                                "marks": [{"type": "em", "attrs": {}}],
                                "text": "Test ",
                            },
                            {
                                "type": "text",
                                "marks": [
                                    {"type": "em", "attrs": {}},
                                    {"type": "strong", "attrs": {}},
                                ],
                                "text": "break",
                            },
                            {"type": "hard_break"},
                            {"type": "text", "text": "Another bit of testing data."},
                        ],
                    },
                ],
            },
        ),
        (
            "Unstructured",
            """Testing the result of this""",
            {
                "type": "doc",
                "content": [
                    {
                        "type": "paragraph",
                        "content": [
                            {"type": "text", "text": "Testing the result of this"}
                        ],
                    }
                ],
            },
        ),
        (
            "Unstructured with tail",
            """Testing the <p>result <strong>o<em>f</em></strong></p> this""",
            {
                "type": "doc",
                "content": [
                    {
                        "type": "paragraph",
                        "content": [{"type": "text", "text": "Testing the"}],
                    },
                    {
                        "type": "paragraph",
                        "content": [
                            {"type": "text", "text": "result "},
                            {
                                "type": "text",
                                "marks": [{"type": "strong", "attrs": {}}],
                                "text": "o",
                            },
                            {
                                "type": "text",
                                "marks": [
                                    {"type": "em", "attrs": {}},
                                    {"type": "strong", "attrs": {}},
                                ],
                                "text": "f",
                            },
                        ],
                    },
                    {
                        "type": "paragraph",
                        "content": [{"type": "text", "text": " this"}],
                    },
                ],
            },
        ),
    ],
)
def test_parser(doc, expect, desc):
    """
    The `expect` dicts are straight copies from the output of the JS lib run in Node,
    with 1 exception of 'attrs' key in marks dicts, in JS if blank attrs isn't written,
    this library does write out 'attrs' even if it is blank, I didn't want to modify
    behavior of existing files with the addition of this
    """
    assert from_html(schema, doc) == expect, desc
