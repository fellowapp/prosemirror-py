import pytest

from prosemirror.transform import Mapping, StepMap


@pytest.mark.parametrize(
    ("mapping_info", "cases"),
    [
        ([[2, 0, 4]], [[0, 0], [2, 6], [2, 2, -1], [3, 7]]),
        (
            [[2, 4, 0]],
            [[0, 0], [2, 2, -1], [3, 2, 1, True], [6, 2, 1], [6, 2, -1, True], [7, 3]],
        ),
        (
            [[2, 4, 4]],
            [[0, 0], [2, 2, 1], [4, 6, 1, True], [4, 2, -1, True], [6, 6, -1], [8, 8]],
        ),
        ([[2, 4, 0], [2, 0, 4], {0: 1}], [[0, 0], [2, 2], [4, 4], [6, 6], [7, 7]]),
        ([[2, 0, 4], [2, 4, 0], {0: 1}], [[0, 0], [2, 2], [3, 3]]),
        (
            [[2, 4, 0], [1, 0, 1], [3, 0, 4], {0: 2}],
            [[0, 0], [1, 2], [4, 5], [6, 7], [7, 8]],
        ),
    ],
)
def test_all_mapping_cases(mapping_info, cases, test_mapping, make_mapping):
    test_mapping(make_mapping(*mapping_info), *cases)


@pytest.mark.parametrize(
    ("mapping_info", "pos", "side", "flags"),
    [
        (([0, 2, 0],), 2, -1, "db"),
        (([0, 2, 0],), 2, 1, "b"),
        (([0, 2, 2],), 2, -1, "db"),
        (
            (
                [0, 1, 0],
                [0, 1, 0],
            ),
            2,
            -1,
            "db",
        ),
        (([0, 1, 0],), 2, -1, ""),
        (([2, 2, 0],), 2, -1, "a"),
        (([2, 2, 0],), 2, 1, "da"),
        (([2, 2, 2],), 2, 1, "da"),
        (
            (
                [2, 1, 0],
                [2, 1, 0],
            ),
            2,
            1,
            "da",
        ),
        (([3, 2, 0],), 2, -1, ""),
        (([0, 4, 0],), 2, -1, "dbax"),
        (([0, 4, 0],), 2, 1, "dbax"),
        (
            (
                [0, 1, 0],
                [4, 1, 0],
                [0, 3, 0],
            ),
            2,
            1,
            "dbax",
        ),
        (
            (
                [4, 1, 0],
                [0, 1, 0],
            ),
            2,
            -1,
            "",
        ),
        (
            (
                [2, 1, 0],
                [0, 2, 0],
            ),
            2,
            -1,
            "dba",
        ),
        (
            (
                [2, 1, 0],
                [0, 1, 0],
            ),
            2,
            -1,
            "a",
        ),
        (
            (
                [3, 1, 0],
                [0, 2, 0],
            ),
            2,
            -1,
            "db",
        ),
    ],
)
def test_all_del_cases(mapping_info, pos, side, flags, test_del, make_mapping):
    test_del(make_mapping(*mapping_info), pos, side, flags)


def test_append_map_does_not_mutate_empty_list_passed_in():
    shared: list[StepMap] = []
    mapping = Mapping(shared)
    mapping.append_map(StepMap([0, 0, 1]))
    assert shared == []
    assert len(mapping.maps) == 1


def test_append_map_on_slice_of_empty_mapping_leaves_original():
    original = Mapping()
    sliced = original.slice()
    sliced.append_map(StepMap([0, 0, 1]))
    assert original.maps == []
    assert len(sliced.maps) == 1
