from collections.abc import Callable
from typing import (
    Any,
    Generic,
    Literal,
    Optional,
    TypeAlias,
    TypeVar,
    cast,
)

from typing_extensions import NotRequired, TypedDict

from prosemirror.model.content import ContentMatch
from prosemirror.model.fragment import Fragment
from prosemirror.model.mark import Mark
from prosemirror.model.node import Node, TextNode
from prosemirror.utils import JSON, Attrs, JSONDict


def default_attrs(attrs: "Attributes") -> Attrs | None:
    defaults = {}
    for attr_name, attr in attrs.items():
        if not attr.has_default:
            return None
        defaults[attr_name] = attr.default
    return defaults


def compute_attrs(attrs: "Attributes", value: Attrs | None) -> Attrs:
    built = {}
    for name in attrs:
        given = None
        if value:
            given = value.get(name)
        if given is None:
            attr = attrs[name]
            if attr.has_default:
                given = attr.default
            else:
                raise ValueError("No value supplied for attribute " + name)
        built[name] = given
    return built


def init_attrs(attrs: Optional["AttributeSpecs"]) -> "Attributes":
    result = {}
    if attrs:
        for name in attrs:
            result[name] = Attribute(attrs[name])
    return result


class NodeType:
    """
    Node types are objects allocated once per `Schema` and used to
    [tag](#model.Node.type) `Node` instances. They contain information
    about the node type, such as its name and what kind of node it
    represents.
    """

    name: str

    schema: "Schema[Any, Any]"

    spec: "NodeSpec"

    inline_content: bool

    mark_set: list["MarkType"] | None

    def __init__(self, name: str, schema: "Schema[Any, Any]", spec: "NodeSpec") -> None:
        self.name = name
        self.schema = schema
        self.spec = spec
        self.groups = spec["group"].split(" ") if "group" in spec else []
        self.attrs = init_attrs(spec.get("attrs"))
        self.default_attrs = default_attrs(self.attrs)
        self._content_match: ContentMatch | None = None
        self.mark_set = None
        self.inline_content = False
        self.is_block = not (spec.get("inline") or name == "text")
        self.is_text = name == "text"

    @property
    def content_match(self) -> ContentMatch:
        assert self._content_match is not None
        return self._content_match

    @content_match.setter
    def content_match(self, value: ContentMatch) -> None:
        self._content_match = value

    @property
    def is_inline(self) -> bool:
        return not self.is_block

    @property
    def is_textblock(self) -> bool:
        return self.is_block and self.inline_content

    @property
    def is_leaf(self) -> bool:
        return self.content_match == ContentMatch.empty

    @property
    def is_atom(self) -> bool:
        return self.is_leaf or bool(self.spec.get("atom"))

    @property
    def whitespace(self) -> Literal["pre", "normal"]:
        return self.spec.get("whitespace") or (
            "pre" if self.spec.get("code") else "normal"
        )

    def has_required_attrs(self) -> bool:
        return any(self.attrs[n].is_required for n in self.attrs)

    def compatible_content(self, other: "NodeType") -> bool:
        return self == other or (self.content_match.compatible(other.content_match))

    def compute_attrs(self, attrs: Attrs | None) -> Attrs:
        if attrs is None and self.default_attrs is not None:
            return self.default_attrs
        return compute_attrs(self.attrs, attrs)

    def create(
        self,
        attrs: Attrs | None = None,
        content: Fragment | Node | list[Node] | None = None,
        marks: list[Mark] | None = None,
    ) -> Node:
        if self.is_text:
            raise ValueError("NodeType.create cannot construct text nodes")
        return Node(
            self,
            self.compute_attrs(attrs),
            Fragment.from_(content),
            Mark.set_from(marks),
        )

    def create_checked(
        self,
        attrs: Attrs | None = None,
        content: Fragment | Node | list[Node] | None = None,
        marks: list[Mark] | None = None,
    ) -> Node:
        content = Fragment.from_(content)
        if not self.valid_content(content):
            raise ValueError("Invalid content for node " + self.name)
        return Node(self, self.compute_attrs(attrs), content, Mark.set_from(marks))

    def create_and_fill(
        self,
        attrs: Attrs | None = None,
        content: Fragment | Node | list[Node] | None = None,
        marks: list[Mark] | None = None,
    ) -> Node | None:
        attrs = self.compute_attrs(attrs)
        frag = Fragment.from_(content)
        if frag.size:
            before = self.content_match.fill_before(frag)
            if not before:
                return None
            frag = before.append(frag)
        matched = self.content_match.match_fragment(frag)
        if not matched:
            return None
        after = matched.fill_before(Fragment.empty, True)
        if not after:
            return None
        return Node(self, attrs, frag.append(after), Mark.set_from(marks))

    def valid_content(self, content: Fragment) -> bool:
        result = self.content_match.match_fragment(content)
        if not result or not result.valid_end:
            return False
        for i in range(content.child_count):
            if not self.allows_marks(content.child(i).marks):
                return False
        return True

    def allows_mark_type(self, mark_type: "MarkType") -> bool:
        return self.mark_set is None or mark_type in self.mark_set

    def allows_marks(self, marks: list[Mark]) -> bool:
        if self.mark_set is None:
            return True
        return all(self.allows_mark_type(mark.type) for mark in marks)

    def allowed_marks(self, marks: list[Mark]) -> list[Mark]:
        if self.mark_set is None:
            return marks
        copy: list[Mark] | None = None
        for i, mark in enumerate(marks):
            if not self.allows_mark_type(mark.type):
                if not copy:
                    copy = marks[0:i]
            elif copy:
                copy.append(mark)
        if copy is None:
            return marks
        elif len(copy):
            return copy
        else:
            return Mark.none

    @classmethod
    def compile(
        cls, nodes: dict["Nodes", "NodeSpec"], schema: "Schema[Nodes, Marks]"
    ) -> dict["Nodes", "NodeType"]:
        result: dict["Nodes", "NodeType"] = {}

        for name, spec in nodes.items():
            result[name] = NodeType(name, schema, spec)

        top_node = cast(Nodes, schema.spec.get("topNode") or "doc")
        if not result.get(top_node):
            raise ValueError(f"Schema is missing its top node type {top_node}")
        if not result.get(cast(Nodes, "text")):
            raise ValueError("every schema needs a 'text' type")
        if result[cast(Nodes, "text")].attrs:
            raise ValueError("the text node type should not have attributes")
        return result

    def __str__(self) -> str:
        return f"<NodeType {self.name}>"

    def __repr__(self) -> str:
        return self.__str__()


Attributes: TypeAlias = dict[str, "Attribute"]


class Attribute:
    def __init__(self, options: "AttributeSpec") -> None:
        self.has_default = "default" in options
        self.default = options["default"] if self.has_default else None

    @property
    def is_required(self) -> bool:
        return not self.has_default


class MarkType:
    excluded: list["MarkType"]
    instance: Mark | None

    def __init__(
        self, name: str, rank: int, schema: "Schema[Any, Any]", spec: "MarkSpec"
    ) -> None:
        self.name = name
        self.schema = schema
        self.spec = spec
        self.attrs = init_attrs(spec.get("attrs"))
        self.rank = rank
        self.excluded = None  # type: ignore[assignment]
        defaults = default_attrs(self.attrs)
        self.instance = None
        if defaults:
            self.instance = Mark(self, defaults)

    def create(
        self,
        attrs: Attrs | None = None,
    ) -> Mark:
        if not attrs and self.instance:
            return self.instance
        return Mark(self, compute_attrs(self.attrs, attrs))

    @classmethod
    def compile(
        cls, marks: dict["Marks", "MarkSpec"], schema: "Schema[Nodes, Marks]"
    ) -> dict["Marks", "MarkType"]:
        result = {}
        for rank, (name, spec) in enumerate(marks.items()):
            result[name] = MarkType(name, rank, schema, spec)
        return result

    def remove_from_set(self, set_: list["Mark"]) -> list["Mark"]:
        return [item for item in set_ if item.type != self]

    def is_in_set(self, set: list[Mark]) -> Mark | None:
        return next((item for item in set if item.type == self), None)

    def excludes(self, other: "MarkType") -> bool:
        return any(other.name == e.name for e in self.excluded)


Nodes = TypeVar("Nodes", bound=str, covariant=True)
Marks = TypeVar("Marks", bound=str, covariant=True)


class SchemaSpec(TypedDict, Generic[Nodes, Marks]):
    """
    An object describing a schema, as passed to the [`Schema`](#model.Schema)
    constructor.
    """

    # The node types in this schema. Maps names to
    # [`NodeSpec`](#model.NodeSpec) objects that describe the node type
    # associated with that name. Their order is significant—it
    # determines which [parse rules](#model.NodeSpec.parseDOM) take
    # precedence by default, and which nodes come first in a given
    # [group](#model.NodeSpec.group).
    nodes: dict[Nodes, "NodeSpec"]

    # The mark types that exist in this schema. The order in which they
    # are provided determines the order in which [mark
    # sets](#model.Mark.addToSet) are sorted and in which [parse
    # rules](#model.MarkSpec.parseDOM) are tried.
    marks: NotRequired[dict[Marks, "MarkSpec"]]

    # The name of the default top-level node for the schema. Defaults
    # to `"doc"`.
    topNode: NotRequired[str]


class NodeSpec(TypedDict, total=False):
    """
    A description of a node type, used when defining a schema.
    """

    content: str
    marks: str
    group: str
    inline: bool
    atom: bool
    attrs: "AttributeSpecs"
    selectable: bool
    draggable: bool
    code: bool
    whitespace: Literal["pre", "normal"]
    definingAsContext: bool
    definingForContent: bool
    defining: bool
    isolating: bool
    toDOM: Callable[[Node], Any]  # FIXME: add types
    parseDOM: list[dict[str, Any]]  # FIXME: add types
    toDebugString: Callable[[Node], str]
    leafText: Callable[[Node], str]


AttributeSpecs: TypeAlias = dict[str, "AttributeSpec"]


class MarkSpec(TypedDict, total=False):
    attrs: AttributeSpecs
    inclusive: bool
    excludes: str
    group: str
    spanning: bool
    toDOM: Callable[[Mark, bool], Any]  # FIXME: add types
    parseDOM: list[dict[str, Any]]  # FIXME: add types


class AttributeSpec(TypedDict, total=False):
    default: JSON


class Schema(Generic[Nodes, Marks]):
    spec: SchemaSpec[Nodes, Marks]

    nodes: dict[Nodes, "NodeType"]

    marks: dict[Marks, "MarkType"]

    def __init__(self, spec: SchemaSpec[Nodes, Marks]) -> None:
        self.spec = spec
        self.nodes = NodeType.compile(self.spec["nodes"], self)
        self.marks = MarkType.compile(self.spec.get("marks", {}), self)
        content_expr_cache = {}
        for prop in self.nodes:
            if prop in self.marks:
                raise ValueError(f"{prop} can not be both a node and a mark")
            type = self.nodes[prop]
            content_expr = type.spec.get("content", "")
            mark_expr = type.spec.get("marks")
            if content_expr not in content_expr_cache:
                content_expr_cache[content_expr] = ContentMatch.parse(
                    content_expr, cast(dict[str, "NodeType"], self.nodes)
                )

            type.content_match = content_expr_cache[content_expr]
            type.inline_content = type.content_match.inline_content
            if mark_expr == "_":
                type.mark_set = None
            elif mark_expr:
                type.mark_set = gather_marks(self, mark_expr.split(" "))
            elif mark_expr == "" or not type.inline_content:
                type.mark_set = []
            else:
                type.mark_set = None
        for mark in self.marks.values():
            excl = mark.spec.get("excludes")
            mark.excluded = (
                [mark]
                if excl is None
                else ([] if excl == "" else (gather_marks(self, excl.split(" "))))
            )

        self.top_node_type = self.nodes[cast(Nodes, self.spec.get("topNode") or "doc")]
        self.cached: dict[str, Any] = {}
        self.cached["wrappings"] = {}

    def node(
        self,
        type: str | NodeType,
        attrs: Attrs | None = None,
        content: Fragment | Node | list[Node] | None = None,
        marks: list[Mark] | None = None,
    ) -> Node:
        if isinstance(type, str):
            type = self.node_type(type)
        elif not isinstance(type, NodeType):
            raise ValueError(f"Invalid node type: {type}")
        elif type.schema != self:
            raise ValueError(f"Node type from different schema used ({type.name})")
        return type.create_checked(attrs, content, marks)

    def text(self, text: str, marks: list[Mark] | None = None) -> TextNode:
        type = self.nodes[cast(Nodes, "text")]
        return TextNode(
            type, cast(Attrs, type.default_attrs), text, Mark.set_from(marks)
        )

    def mark(
        self,
        type: str | MarkType,
        attrs: Attrs | None = None,
    ) -> Mark:
        if isinstance(type, str):
            type = self.marks[cast(Marks, type)]
        return type.create(attrs)

    def node_from_json(self, json_data: JSONDict) -> Node | TextNode:
        return Node.from_json(self, json_data)

    def mark_from_json(
        self,
        json_data: JSONDict,
    ) -> Mark:
        return Mark.from_json(self, json_data)

    def node_type(self, name: str) -> NodeType:
        found = self.nodes.get(cast(Nodes, name))
        if not found:
            raise ValueError(f"Unknown node type: {name}")
        return found


def gather_marks(schema: Schema[Any, Any], marks: list[str]) -> list[MarkType]:
    found = []
    for name in marks:
        mark = schema.marks.get(name)
        ok = mark
        if mark:
            found.append(mark)
        else:
            for mark in schema.marks.values():
                if name == "_" or (
                    mark.spec.get("group") and name in mark.spec["group"].split(" ")
                ):
                    ok = mark
                    found.append(mark)
        if not ok:
            raise SyntaxError(f"unknow mark type: '{mark}'")
    return found
