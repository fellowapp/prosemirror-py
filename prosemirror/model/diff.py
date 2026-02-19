from typing import TYPE_CHECKING, TypedDict, cast

from prosemirror.utils import text_length

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
                a16 = text_a.encode("utf-16-le")
                b16 = text_b.encode("utf-16-le")
                j = 0
                while j < len(a16) and j < len(b16) and a16[j] == b16[j]:
                    j += 1
                pos += j // 2
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
                min_size = min(text_length(text_a), text_length(text_b))
                a16 = text_a.encode("utf-16-le")
                b16 = text_b.encode("utf-16-le")
                a16_len = len(a16)
                b16_len = len(b16)
                while (
                    same < min_size
                    and a16[a16_len - 2 * same - 2 : a16_len - 2 * same]
                    == b16[b16_len - 2 * same - 2 : b16_len - 2 * same]
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
