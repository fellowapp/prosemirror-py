from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    ClassVar,
    Iterable,
    Optional,
    Sequence,
    Union,
    cast,
)

from prosemirror.utils import JSONList, text_length

if TYPE_CHECKING:
    from prosemirror.model.schema import Schema

    from .diff import Diff
    from .node import Node, TextNode


def retIndex(index: int, offset: int) -> dict[str, int]:
    return {"index": index, "offset": offset}


class Fragment:
    empty: ClassVar["Fragment"]
    content: list["Node"]
    size: int

    def __init__(self, content: list["Node"], size: Optional[int] = None) -> None:
        self.content = content
        self.size = size if size is not None else sum(c.node_size for c in content)

    def nodes_between(
        self,
        from_: int,
        to: int,
        f: Callable[["Node", int, Optional["Node"], int], Optional[bool]],
        node_start: int = 0,
        parent: Optional["Node"] = None,
    ) -> None:
        i = 0
        pos = 0
        while pos < to:
            child = self.content[i]
            end = pos + child.node_size
            if (
                end > from_
                and f(child, node_start + pos, parent, i) is not False
                and getattr(child.content, "size", None)
            ):
                start = pos + 1
                child.nodes_between(
                    max(0, from_ - start),
                    min(child.content.size, to - start),
                    f,
                    node_start + start,
                )
            pos = end
            i += 1

    def descendants(
        self, f: Callable[["Node", int, Optional["Node"], int], Optional[bool]]
    ) -> None:
        self.nodes_between(0, self.size, f)

    def text_between(
        self,
        from_: int,
        to: int,
        block_separator: str = "",
        leaf_text: Union[Callable[["Node"], str], str] = "",
    ) -> str:
        text = []
        separated = True

        def iteratee(
            node: "Node", pos: int, _parent: Optional["Node"], _to: int
        ) -> None:
            nonlocal text
            nonlocal separated
            if node.is_text:
                text_node = cast("TextNode", node)
                text.append(text_node.text[max(from_, pos) - pos : to - pos])
                separated = not block_separator
            elif node.is_leaf:
                if leaf_text:
                    text.append(leaf_text(node) if callable(leaf_text) else leaf_text)
                elif node.type.spec.get("leafText") is not None:
                    text.append(node.type.spec["leafText"](node))
                separated = not block_separator
            elif not separated and node.is_block:
                text.append(block_separator)
                separated = True

        self.nodes_between(from_, to, iteratee, 0)
        return "".join(text)

    def append(self, other: "Fragment") -> "Fragment":
        if not other.size:
            return self
        if not self.size:
            return other
        last, first, content, i = (
            self.last_child,
            other.first_child,
            self.content.copy(),
            0,
        )
        assert last is not None and first is not None
        if pm_node.is_text(last) and last.same_markup(first):
            assert isinstance(first, pm_node.TextNode)
            content[len(content) - 1] = last.with_text(last.text + first.text)
            i = 1
        while i < len(other.content):
            content.append(other.content[i])
            i += 1
        return Fragment(content, self.size + other.size)

    def cut(self, from_: int, to: Optional[int] = None) -> "Fragment":
        if to is None:
            to = self.size
        if from_ == 0 and to == self.size:
            return self
        result: list["Node"] = []
        size = 0
        if to <= from_:
            return Fragment(result, size)
        i, pos = 0, 0
        while pos < to:
            child = self.content[i]
            end = pos + child.node_size
            if end > from_:
                if pos < from_ or end > to:
                    if pm_node.is_text(child):
                        child = child.cut(
                            max(0, from_ - pos), min(text_length(child.text), to - pos)
                        )
                    else:
                        child = child.cut(
                            max(0, from_ - pos - 1),
                            min(child.content.size, to - pos - 1),
                        )
                result.append(child)
                size += child.node_size
            pos = end
            i += 1
        return Fragment(result, size)

    def cut_by_index(self, from_: int, to: Optional[int] = None) -> "Fragment":
        if from_ == to:
            return Fragment.empty
        if from_ == 0 and to == len(self.content):
            return self
        return Fragment(self.content[from_:to])

    def replace_child(self, index: int, node: "Node") -> "Fragment":
        current = self.content[index]
        if current == node:
            return self
        copy = self.content.copy()
        size = self.size + node.node_size - current.node_size
        copy[index] = node
        return Fragment(copy, size)

    def add_to_start(self, node: "Node") -> "Fragment":
        return Fragment([node, *self.content], self.size + node.node_size)

    def add_to_end(self, node: "Node") -> "Fragment":
        return Fragment([*self.content, node], self.size + node.node_size)

    def eq(self, other: "Fragment") -> bool:
        if len(self.content) != len(other.content):
            return False
        return all(a.eq(b) for (a, b) in zip(self.content, other.content))

    @property
    def first_child(self) -> Optional["Node"]:
        return self.content[0] if self.content else None

    @property
    def last_child(self) -> Optional["Node"]:
        return self.content[-1] if self.content else None

    @property
    def child_count(self) -> int:
        return len(self.content)

    def child(self, index: int) -> "Node":
        return self.content[index]

    def maybe_child(self, index: int) -> Optional["Node"]:
        try:
            return self.content[index]
        except IndexError:
            return None

    def for_each(self, f: Callable[["Node", int, int], Any]) -> None:
        i = 0
        p = 0
        while i < len(self.content):
            child = self.content[i]
            f(child, p, i)
            p += child.node_size
            i += 1

    def find_diff_start(self, other: "Fragment", pos: int = 0) -> Optional[int]:
        from .diff import find_diff_start

        return find_diff_start(self, other, pos)

    def find_diff_end(
        self,
        other: "Fragment",
        pos: Optional[int] = None,
        other_pos: Optional[int] = None,
    ) -> Optional["Diff"]:
        from .diff import find_diff_end

        if pos is None:
            pos = self.size
        if other_pos is None:
            other_pos = other.size
        return find_diff_end(self, other, pos, other_pos)

    def find_index(self, pos: int, round: int = -1) -> dict[str, int]:
        if pos == 0:
            return retIndex(0, pos)
        if pos == self.size:
            return retIndex(len(self.content), pos)
        if pos > self.size or pos < 0:
            raise ValueError(f"Position {pos} outside of fragment ({self})")
        i = 0
        cur_pos = 0
        while True:
            cur = self.child(i)
            end = cur_pos + cur.node_size
            if end >= pos:
                if end == pos or round > 0:
                    return retIndex(i + 1, end)
                return retIndex(i, cur_pos)
            i += 1
            cur_pos = end

    def to_json(self) -> Optional[JSONList]:
        if self.content:
            return [item.to_json() for item in self.content]
        return None

    @classmethod
    def from_json(cls, schema: "Schema[Any, Any]", value: Any) -> "Fragment":
        if not value:
            return cls.empty

        if isinstance(value, str):
            import json

            value = json.loads(value)

        if not isinstance(value, list):
            raise ValueError("Invalid input for Fragment.from_json")

        return cls([schema.node_from_json(item) for item in value])

    @classmethod
    def from_array(cls, array: list["Node"]) -> "Fragment":
        if not array:
            return cls.empty
        joined: Optional[list["Node"]] = None
        size = 0
        for i in range(len(array)):
            node = array[i]
            size += node.node_size
            if i and pm_node.is_text(node) and array[i - 1].same_markup(node):
                if not joined:
                    joined = array[0:i]
                last = joined[-1]
                assert isinstance(last, pm_node.TextNode)
                joined[-1] = node.with_text(last.text + node.text)
            elif joined:
                joined.append(node)
        return cls(joined or array, size)

    @classmethod
    def from_(
        cls, nodes: Union["Fragment", "Node", Sequence["Node"], None]
    ) -> "Fragment":
        if not nodes:
            return cls.empty
        if isinstance(nodes, Fragment):
            return nodes
        if isinstance(nodes, Iterable):
            return cls.from_array(list(nodes))
        if hasattr(nodes, "attrs"):
            return cls([nodes], nodes.node_size)
        raise ValueError(f"cannot convert {nodes!r} to a fragment")

    def to_string_inner(self) -> str:
        return ", ".join([str(i) for i in self.content])

    def __str__(self) -> str:
        return f"<{self.to_string_inner()}>"

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} {self.__str__()}>"


Fragment.empty = Fragment([], 0)

from . import node as pm_node  # noqa: E402
