# type: ignore

from typing import Any

from prosemirror.model import Node, Schema
from prosemirror.schema.basic import schema as _schema
from prosemirror.schema.list import add_list_nodes

from .build import builders

nodes = add_list_nodes(_schema.spec["nodes"], "paragraph block*", "block")

nodes.update({
    "doc": {
        "content": "block+",
        "attrs": {"meta": {"default": None}},
    }
})

test_schema: Schema[Any, Any] = Schema({
    "nodes": nodes,
    "marks": _schema.spec["marks"],
})

out = builders(
    test_schema,
    {
        "doc": {"nodeType": "doc"},
        "docMetaOne": {"nodeType": "doc", "meta": 1},
        "docMetaTwo": {"nodeType": "doc", "meta": 2},
        "p": {"nodeType": "paragraph"},
        "pre": {"nodeType": "code_block"},
        "h1": {"nodeType": "heading", "level": 1},
        "h2": {"nodeType": "heading", "level": 2},
        "h3": {"nodeType": "heading", "level": 3},
        "li": {"nodeType": "list_item"},
        "ul": {"nodeType": "bullet_list"},
        "ol": {"nodeType": "ordered_list"},
        "br": {"nodeType": "hard_break"},
        "img": {"nodeType": "image", "src": "img.png"},
        "hr": {"nodeType": "horizontal_rule"},
        "a": {"markType": "link", "href": "foo"},
    },
)


def eq(a: Node, b: Node) -> bool:
    return a.eq(b)
