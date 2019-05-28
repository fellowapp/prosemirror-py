import pytest
from prosemirror_test_builder import out

doc = out["doc"]
p = out["p"]
em = out["em"]
blockquote = out["blockquote"]

test_doc = doc(p("ab"), blockquote(p(em("cd"), "ef")))
_doc = {"node": test_doc, "start": 0, "end": 12}
_p1 = {"node": test_doc.child(0), "start": 1, "end": 3}
_blk = {"node": test_doc.child(1), "start": 5, "end": 11}
_p2 = {"node": _blk["node"].child(0), "start": 6, "end": 10}


@pytest.mark.parametrize(
    "pos,exp",
    list(
        enumerate(
            [
                [_doc, 0, None, _p1["node"]],
                [_doc, _p1, 0, None, "ab"],
                [_doc, _p1, 1, "a", "b"],
                [_doc, _p1, 2, "ab", None],
                [_doc, 4, _p1["node"], _blk["node"]],
                [_doc, _blk, 0, None, _p2["node"]],
                [_doc, _blk, _p2, 0, None, "cd"],
                [_doc, _blk, _p2, 1, "c", "d"],
                [_doc, _blk, _p2, 2, "cd", "ef"],
                [_doc, _blk, _p2, 3, "e", "f"],
                [_doc, _blk, _p2, 4, "ef", None],
                [_doc, _blk, 6, _p2["node"], None],
                [_doc, 12, _blk["node"], None],
            ]
        )
    ),
)
def test_node_resolve(pos, exp):
    pos = test_doc.resolve(pos)
    assert pos.depth == len(exp) - 4
    for i in range(len(exp) - 3):
        assert pos.node(i).eq(exp[i]["node"])
        assert pos.start(i) == exp[i]["start"]
        assert pos.end(i) == exp[i]["end"]
        if i:
            assert pos.before(i) == exp[i]["start"] - 1
            assert pos.after(i) == exp[i]["end"] + 1
        assert pos.parent_offset == exp[len(exp) - 3]
        before = pos.node_before
        e_before = exp[len(exp) - 2]
        if isinstance(e_before, str):
            assert before.text_content == e_before
        else:
            assert before == e_before
        after = pos.node_after
        e_after = exp[len(exp) - 1]
        if isinstance(e_after, str):
            assert after.text_content == e_after
        else:
            assert after == e_after
