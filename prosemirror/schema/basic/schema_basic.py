from prosemirror.model import Schema

p_dom = ["p", 0]
blockquote_dom = ["blockquote", 0]
hr_dom = ["hr"]
pre_dom = ["pre", ["code", 0]]
br_dom = ["br"]

nodes = {
    "doc": {"content": "block+"},
    "paragraph": {
        "content": "inline*",
        "group": "block",
        "parseDOM": [{"tag": "p"}],
        "toDOM": lambda _: p_dom,
    },
    "blockquote": {
        "content": "block+",
        "group": "block",
        "defining": True,
        "parseDOM": [{"tag": "blockquote"}],
        "toDOM": lambda _: blockquote_dom,
    },
    "horizontal_rule": {
        "group": "block",
        "parseDOM": [{"tag": "hr"}],
        "toDOM": lambda _: hr_dom,
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
        "toDOM": lambda _: pre_dom,
    },
    "text": {"group": "inline"},
    "image": {
        "inline": True,
        "attrs": {"src": {}, "alt": {"default": None}, "title": {"default": None}},
        "group": "inline",
        "draggable": True,
        "parseDOM": [{"tag": "img", "getAttrs": lambda dom_: {"src": dom_.get('src'), "title": dom_.get('title')} }],
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
        "toDOM": lambda _: br_dom,
    },
}

em_dom = ["em", 0]
strong_dom = ["strong", 0]
code_dom = ["code", 0]

marks = {
    "link": {
        "attrs": {"href": {}, "title": {"default": None}},
        "inclusive": False,
        "parseDOM": [{"tag": "a", "getAttrs": lambda d: {'href': d.get('href')}}],
        "toDOM": lambda node, _: [
            "a",
            {"href": node.attrs["href"], "title": node.attrs["title"]},
            0,
        ],
    },
    "em": {
        "parseDOM": [{"tag": "i"}, {"tag": "em"}, {"style": "font-style=italic"}],
        "toDOM": lambda _, __: em_dom,
    },
    "strong": {
        "parseDOM": [{"tag": "strong"}, {"tag": "b"}, {"style": "font-weight"}],
        "toDOM": lambda _, __: strong_dom,
    },
    "code": {"parseDOM": [{"tag": "code"}], "toDOM": lambda _, __: code_dom},
}


schema = Schema({"nodes": nodes, "marks": marks})
