from prosemirror.model import Schema


def const(obj):
    return lambda *_, **__: obj


spec = {
    "nodes": {
        "doc": {"content": "block+"},
        "paragraph": {
            "content": "inline*",
            "group": "block",
            "parseDOM": [{"tag": "p"}],
            "toDOM": const(["p", 0]),
        },
        "blockquote": {
            "content": "block+",
            "group": "block",
            "defining": True,
            "parseDOM": [{"tag": "blockquote"}],
            "toDOM": const(["blockquote", 0]),
        },
        "horizontal_rule": {
            "group": "block",
            "parseDOM": [{"tag": "hr"}],
            "toDOM": const(["hr"]),
        },
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
            "toDOM": lambda node: [f"h{node.attrs['level']}", 0],
        },
        "code_block": {
            "content": "text*",
            "marks": "",
            "group": "block",
            "code": True,
            "defining": True,
            "parseDOM": [{"tag": "pre", "preserveWhitespace": "full"}],
            "toDOM": const(["pre", ["code", 0]]),
        },
        "text": {"group": "inline"},
        "image": {
            "inline": True,
            "attrs": {"src": {}, "alt": {"default": None}, "title": {"default": None}},
            "group": "inline",
            "draggable": True,
            "parseDOM": [{"tag": "img[src]"}],
            "toDOM": lambda node: [
                "img",
                {
                    "src": node.attrs["src"],
                    "alt": node.attrs["alt"],
                    "title": node.attrs["title"],
                },
            ],
        },
        "hard_break": {
            "inline": True,
            "group": "inline",
            "selectable": False,
            "parseDOM": [{"tag": "br"}],
            "toDOM": const(["br"]),
        },
        "ordered_list": {
            "attrs": {"order": {"default": 1}},
            "parseDOM": [{"tag": "ol"}],
            "content": "list_item+",
            "group": "block",
            "toDOM": const(["ol", 0]),
        },
        "bullet_list": {
            "parseDOM": [{"tag": "ul"}],
            "content": "list_item+",
            "group": "block",
            "toDOM": const(["ul", 0]),
        },
        "list_item": {
            "parseDOM": [{"tag": "li"}],
            "defining": True,
            "content": "paragraph block*",
            "toDOM": const(["li", 0]),
        },
    },
    "marks": {
        "link": {
            "attrs": {"href": {}, "title": {"default": None}},
            "inclusive": False,
            "parseDOM": [{"tag": "a[href]"}],
            "toDOM": lambda node, _: [
                "a",
                {"href": node.attrs["href"], "title": node.attrs["title"]},
                0,
            ],
        },
        "em": {
            "parseDOM": [{"tag": "i"}, {"tag": "em"}, {"style": "font-style=italic"}],
            "toDOM": const(["em", 0]),
        },
        "strong": {
            "parseDOM": [{"tag": "strong"}, {"tag": "b"}, {"style": "font-weight"}],
            "toDOM": const(["strong", 0]),
        },
        "code": {"parseDOM": [{"tag": "code"}], "toDOM": const(["code", 0])},
    },
}


schema = Schema(spec)
