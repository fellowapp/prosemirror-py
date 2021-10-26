import pytest

from prosemirror.model import ContentMatch, Node
from prosemirror.test_builder import out, test_schema as schema

doc = out["doc"]
h1 = out["h1"]
p = out["p"]
pre = out["pre"]
img = out["img"]
br = out["br"]
hr = out["hr"]


def get(expr):
    return ContentMatch.parse(expr, schema.nodes)


def match(expr, types):
    m = get(expr)
    ts = [schema.nodes[t] for t in types.split(" ")] if types else []
    i = 0
    while m and i < len(ts):
        m = m.match_type(ts[i])
        i += 1
    if m:
        return m.valid_end
    return False


@pytest.mark.parametrize(
    "expr,types,valid",
    [
        ("", "", True),
        ("", "image", False),
        ("image*", "", True),
        ("image*", "image", True),
        ("image*", "image image image image", True),
        ("image*", "image text", False),
        ("inline*", "image text", True),
        ("inline*", "paragraph", False),
        ("(paragraph | heading)", "paragraph", True),
        ("(paragraph | heading)", "image", False),
        (
            "paragraph horizontal_rule paragraph",
            "paragraph horizontal_rule paragraph",
            True,
        ),
        ("paragraph horizontal_rule", "paragraph horizontal_rule paragraph", False),
        ("paragraph horizontal_rule paragraph", "paragraph horizontal_rule", False),
        (
            "paragraph horizontal_rule",
            "horizontal_rule paragraph horizontal_rule",
            False,
        ),
        ("heading paragraph*", "heading", True),
        ("heading paragraph*", "heading paragraph paragraph", True),
        ("heading paragraph+", "heading paragraph", True),
        ("heading paragraph+", "heading paragraph paragraph", True),
        ("heading paragraph+", "heading", False),
        ("heading paragraph+", "paragraph paragraph", False),
        ("image?", "image", True),
        ("image?", "", True),
        ("image?", "image image", False),
        (
            "(heading paragraph+)+",
            "heading paragraph heading paragraph paragraph",
            True,
        ),
        (
            "(heading paragraph+)+",
            "heading paragraph heading paragraph paragraph horizontal_rule",
            False,
        ),
        ("hard_break{2}", "hard_break hard_break", True),
        ("hard_break{2}", "hard_break", False),
        ("hard_break{2}", "hard_break hard_break hard_break", False),
        ("hard_break{2, 4}", "hard_break hard_break", True),
        ("hard_break{2, 4}", "hard_break hard_break hard_break hard_break", True),
        ("hard_break{2, 4}", "hard_break hard_break hard_break", True),
        ("hard_break{2, 4}", "hard_break", False),
        (
            "hard_break{2, 4}",
            "hard_break hard_break hard_break hard_break hard_break",
            False,
        ),
        ("hard_break{2, 4} text*", "hard_break hard_break image", False),
        ("hard_break{2, 4} image?", "hard_break hard_break image", True),
        ("hard_break{2,}", "hard_break hard_break", True),
        ("hard_break{2,}", "hard_break hard_break hard_break hard_break", True),
        ("hard_break{2,}", "hard_break", False),
    ],
)
def test_match_type(expr, types, valid):
    if valid:
        assert match(expr, types)
    else:
        assert not match(expr, types)


@pytest.mark.parametrize(
    "expr,before,after,result",
    [
        (
            "paragraph horizontal_rule paragraph",
            '{"type":"doc","content":[{"type":"paragraph"},{"type":"horizontal_rule"}]}',
            '{"type":"doc","content":[{"type":"paragraph"}]}',
            '{"type":"doc"}',
        ),
        (
            "paragraph horizontal_rule paragraph",
            '{"type":"doc","content":[{"type":"paragraph"}]}',
            '{"type":"doc","content":[{"type":"paragraph"}]}',
            '{"type":"doc","content":[{"type":"horizontal_rule"}]}',
        ),
        (
            "hard_break*",
            '{"type":"paragraph","content":[{"type":"hard_break"}]}',
            '{"type":"paragraph","content":[{"type":"hard_break"}]}',
            '{"type":"paragraph"}',
        ),
        (
            "hard_break*",
            '{"type":"paragraph","content":[{"type":"hard_break"}]}',
            '{"type":"paragraph"}',
            '{"type":"paragraph"}',
        ),
        (
            "hard_break*",
            '{"type":"paragraph"}',
            '{"type":"paragraph","content":[{"type":"hard_break"}]}',
            '{"type":"paragraph"}',
        ),
        (
            "hard_break*",
            '{"type":"paragraph"}',
            '{"type":"paragraph"}',
            '{"type":"paragraph"}',
        ),
        (
            "hard_break+",
            '{"type":"paragraph","content":[{"type":"hard_break"}]}',
            '{"type":"paragraph","content":[{"type":"hard_break"}]}',
            '{"type":"paragraph"}',
        ),
        (
            "hard_break+",
            '{"type":"paragraph"}',
            '{"type":"paragraph"}',
            '{"type":"paragraph","content":[{"type":"hard_break"}]}',
        ),
        (
            "hard_break+",
            '{"type":"paragraph"}',
            '{"type":"paragraph","content":[{"type":"image","attrs":{"src":"img.png","alt":null,"title":null}}]}',
            None,
        ),
        (
            "heading* paragraph*",
            '{"type":"doc","content":[{"type":"heading","attrs":{"level":1}}]}',
            '{"type":"doc","content":[{"type":"paragraph"}]}',
            '{"type":"doc"}',
        ),
        (
            "heading* paragraph*",
            '{"type":"doc","content":[{"type":"heading","attrs":{"level":1}}]}',
            '{"type":"doc"}',
            '{"type":"doc"}',
        ),
        (
            "heading+ paragraph+",
            '{"type":"doc","content":[{"type":"heading","attrs":{"level":1}}]}',
            '{"type":"doc","content":[{"type":"paragraph"}]}',
            '{"type":"doc"}',
        ),
        (
            "heading+ paragraph+",
            '{"type":"doc","content":[{"type":"heading","attrs":{"level":1}}]}',
            '{"type":"doc"}',
            '{"type":"doc","content":[{"type":"paragraph"}]}',
        ),
        (
            "hard_break{3}",
            '{"type":"paragraph","content":[{"type":"hard_break"}]}',
            '{"type":"paragraph","content":[{"type":"hard_break"}]}',
            '{"type":"paragraph","content":[{"type":"hard_break"}]}',
        ),
        (
            "hard_break{3}",
            '{"type":"paragraph","content":[{"type":"hard_break"},{"type":"hard_break"}]}',
            '{"type":"paragraph","content":[{"type":"hard_break"},{"type":"hard_break"}]}',
            None,
        ),
        (
            "code_block{2} paragraph{2}",
            '{"type":"doc","content":[{"type":"code_block"}]}',
            '{"type":"doc","content":[{"type":"paragraph"}]}',
            '{"type":"doc","content":[{"type":"code_block"},{"type":"paragraph"}]}',
        ),
    ],
)
def test_fill_before(expr, before, after, result):
    before = Node.from_json(schema, before)
    after = Node.from_json(schema, after)
    filled = get(expr).match_fragment(before.content).fill_before(after.content, True)
    if result:
        result = Node.from_json(schema, result)
        assert filled.eq(result.content)
    else:
        assert not filled


@pytest.mark.parametrize(
    "expr,before,mid,after,left,right",
    [
        (
            "paragraph horizontal_rule paragraph horizontal_rule paragraph",
            '{"type":"doc","content":[{"type":"paragraph"}]}',
            '{"type":"doc","content":[{"type":"paragraph"}]}',
            '{"type":"doc","content":[{"type":"paragraph"}]}',
            '{"type":"doc","content":[{"type":"horizontal_rule"}]}',
            '{"type":"doc","content":[{"type":"horizontal_rule"}]}',
        ),
        (
            "code_block+ paragraph+",
            '{"type":"doc","content":[{"type":"code_block"}]}',
            '{"type":"doc","content":[{"type":"code_block"}]}',
            '{"type":"doc","content":[{"type":"paragraph"}]}',
            '{"type":"doc"}',
            '{"type":"doc"}',
        ),
        (
            "code_block+ paragraph+",
            '{"type":"doc"}',
            '{"type":"doc"}',
            '{"type":"doc"}',
            '{"type":"doc"}',
            '{"type":"doc","content":[{"type":"code_block"},{"type":"paragraph"}]}',
        ),
        (
            "code_block{3} paragraph{3}",
            '{"type":"doc","content":[{"type":"code_block"}]}',
            '{"type":"doc","content":[{"type":"paragraph"}]}',
            '{"type":"doc"}',
            '{"type":"doc","content":[{"type":"code_block"},{"type":"code_block"}]}',
            '{"type":"doc","content":[{"type":"paragraph"},{"type":"paragraph"}]}',
        ),
        (
            "paragraph*",
            '{"type":"doc","content":[{"type":"paragraph"}]}',
            '{"type":"doc","content":[{"type":"code_block"}]}',
            '{"type":"doc","content":[{"type":"paragraph"}]}',
            None,
            None,
        ),
        (
            "paragraph{4}",
            '{"type":"doc","content":[{"type":"paragraph"}]}',
            '{"type":"doc","content":[{"type":"paragraph"}]}',
            '{"type":"doc","content":[{"type":"paragraph"}]}',
            '{"type":"doc"}',
            '{"type":"doc","content":[{"type":"paragraph"}]}',
        ),
        (
            "paragraph{2}",
            '{"type":"doc","content":[{"type":"paragraph"}]}',
            '{"type":"doc","content":[{"type":"paragraph"}]}',
            '{"type":"doc","content":[{"type":"paragraph"}]}',
            None,
            None,
        ),
    ],
)
def test_fill3_before(expr, before, mid, after, left, right):
    before = Node.from_json(schema, before)
    mid = Node.from_json(schema, mid)
    after = Node.from_json(schema, after)
    content = get(expr)
    a = content.match_fragment(before.content).fill_before(mid.content)
    b = False
    if a:
        b = content.match_fragment(
            before.content.append(a).append(mid.content)
        ).fill_before(after.content, True)
    if left:
        left = Node.from_json(schema, left)
        right = Node.from_json(schema, right)
        assert a.eq(left.content)
        assert b.eq(right.content)
    else:
        assert not b
