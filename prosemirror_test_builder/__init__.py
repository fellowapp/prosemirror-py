from prosemirror_schema_basic import schema
from prosemirror_schema_list import add_list_nodes
from prosemirror_model import Schema

from .build import builders


test_schema = Schema(
    {
        "nodes": add_list_nodes(schema.spec["nodes"], "paragraph block*", "block"),
        "marks": schema.spec["marks"],
    }
)

out = builders(
    test_schema,
    {
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


def eq(a, b):
    return a.eq(b)
