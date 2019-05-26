import pytest
from prosemirror_test_builder import schema, out, builders
from prosemirror_transform import Transform
from prosemirror_model import Schema


doc = out["doc"]
blockquote = out["blockquote"]
pre = out["pre"]
h1 = out["h1"]
h2 = out["h2"]
p = out["p"]
li = out["li"]
ul = out["ul"]
ol = out["ol"]
em = out["em"]
strong = out["strong"]
code = out["code"]
a = out["a"]
img = out["img"]
br = out["br"]
hr = out["hr"]


@pytest.mark.parametrize(
    "doc,mark,expect",
    [
        (
            doc(p("hello <a>there<b>!")),
            schema.mark("strong"),
            doc(p("hello ", strong("there"), "!")),
        ),
        (
            doc(p("hello ", strong("<a>there"), "!<b>")),
            schema.mark("strong"),
            doc(p("hello ", strong("there!"))),
        ),
        (
            doc(p("one <a>two ", em("three<b> four"))),
            schema.mark("strong"),
            doc(p("one ", strong("two ", em("three")), em(" four"))),
        ),
        (
            doc(
                p("before"), blockquote(p("the variable is called <a>i<b>")), p("after")
            ),
            schema.mark("code"),
            doc(
                p("before"),
                blockquote(p("the variable is called ", code("i"))),
                p("after"),
            ),
        ),
        (
            doc(p("hi <a>this"), blockquote(p("is")), p("a docu<b>ment"), p("!")),
            schema.mark("em"),
            doc(
                p("hi ", em("this")),
                blockquote(p(em("is"))),
                p(em("a docu"), "ment"),
                p("!"),
            ),
        ),
    ],
)
def test_add_mark(doc, mark, expect, test_transform):
    test_transform(Transform(doc).add_mark(doc.tag["a"], doc.tag["b"], mark), expect)


def test_does_not_remove_non_excluded_marks_of_the_same_type():
    schema = Schema(
        {
            "nodes": {"doc": {"content": "text*"}, "text": {}},
            "marks": {"comment": {"excludes": "", "attrs": {"id": {}}}},
        }
    )
    tr = Transform(
        schema.node(
            "doc", None, schema.text("hi", [schema.mark("comment", {"id": 10})])
        )
    )
    tr.add_mark(0, 2, schema.mark("comment", {"id": 20}))
    assert len(tr.doc.first_child.marks) == 2


def test_can_remote_multiple_excluded_marks():
    schema = Schema(
        {
            "nodes": {"doc": {"content": "text*"}, "text": {}},
            "marks": {"big": {"excludes": "small1 small2"}, "small1": {}, "small2": {}},
        }
    )
    tr = Transform(
        schema.node("doc", None, schema.text("hi", [schema.mark("small1"), schema.mark("small2")]))
    )
    assert len(tr.doc.first_child.marks) == 2
    tr.add_mark(0, 2, schema.mark("big"))
    assert len(tr.doc.first_child.marks) == 1
