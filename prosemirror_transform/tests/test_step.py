import pytest
from .conftest import _make_step, _test_doc


def yes(from1, to1, val1, from2, to2, val2):
    def inner():
        step1 = _make_step(from1, to1, val1)
        step2 = _make_step(from2, to2, val2)
        merged = step1.merge(step2)
        assert merged
        assert merged.apply(_test_doc).doc.eq(
            step2.apply(step1.apply(_test_doc).doc).doc
        )

    return inner


def no(from1, to1, val1, from2, to2, val2):
    def inner():
        step1 = _make_step(from1, to1, val1)
        step2 = _make_step(from2, to2, val2)
        with pytest.raises(ValueError):
            step1.merge(step2)

    return inner


@pytest.mark.parametrize(
    "pass_,from1,to1,val1,from2,to2,val2",
    [
        (yes, 2, 2, "a", 3, 3, "b"),
        (yes, 2, 2, "a", 2, 2, "b"),
        (no, 2, 2, "a", 4, 4, "b"),
        (no, 3, 3, "a", 2, 2, "b"),
        (yes, 3, 4, None, 2, 3, None),
        (yes, 2, 3, None, 2, 3, None),
        (no, 1, 2, None, 2, 3, None),
        (yes, 2, 3, None, 2, 2, "x"),
        (yes, 2, 2, "quux", 6, 6, "baz"),
        (yes, 2, 2, "quux", 2, 2, "baz"),
        (yes, 2, 5, None, 2, 4, None),
        (yes, 4, 6, None, 2, 4, None),
        (yes, 3, 4, "x", 4, 5, "y"),
        (yes, 1, 2, "+em", 2, 4, "+em"),
        (yes, 1, 3, "+em", 2, 4, "+em"),
        (no, 1, 2, "+em", 3, 4, "+em"),
        (yes, 1, 2, "-em", 2, 4, "-em"),
        (yes, 1, 3, "-em", 2, 4, "-em"),
        (no, 1, 2, "-em", 3, 4, "-em"),
    ],
)
def test_all_cases(pass_, from1, to1, val1, from2, to2, val2):
    pass_(from1, to1, val1, from2, to2, val2)
