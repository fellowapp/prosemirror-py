import re
from prosemirror_model import Node

NO_TAG = Node.tag = {}


def flatten(schema, children, f):
    result, pos, tag = [], 0, NO_TAG

    for child in children:
        if hasattr(child, "tag") and child.tag != NO_TAG:
            if tag == NO_TAG:
                tag = {}
            for id in child.tag:
                tag[id] = child.tag[id] + (0 if child.is_text else 1) + pos
        if isinstance(child, dict) and "tag" in child and child["tag"] != Node.tag:
            if tag == NO_TAG:
                tag = {}
            for id in child["tag"]:
                tag[id] = child["tag"][id] + (0 if "flat" in child else 1) + pos
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
        elif isinstance(child, dict) and "flat" in child:
            for item in child["flat"]:
                node = f(item)
                pos += node.node_size
                result.append(node)
        elif getattr(child, "flat", 0):
            for item in child.flat:
                node = f(item)
                pos += node.node_size
                result.append(node)
        else:
            node = f(child)
            pos += node.node_size
            result.append(node)
    return {"nodes": result, "tag": tag}


def id(x):
    return x


def block(type, attrs):
    def result(*args):
        my_attrs = attrs
        if (
            args
            and args[0]
            and not isinstance(args[0], (str, Node))
            and not getattr(args[0], "flat", None)
            and "flat" not in args[0]
        ):
            my_attrs.update(args[0])
            args = args[1:]
        flatten_res = flatten(type.schema, args, id)
        nodes = flatten_res["nodes"]
        tag = flatten_res["tag"]
        node = type.create(my_attrs, nodes)
        if tag != NO_TAG:
            node.tag = tag
        return node

    if type.is_leaf:
        try:
            result.flat = [type.create(attrs)]
        except ValueError:
            pass

    return result


def mark(type, attrs):
    def result(*args):
        my_attrs = attrs.copy()
        if (
            args
            and args[0]
            and not isinstance(args[0], (str, Node))
            and not getattr(args[0], "flat", None)
            and "flat" not in args[0]
        ):
            my_attrs.update(args[0])
            args = args[1:]
        mark = type.create(my_attrs)

        def f(n):
            return (
                n if mark.type.is_in_set(n.marks) else n.mark(mark.add_to_set(n.marks))
            )

        flatten_res = flatten(type.schema, args, f)
        return {"flat": flatten_res["nodes"], "tag": flatten_res["tag"]}

    return result


def builders(schema, names):
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
