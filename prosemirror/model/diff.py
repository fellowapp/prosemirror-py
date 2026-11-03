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
                t_a, t_b, j = _code_units(text_a), _code_units(text_b), 0
                while j < len(t_a) and j < len(t_b) and t_a[j] == t_b[j]:
                    j += 1
                    pos += 1
                if (
                    j
                    and j < len(t_a)
                    and j < len(t_b)
                    and _surrogate_high(t_a[j - 1])
                    and _surrogate_low(t_a[j])
                ):
                    pos -= 1
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
                t_a, t_b = _code_units(text_a), _code_units(text_b)
                i_a_text, i_b_text = len(t_a), len(t_b)
                while (
                    i_a_text > 0
                    and i_b_text > 0
                    and t_a[i_a_text - 1] == t_b[i_b_text - 1]
                ):
                    i_a_text -= 1
                    i_b_text -= 1
                    pos_a -= 1
                    pos_b -= 1
                if (
                    i_a_text
                    and i_b_text
                    and i_a_text < len(t_a)
                    and _surrogate_high(t_a[i_a_text - 1])
                    and _surrogate_low(t_a[i_a_text])
                ):
                    pos_a += 1
                    pos_b += 1
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


def _code_units(text: str) -> list[int]:
    # UTF-16 code units, matching JS string indexing.
    data = text.encode("utf-16-le")
    return [data[k] | (data[k + 1] << 8) for k in range(0, len(data), 2)]


def _surrogate_low(ch: int) -> bool:
    return 0xDC00 <= ch < 0xE000


def _surrogate_high(ch: int) -> bool:
    return 0xD800 <= ch < 0xDC00
