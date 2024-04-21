import html
from collections.abc import Callable, Mapping, Sequence
from typing import (
    Any,
    Union,
    cast,
)

from .fragment import Fragment
from .mark import Mark
from .node import Node
from .schema import MarkType, NodeType, Schema

HTMLNode = Union["Element", "str"]


class DocumentFragment:
    def __init__(self, children: list[HTMLNode]) -> None:
        self.children = children

    def __str__(self) -> str:
        return "".join([str(c) for c in self.children])


SELF_CLOSING_ELEMENTS = frozenset({
    "area",
    "base",
    "br",
    "col",
    "embed",
    "hr",
    "img",
    "input",
    "keygen",
    "link",
    "meta",
    "param",
    "source",
    "track",
    "wbr",
})


class Element(DocumentFragment):
    def __init__(
        self,
        name: str,
        attrs: dict[str, str],
        children: list[HTMLNode],
    ) -> None:
        self.name = name
        self.attrs = attrs
        super().__init__(children)

    def __str__(self) -> str:
        attrs_str = " ".join([f'{k}="{html.escape(v)}"' for k, v in self.attrs.items()])
        open_tag_str = " ".join([s for s in [self.name, attrs_str] if s])
        if self.name in SELF_CLOSING_ELEMENTS:
            assert not self.children, "self-closing elements should not have children"
            return f"<{open_tag_str}>"
        children_str = "".join([str(c) for c in self.children])
        return f"<{open_tag_str}>{children_str}</{self.name}>"


HTMLOutputSpec = str | Sequence[Any] | Element


class DOMSerializer:
    def __init__(
        self,
        nodes: dict[str, Callable[[Node], HTMLOutputSpec]],
        marks: dict[str, Callable[[Mark, bool], HTMLOutputSpec]],
    ) -> None:
        self.nodes = nodes
        self.marks = marks

    def serialize_fragment(
        self,
        fragment: Fragment,
        target: Element | DocumentFragment | None = None,
    ) -> DocumentFragment:
        tgt: DocumentFragment = target or DocumentFragment(children=[])

        top = tgt
        active: list[tuple[Mark, DocumentFragment]] | None = None

        def each(node: Node, offset: int, index: int) -> None:
            nonlocal top, active

            if active or node.marks:
                if not active:
                    active = []
                keep = 0
                rendered = 0
                while keep < len(active) and rendered < len(node.marks):
                    next = node.marks[rendered]
                    if not self.marks.get(next.type.name):
                        rendered += 1
                        continue
                    if (
                        not next.eq(active[keep][0])
                        or next.type.spec.get("spanning") is False
                    ):
                        break
                    keep += 1
                    rendered += 1
                while keep < len(active):
                    top = active.pop()[1]
                while rendered < len(node.marks):
                    add = node.marks[rendered]
                    rendered += 1
                    mark_dom = self.serialize_mark(add, node.is_inline)
                    if mark_dom:
                        active.append((add, top))
                        top.children.append(mark_dom[0])
                        top = cast(DocumentFragment, mark_dom[1] or mark_dom[0])
            top.children.append(self.serialize_node_inner(node))

        fragment.for_each(each)
        return tgt

    def serialize_node_inner(self, node: Node) -> HTMLNode:
        dom, content_dom = type(self).render_spec(self.nodes[node.type.name](node))
        if content_dom:
            if node.is_leaf:
                msg = "Content hole not allowed in a leaf node spec"
                raise Exception(msg)
            self.serialize_fragment(node.content, content_dom)
        return dom

    def serialize_node(self, node: Node) -> HTMLNode:
        dom = self.serialize_node_inner(node)
        for mark in reversed(node.marks):
            wrap = self.serialize_mark(mark, node.is_inline)
            if wrap:
                inner, content_dom = wrap
                cast(DocumentFragment, content_dom or inner).children.append(dom)
                dom = inner
        return dom

    def serialize_mark(
        self,
        mark: Mark,
        inline: bool,
    ) -> tuple[HTMLNode, Element | None] | None:
        to_dom = self.marks.get(mark.type.name)
        if to_dom:
            return type(self).render_spec(to_dom(mark, inline))
        return None

    @classmethod
    def render_spec(cls, structure: HTMLOutputSpec) -> tuple[HTMLNode, Element | None]:
        if isinstance(structure, str):
            return html.escape(structure), None
        if isinstance(structure, Element):
            return structure, None
        tag_name = structure[0]
        if " " in tag_name[1:]:
            msg = "XML namespaces are not supported"
            raise NotImplementedError(msg)
        content_dom: Element | None = None
        dom = Element(name=tag_name, attrs={}, children=[])
        attrs = structure[1] if len(structure) > 1 else None
        start = 1
        if isinstance(attrs, dict):
            start = 2
            for name, value in attrs.items():
                if value is None:
                    continue
                if " " in name[1:]:
                    msg = "XML namespaces are not supported"
                    raise NotImplementedError(msg)
                dom.attrs[name] = value
        for i in range(start, len(structure)):
            child = structure[i]
            if child == 0:
                if i < len(structure) - 1 or i > start:
                    msg = "Content hole must be the only child of its parent node"
                    raise Exception(msg)
                return dom, dom
            inner, inner_content = cls.render_spec(child)
            dom.children.append(inner)
            if inner_content:
                if content_dom:
                    msg = "Multiple content holes"
                    raise Exception(msg)
                content_dom = inner_content
        return dom, content_dom

    @classmethod
    def from_schema(cls, schema: Schema[Any, Any]) -> "DOMSerializer":
        return cls(cls.nodes_from_schema(schema), cls.marks_from_schema(schema))

    @classmethod
    def nodes_from_schema(
        cls,
        schema: Schema[str, Any],
    ) -> dict[str, Callable[["Node"], HTMLOutputSpec]]:
        result = gather_to_dom(schema.nodes)
        if "text" not in result:
            result["text"] = lambda node: node.text
        return result

    @classmethod
    def marks_from_schema(
        cls,
        schema: Schema[Any, Any],
    ) -> dict[str, Callable[["Mark", bool], HTMLOutputSpec]]:
        return gather_to_dom(schema.marks)


def gather_to_dom(
    obj: Mapping[str, NodeType | MarkType],
) -> dict[str, Callable[..., Any]]:
    result = {}
    for name in obj:
        to_dom = obj[name].spec.get("toDOM")
        if to_dom:
            result[name] = to_dom
    return result
