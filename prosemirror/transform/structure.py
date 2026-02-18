from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

from prosemirror.model import ContentMatch, Node, NodeRange, NodeType, Slice
from prosemirror.model.node import TextNode
from prosemirror.utils import Attrs

if TYPE_CHECKING:
    from prosemirror.transform.transform import Transform


def can_cut(node: Node, start: int, end: int) -> bool:
    if start == 0 or node.can_replace(start, node.child_count):
        return (end == node.child_count) or node.can_replace(0, end)
    return False


def lift_target(range_: NodeRange) -> int | None:
    parent = range_.parent
    content = parent.content.cut_by_index(range_.start_index, range_.end_index)
    depth = range_.depth
    content_before = 0
    content_after = 0
    while True:
        node = range_.from_.node(depth)
        index = range_.from_.index(depth) + content_before
        end_index = range_.to.index_after(depth) - content_after
        if depth < range_.depth and node.can_replace(index, end_index, content):
            return depth
        if (
            depth == 0
            or node.type.spec.get("isolating")
            or not can_cut(node, index, end_index)
        ):
            break
        if index:
            content_before = 1
        if end_index < node.child_count:
            content_after = 1
        depth -= 1

    return None


@dataclass
class NodeTypeWithAttrs:
    type: NodeType
    attrs: Attrs | None = None


def find_wrapping(
    range_: NodeRange,
    node_type: NodeType,
    attrs: Attrs | None = None,
    inner_range: NodeRange | None = None,
) -> list[NodeTypeWithAttrs] | None:
    if inner_range is None:
        inner_range = range_

    around = find_wrapping_outside(range_, node_type)
    inner = None

    if around is not None:
        inner = find_wrapping_inside(inner_range, node_type)
    else:
        return None

    if inner is None:
        return None

    return (
        [with_attrs(item) for item in around]
        + [NodeTypeWithAttrs(type=node_type, attrs=attrs)]
        + [with_attrs(item) for item in inner]
    )


def with_attrs(type: NodeType) -> NodeTypeWithAttrs:
    return NodeTypeWithAttrs(type=type, attrs=None)


def find_wrapping_outside(range_: NodeRange, type: NodeType) -> list[NodeType] | None:
    parent = range_.parent
    start_index = range_.start_index
    end_index = range_.end_index
    around = parent.content_match_at(start_index).find_wrapping(type)
    if around is None:
        return None
    outer = around[0] if len(around) and around[0] else type
    return around if parent.can_replace_with(start_index, end_index, outer) else None


def find_wrapping_inside(range_: NodeRange, type: NodeType) -> list[NodeType] | None:
    parent = range_.parent
    start_index = range_.start_index
    end_index = range_.end_index
    inner = parent.child(start_index)
    inside = type.content_match.find_wrapping(inner.type)

    if inside is None:
        return None

    last_type = inside[-1] if len(inside) else type
    inner_match: ContentMatch | None = last_type.content_match
    i = start_index

    while inner_match and i < end_index:
        inner_match = inner_match.match_type(parent.child(i).type)
        i += 1

    if not inner_match or not inner_match.valid_end:
        return None

    return inside


def can_change_type(doc: Node, pos: int, type: NodeType) -> bool:
    pos_ = doc.resolve(pos)
    index = pos_.index()
    return pos_.parent.can_replace_with(index, index + 1, type)


def replace_newlines(tr: Transform, node: Node, pos: int, map_from: int) -> None:
    newline = re.compile(r"\r?\n|\r")
    node.for_each(
        lambda child, offset, _index: _replace_newlines_child(
            tr,
            node,
            pos,
            map_from,
            child,
            offset,
            newline,
        )
    )


def _replace_newlines_child(
    tr: Transform,
    node: Node,
    pos: int,
    map_from: int,
    child: Node,
    offset: int,
    newline: re.Pattern[str],
) -> None:
    if child.is_text:
        assert isinstance(child, TextNode)
        m = newline.search(child.text)
        while m:
            start = tr.mapping.slice(map_from).map(
                pos + 1 + offset + m.start(),
            )
            assert node.type.schema.linebreak_replacement is not None
            lb_repl = node.type.schema.linebreak_replacement
            tr.replace_with(start, start + 1, lb_repl.create())
            m = newline.search(child.text, m.end())


def replace_linebreaks(tr: Transform, node: Node, pos: int, map_from: int) -> None:
    node.for_each(
        lambda child, offset, _index: _replace_linebreaks_child(
            tr,
            node,
            pos,
            map_from,
            child,
            offset,
        )
    )


def _replace_linebreaks_child(
    tr: Transform,
    node: Node,
    pos: int,
    map_from: int,
    child: Node,
    offset: int,
) -> None:
    if child.type == child.type.schema.linebreak_replacement:
        start = tr.mapping.slice(map_from).map(pos + 1 + offset)
        tr.replace_with(start, start + 1, node.type.schema.text("\n"))


def can_split(
    doc: Node,
    pos: int,
    depth: int | None = None,
    types_after: list[NodeTypeWithAttrs] | None = None,
) -> bool:
    if depth is None:
        depth = 1
    pos_ = doc.resolve(pos)
    base = pos_.depth - depth
    inner_type: NodeTypeWithAttrs = cast(
        NodeTypeWithAttrs,
        (types_after and types_after[-1]) or pos_.parent,
    )

    if (
        base < 0
        or pos_.parent.type.spec.get("isolating")
        or not pos_.parent.can_replace(pos_.index(), pos_.parent.child_count)
        or not inner_type.type.valid_content(
            pos_.parent.content.cut_by_index(pos_.index(), pos_.parent.child_count),
        )
    ):
        return False

    d = pos_.depth - 1
    i = depth - 2

    while d > base:
        node = pos_.node(d)
        index = pos_.index(d)
        if node.type.spec.get("isolating"):
            return False
        rest = node.content.cut_by_index(index, node.child_count)

        if types_after and len(types_after) > i + 1:
            override_child = types_after[i + 1]
            rest = rest.replace_child(
                0,
                override_child.type.create(override_child.attrs),
            )
        after: NodeTypeWithAttrs = cast(
            NodeTypeWithAttrs,
            (types_after and len(types_after) > i and types_after[i]) or node,
        )
        if not node.can_replace(
            index + 1,
            node.child_count,
        ) or not after.type.valid_content(rest):
            return False
        d -= 1
        i -= 1
    index = pos_.index_after(base)
    base_type = types_after[0] if types_after else None
    return pos_.node(base).can_replace_with(
        index,
        index,
        base_type.type if base_type else pos_.node(base + 1).type,
    )


def can_join(doc: Node, pos: int) -> bool | None:
    pos_ = doc.resolve(pos)
    index = pos_.index()
    return (
        pos_.parent.can_replace(index, index + 1)
        if joinable(pos_.node_before, pos_.node_after)
        else None
    )


def can_append_with_substituted_linebreaks(a: Node, b: Node) -> bool:
    if not b.content.size:
        a.type.compatible_content(b.type)
    match: ContentMatch | None = a.content_match_at(a.child_count)
    linebreak_replacement = a.type.schema.linebreak_replacement
    for i in range(b.child_count):
        child = b.child(i)
        type_ = (
            a.type.schema.nodes["text"]
            if child.type == linebreak_replacement
            else child.type
        )
        match = match.match_type(type_)
        if not match:
            return False
        if not a.type.allows_marks(child.marks):
            return False
    return match.valid_end


def joinable(a: Node | None, b: Node | None) -> bool:
    return bool(
        a and b and not a.is_leaf and can_append_with_substituted_linebreaks(a, b),
    )


def join_point(doc: Node, pos: int, dir: int = -1) -> int | None:
    pos_ = doc.resolve(pos)
    for d in range(pos_.depth, -1, -1):
        before = None
        after = None
        index = pos_.index(d)
        if d == pos_.depth:
            before = pos_.node_before
            after = pos_.node_after
        elif dir > 0:
            before = pos_.node(d + 1)
            index += 1
            after = pos_.node(d).maybe_child(index)
        else:
            before = pos_.node(d).maybe_child(index - 1)
            after = pos_.node(d + 1)
        if (
            before
            and not before.is_textblock
            and joinable(before, after)
            and pos_.node(d).can_replace(index, index + 1)
        ):
            return pos
        if d == 0:
            break
        pos = pos_.before(d) if dir < 0 else pos_.after(d)

    return None


def insert_point(doc: Node, pos: int, node_type: NodeType) -> int | None:
    pos_ = doc.resolve(pos)
    if pos_.parent.can_replace_with(pos_.index(), pos_.index(), node_type):
        return pos
    if pos_.parent_offset == 0:
        for d in range(pos_.depth - 1, -1, -1):
            index = pos_.index(d)
            if pos_.node(d).can_replace_with(index, index, node_type):
                return pos_.before(d + 1)
            if index > 0:
                return None
    if pos_.parent_offset == pos_.parent.content.size:
        for d in range(pos_.depth - 1, -1, -1):
            index = pos_.index_after(d)
            if pos_.node(d).can_replace_with(index, index, node_type):
                return pos_.after(d + 1)
            if index < pos_.node(d).child_count:
                return None

    return None


def drop_point(doc: Node, pos: int, slice: Slice) -> int | None:
    pos_ = doc.resolve(pos)
    if not slice.content.size:
        return pos
    content = slice.content
    for _i in range(slice.open_start):
        assert content.first_child is not None
        content = content.first_child.content
    pass_ = 1
    while pass_ <= (2 if slice.open_start == 0 and slice.size else 1):
        for d in range(pos_.depth, 0, -1):
            if d == pos_.depth:
                bias = 0
            elif pos_.pos <= (pos_.start(d + 1) + pos_.end(d + 1)) / 2:
                bias = -1
            else:
                bias = 1
            insert_pos = pos_.index(d) + (1 if bias > 0 else 0)
            parent = pos_.node(d)
            fits = False
            if pass_ == 1:
                fits = parent.can_replace(insert_pos, insert_pos, content)
            else:
                assert content.first_child is not None
                wrapping = parent.content_match_at(insert_pos).find_wrapping(
                    content.first_child.type,
                )
                fits = wrapping is not None and parent.can_replace_with(
                    insert_pos,
                    insert_pos,
                    wrapping[0],
                )
            if fits:
                if bias == 0:
                    return pos_.pos
                elif bias < 0:
                    return pos_.before(d + 1)
                else:
                    return pos_.after(d + 1)
        pass_ += 1
    return None
