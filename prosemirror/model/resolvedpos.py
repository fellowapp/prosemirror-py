from typing import TYPE_CHECKING, List, Optional, Union, cast

from .mark import Mark

if TYPE_CHECKING:
    from .node import Node


class ResolvedPos:
    def __init__(
        self, pos: int, path: List[Union["Node", int]], parent_offset: int
    ) -> None:
        self.pos = pos
        self.path = path
        self.depth = int(len(path) / 3 - 1)
        self.parent_offset = parent_offset

    def resolve_depth(self, val: Optional[int] = None) -> int:
        if val is None:
            return self.depth
        return self.depth + val if val < 0 else val

    @property
    def parent(self) -> "Node":
        return self.node(self.depth)

    @property
    def doc(self) -> "Node":
        return self.node(0)

    def node(self, depth: int) -> "Node":
        return cast("Node", self.path[self.resolve_depth(depth) * 3])

    def index(self, depth: Optional[int] = None) -> int:
        return cast(int, self.path[self.resolve_depth(depth) * 3 + 1])

    def index_after(self, depth: int) -> int:
        depth = self.resolve_depth(depth)
        return self.index(depth) + (
            0 if depth == self.depth and not self.text_offset else 1
        )

    def start(self, depth: Optional[int] = None) -> int:
        depth = self.resolve_depth(depth)
        return 0 if depth == 0 else cast(int, self.path[depth * 3 - 1]) + 1

    def end(self, depth: Optional[int] = None) -> int:
        depth = self.resolve_depth(depth)
        return self.start(depth) + self.node(depth).content.size

    def before(self, depth: Optional[int] = None) -> int:
        depth = self.resolve_depth(depth)
        if not depth:
            raise ValueError("There is no position before the top level node")
        return (
            self.pos if depth == self.depth + 1 else cast(int, self.path[depth * 3 - 1])
        )

    def after(self, depth: Optional[int] = None) -> int:
        depth = self.resolve_depth(depth)
        if not depth:
            raise ValueError("There is no position after the top level node")
        return (
            self.pos
            if depth == self.depth + 1
            else cast(int, self.path[depth * 3 - 1])
            + cast("Node", self.path[depth * 3]).node_size
        )

    @property
    def text_offset(self) -> int:
        return self.pos - cast(int, self.path[-1])

    @property
    def node_after(self) -> Optional["Node"]:
        parent = self.parent
        index = self.index(self.depth)
        if index == parent.child_count:
            return None
        d_off = self.pos - cast(int, self.path[-1])
        child = parent.child(index)
        return parent.child(index).cut(d_off) if d_off else child

    @property
    def node_before(self) -> Optional["Node"]:
        index = self.index(self.depth)
        d_off = self.pos - cast(int, self.path[-1])
        if d_off:
            return self.parent.child(index).cut(0, d_off)
        return None if index == 0 else self.parent.child(index - 1)

    def pos_at_index(self, index: int, depth: Optional[int] = None) -> int:
        depth = self.resolve_depth(depth)
        node = cast("Node", self.path[depth * 3])
        pos = 0 if depth == 0 else cast(int, self.path[depth * 3 - 1]) + 1
        for i in range(index):
            pos += node.child(i).node_size
        return pos

    def marks(self) -> List["Mark"]:
        parent = self.parent
        index = self.index()
        if parent.content.size == 0:
            return Mark.none
        if self.text_offset:
            return parent.child(index).marks
        main = parent.maybe_child(index - 1)
        other = parent.maybe_child(index)
        if not main:
            main, other = other, main
        marks = cast("Node", main).marks
        i = 0
        while i < len(marks):
            if marks[i].type.spec.get("inclusive") is False and (
                not other or not marks[i].is_in_set(other.marks)
            ):
                marks = marks[i].remove_from_set(marks)
                i -= 1
            i += 1
        return marks

    def marks_across(self, end: "ResolvedPos") -> Optional[List["Mark"]]:
        after = self.parent.maybe_child(self.index())
        if not after or not after.is_inline:
            return None
        marks = after.marks
        next = end.parent.maybe_child(end.index())
        i = 0
        while i < len(marks):
            if marks[i].type.spec.get("inclusive") is False and (
                not next or not marks[i].is_in_set(next.marks)
            ):
                marks = marks[i].remove_from_set(marks)
                i -= 1
            i += 1
        return marks

    def shared_depth(self, pos: int) -> int:
        depth = self.depth
        while depth > 0:
            if self.start(depth) <= pos and self.end(depth) >= pos:
                return depth
            depth -= 1
        return 0

    def block_range(
        self, other: Optional["ResolvedPos"] = None, pred: None = None
    ) -> Optional["NodeRange"]:
        if other is None:
            other = self
        if other.pos < self.pos:
            return other.block_range(self)
        d = self.depth - (
            self.parent.inline_content or (1 if self.pos == other.pos else 0)
        )
        while d >= 0:
            if other.pos <= self.end(d) and (not pred or pred(self.node(d))):
                return NodeRange(self, other, d)
            d -= 1
        return None

    def same_parent(self, other: "ResolvedPos") -> bool:
        return self.pos - self.parent_offset == other.pos - other.parent_offset

    def max(self, other: "ResolvedPos") -> "ResolvedPos":
        return other if other.pos > self.pos else self

    def min(self, other: "ResolvedPos") -> "ResolvedPos":
        return other if other.pos < self.pos else self

    def __str__(self) -> str:
        path = "/".join(
            [
                f"{self.node(i).type.name}_{self.index(i - 1)}"
                for i in range(1, self.depth + 1)
            ]
        )
        return f"{path}:{self.parent_offset}"

    @classmethod
    def resolve(cls, doc: "Node", pos: int) -> "ResolvedPos":
        if not (pos >= 0 and pos <= doc.content.size):
            raise ValueError(f"Position {pos} out of range")
        path: List[Union["Node", int]] = []
        start = 0
        parent_offset = pos
        node = doc
        while True:
            index_info = node.content.find_index(parent_offset)
            index, offset = index_info["index"], index_info["offset"]
            rem = parent_offset - offset
            path.extend([node, index, start + offset])
            if not rem:
                break
            node = node.child(index)
            if node.is_text:
                break
            parent_offset = rem - 1
            start += offset + 1
        return cls(pos, path, parent_offset)

    @classmethod
    def resolve_cached(cls, doc: "Node", pos: int) -> "ResolvedPos":
        # no cache for now
        return cls.resolve(doc, pos)


class NodeRange:
    def __init__(self, from_: ResolvedPos, to: ResolvedPos, depth: int) -> None:
        self.from_ = from_
        self.to = to
        self.depth = depth

    @property
    def start(self) -> int:
        return self.from_.before(self.depth + 1)

    @property
    def end(self) -> int:
        return self.to.after(self.depth + 1)

    @property
    def parent(self) -> "Node":
        return self.from_.node(self.depth)

    @property
    def start_index(self) -> int:
        return self.from_.index(self.depth)

    @property
    def end_index(self) -> int:
        return self.to.index_after(self.depth)
