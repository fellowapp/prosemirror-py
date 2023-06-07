import html
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple, Union, cast

from . import Fragment, Mark, Node, Schema

HTMLNode = Union["Element", str]


class DocumentFragment:
    def __init__(self, children: List[HTMLNode]):
        self.children = children

    def __str__(self):
        return "".join([str(c) for c in self.children])


class Element(DocumentFragment):
    self_closing_elements = frozenset(
        [
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
        ]
    )

    def __init__(self, name: str, attrs: Dict[str, str], children: List[HTMLNode]):
        self.name = name
        self.attrs = attrs
        super().__init__(children)

    def __str__(self):
        attrs_str = " ".join([f'{k}="{html.escape(v)}"' for k, v in self.attrs.items()])
        open_tag_str = " ".join([s for s in [self.name, attrs_str] if s])
        if self.name in self.self_closing_elements:
            assert not self.children, "self-closing elements should not have children"
            return f"<{open_tag_str}>"
        children_str = "".join([str(c) for c in self.children])
        return f"<{open_tag_str}>{children_str}</{self.name}>"


HTMLOutputSpec = Union[str, Sequence[Any], Element]


class DOMSerializer:
    def __init__(
        self,
        nodes: Dict[str, Callable[[Node], HTMLOutputSpec]],
        marks: Dict[str, Callable[[Mark, bool], HTMLOutputSpec]],
    ):
        self.nodes = nodes
        self.marks = marks

    def serialize_fragment(
        self, fragment: Fragment, target: Optional[Element] = None
    ) -> DocumentFragment:
        tgt: DocumentFragment = target or DocumentFragment(children=[])

        top = tgt
        active: Optional[List[DocumentFragment]] = None

        def each(node: Node, *_):
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
                        not next.eq(active[keep])
                        or next.type.spec.get("spanning") is False
                    ):
                        break
                    keep += 2
                    rendered += 1
                while keep < len(active):
                    top = active.pop()
                    active.pop()
                while rendered < len(node.marks):
                    add = node.marks[rendered]
                    rendered += 1
                    mark_dom = self.serialize_mark(add, node.is_inline)
                    if mark_dom:
                        active.append(add)  # type: ignore
                        active.append(top)
                        top.children.append(mark_dom[0])
                        top = cast(DocumentFragment, mark_dom[1] or mark_dom[0])
            top.children.append(self.serialize_node_inner(node))

        fragment.for_each(each)
        return tgt

    def serialize_node_inner(self, node: Node) -> HTMLNode:
        dom, content_dom = type(self).render_spec(self.nodes[node.type.name](node))
        if content_dom:
            if node.is_leaf:
                raise Exception("Content hole not allowed in a leaf node spec")
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
        self, mark: Mark, inline: bool
    ) -> Optional[Tuple[HTMLNode, Optional[Element]]]:
        to_dom = self.marks.get(mark.type.name)
        if to_dom:
            return type(self).render_spec(to_dom(mark, inline))
        return None

    @classmethod
    def render_spec(
        cls, structure: HTMLOutputSpec
    ) -> Tuple[HTMLNode, Optional[Element]]:
        if isinstance(structure, str):
            return html.escape(structure), None
        if isinstance(structure, Element):
            return structure, None
        tag_name = structure[0]
        if " " in tag_name[1:]:
            raise NotImplementedError("XML namespaces are not supported")
        content_dom = None
        dom = Element(name=tag_name, attrs={}, children=[])
        attrs = structure[1] if len(structure) > 1 else None
        start = 1
        if isinstance(attrs, dict):
            start = 2
            for name, value in attrs.items():
                if value is None:
                    continue
                if " " in name[1:]:
                    raise NotImplementedError("XML namespaces are not supported")
                dom.attrs[name] = value
        for i in range(start, len(structure)):
            child = structure[i]
            if child == 0:
                if i < len(structure) - 1 or i > start:
                    raise Exception(
                        "Content hole must be the only child of its parent node"
                    )
                return dom, dom
            inner, inner_content = cls.render_spec(child)
            dom.children.append(inner)
            if inner_content:
                if content_dom:
                    raise Exception("Multiple content holes")
                content_dom = inner_content
        return dom, content_dom

    @classmethod
    def from_schema(cls, schema: Schema) -> "DOMSerializer":
        return cls(cls.nodes_from_schema(schema), cls.marks_from_schema(schema))

    @classmethod
    def nodes_from_schema(cls, schema: Schema):
        result = gather_to_dom(schema.nodes)
        if "text" not in result:
            result["text"] = lambda node: node.text
        return result

    @classmethod
    def marks_from_schema(cls, schema: Schema):
        return gather_to_dom(schema.marks)


def gather_to_dom(obj: Dict[str, Any]):
    result = {}
    for name in obj:
        to_dom = obj[name].spec.get("toDOM")
        if to_dom:
            result[name] = to_dom
    return result
