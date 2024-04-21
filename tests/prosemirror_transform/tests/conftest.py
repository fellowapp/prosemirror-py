import pytest

from prosemirror.model import Fragment, Slice
from prosemirror.test_builder import out
from prosemirror.test_builder import test_schema as schema
from prosemirror.transform import (
    AddMarkStep,
    Mapping,
    RemoveMarkStep,
    ReplaceStep,
    Step,
    StepMap,
    Transform,
)

doc = out["doc"]
p = out["p"]


@pytest.fixture()
def test_mapping():
    def t_mapping(mapping, *cases):
        inverted = mapping.invert()
        for case in cases:
            from_, to, bias, lossy = (
                lambda from_, to, bias=1, lossy=False: (from_, to, bias, lossy)
            )(*case)
            assert mapping.map(from_, bias) == to
            if not lossy:
                assert inverted.map(to, bias) == from_

    return t_mapping


@pytest.fixture()
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


@pytest.fixture()
def test_del():
    def t_del(mapping: Mapping, pos: int, side: int, flags: str):
        r = mapping.map_result(pos, side)
        found = ""
        if r.deleted:
            found += "d"
        if r.deleted_before:
            found += "b"
        if r.deleted_after:
            found += "a"
        if r.deleted_across:
            found += "x"
        assert found == flags

    return t_del


@pytest.fixture()
def make_step():
    return _make_step


def _make_step(from_: int, to: int, val: str | None) -> Step:
    if val == "+em":
        return AddMarkStep(from_, to, schema.marks["em"].create())
    elif val == "-em":
        return RemoveMarkStep(from_, to, schema.marks["em"].create())
    return ReplaceStep(
        from_,
        to,
        Slice.empty if val is None else Slice(Fragment.from_(schema.text(val)), 0, 0),
    )


@pytest.fixture()
def test_doc():
    return doc(p("foobar"))


_test_doc = doc(p("foobar"))


@pytest.fixture()
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
        for i, map in enumerate(reversed(mapping.maps)):
            remap.append_map(map, len(mapping.maps) - 1 - i)
        assert remap.map(pos, 1) == pos

    def test_transform(tr, expect):
        assert tr.doc.eq(expect)
        assert invert(tr).doc.eq(tr.before)
        test_step_json(tr)

        for tag in expect.tag:
            test_mapping(tr.mapping, tr.before.tag.get(tag), expect.tag.get(tag))

    return test_transform
