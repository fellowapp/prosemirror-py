from prosemirror_model import Schema

spec = {
    "nodes": {
        "doc": {"content": "block+"},
        "paragraph": {
            "content": "inline*",
            "group": "block",
            "parseDOM": [{"tag": "p"}],
        },
        "blockquote": {
            "content": "block+",
            "group": "block",
            "defining": True,
            "parseDOM": [{"tag": "blockquote"}],
        },
        "horizontal_rule": {"group": "block", "parseDOM": [{"tag": "hr"}]},
        "heading": {
            "attrs": {"level": {"default": 1}},
            "content": "inline*",
            "group": "block",
            "defining": True,
            "parseDOM": [
                {"tag": "h1", "attrs": {"level": 1}},
                {"tag": "h2", "attrs": {"level": 2}},
                {"tag": "h3", "attrs": {"level": 3}},
                {"tag": "h4", "attrs": {"level": 4}},
                {"tag": "h5", "attrs": {"level": 5}},
                {"tag": "h6", "attrs": {"level": 6}},
            ],
        },
        "code_block": {
            "content": "text*",
            "marks": "",
            "group": "block",
            "code": True,
            "defining": True,
            "parseDOM": [{"tag": "pre", "preserveWhitespace": "full"}],
        },
        "text": {"group": "inline"},
        "image": {
            "inline": True,
            "attrs": {"src": {}, "alt": {"default": None}, "title": {"default": None}},
            "group": "inline",
            "draggable": True,
            "parseDOM": [{"tag": "img[src]"}],
        },
        "hard_break": {
            "inline": True,
            "group": "inline",
            "selectable": False,
            "parseDOM": [{"tag": "br"}],
        },
        "ordered_list": {
            "attrs": {"order": {"default": 1}},
            "parseDOM": [{"tag": "ol"}],
            "content": "list_item+",
            "group": "block",
        },
        "bullet_list": {
            "parseDOM": [{"tag": "ul"}],
            "content": "list_item+",
            "group": "block",
        },
        "list_item": {
            "parseDOM": [{"tag": "li"}],
            "defining": True,
            "content": "paragraph block*",
        },
    },
    "marks": {
        "link": {
            "attrs": {"href": {}, "title": {"default": None}},
            "inclusive": False,
            "parseDOM": [{"tag": "a[href]"}],
        },
        "em": {
            "parseDOM": [{"tag": "i"}, {"tag": "em"}, {"style": "font-style=italic"}]
        },
        "strong": {
            "parseDOM": [{"tag": "strong"}, {"tag": "b"}, {"style": "font-weight"}]
        },
        "code": {"parseDOM": [{"tag": "code"}]},
    },
}


schema = Schema(spec)
