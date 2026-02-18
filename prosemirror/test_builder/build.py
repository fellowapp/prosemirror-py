# type: ignore

import contextlib
import re
from collections.abc import Callable
from typing import Any

from prosemirror.model import MarkType, Node, NodeType, Schema
from prosemirror.utils import Attrs, JSONDict

NO_TAG = Node.tag = {}


def flatten(
    schema: Schema[Any, Any],
    children: list[Node | JSONDict | str],
    f: Callable[[Node], Node],
) -> tuple[list[Node], dict[str, int]]:
    result, pos, tag = [], 0, NO_TAG

    for child in children:
        if isinstance(child, str):
            at = 0
            out = ""
            for m in re.finditer(r"<(\w+)>", child):
                out += child[at : m.start()]
                pos += m.start() - at
                at = m.start() + len(m[0])
                if tag == NO_TAG:
                    tag = {}
                tag[m[1]] = pos
            out += child[at:]
            pos += len(child) - at
            if out:
                result.append(f(schema.text(out)))
        else:
            # Merge tag info from child (Node with .tag or dict with "tag" key)
            child_tag = (
                getattr(child, "tag", NO_TAG)
                if isinstance(child, Node)
                else child.get("tag", NO_TAG)
                if isinstance(child, dict)
                else NO_TAG
            )
            if child_tag and child_tag != NO_TAG:
                if tag == NO_TAG:
                    tag = {}
                is_flat = getattr(child, "flat", None) or (
                    isinstance(child, dict) and "flat" in child
                )
                is_text = getattr(child, "is_text", False)
                for id in child_tag:
                    tag[id] = child_tag[id] + (0 if is_flat or is_text else 1) + pos
            # Process flat children or single node
            flat = getattr(child, "flat", None) or (
                child.get("flat") if isinstance(child, dict) else None
            )
            if flat:
                for item in flat:
                    node = f(item)
                    pos += node.node_size
                    result.append(node)
            else:
                node = f(child)
                pos += node.node_size
                result.append(node)
    return result, tag


def _take_attrs(
    attrs: Attrs | None, args: tuple[Any, ...]
) -> tuple[Attrs | None, tuple[Any, ...]]:
    if not args:
        return attrs, args
    a0 = args[0]
    if a0 and (
        isinstance(a0, str | Node)
        or getattr(a0, "flat", None)
        or (isinstance(a0, dict) and "flat" in a0)
    ):
        return attrs, args
    args = args[1:]
    if not attrs:
        return a0, args
    if not a0:
        return attrs, args
    result = {**attrs, **a0}
    return result, args


def block(type: NodeType, attrs: Attrs | None = None):
    def result(*args):
        my_attrs, args = _take_attrs(attrs, args)
        nodes, tag = flatten(type.schema, args, lambda x: x)
        node = type.create(my_attrs, nodes)
        if tag != NO_TAG:
            node.tag = tag
        return node

    if type.is_leaf:
        with contextlib.suppress(ValueError):
            result.flat = [type.create(attrs)]

    return result


def mark(type: MarkType, attrs: Attrs):
    def result(*args):
        my_attrs, args = _take_attrs(attrs, args)
        mark = type.create(my_attrs)

        def f(n):
            new_marks = mark.add_to_set(n.marks)
            return n.mark(new_marks) if len(new_marks) > len(n.marks) else n

        nodes, tag = flatten(type.schema, args, f)
        return {"flat": nodes, "tag": tag}

    return result


def builders(schema: Schema[Any, Any], names):
    result = {"schema": schema}
    for name in schema.nodes:
        result[name] = block(schema.nodes[name], {})
    for name in schema.marks:
        result[name] = mark(schema.marks[name], {})

    if names:
        for name in names:
            value = names[name]
            type_name = value.get("nodeType") or value.get("markType") or name
            type = schema.nodes.get(type_name)
            if type:
                result[name] = block(type, value)
            else:
                type = schema.marks.get(type_name)
                if type:
                    result[name] = mark(type, value)
    return result
