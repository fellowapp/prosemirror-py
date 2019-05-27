import pytest
from prosemirror_model import ContentMatch
from prosemirror_test_builder import out, schema


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
def test_match_type_valid(expr, types, valid):
    if valid:
        assert match(expr, types)
    else:
        assert not match(expr, types)

