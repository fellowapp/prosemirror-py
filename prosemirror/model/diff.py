from typing import TYPE_CHECKING, TypedDict, cast

if TYPE_CHECKING:
    from prosemirror.model.fragment import Fragment
    from prosemirror.model.node import TextNode


class Diff(TypedDict):
    a: int
    b: int


def find_diff_start(a: "Fragment", b: "Fragment", pos: int) -> int | None:
    i = 0
    while True:
        if i == a.child_count or i == b.child_count:
            return None if a.child_count == b.child_count else pos
        child_a, child_b = a.child(i), b.child(i)
        if child_a == child_b:
            pos += child_a.node_size
            i += 1
            continue
        if not child_a.same_markup(child_b):
            return pos
        if child_a.is_text:
            text_a = cast("TextNode", child_a).text
            text_b = cast("TextNode", child_b).text
            if text_a != text_b:
                j = 0
                while j < len(text_a) and j < len(text_b) and text_a[j] == text_b[j]:
                    j += 1
                    pos += 1
                return pos
        if child_a.content.size or child_b.content.size:
            inner = find_diff_start(child_a.content, child_b.content, pos + 1)
            if inner is not None:
                return inner
        pos += child_a.node_size
        i += 1


def find_diff_end(a: "Fragment", b: "Fragment", pos_a: int, pos_b: int) -> Diff | None:
    i_a, i_b = a.child_count, b.child_count
    while True:
        if i_a == 0 or i_b == 0:
            return None if i_a == i_b else {"a": pos_a, "b": pos_b}
        i_a -= 1
        i_b -= 1
        child_a, child_b = a.child(i_a), b.child(i_b)
        size = child_a.node_size
        if child_a == child_b:
            pos_a -= size
            pos_b -= size
            continue

        if not child_a.same_markup(child_b):
            return {"a": pos_a, "b": pos_b}

        if child_a.is_text:
            text_a = cast("TextNode", child_a).text
            text_b = cast("TextNode", child_b).text
            if text_a != text_b:
                same = 0
                min_size = min(len(text_a), len(text_b))
                while (
                    same < min_size
                    and text_a[len(text_a) - same - 1] == text_b[len(text_b) - same - 1]
                ):
                    same += 1
                    pos_a -= 1
                    pos_b -= 1
                return {"a": pos_a, "b": pos_b}

        if child_a.content.size or child_b.content.size:
            inner = find_diff_end(
                child_a.content,
                child_b.content,
                pos_a - 1,
                pos_b - 1,
            )
            if inner:
                return inner

        pos_a -= size
        pos_b -= size
