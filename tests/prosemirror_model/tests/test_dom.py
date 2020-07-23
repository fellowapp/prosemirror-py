import pytest

from prosemirror.model import DOMSerializer
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

serializer = DOMSerializer.from_schema(schema)
_marks_copy = serializer.marks.copy()
del _marks_copy["em"]
no_em = DOMSerializer(serializer.nodes, _marks_copy)


@pytest.mark.parametrize(
    "serializer,doc,expect,desc",
    [
        (
            no_em,
            p("foo", em("bar"), strong("baz")),
            "foobar<strong>baz</strong>",
            "it can omit a mark",
        ),
        (
            no_em,
            p("foo", code("bar"), em(code("baz"), "quux"), "xyz"),
            "foo<code>barbaz</code>quuxxyz",
            "it doesn't split other marks for omitted marks",
        ),
        (
            DOMSerializer(
                serializer.nodes,
                {
                    **serializer.marks,
                    "em": lambda *_: ["em", ["i", {"data-emphasis": "true"}, 0]],
                },
            ),
            p(strong("foo", code("bar"), em(code("baz"))), em("quux"), "xyz"),
            "<strong>foo<code>bar</code></strong>"
            '<em><i data-emphasis="true"><strong><code>baz</code></strong>quux</i></em>xyz',
            "it can render marks with complex structure",
        ),
    ],
)
def test_serializer(serializer, doc, expect, desc):
    assert str(serializer.serialize_fragment(doc.content)) == expect, desc
