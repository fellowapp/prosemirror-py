from typing import TYPE_CHECKING, Any, ClassVar, Optional, cast

from prosemirror.utils import JSONDict

from .fragment import Fragment

if TYPE_CHECKING:
    from .node import Node, TextNode
    from .resolvedpos import ResolvedPos
    from .schema import Schema


class ReplaceError(ValueError):
    pass


def remove_range(content: Fragment, from_: int, to: int) -> Fragment:
    from_index_info = content.find_index(from_)
    index, offset = from_index_info["index"], from_index_info["offset"]
    child = content.maybe_child(index)
    to_index_info = content.find_index(to)
    index_to, offset_to = to_index_info["index"], to_index_info["offset"]
    if offset == from_ or cast("Node", child).is_text:
        if offset_to != to and not content.child(index_to).is_text:
            raise ValueError("removing non-flat range")
        return content.cut(0, from_).append(content.cut(to))
    assert child
    if index != index_to:
        raise ValueError("removing non-flat range")
    return content.replace_child(
        index,
        child.copy(remove_range(child.content, from_ - offset - 1, to - offset - 1)),
    )


def insert_into(
    content: Fragment, dist: int, insert: Fragment, parent: Optional["Node"]
) -> Optional[Fragment]:
    a = content.find_index(dist)
    index, offset = a["index"], a["offset"]
    child = content.maybe_child(index)
    if offset == dist or cast("Node", child).is_text:
        if parent and not parent.can_replace(index, index, insert):
            return None
        return content.cut(0, dist).append(insert).append(content.cut(dist))
    assert child
    inner = insert_into(child.content, dist - offset - 1, insert, None)
    if inner:
        return content.replace_child(index, child.copy(inner))
    return None


class Slice:
    empty: ClassVar["Slice"]

    def __init__(self, content: Fragment, open_start: int, open_end: int) -> None:
        self.content = content
        self.open_start = open_start
        self.open_end = open_end

    @property
    def size(self) -> int:
        return self.content.size - self.open_start - self.open_end

    def insert_at(self, pos: int, fragment: Fragment) -> Optional["Slice"]:
        content = insert_into(self.content, pos + self.open_start, fragment, None)
        if content:
            return Slice(content, self.open_start, self.open_end)
        return None

    def remove_between(self, from_: int, to: int) -> "Slice":
        return Slice(
            remove_range(self.content, from_ + self.open_start, to + self.open_start),
            self.open_start,
            self.open_end,
        )

    def eq(self, other: "Slice") -> bool:
        return (
            self.content.eq(other.content)
            and self.open_start == other.open_start
            and self.open_end == other.open_end
        )

    def __str__(self) -> str:
        return f"{self.content}({self.open_start},{self.open_end})"

    def to_json(self) -> Optional[JSONDict]:
        if not self.content.size:
            return None
        json: JSONDict = {"content": self.content.to_json()}
        if self.open_start > 0:
            json = {
                **json,
                "openStart": self.open_start,
            }
        if self.open_end > 0:
            json = {
                **json,
                "openEnd": self.open_end,
            }
        return json

    @classmethod
    def from_json(
        cls,
        schema: "Schema[Any, Any]",
        json_data: Optional[JSONDict],
    ) -> "Slice":
        if not json_data:
            return cls.empty
        open_start = json_data.get("openStart", 0) or 0
        open_end = json_data.get("openEnd", 0) or 0
        if not isinstance(open_start, int) or not isinstance(open_end, int):
            raise ValueError("invalid input for Slice.from_json")
        return cls(
            Fragment.from_json(schema, json_data.get("content")),
            open_start,
            open_end,
        )

    @classmethod
    def max_open(cls, fragment: Fragment, open_isolating: bool = True) -> "Slice":
        open_start = 0
        open_end = 0
        n = fragment.first_child
        while n and not n.is_leaf and (open_isolating or n.type.spec.get("isolating")):
            open_start += 1
            n = n.first_child
        n = fragment.last_child
        while n and not n.is_leaf and (open_isolating or n.type.spec.get("isolating")):
            open_end += 1
            n = n.last_child
        return cls(fragment, open_start, open_end)


Slice.empty = Slice(Fragment.empty, 0, 0)


def replace(from_: "ResolvedPos", to: "ResolvedPos", slice: Slice) -> "Node":
    if slice.open_start > from_.depth:
        raise ReplaceError("Inserted content deeper than insertion position")
    if from_.depth - slice.open_start != to.depth - slice.open_end:
        raise ReplaceError("Inconsistent open depths")
    return replace_outer(from_, to, slice, 0)


def replace_outer(
    from_: "ResolvedPos", to: "ResolvedPos", slice: Slice, depth: int
) -> "Node":
    index = from_.index(depth)
    node = from_.node(depth)
    if index == to.index(depth) and depth < from_.depth - slice.open_start:
        inner = replace_outer(from_, to, slice, depth + 1)
        return node.copy(node.content.replace_child(index, inner))
    elif not slice.content.size:
        return close(node, replace_two_way(from_, to, depth))
    elif (
        not slice.open_start
        and not slice.open_end
        and from_.depth == depth
        and to.depth == depth
    ):
        parent = from_.parent
        content = parent.content
        return close(
            parent,
            content.cut(0, from_.parent_offset)
            .append(slice.content)
            .append(content.cut(to.parent_offset)),
        )
    else:
        prepare = prepare_slice_for_replace(slice, from_)
        start, end = prepare["start"], prepare["end"]
        return close(node, replace_three_way(from_, start, end, to, depth))


def check_join(main: "Node", sub: "Node") -> None:
    if not sub.type.compatible_content(main.type):
        raise ReplaceError(f"Cannot join {sub.type.name} onto {main.type.name}")


def joinable(before: "ResolvedPos", after: "ResolvedPos", depth: int) -> "Node":
    node = before.node(depth)
    check_join(node, after.node(depth))
    return node


def add_node(child: "Node", target: list["Node"]) -> None:
    last = len(target) - 1
    if last >= 0 and pm_node.is_text(child) and child.same_markup(target[last]):
        target[last] = child.with_text(cast("TextNode", target[last]).text + child.text)
    else:
        target.append(child)


def add_range(
    start: Optional["ResolvedPos"],
    end: Optional["ResolvedPos"],
    depth: int,
    target: list["Node"],
) -> None:
    node = cast("ResolvedPos", end or start).node(depth)
    start_index = 0
    end_index = end.index(depth) if end else node.child_count
    if start:
        start_index = start.index(depth)
        if start.depth > depth:
            start_index += 1
        elif start.text_offset:
            add_node(cast("Node", start.node_after), target)
            start_index += 1
    i = start_index
    while i < end_index:
        add_node(node.child(i), target)
        i += 1
    if end and end.depth == depth and end.text_offset:
        add_node(cast("Node", end.node_before), target)


def close(node: "Node", content: Fragment) -> "Node":
    if not node.type.valid_content(content):
        raise ReplaceError(f"Invalid content for node {node.type.name}")
    return node.copy(content)


def replace_three_way(
    from_: "ResolvedPos",
    start: "ResolvedPos",
    end: "ResolvedPos",
    to: "ResolvedPos",
    depth: int,
) -> Fragment:
    open_start = joinable(from_, start, depth + 1) if from_.depth > depth else None
    open_end = joinable(end, to, depth + 1) if to.depth > depth else None
    content: list["Node"] = []
    add_range(None, from_, depth, content)
    if open_start and open_end and start.index(depth) == end.index(depth):
        check_join(open_start, open_end)
        add_node(
            close(open_start, replace_three_way(from_, start, end, to, depth + 1)),
            content,
        )
    else:
        if open_start:
            add_node(
                close(open_start, replace_two_way(from_, start, depth + 1)), content
            )
        add_range(start, end, depth, content)
        if open_end:
            add_node(close(open_end, replace_two_way(end, to, depth + 1)), content)
    add_range(to, None, depth, content)
    return Fragment(content)


def replace_two_way(from_: "ResolvedPos", to: "ResolvedPos", depth: int) -> Fragment:
    content: list["Node"] = []
    add_range(None, from_, depth, content)
    if from_.depth > depth:
        type = joinable(from_, to, depth + 1)
        add_node(close(type, replace_two_way(from_, to, depth + 1)), content)
    add_range(to, None, depth, content)
    return Fragment(content)


def prepare_slice_for_replace(
    slice: Slice, along: "ResolvedPos"
) -> dict[str, "ResolvedPos"]:
    extra = along.depth - slice.open_start
    parent = along.node(extra)
    node = parent.copy(slice.content)
    for i in range(extra - 1, -1, -1):
        node = along.node(i).copy(Fragment.from_(node))
    return {
        "start": node.resolve_no_cache(slice.open_start + extra),
        "end": node.resolve_no_cache(node.content.size - slice.open_end - extra),
    }


from . import node as pm_node  # noqa: E402
