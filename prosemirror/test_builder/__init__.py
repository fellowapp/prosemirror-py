# type: ignore

from prosemirror.model import Node, Schema
from prosemirror.schema.basic import schema as _schema
from prosemirror.schema.list import add_list_nodes

from .build import builders

test_schema: Schema[str, str] = Schema(
    {
        "nodes": add_list_nodes(_schema.spec["nodes"], "paragraph block*", "block"),
        "marks": _schema.spec["marks"],
    }
)

out = builders(
    test_schema,
    {
        "doc": {"nodeType": "doc"},
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
