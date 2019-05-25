import pydash
import pytest
from prosemirror_model import Slice, Fragment
from .. import Mapping, StepMap, AddMarkStep, ReplaceStep, RemoveMarkStep

from prosemirror_test_builder import eq, schema, out

doc = out["doc"]
p = out["p"]


@pytest.fixture
def test_mapping():
    def t_mapping(mapping, *cases):
        inverted = mapping.invert()
        for case in cases:
            from_, to, bias, lossy = [
                pydash.get(case, *param) for param in enumerate([None, None, 1, False])
            ]
            # if from_ == 2:
            #     import ipdb; ipdb.set_trace()
            assert mapping.map(from_, bias) == to
            if not lossy:
                assert inverted.map(to, bias) == from_

    return t_mapping


@pytest.fixture
def make_mapping():
    def mk(*args):
        mapping = Mapping()
        for arg in args:
            if isinstance(arg, list):
                mapping.append_map(StepMap(arg))
            else:
                for from_ in arg:
                    mapping.set_mirror(from_, arg[from_])
        return mapping

    return mk


@pytest.fixture
def make_step():
    return _make_step


def _make_step(from_, to, val):
    if val == "+em":
        return AddMarkStep(from_, to, schema.marks["em"].create)
    elif val == "-em":
        return RemoveMarkStep(from_, to, schema.marks["em"].create)
    return ReplaceStep(
        from_,
        to,
        Slice.empty if val is None else Slice(Fragment.from_(schema.text(val), 0, 0)),
    )


@pytest.fixture
def test_doc():
    return doc(p("foobar"))


_test_doc = doc(p("foobar"))
