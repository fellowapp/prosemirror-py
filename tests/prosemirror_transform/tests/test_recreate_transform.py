from __future__ import annotations

from prosemirror.model import Node, Schema
from prosemirror.test_builder import out
from prosemirror.transform import recreate_transform

doc = out["doc"]
blockquote = out["blockquote"]
h1 = out["h1"]
h2 = out["h2"]
p = out["p"]
em = out["em"]
strong = out["strong"]


def assert_steps(start_doc: Node, end_doc: Node, steps: list[dict], options=None):
    tr = recreate_transform(start_doc, end_doc, options)
    assert [step.to_json() for step in tr.steps] == steps


def test_simple_add_em():
    assert_steps(
        doc(p("Before textitalicAfter text")),
        doc(p("Before text", em("italic"), "After text")),
        [
            {
                "stepType": "replace",
                "from": 12,
                "to": 18,
                "slice": {
                    "content": [
                            {
                                "type": "text",
                                "marks": [{"type": "em", "attrs": {}}],
                                "text": "italic",
                            },
                    ],
                },
            },
        ],
        {"complex_steps": False},
    )


def test_simple_remove_strong():
    assert_steps(
        doc(p("Before text", strong("bold"), "After text")),
        doc(p("Before textboldAfter text")),
        [
            {
                "stepType": "replace",
                "from": 12,
                "to": 16,
                "slice": {
                    "content": [{"type": "text", "text": "bold"}],
                },
            },
        ],
        {"complex_steps": False},
    )


def test_simple_wrap_blockquote():
    assert_steps(
        doc(p("A quoted sentence")),
        doc(blockquote(p("A quoted sentence"))),
        [
            {
                "stepType": "replace",
                "from": 0,
                "to": 19,
                "slice": {
                    "content": [
                        {
                            "type": "blockquote",
                            "content": [
                                {
                                    "type": "paragraph",
                                    "content": [
                                        {"type": "text", "text": "A quoted sentence"},
                                    ],
                                },
                            ],
                        },
                    ],
                },
            },
        ],
        {"complex_steps": False},
    )


def test_simple_unwrap_blockquote():
    assert_steps(
        doc(blockquote(p("A quoted sentence"))),
        doc(p("A quoted sentence")),
        [
            {
                "stepType": "replace",
                "from": 0,
                "to": 21,
                "slice": {
                    "content": [
                        {
                            "type": "paragraph",
                            "content": [
                                {"type": "text", "text": "A quoted sentence"},
                            ],
                        },
                    ],
                },
            },
        ],
        {"complex_steps": False},
    )


def test_simple_change_headline():
    assert_steps(
        doc(h1("A title")),
        doc(h2("A title")),
        [
            {
                "stepType": "replace",
                "from": 0,
                "to": 9,
                "slice": {
                    "content": [
                        {
                            "type": "heading",
                            "attrs": {"level": 2},
                            "content": [{"type": "text", "text": "A title"}],
                        },
                    ],
                },
            },
        ],
        {"complex_steps": False},
    )


def test_complex_add_em():
    assert_steps(
        doc(p("Before textitalicAfter text")),
        doc(p("Before text", em("italic"), "After text")),
        [
            {
                "stepType": "addMark",
                "mark": {"type": "em", "attrs": {}},
                "from": 12,
                "to": 18,
            },
        ],
    )


def test_complex_remove_strong():
    assert_steps(
        doc(p("Before text", strong("bold"), "After text")),
        doc(p("Before textboldAfter text")),
        [
            {
                "stepType": "removeMark",
                "mark": {"type": "strong", "attrs": {}},
                "from": 12,
                "to": 16,
            },
        ],
    )


def test_complex_add_em_and_strong():
    assert_steps(
        doc(p("Before textitalic/boldAfter text")),
        doc(p("Before text", strong(em("italic/bold")), "After text")),
        [
            {
                "stepType": "addMark",
                "mark": {"type": "em", "attrs": {}},
                "from": 12,
                "to": 23,
            },
            {
                "stepType": "addMark",
                "mark": {"type": "strong", "attrs": {}},
                "from": 12,
                "to": 23,
            },
        ],
    )


def test_complex_replace_em_with_strong():
    assert_steps(
        doc(p("Before text", em("styled"), "After text")),
        doc(p("Before text", strong("styled"), "After text")),
        [
            {
                "stepType": "removeMark",
                "mark": {"type": "em", "attrs": {}},
                "from": 12,
                "to": 18,
            },
            {
                "stepType": "addMark",
                "mark": {"type": "strong", "attrs": {}},
                "from": 12,
                "to": 18,
            },
        ],
    )


def test_complex_replace_em_with_strong_different_parts():
    assert_steps(
        doc(p("Before text", em("styledAfter text"))),
        doc(p(strong("Before textstyled"), "After text")),
        [
            {
                "stepType": "addMark",
                "mark": {"type": "strong", "attrs": {}},
                "from": 1,
                "to": 12,
            },
            {
                "stepType": "removeMark",
                "mark": {"type": "em", "attrs": {}},
                "from": 12,
                "to": 18,
            },
            {
                "stepType": "addMark",
                "mark": {"type": "strong", "attrs": {}},
                "from": 12,
                "to": 18,
            },
            {
                "stepType": "removeMark",
                "mark": {"type": "em", "attrs": {}},
                "from": 18,
                "to": 28,
            },
        ],
    )


def test_complex_wrap_blockquote():
    assert_steps(
        doc(p("A quoted sentence")),
        doc(blockquote(p("A quoted sentence"))),
        [
            {
                "stepType": "replace",
                "from": 0,
                "to": 19,
                "slice": {
                    "content": [
                        {
                            "type": "blockquote",
                            "content": [
                                {
                                    "type": "paragraph",
                                    "content": [
                                        {"type": "text", "text": "A quoted sentence"},
                                    ],
                                },
                            ],
                        },
                    ],
                },
            },
        ],
    )


def test_complex_unwrap_blockquote():
    assert_steps(
        doc(blockquote(p("A quoted sentence"))),
        doc(p("A quoted sentence")),
        [
            {
                "stepType": "replace",
                "from": 0,
                "to": 21,
                "slice": {
                    "content": [
                        {
                            "type": "paragraph",
                            "content": [
                                {"type": "text", "text": "A quoted sentence"},
                            ],
                        },
                    ],
                },
            },
        ],
    )


def test_complex_change_headline_type():
    assert_steps(
        doc(h1("A title")),
        doc(h2("A title")),
        [
            {
                "stepType": "replaceAround",
                "from": 0,
                "to": 9,
                "gapFrom": 1,
                "gapTo": 8,
                "insert": 1,
                "slice": {"content": [{"type": "heading", "attrs": {"level": 2}}]},
                "structure": True,
            },
        ],
        {"complex_steps": True},
    )


def test_text_diff_single_node():
    assert_steps(
        doc(blockquote(p("The start text"))),
        doc(blockquote(p("The end text"))),
        [
            {
                "stepType": "replace",
                "from": 6,
                "to": 11,
                "slice": {"content": [{"type": "text", "text": "end"}]},
            },
        ],
    )


def test_text_diff_multiple_nodes():
    assert_steps(
        doc(blockquote(p("The start text"), p("The second text"))),
        doc(blockquote(p("The end text"), p("The second sentence"))),
        [
            {
                "stepType": "replace",
                "from": 6,
                "to": 11,
                "slice": {"content": [{"type": "text", "text": "end"}]},
            },
            {
                "stepType": "replace",
                "from": 27,
                "to": 27,
                "slice": {"content": [{"type": "text", "text": "sen"}]},
            },
            {
                "stepType": "replace",
                "from": 32,
                "to": 34,
                "slice": {"content": [{"type": "text", "text": "nce"}]},
            },
        ],
    )


def test_text_diff_multiple_nodes_word_diffs():
    assert_steps(
        doc(blockquote(p("The start text"), p("The second text"))),
        doc(blockquote(p("The end text"), p("The second sentence"))),
        [
            {
                "stepType": "replace",
                "from": 6,
                "to": 11,
                "slice": {"content": [{"type": "text", "text": "end"}]},
            },
            {
                "stepType": "replace",
                "from": 27,
                "to": 31,
                "slice": {"content": [{"type": "text", "text": "sentence"}]},
            },
        ],
        {"word_diffs": True},
    )


def test_text_diff_same_node_multiple_changes():
    assert_steps(
        doc(blockquote(p("The cat is barking at the house"))),
        doc(blockquote(p("The dog is meauwing in the ship"))),
        [
            {
                "stepType": "replace",
                "from": 6,
                "to": 9,
                "slice": {"content": [{"type": "text", "text": "dog"}]},
            },
            {
                "stepType": "replace",
                "from": 13,
                "to": 14,
                "slice": {"content": [{"type": "text", "text": "me"}]},
            },
            {
                "stepType": "replace",
                "from": 16,
                "to": 18,
                "slice": {"content": [{"type": "text", "text": "uw"}]},
            },
            {
                "stepType": "replace",
                "from": 22,
                "to": 24,
                "slice": {"content": [{"type": "text", "text": "in"}]},
            },
            {
                "stepType": "replace",
                "from": 29,
                "to": 29,
                "slice": {"content": [{"type": "text", "text": "s"}]},
            },
            {
                "stepType": "replace",
                "from": 31,
                "to": 35,
                "slice": {"content": [{"type": "text", "text": "ip"}]},
            },
        ],
    )


def test_attrs_update():
    schema = _widget_schema()
    start = _doc(schema, _node("widget_a", {"first": "", "aSecond": ""}))
    end = _doc(schema, _node("widget_a", {"first": "first", "aSecond": ""}))
    assert_steps(
        start,
        end,
        [
            {
                "stepType": "replaceAround",
                "from": 0,
                "to": 2,
                "gapFrom": 1,
                "gapTo": 1,
                "insert": 1,
                "slice": {
                    "content": [
                        {"type": "widget_a", "attrs": {"first": "first", "aSecond": ""}},
                    ],
                },
                "structure": True,
            },
        ],
    )


def test_attrs_update_all():
    schema = _widget_schema()
    start = _doc(schema, _node("widget_a", {"first": "", "aSecond": ""}))
    end = _doc(schema, _node("widget_a", {"first": "first", "aSecond": "second"}))
    assert_steps(
        start,
        end,
        [
            {
                "stepType": "replaceAround",
                "from": 0,
                "to": 2,
                "gapFrom": 1,
                "gapTo": 1,
                "insert": 1,
                "slice": {
                    "content": [
                        {
                            "type": "widget_a",
                            "attrs": {"first": "first", "aSecond": "second"},
                        },
                    ],
                },
                "structure": True,
            },
        ],
    )


def test_attrs_update_with_position_change():
    schema = _widget_schema()
    start = _doc(
        schema,
        _p("Lorem Ipsum"),
        _p("Dolor sit"),
        _node("widget_a", {"first": "", "aSecond": ""}),
    )
    end = _doc(
        schema,
        _p("Dolor sit"),
        _node("widget_a", {"first": "first", "aSecond": "second"}),
    )
    assert_steps(
        start,
        end,
        [
            {"stepType": "replace", "from": 0, "to": 13},
            {
                "stepType": "replaceAround",
                "from": 11,
                "to": 13,
                "gapFrom": 12,
                "gapTo": 12,
                "insert": 1,
                "slice": {
                    "content": [
                        {
                            "type": "widget_a",
                            "attrs": {"first": "first", "aSecond": "second"},
                        },
                    ],
                },
                "structure": True,
            },
        ],
    )


def test_attrs_update_type_change():
    schema = _widget_schema()
    start = _doc(
        schema,
        _node("widget_a", {"first": "a-first", "aSecond": "a-second"}),
    )
    end = _doc(
        schema,
        _node(
            "widget_b",
            {"first": "b-first", "bSecond": "b-second", "third": "b-third"},
        ),
    )
    assert_steps(
        start,
        end,
        [
            {
                "stepType": "replaceAround",
                "from": 0,
                "to": 2,
                "gapFrom": 1,
                "gapTo": 1,
                "insert": 1,
                "slice": {
                    "content": [
                        {
                            "type": "widget_b",
                            "attrs": {
                                "first": "b-first",
                                "bSecond": "b-second",
                                "third": "b-third",
                            },
                        },
                    ],
                },
                "structure": True,
            },
        ],
    )


def test_attrs_update_type_change_with_position_change():
    schema = _widget_schema()
    start = _doc(
        schema,
        _p("Lorem Ipsum"),
        _p("Dolor sit"),
        _node("widget_a", {"first": "a-first", "aSecond": "a-second"}),
    )
    end = _doc(
        schema,
        _p("Dolor sit"),
        _node(
            "widget_b",
            {"first": "b-first", "bSecond": "b-second", "third": "b-third"},
        ),
    )
    assert_steps(
        start,
        end,
        [
            {"stepType": "replace", "from": 0, "to": 13},
            {
                "stepType": "replaceAround",
                "from": 11,
                "to": 13,
                "gapFrom": 12,
                "gapTo": 12,
                "insert": 1,
                "slice": {
                    "content": [
                        {
                            "type": "widget_b",
                            "attrs": {
                                "first": "b-first",
                                "bSecond": "b-second",
                                "third": "b-third",
                            },
                        },
                    ],
                },
                "structure": True,
            },
        ],
    )


def _widget_schema() -> Schema:
    return Schema({
        "nodes": {
            "doc": {"content": "(block)+"},
            "text": {"group": "inline"},
            "paragraph": {"content": "text*", "group": "block"},
            "widget_a": {
                "content": "text*",
                "group": "block",
                "marks": "",
                "code": True,
                "defining": True,
                "attrs": {"first": {"default": ""}, "aSecond": {"default": ""}},
            },
            "widget_b": {
                "content": "text*",
                "group": "block",
                "marks": "",
                "code": True,
                "defining": True,
                "attrs": {
                    "first": {"default": ""},
                    "bSecond": {"default": ""},
                    "third": {"default": ""},
                },
            },
        },
        "marks": {},
    })


def _doc(schema: Schema, *content):
    return Node.from_json(schema, {"type": "doc", "content": list(content)})


def _node(type_name: str, attrs: dict, *content):
    data = {"type": type_name, "attrs": attrs}
    if content:
        data["content"] = list(content)
    return data


def _p(text: str):
    return {"type": "paragraph", "content": [_t(text)]}


def _t(text: str):
    return {"type": "text", "text": text}
