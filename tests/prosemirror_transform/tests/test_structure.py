import pytest

from prosemirror.model import Schema, Slice
from prosemirror.transform import Transform, can_split, find_wrapping, lift_target

schema = Schema(
    {
        "nodes": {
            "doc": {"content": "head? block* sect* closing?"},
            "para": {"content": "text*", "group": "block"},
            "head": {"content": "text*", "marks": ""},
            "figure": {"content": "caption figureimage", "group": "block"},
            "quote": {"content": "block+", "group": "block"},
            "figureimage": {},
            "caption": {"content": "text*", "marks": ""},
            "sect": {"content": "head block* sect*"},
            "closing": {"content": "text*"},
            "text": {"group": "inline"},
            "fixed": {"content": "head para closing", "group": "block"},
        },
        "marks": {"em": {}},
    }
)


def n(name, *content):
    return schema.nodes[name].create(None, content)


def t(str, em=None):
    return schema.text(str, [schema.mark["em"]] if em else None)


doc = n(
    "doc",  # 0
    n("head", t("Head")),  # 6
    n("para", t("Intro")),  # 13
    n(
        "sect",  # 14
        n("head", t("Section head")),  # 28
        n(
            "sect",  # 29
            n("head", t("Subsection head")),  # 46
            n("para", t("Subtext")),  # 55
            n(
                "figure", n("caption", t("Figure caption")), n("figureimage")
            ),  # 56  # 72  # 74
            n("quote", n("para", t("!"))),
        ),
    ),  # 81
    n("sect", n("head", t("S2")), n("para", t("Yes"))),  # 82  # 86  # 92
    n("closing", t("fin")),
)  # 97


def range_(pos, end=None):
    return doc.resolve(pos).block_range(None if end is None else doc.resolve(end))


def fill(params, length):
    new_params = []
    for item in params:
        item = list(item)
        diff = length - len(item)
        if diff > 0:
            item += [None] * diff
        new_params.append(item)
    return new_params


class TestCanSplit:
    @pytest.mark.parametrize(
        "pass_,pos,depth,after",
        fill(
            [
                (False, 0),
                (False, 3),
                (True, 3, 1, "para"),
                (False, 6),
                (True, 8),
                (False, 14),
                (False, 17),
                (True, 17, 2),
                (True, 18, 1, "para"),
                (False, 46),
                (True, 48),
                (False, 60),
                (False, 62, 2),
                (False, 72),
                (True, 76),
                (True, 77, 2),
                (False, 97),
            ],
            4,
        ),
    )
    def test_can_split(self, pass_, pos, depth, after):
        res = can_split(
            doc, pos, depth, [{"type": schema.nodes[after]}] if after else None
        )
        if pass_:
            assert res
        else:
            assert not res

    def test_doesnt_return_true_when_the_split_off_content_doesnt_fit_in_the_given_node_type(
        self
    ):
        s = Schema(
            {
                "nodes": {
                    "doc": {"content": "chapter+"},
                    "para": {"content": "text*", "group": "block"},
                    "head": {"content": "text*", "marks": ""},
                    "figure": {"content": "caption figureimage", "group": "block"},
                    "quote": {"content": "block+", "group": "block"},
                    "figureimage": {},
                    "caption": {"content": "text*", "marks": ""},
                    "sect": {"content": "head block* sect*"},
                    "closing": {"content": "text*"},
                    "text": {"group": "inline"},
                    "fixed": {"content": "head para closing", "group": "block"},
                    "title": {"content": "text*"},
                    "chapter": {"content": "title scene+"},
                    "scene": {"content": "para+"},
                }
            }
        )
        assert not can_split(
            s.node(
                "doc",
                None,
                s.node(
                    "chapter",
                    None,
                    [
                        s.node("title", None, s.text("title")),
                        s.node("scene", None, s.node("para", None, s.text("scene"))),
                    ],
                ),
            ),
            4,
            1,
            [{"type": s.nodes["scene"]}],
        )


class TestLiftTarget:
    @pytest.mark.parametrize(
        "pass_,pos",
        [(False, 0), (False, 3), (False, 52), (False, 70), (True, 76), (False, 86)],
    )
    def test_lift_target(self, pass_, pos):
        r = range_(pos)
        if pass_:
            assert bool(r and lift_target(r))
        else:
            assert not bool(r and lift_target(r))


class TestFindWrapping:
    @pytest.mark.parametrize(
        "pass_,pos,end,type",
        [
            (True, 0, 92, "sect"),
            (False, 4, 4, "sect"),
            (True, 8, 8, "quote"),
            (False, 18, 18, "quote"),
            (True, 55, 74, "quote"),
            (False, 90, 90, "figure"),
        ],
    )
    def test_find_wrapping(self, pass_, pos, end, type):
        r = range_(pos, end)
        if pass_:
            assert find_wrapping(r, schema.nodes[type])
        else:
            assert not bool(find_wrapping(r, schema.nodes[type]))


@pytest.mark.parametrize(
    "doc,from_,to,content,open_start,open_end,result",
    [
        (
            n("doc", n("sect", n("head", t("foo")), n("para", t("bar")))),
            6,
            6,
            n("doc", n("sect"), n("sect")),
            1,
            1,
            n(
                "doc",
                n("sect", n("head", t("foo"))),
                n("sect", n("head"), n("para", t("bar"))),
            ),
        ),
        (
            n("doc", n("para", t("a")), n("para", t("b"))),
            3,
            3,
            n("doc", n("closing", t("."))),
            0,
            0,
            n("doc", n("para", t("a")), n("para", t("b"))),
        ),
        (
            n("doc", n("sect", n("head", t("foo")), n("para", t("bar")))),
            1,
            3,
            n("doc", n("sect"), n("sect", n("head", t("hi")))),
            1,
            2,
            n(
                "doc",
                n("sect", n("head")),
                n("sect", n("head", t("hioo")), n("para", t("bar"))),
            ),
        ),
        (
            n("doc"),
            0,
            0,
            n("doc", n("figure", n("figureimage"))),
            1,
            0,
            n("doc", n("figure", n("caption"), n("figureimage"))),
        ),
        (
            n("doc"),
            0,
            0,
            n("doc", n("figure", n("caption"))),
            0,
            1,
            n("doc", n("figure", n("caption"), n("figureimage"))),
        ),
        (
            n(
                "doc",
                n("figure", n("caption"), n("figureimage")),
                n("figure", n("caption"), n("figureimage")),
            ),
            3,
            8,
            None,
            0,
            0,
            n("doc", n("figure", n("caption"), n("figureimage"))),
        ),
        (
            n("doc", n("sect", n("head"), n("figure", n("caption"), n("figureimage")))),
            7,
            9,
            n("doc", n("para", t("hi"))),
            0,
            0,
            n(
                "doc",
                n(
                    "sect",
                    n("head"),
                    n("figure", n("caption"), n("figureimage")),
                    n("para", t("hi")),
                ),
            ),
        ),
    ],
)
def test_replace(doc, from_, to, content, open_start, open_end, result):
    if content:
        slice = Slice(content.content, open_start, open_end)
    else:
        slice = Slice.empty
    tr = Transform(doc).replace(from_, to, slice)
    assert tr.doc.eq(result)
