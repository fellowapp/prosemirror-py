from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, TypedDict, Union

from typing_extensions import TypeGuard

from prosemirror.utils import JSON, JSONDict, text_length

from .comparedeep import compare_deep
from .fragment import Fragment
from .mark import Mark
from .replace import Slice, replace
from .resolvedpos import ResolvedPos

if TYPE_CHECKING:
    from .content import ContentMatch
    from .schema import MarkType, NodeType, Schema


empty_attrs: JSONDict = {}


class ChildInfo(TypedDict):
    node: Optional["Node"]
    index: int
    offset: int


class Node:
    def __init__(
        self,
        type: "NodeType",
        attrs: JSONDict,
        content: Optional[Fragment],
        marks: List[Mark],
    ) -> None:
        self.type = type
        self.attrs = attrs
        self.content = content or Fragment.empty
        self.marks = marks or Mark.none

    @property
    def node_size(self) -> int:
        return 1 if self.is_leaf else 2 + self.content.size

    @property
    def child_count(self) -> int:
        return self.content.child_count

    def child(self, index: int) -> "Node":
        return self.content.child(index)

    def maybe_child(self, index: int) -> Optional["Node"]:
        return self.content.maybe_child(index)

    def for_each(self, f: Callable[["Node", int, int], None]) -> None:
        self.content.for_each(f)

    def nodes_between(
        self,
        from_: int,
        to: int,
        f: Callable[["Node", int, Optional["Node"], int], Optional[bool]],
        start_pos: int = 0,
    ) -> None:
        self.content.nodes_between(from_, to, f, start_pos, self)

    def descendants(
        self, f: Callable[["Node", int, Optional["Node"], int], Optional[bool]]
    ) -> None:
        self.nodes_between(0, self.content.size, f)

    @property
    def text_content(self) -> str:
        if self.is_leaf and self.type.spec.get("leafText") is not None:
            return self.type.spec["leafText"](self)
        return self.text_between(0, self.content.size, "")

    def text_between(
        self,
        from_: int,
        to: int,
        block_separator: str = "",
        leaf_text: Union[Callable[["Node"], str], str] = "",
    ) -> str:
        return self.content.text_between(from_, to, block_separator, leaf_text)

    @property
    def first_child(self) -> Optional["Node"]:
        return self.content.first_child

    @property
    def last_child(self) -> Optional["Node"]:
        return self.content.last_child

    def eq(self, other: "Node") -> bool:
        return self == other or (
            self.same_markup(other) and self.content.eq(other.content)
        )

    def same_markup(self, other: "Node") -> bool:
        return self.has_markup(other.type, other.attrs, other.marks)

    def has_markup(
        self,
        type: "NodeType",
        attrs: Optional[JSONDict] = None,
        marks: Optional[List[Mark]] = None,
    ) -> bool:
        return (
            self.type.name == type.name
            and (compare_deep(self.attrs, attrs or type.default_attrs or empty_attrs))
            and (Mark.same_set(self.marks, marks or Mark.none))
        )

    def copy(self, content: Optional[Fragment] = None) -> "Node":
        if content == self.content:
            return self
        return self.__class__(self.type, self.attrs, content, self.marks)

    def mark(self, marks: List[Mark]) -> "Node":
        if marks == self.marks:
            return self
        return self.__class__(self.type, self.attrs, self.content, marks)

    def cut(self, from_: int, to: Optional[int] = None) -> "Node":
        if from_ == 0 and to == self.content.size:
            return self
        return self.copy(self.content.cut(from_, to))

    def slice(
        self, from_: int, to: Optional[int] = None, include_parents: bool = False
    ) -> Slice:
        if to is None:
            to = self.content.size
        if from_ == to:
            return Slice.empty
        from__ = self.resolve(from_)
        to_ = self.resolve(to)
        depth = 0 if include_parents else from__.shared_depth(to)
        start = from__.start(depth)
        node = from__.node(depth)
        content = node.content.cut(from__.pos - start, to_.pos - start)
        return Slice(content, from__.depth - depth, to_.depth - depth)

    def replace(self, from_: int, to: int, slice: Slice) -> "Node":
        return replace(self.resolve(from_), self.resolve(to), slice)

    def node_at(self, pos: int) -> Optional["Node"]:
        node = self
        while True:
            index_info = node.content.find_index(pos)
            index, offset = index_info["index"], index_info["offset"]
            next_node = node.maybe_child(index)
            if not next_node:
                return None
            node = next_node
            if offset == pos or node.is_text:
                return node
            pos -= offset + 1

    def child_after(self, pos: int) -> ChildInfo:
        index_info = self.content.find_index(pos)
        index, offset = index_info["index"], index_info["offset"]
        return {
            "node": self.content.maybe_child(index),
            "index": index,
            "offset": offset,
        }

    def child_before(self, pos: int) -> ChildInfo:
        if pos == 0:
            return {"node": None, "index": 0, "offset": 0}
        index_info = self.content.find_index(pos)
        index, offset = index_info["index"], index_info["offset"]
        if offset < pos:
            return {"node": self.content.child(index), "index": index, "offset": offset}
        node = self.content.child(index - 1)
        return {"node": node, "index": index - 1, "offset": offset - node.node_size}

    def resolve(self, pos: int) -> ResolvedPos:
        return ResolvedPos.resolve_cached(self, pos)

    def resolve_no_cache(self, pos: int) -> ResolvedPos:
        return ResolvedPos.resolve(self, pos)

    def range_has_mark(
        self, from_: int, to: int, type: Union[Mark, "MarkType"]
    ) -> bool:
        found = False
        if to > from_:

            def iteratee(
                node: "Node", pos: int, parent: Optional["Node"], index: int
            ) -> bool:
                nonlocal found
                if type.is_in_set(node.marks):
                    found = True
                return not found

            self.nodes_between(from_, to, iteratee)
        return found

    @property
    def is_block(self) -> bool:
        return self.type.is_block

    @property
    def is_text_block(self) -> bool:
        return self.type.is_text_block

    @property
    def inline_content(self) -> bool:
        return self.type.inline_content

    @property
    def is_inline(self) -> bool:
        return self.type.is_inline

    @property
    def is_text(self) -> bool:
        return self.type.is_text

    @property
    def is_leaf(self) -> bool:
        return self.type.is_leaf

    @property
    def is_atom(self) -> bool:
        return self.type.is_atom

    def __str__(self) -> str:
        to_debug_string = (
            self.type.spec["toDebugString"]
            if "toDebugString" in self.type.spec
            else None
        )
        if to_debug_string:
            return to_debug_string(self)
        name = self.type.name
        if self.content.size:
            name += f"({self.content.to_string_inner()})"
        return wrap_marks(self.marks, name)

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} {self.__str__()}>"

    def content_match_at(self, index: int) -> "ContentMatch":
        match = self.type.content_match.match_fragment(self.content, 0, index)
        if not match:
            raise ValueError("Called contentMatchAt on a node with invalid content")
        return match

    def can_replace(
        self,
        from_: int,
        to: int,
        replacement: Fragment = Fragment.empty,
        start: int = 0,
        end: Optional[int] = None,
    ) -> bool:
        if end is None:
            end = replacement.child_count
        one = self.content_match_at(from_).match_fragment(replacement, start, end)
        two: Optional["ContentMatch"] = None
        if one:
            two = one.match_fragment(self.content, to)
        if not two or not two.valid_end:
            return False
        for i in range(start, end):
            if not self.type.allows_marks(replacement.child(i).marks):
                return False
        return True

    def can_replace_with(
        self, from_: int, to: int, type: "NodeType", marks: Optional[List[Mark]] = None
    ) -> bool:
        if marks and not self.type.allows_marks(marks):
            return False
        start = self.content_match_at(from_).match_type(type)
        end: Optional["ContentMatch"] = None
        if start:
            end = start.match_fragment(self.content, to)
        return end.valid_end if end else False

    def can_append(self, other: "Node") -> bool:
        if other.content.size:
            return self.can_replace(self.child_count, self.child_count, other.content)
        else:
            return self.type.compatible_content(other.type)

    def check(self) -> None:
        if not self.type.valid_content(self.content):
            raise ValueError(
                f"Invalid content for node {self.type.name}: {str(self.content)[:50]}"
            )
        copy = Mark.none
        for mark in self.marks:
            copy = mark.add_to_set(copy)
        if not Mark.same_set(copy, self.marks):
            raise ValueError(
                f"Invalid collection of marks for node {self.type.name}:"
                f" {[m.type.name for m in self.marks]!r}"
            )

        def iteratee(node: "Node", offset: int, index: int) -> None:
            node.check()

        return self.content.for_each(iteratee)

    def to_json(self) -> JSONDict:
        obj: Dict[str, JSON] = {"type": self.type.name}
        for _ in self.attrs:
            obj["attrs"] = self.attrs
            break
        if getattr(self.content, "size", None):
            obj["content"] = self.content.to_json()
        if len(self.marks):
            obj["marks"] = [n.to_json() for n in self.marks]
        return obj

    @classmethod
    def from_json(cls, schema: "Schema[str, str]", json_data: Any) -> "Node":
        if isinstance(json_data, str):
            import json

            json_data = json.loads(json_data)
        if not json_data:
            raise ValueError("Invalid input for Node.from_json")
        marks = None
        if json_data.get("marks"):
            if not isinstance(json_data["marks"], list):
                raise ValueError("Invalid mark data for Node.fromJSON")
            marks = [schema.mark_from_json(item) for item in json_data["marks"]]
        if json_data["type"] == "text":
            return schema.text(json_data["text"], marks)
        content = Fragment.from_json(schema, json_data.get("content"))
        return schema.node_type(json_data["type"]).create(
            json_data.get("attrs"), content, marks
        )


class TextNode(Node):
    def __init__(
        self,
        type: "NodeType",
        attrs: JSONDict,
        content: str,
        marks: List[Mark],
    ) -> None:
        super().__init__(type, attrs, None, marks)
        if not content:
            raise ValueError("Empty text nodes are not allowed")
        self.text = content

    def __str__(self) -> str:
        import json

        to_debug_string = (
            self.type.spec["toDebugString"]
            if "toDebugString" in self.type.spec
            else None
        )
        if to_debug_string:
            return to_debug_string(self)
        return wrap_marks(self.marks, json.dumps(self.text))

    @property
    def text_content(self) -> str:
        return self.text

    def text_between(
        self,
        from_: int,
        to: int,
        block_separator: str = "",
        leaf_text: Union[Callable[["Node"], str], str] = "",
    ) -> str:
        return self.text[from_:to]

    @property
    def node_size(self) -> int:
        return text_length(self.text)

    def mark(self, marks: List[Mark]) -> "TextNode":
        return (
            self
            if marks == self.marks
            else TextNode(self.type, self.attrs, self.text, marks)
        )

    def with_text(self, text: str) -> "TextNode":
        if text == self.text:
            return self
        return TextNode(self.type, self.attrs, text, self.marks)

    def cut(self, from_: int = 0, to: Optional[int] = None) -> "TextNode":
        if to is None:
            to = text_length(self.text)
        if from_ == 0 and to == text_length(self.text):
            return self
        substring = self.text.encode("utf-16-le")[2 * from_ : 2 * to].decode(
            "utf-16-le"
        )
        return self.with_text(substring)

    def eq(self, other: Node) -> bool:
        return self.same_markup(other) and self.text == getattr(other, "text", None)

    def to_json(
        self,
    ) -> JSONDict:
        return {**super().to_json(), "text": self.text}


def wrap_marks(marks: List[Mark], str: str) -> str:
    i = len(marks) - 1
    while i >= 0:
        str = marks[i].type.name + "(" + str + ")"
        i -= 1
    return str


def is_text(node: Node) -> TypeGuard[TextNode]:
    """
    Helper function to check if a node is a text node, but with
    type narrowing. (TypeGuard cannot narrow the type of `self`; see
    https://mypy.readthedocs.io/en/stable/type_narrowing.html#typeguards-as-methods)
    """
    return node.is_text
