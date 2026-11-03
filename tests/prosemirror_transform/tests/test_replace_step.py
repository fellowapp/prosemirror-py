import pytest

from prosemirror.model import Fragment, Slice
from prosemirror.test_builder import out
from prosemirror.test_builder import test_schema as schema
from prosemirror.transform import (
    ReplaceAroundStep,
    Transform,
    TransformError,
    find_wrapping,
)

doc = out["doc"]
blockquote = out["blockquote"]
p = out["p"]


def test_replace_around_step_verifies_inserted_content_fits():
    tr = Transform(doc(p("a")))
    with pytest.raises(TransformError, match="Content does not fit in gap"):
        tr.step(
            ReplaceAroundStep(
                1, 2, 1, 2, Slice(Fragment.from_(blockquote()), 0, 0), 1, True
            )
        )


def test_replace_around_step_considers_slice_openness():
    tr = Transform(doc(blockquote(p("x"))))
    tr.step(
        ReplaceAroundStep(
            0, 1, 1, 1, Slice(Fragment.from_(blockquote()), 0, 1), 1, True
        )
    )
    assert tr.doc.eq(doc(blockquote(p("x"))))


def test_replace_around_step_map_wrap_insertion():
    """Wrap steps don't break on insertions at start."""
    d = doc(p("a"))
    tr_a = Transform(d)
    range_ = tr_a.doc.resolve(1).block_range()
    assert range_ is not None
    wrappers = find_wrapping(range_, schema.nodes["blockquote"])
    assert wrappers is not None
    tr_a.wrap(range_, wrappers)

    tr_b = Transform(d)
    tr_b.insert(0, p("b"))

    mapped_step = tr_a.steps[0].map(tr_b.mapping)
    assert mapped_step is not None
    result = Transform(tr_b.doc).step(mapped_step).doc
    expected = doc(p("b"), blockquote(p("a")))
    assert result.eq(expected)


def test_replace_around_step_map_unwrap_insertion():
    """Content inserted at start of unwrap step isn't overwritten."""
    d = doc(blockquote(p("a")))
    tr_a = Transform(d)
    range_ = tr_a.doc.resolve(2).block_range()
    assert range_ is not None
    tr_a.lift(range_, 0)

    tr_b = Transform(d)
    tr_b.insert(2, schema.text("x"))

    mapped_step = tr_a.steps[0].map(tr_b.mapping)
    assert mapped_step is not None
    result = Transform(tr_b.doc).step(mapped_step).doc
    expected = doc(p("xa"))
    assert result.eq(expected)
