import pydash
import pytest
from prosemirror_model import Slice, Fragment, Schema
from .. import Mapping, StepMap, AddMarkStep, ReplaceStep, RemoveMarkStep
from prosemirror_transform import Transform, Step, Mapping

from prosemirror_test_builder import schema, out

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


@pytest.fixture
def test_transform():
    def invert(transform):
        out = Transform(transform.doc)
        for i, step in reversed(list(enumerate(transform.steps))):
            out.step(step.invert(transform.docs[i]))
        return out

    def test_step_json(tr):
        new_tr = Transform(tr.before)
        for step in tr.steps:
            new_tr.step(Step.from_json(tr.doc.type.schema, step.to_json()))

    def test_mapping(mapping, pos, new_pos):
        mapped = mapping.map(pos, 1)
        assert mapped == new_pos
        remap = Mapping([m.invert() for m in mapping.maps])
        for i, map in enumerate(mapping.maps):
            remap.append_map(map, len(mapping.maps) - i)
        assert remap.map(pos, 1) == pos

    def test_transform(tr, expect):
        assert tr.doc.eq(expect)
        assert invert(tr).doc.eq(tr.before)
        test_step_json(tr)

        for tag in expect.tag:
            test_mapping(tr.mapping, tr.before.tag.get(tag), expect.tag.get(tag))

    return test_transform
