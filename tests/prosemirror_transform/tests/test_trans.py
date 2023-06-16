import pytest

from prosemirror.model import Fragment, Schema, Slice
from prosemirror.test_builder import builders, out
from prosemirror.test_builder import test_schema as schema
from prosemirror.transform import Transform, TransformError, find_wrapping, lift_target

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
            doc(p("this is a ", a("<a>link<b>"))),
            schema.mark("link", {"href": "bar"}),
            doc(p("this is a ", a({"href": "bar"}, "link"))),
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
        schema.node(
            "doc",
            None,
            schema.text("hi", [schema.mark("small1"), schema.mark("small2")]),
        )
    )
    assert len(tr.doc.first_child.marks) == 2
    tr.add_mark(0, 2, schema.mark("big"))
    assert len(tr.doc.first_child.marks) == 1


@pytest.mark.parametrize(
    "doc,mark,expect",
    [
        (
            doc(p(em("hello <a>world<b>!"))),
            schema.mark("em"),
            doc(p(em("hello "), "world", em("!"))),
        ),
        (
            doc(p(em("hello"), " <a>world<b>!")),
            schema.mark("em"),
            doc(p(em("hello"), " <a>world<b>!")),
        ),
        (
            doc(p(em("one ", strong("<a>two<b>"), " three"))),
            schema.mark("strong"),
            doc(p(em("one two three"))),
        ),
        (
            doc(p("<a>hello ", a("link<b>"))),
            schema.mark("link", {"href": "foo"}),
            doc(p("hello link")),
        ),
        (
            doc(p("<a>hello ", a("link<b>"))),
            schema.mark("link", {"href": "foo"}),
            doc(p("hello link")),
        ),
        (
            doc(p("hello ", a("link"))),
            schema.mark("link", {"href": "bar"}),
            doc(p("hello ", a("link"))),
        ),
        (
            doc(
                blockquote(p(em("much <a>em")), p(em("here too"))),
                p("between", em("...")),
                p(em("end<b>")),
            ),
            schema.mark("em"),
            doc(
                blockquote(p(em("much "), "em"), p("here too")),
                p("between..."),
                p("end"),
            ),
        ),
        (
            doc(p("<a>hello, ", em("this is ", strong("much"), " ", a("markup<b>")))),
            None,
            doc(p("<a>hello, this is much markup")),
        ),
    ],
)
def test_remove_mark(doc, mark, expect, test_transform):
    test_transform(
        Transform(doc).remove_mark(doc.tag.get("a", 0), doc.tag.get("b", 0), mark),
        expect,
    )


def test_remove_more_than_one_mark_of_same_type_from_block():
    schema = Schema(
        {
            "nodes": {
                "doc": {"content": "text*"},
                "text": {},
            },
            "marks": {
                "comment": {"excludes": "", "attrs": {"id": {}}},
            },
        }
    )
    tr = Transform(
        schema.node(
            "doc",
            None,
            schema.text(
                "hi",
                [schema.mark("comment", {"id": 1}), schema.mark("comment", {"id": 2})],
            ),
        )
    )
    assert len(tr.doc.first_child.marks) == 2
    tr.remove_mark(0, 2, schema.marks["comment"])
    assert not tr.doc.first_child.marks


@pytest.mark.parametrize(
    "doc,nodes,expect",
    [
        (
            doc(p("hello<a>there")),
            schema.node("hard_break"),
            doc(p("hello", br, "<a>there")),
        ),
        (
            doc(p("one"), "<a>", p("two<2>")),
            schema.node("paragraph"),
            doc(p("one"), p(), "<a>", p("two<2>")),
        ),
        (
            doc(p("one"), "<a>", p("two<2>")),
            [
                schema.node("paragraph", None, [schema.text("hi")]),
                schema.node("horizontal_rule"),
            ],
            doc(p("one"), p("hi"), hr, "<a>", p("two<2>")),
        ),
        (
            doc(blockquote(p("he<before>y"), "<a>"), p("after<after>")),
            schema.node("paragraph"),
            doc(blockquote(p("he<before>y"), p()), p("after<after>")),
        ),
        (
            doc(blockquote("<a>", p("he<1>y")), p("after<2>")),
            schema.node("paragraph"),
            doc(blockquote(p(), "<a>", p("he<1>y")), p("after<2>")),
        ),
        (
            doc(p("foo<a>bar")),
            schema.nodes["list_item"].create_and_fill(),
            doc(p("foo"), ol(li(p())), p("bar")),
        ),
    ],
)
def test_insert(doc, nodes, expect, test_transform):
    test_transform(Transform(doc).insert(doc.tag.get("a", 0), nodes), expect)


@pytest.mark.parametrize(
    "doc,expect",
    [
        (
            doc(p("<1>one"), "<a>", p("tw<2>o"), "<b>", p("<3>three")),
            doc(p("<1>one"), "<a><2>", p("<3>three")),
        ),
        (doc(blockquote("<a>", p("hi"), "<b>"), p("x")), doc(blockquote(p()), p("x"))),
        (
            doc(blockquote(p("a"), "<a>", p("b"), "<b>"), p("c<1>")),
            doc(blockquote(p("a")), p("c<1>")),
        ),
        (doc(pre("fo<a>o"), p("b<b>ar", img)), doc(pre("fo"), p("ar", img))),
        (doc(pre("fo<a>o"), p(em("b<b>ar"))), doc(pre("fo"), p(em("ar")))),
    ],
)
def test_delete(doc, expect, test_transform):
    tr = Transform(doc).delete(doc.tag.get("a"), doc.tag.get("b"))
    test_transform(tr, expect)


@pytest.mark.parametrize(
    "doc,expect",
    [
        (
            doc(
                blockquote(p("<before>a")), "<a>", blockquote(p("b")), p("after<after>")
            ),
            doc(blockquote(p("<before>a"), "<a>", p("b")), p("after<after>")),
        ),
        (doc(h1("foo"), "<a>", p("bar")), doc(h1("foobar"))),
        (
            doc(
                blockquote(
                    blockquote(p("a"), p("b<before>")),
                    "<a>",
                    blockquote(p("c"), p("d<after>")),
                )
            ),
            doc(
                blockquote(
                    blockquote(p("a"), p("b<before>"), "<a>", p("c"), p("d<after>"))
                )
            ),
        ),
        (
            doc(ol(li(p("one")), li(p("two"))), "<a>", ol(li(p("three")))),
            doc(ol(li(p("one")), li(p("two")), "<a>", li(p("three")))),
        ),
        (
            doc(ol(li(p("one")), li(p("two")), "<a>", li(p("three")))),
            doc(ol(li(p("one")), li(p("two"), "<a>", p("three")))),
        ),
        (doc(p("foo"), "<a>", p("bar")), doc(p("foo<a>bar"))),
    ],
)
def test_join(doc, expect, test_transform):
    tr = Transform(doc).join(doc.tag.get("a"))
    test_transform(tr, expect)


@pytest.mark.parametrize(
    "doc,expect,args",
    [
        (
            doc(p("<1>a"), p("<2>foo<a>bar<3>"), p("<4>b")),
            doc(p("<1>a"), p("<2>foo"), p("<a>bar<3>"), p("<4>b")),
            [],
        ),
        (
            doc(blockquote(blockquote(p("foo<a>bar"))), p("after<1>")),
            doc(
                blockquote(blockquote(p("foo")), blockquote(p("<a>bar"))), p("after<1>")
            ),
            [2],
        ),
        (
            doc(blockquote(blockquote(p("foo<a>bar"))), p("after<1>")),
            doc(
                blockquote(blockquote(p("foo"))),
                blockquote(blockquote(p("<a>bar"))),
                p("after<1>"),
            ),
            [3],
        ),
        (doc(blockquote(p("hi<a>"))), doc(blockquote(p("hi"), p("<a>"))), []),
        (doc(blockquote(p("<a>hi"))), doc(blockquote(p(), p("<a>hi"))), []),
        (
            doc(ol(li(p("one<1>")), li(p("two<a>three")), li(p("four<2>")))),
            doc(ol(li(p("one<1>")), li(p("two"), p("<a>three")), li(p("four<2>")))),
            [],
        ),
        (
            doc(ol(li(p("one<1>")), li(p("two<a>three")), li(p("four<2>")))),
            doc(ol(li(p("one<1>")), li(p("two")), li(p("<a>three")), li(p("four<2>")))),
            [2],
        ),
        (
            doc(h1("hell<a>o!")),
            doc(h1("hell"), p("<a>o!")),
            [None, [{"type": schema.nodes["paragraph"]}]],
        ),
        (doc(blockquote("<a>", p("x"))), "fail", []),
        (doc(blockquote(p("x"), "<a>")), "fail", []),
    ],
)
def test_split(doc, expect, args, test_transform):
    if expect == "fail":
        with pytest.raises(TransformError):
            Transform(doc).split(doc.tag.get("a"), *args)
    else:
        tr = Transform(doc).split(doc.tag.get("a"), *args)
        test_transform(tr, expect)


@pytest.mark.parametrize(
    "doc,expect",
    [
        (
            doc(blockquote(p("<before>one"), p("<a>two"), p("<after>three"))),
            doc(
                blockquote(p("<before>one")), p("<a>two"), blockquote(p("<after>three"))
            ),
        ),
        (
            doc(blockquote(p("<a>two"), p("<after>three"))),
            doc(p("<a>two"), blockquote(p("<after>three"))),
        ),
        (
            doc(blockquote(p("<before>one"), p("<a>two"))),
            doc(blockquote(p("<before>one")), p("<a>two")),
        ),
        (doc(blockquote(p("<a>t<in>wo"))), doc(p("<a>t<in>wo"))),
        (
            doc(blockquote(blockquote(p("on<a>e"), p("tw<b>o")), p("three"))),
            doc(blockquote(p("on<a>e"), p("tw<b>o"), p("three"))),
        ),
        (
            doc(p("start"), blockquote(blockquote(p("a"), p("<a>b")), p("<b>c"))),
            doc(p("start"), blockquote(p("a"), p("<a>b")), p("<b>c")),
        ),
        (
            doc(
                blockquote(
                    blockquote(
                        p("<1>one"),
                        p("<a>two"),
                        p("<3>three"),
                        p("<b>four"),
                        p("<5>five"),
                    )
                )
            ),
            doc(
                blockquote(
                    blockquote(p("<1>one")),
                    p("<a>two"),
                    p("<3>three"),
                    p("<b>four"),
                    blockquote(p("<5>five")),
                )
            ),
        ),
        (
            doc(ul(li(p("one")), li(p("two<a>")), li(p("three")))),
            doc(ul(li(p("one"))), p("two<a>"), ul(li(p("three")))),
        ),
        (
            doc(ul(li(p("a")), li(p("b<a>")), "<1>")),
            doc(ul(li(p("a"))), p("b<a>"), "<1>"),
        ),
    ],
)
def test_lift(doc, expect, test_transform):
    range = doc.resolve(doc.tag.get("a")).block_range(
        doc.resolve(doc.tag.get("b") or doc.tag.get("a"))
    )
    tr = Transform(doc).lift(range, lift_target(range))
    test_transform(tr, expect)


@pytest.mark.parametrize(
    "doc,expect,type,attrs",
    [
        (
            doc(p("one"), p("<a>two"), p("three")),
            doc(p("one"), blockquote(p("<a>two")), p("three")),
            "blockquote",
            None,
        ),
        (
            doc(p("one<1>"), p("<a>two"), p("<b>three"), p("four<4>")),
            doc(p("one<1>"), blockquote(p("<a>two"), p("three")), p("four<4>")),
            "blockquote",
            None,
        ),
        (
            doc(p("<a>one"), p("<b>two")),
            doc(ol(li(p("<a>one"), p("<b>two")))),
            "ordered_list",
            None,
        ),
        (
            doc(
                ol(
                    li(p("<1>one")),
                    li(p("..."), p("<a>two"), p("<b>three")),
                    li(p("<4>four")),
                )
            ),
            doc(
                ol(
                    li(p("<1>one")),
                    li(p("..."), ol(li(p("<a>two"), p("<b>three")))),
                    li(p("<4>four")),
                )
            ),
            "ordered_list",
            None,
        ),
        (
            doc(blockquote(p("<1>one"), p("two<a>")), p("three<b>")),
            doc(blockquote(blockquote(p("<1>one"), p("two<a>")), p("three<b>"))),
            "blockquote",
            None,
        ),
    ],
)
def test_wrap(doc, expect, type, attrs, test_transform):
    range = doc.resolve(doc.tag.get("a")).block_range(
        doc.resolve(doc.tag.get("b") or doc.tag.get("a"))
    )
    tr = Transform(doc).wrap(range, find_wrapping(range, schema.nodes[type], attrs))
    test_transform(tr, expect)


@pytest.mark.parametrize(
    "doc,expect,node_type,attrs",
    [
        (doc(p("am<a> i")), doc(h2("am i")), "heading", {"level": 2}),
        (
            doc(h1("<a>hello"), p("there"), p("<b>you"), p("end")),
            doc(pre("hello"), pre("there"), pre("you"), p("end")),
            "code_block",
            {},
        ),
        (
            doc(blockquote(p("one<a>"), p("two<b>"))),
            doc(blockquote(h1("one<a>"), h1("two<b>"))),
            "heading",
            {"level": 1},
        ),
        (doc(p("hello<a> ", em("world"))), doc(pre("hello world")), "code_block", {}),
        (
            doc(p("hello<a> ", em("world"))),
            doc(h1("hello<a> ", em("world"))),
            "heading",
            {"level": 1},
        ),
        (
            doc(p("<a>hello", img), p("okay"), ul(li(p("foo<b>")))),
            doc(pre("<a>hello"), pre("okay"), ul(li(p("foo<b>")))),
            "code_block",
            None,
        ),
    ],
)
def test_set_block_type(doc, expect, node_type, attrs, test_transform):
    tr = Transform(doc).set_block_type(
        doc.tag.get("a"),
        doc.tag.get("b") or doc.tag.get("a"),
        schema.nodes[node_type],
        attrs,
    )
    test_transform(tr, expect)


def test_set_block_type_works_after_another_step(test_transform):
    d = doc(p("f<x>oob<y>ar"), p("baz<a>"))
    tr = Transform(d).delete(d.tag.get("x"), d.tag.get("y"))
    pos = tr.mapping.map(d.tag.get("a"))
    tr.set_block_type(pos, pos, schema.nodes["heading"], {"level": 1})
    test_transform(tr, doc(p("f<x><y>ar"), h1("baz<a>")))


@pytest.mark.parametrize(
    "doc,expect,type,attrs",
    [
        (doc("<a>", p("foo")), doc(h1("foo")), "heading", {"level": 1}),
        (
            doc(p("foo<a>", img, "bar")),
            doc(p("foo", img({"src": "bar", "alt": "y"}), "bar")),
            "image",
            {"src": "bar", "alt": "y"},
        ),
    ],
)
def test_set_node_markup(doc, expect, type, attrs, test_transform):
    tr = Transform(doc).set_node_markup(doc.tag.get("a"), schema.nodes[type], attrs)
    test_transform(tr, expect)


@pytest.mark.parametrize(
    "doc,expect,attr,value",
    [
        (doc("<a>", h1("foo")), doc(h2("foo")), "level", 2),
        (
            doc(p("<a>", img({"src": "foo", "alt": None, "title": None}))),
            doc(p(img({"src": "bar"}))),
            "src",
            "bar",
        ),
    ],
)
def test_set_node_attribute(doc, expect, attr, value, test_transform):
    tr = Transform(doc).set_node_attribute(doc.tag.get("a"), attr, value)
    test_transform(tr, expect)


@pytest.mark.parametrize(
    "doc,source,expect",
    [
        (doc(p("hell<a>o y<b>ou")), None, doc(p("hell<a><b>ou"))),
        (doc(p("hell<a>o"), p("y<b>ou")), None, doc(p("hell<a><b>ou"))),
        (
            doc(blockquote(p("ab<a>c")), "<b>", p("def")),
            None,
            doc(blockquote(p("ab<a>")), "<b>", p("def")),
        ),
        (
            doc(p("abc"), "<a>", blockquote(p("d<b>ef"))),
            None,
            doc(p("abc"), "<a>", blockquote(p("<b>ef"))),
        ),
        (doc(p("hell<a>o y<b>ou")), doc(p("<a>i k<b>")), doc(p("hell<a>i k<b>ou"))),
        (doc(p("hell<a><b>o")), doc(p("<a>i k<b>")), doc(p("helli k<a><b>o"))),
        (
            doc(p("hello<a>you")),
            doc("<a>", p("there"), "<b>"),
            doc(p("hello"), p("there"), p("<a>you")),
        ),
        (doc(h1("he<a>llo"), p("arg<b>!")), doc(p("1<a>2<b>3")), doc(h1("he2!"))),
        (
            doc(ol(li(p("one<a>")), li(p("three")))),
            doc(ol(li(p("<a>half")), li(p("two")), "<b>")),
            doc(ol(li(p("onehalf")), li(p("two")), li(p("three")))),
        ),
        (doc(p("a<a>"), p("b"), p("<b>c")), None, doc(p("a<a><b>c"))),
        (doc(h1("wo<a>ah"), blockquote(p("ah<b>ha"))), None, doc(h1("wo<a><b>ha"))),
        (
            doc(blockquote(p("foo<a>bar")), p("middle"), h1("quux<b>baz")),
            None,
            doc(blockquote(p("foo<a><b>baz"))),
        ),
        (
            doc(
                blockquote(
                    ul(li(p("a")), li(p("b<a>")), li(p("c")), li(p("<b>d")), li(p("e")))
                )
            ),
            None,
            doc(blockquote(ul(li(p("a")), li(p("b<a><b>d")), li(p("e"))))),
        ),
        (
            doc(p("he<before>llo<a> w<after>orld")),
            doc(p("<a> big<b>")),
            doc(p("he<before>llo big w<after>orld")),
        ),
        (
            doc(p("one<a>two")),
            doc(p("a<a>"), p("hello"), p("<b>b")),
            doc(p("one"), p("hello"), p("<a>two")),
        ),
        (
            doc(p("one<a>"), p("t<inside>wo"), p("<b>three<end>")),
            doc(p("a<a>"), p("TWO"), p("<b>b")),
            doc(p("one<a>"), p("TWO"), p("<inside>three<end>")),
        ),
        (
            doc(p("foo ", em("bar<a>baz"), "<b> quux")),
            doc(p("foo ", em("xy<a>zzy"), " foo<b>")),
            doc(p("foo ", em("barzzy"), " foo quux")),
        ),
        (
            doc(p("foo<a>b<inside>b<b>bar")),
            doc(p("<a>", br, "<b>")),
            doc(p("foo", br, "<inside>bar")),
        ),
        (doc(h1("hell<a>o"), p("by<b>e")), None, doc(h1("helle"))),
        (
            doc(h1("hell<a>o"), "<b>"),
            doc(ol(li(p("on<a>e")), li(p("tw<b>o")))),
            doc(h1("helle"), ol(li(p("tw")))),
        ),
        (
            doc(h1("hell<a>o"), p("yo<b>u")),
            doc(ol(li(p("on<a>e")), li(p("tw<b>o")))),
            doc(h1("helle"), ol(li(p("twu")))),
        ),
        (
            doc(p("a"), p("<a>"), p("b")),
            doc(p("x<a>y<b>z")),
            doc(p("a"), p("y<a>"), p("b")),
        ),
        (
            doc(p("one<a>"), p("two"), p("three")),
            doc(p("outside<a>"), blockquote(p("inside<b>"))),
            doc(p("one"), blockquote(p("inside")), p("two"), p("three")),
        ),
        (
            doc(blockquote(p("b<a>c"), p("d<b>e"), p("f"))),
            doc(blockquote(p("x<a>y")), p("after"), "<b>"),
            doc(blockquote(p("b<a>y")), p("after"), blockquote(p("<b>e"), p("f"))),
        ),
        (
            doc(blockquote(p("b<a>c"), p("d<b>e"), p("f"))),
            doc(blockquote(p("x<a>y")), p("z<b>")),
            doc(blockquote(p("b<a>y")), p("z<b>e"), blockquote(p("f"))),
        ),
        (
            doc(
                blockquote(
                    blockquote(p("one"), p("tw<a>o"), p("t<b>hree<3>"), p("four<4>"))
                )
            ),
            doc(ol(li(p("hello<a>world")), li(p("bye"))), p("ne<b>xt")),
            doc(
                blockquote(
                    blockquote(
                        p("one"),
                        p("tw<a>world"),
                        ol(li(p("bye"))),
                        p("ne<b>hree<3>"),
                        p("four<4>"),
                    )
                )
            ),
        ),
        (
            doc(p("x"), "<a>"),
            doc("<a>", ul(li(p("a")), li("<b>", p("b")))),
            doc(p("x"), ul(li(p("a")), li(p())), "<a>"),
        ),
        (doc("<a>", h1("hi"), p("you"), "<b>"), None, doc(p())),
        (
            doc(blockquote("<a>", p("hi")), p("b<b>x")),
            doc(p("<a>hi<b>")),
            doc(blockquote(p("hix"))),
        ),
        (
            doc(p("x<a>hi"), blockquote(p("yy"), "<b>"), p("c")),
            doc(p("<a>hi<b>")),
            doc(p("xhi"), p("c")),
        ),
        (doc(p("<a>x")), doc(blockquote(p("hi"), "<a>"), p("b<b>")), doc(p(), p("bx"))),
        (
            doc(p("<a>x")),
            doc(p("b<a>"), blockquote("<b>", p("hi"))),
            doc(p(), blockquote(p()), p("x")),
        ),
        (p("<a>x"), Slice(Fragment.from_([blockquote(), hr()]), 0, 0), p("x")),
        (
            doc(p("foo"), "<a>", p("bar<b>")),
            ol(li(p("<a>a")), li(p("b<b>"))),
            doc(p("foo"), p("a"), ol(li(p("b")))),
        ),
        (
            doc(ul(li(p("ab<a>cd")), li(p("ef<b>gh")))),
            doc(ul(li(p("ABCD")), li(p("EFGH")))).slice(5, 13, True),
            doc(ul(li(p("abCD")), li(p("EFgh")))),
        ),
        (
            doc(ul(li(p("foo")), "<a>", li(p("bar")))),
            ul(li(p("a<a>bc")), li(p("de<b>f"))),
            doc(ul(li(p("foo")), li(p("bc")), li(p("de")), li(p("bar")))),
        ),
        (
            doc("<a>", p(), "<b>"),
            doc(blockquote(blockquote(blockquote(p("hi"))))).slice(3, 6, True),
            doc(p("hi")),
        ),
    ],
)
def test_replace(doc, source, expect, test_transform):
    slice = None
    if source is None:
        slice = Slice.empty
    elif isinstance(source, Slice):
        slice = source
    else:
        slice = source.slice(source.tag.get("a"), source.tag.get("b"))
    tr = Transform(doc).replace(
        doc.tag.get("a"), doc.tag.get("b") or doc.tag.get("a"), slice
    )
    test_transform(tr, expect)


def test_doesnt_fail_when_moving_text_would_solve_unsatisfied_content_constraint():
    s = Schema(
        {
            "nodes": {
                **schema.spec["nodes"],
                "title": {"content": "text*"},
                "doc": {"content": "title? block*"},
            },
        }
    )
    tr = Transform(s.node("doc", None, s.node("title", None, s.text("hi"))))
    tr.replace(
        1,
        1,
        s.node(
            "bullet_list",
            None,
            [
                s.node("list_item", None, s.node("paragraph", None, s.text("one"))),
                s.node("list_item", None, s.node("paragraph", None, s.text("two"))),
            ],
        ).slice(2, 12),
    )
    assert tr.steps


def test_pasting_half_open_slice_with_title_and_code_block_into_empty_title():
    s = Schema(
        {
            "nodes": {
                **schema.spec["nodes"],
                "title": {"content": "text*"},
                "doc": {"content": "title? block*"},
            },
        }
    )
    tr = Transform(s.node("doc", None, [s.node("title", None, [])]))
    tr.replace(
        1,
        1,
        s.node(
            "doc",
            None,
            [
                s.node("title", None, s.text("title")),
                s.node("code_block", None, s.text("two")),
            ],
        ).slice(1),
    )
    assert tr.steps


def test_pasting_half_open_slice_with_heading_and_code_block_into_empty_title():
    s = Schema(
        {
            "nodes": {
                **schema.spec["nodes"],
                "title": {"content": "text*"},
                "doc": {"content": "title? block*"},
            },
        }
    )
    tr = Transform(s.node("doc", None, [s.node("title")]))
    tr.replace(
        1,
        1,
        s.node(
            "doc",
            None,
            [
                s.node("heading", {"level": 1}, s.text("heading")),
                s.node("code_block", None, s.text("code")),
            ],
        ).slice(1),
    )
    assert tr.steps


def test_replacing_in_nodes_with_fixed_content():
    s = Schema(
        {
            "nodes": {
                "doc": {"content": "block+"},
                "a": {"content": "inline*"},
                "b": {"content": "inline*"},
                "block": {"content": "a b"},
                "text": {"group": "inline"},
            }
        }
    )

    doc = s.node(
        "doc",
        None,
        [
            s.node(
                "block",
                None,
                [s.node("a", None, [s.text("aa")]), s.node("b", None, [s.text("bb")])],
            ),
        ],
    )
    from_ = 3
    to = doc.content.size
    assert Transform(doc).replace(from_, to, doc.slice(from_, to)).doc.eq(doc)


class TestTopLevelMarkReplace:
    ms = Schema(
        {
            "nodes": {
                **schema.spec["nodes"],
                "doc": {**schema.spec["nodes"]["doc"], "marks": "_"},  # type: ignore
            },
            "marks": schema.spec["marks"],
        }
    )

    def test_preserves_mark_on_block_nodes(self):
        ms = self.ms
        tr = Transform(
            ms.node(
                "doc",
                None,
                [
                    ms.node("paragraph", None, [ms.text("hey")], [ms.mark("em")]),
                    ms.node("paragraph", None, [ms.text("ok")], [ms.mark("strong")]),
                ],
            )
        )
        tr.replace(2, 7, tr.doc.slice(2, 7))
        assert tr.doc.eq(tr.before)

    def test_preserves_marks_on_open_slice_block_nodes(self):
        ms = self.ms
        tr = Transform(
            ms.node("doc", None, [ms.node("paragraph", None, [ms.text("a")])])
        )
        tr.replace(
            3,
            3,
            ms.node(
                "doc",
                None,
                [ms.node("paragraph", None, [ms.text("b")], [ms.mark("em")])],
            ).slice(1, 3),
        )
        assert tr.doc.child_count == 2
        assert len(tr.doc.last_child.marks) == 1


class TestEnforcingHeadingAndBody:
    nodes_sepc = schema.spec["nodes"].copy()
    nodes_sepc.update(
        {
            "doc": {**nodes_sepc["doc"], "content": "heading body"},  # type: ignore
            "body": {"content": "block+"},
        }
    )
    hb_schema = Schema({"nodes": nodes_sepc, "marks": schema.spec["marks"]})
    hb = builders(
        hb_schema,
        {
            "p": {"nodeType": "paragraph"},
            "b": {"nodeType": "body"},
            "h": {"nodeType": "heading", "level": 1},
        },
    )

    def test_can_unwrap_a_paragraph_when_replacing_into_a_strict_schema(self):
        hb = self.hb
        tr = Transform(hb["doc"](hb["h"]("Head"), hb["b"](hb["p"]("Content"))))
        tr.replace(0, tr.doc.content.size, tr.doc.slice(7, 16))
        assert tr.doc.eq(hb["doc"](hb["h"]("Content"), hb["b"](hb["p"]())))

    def test_can_unwrap_a_body_after_a_placed_node(self):
        hb = self.hb
        doc = hb["doc"]
        h = hb["h"]
        b = hb["b"]
        p = hb["p"]
        tr = Transform(hb["doc"](hb["h"]("Head"), hb["b"](hb["p"]("Content"))))
        tr.replace(7, 7, tr.doc.slice(0, tr.doc.content.size))
        assert tr.doc.eq(doc(h("Head"), b(h("Head"), p("Content"), p("Content"))))

    def test_can_wrap_a_paragraph_in_a_body_even_when_its_not_the_first_node(self):
        hb = self.hb
        doc = hb["doc"]
        h = hb["h"]
        b = hb["b"]
        p = hb["p"]
        tr = Transform(doc(h("Head"), b(p("One"), p("Two"))))
        tr.replace(0, tr.doc.content.size, tr.doc.slice(8, 16))
        assert tr.doc.eq(doc(h("One"), b(p("Two"))))

    def test_can_split_a_fragment_and_place_its_children_in_different_parents(self):
        hb = self.hb
        doc = hb["doc"]
        h = hb["h"]
        b = hb["b"]
        p = hb["p"]
        tr = Transform(doc(h("Head"), b(h("One"), p("Two"))))
        tr.replace(0, tr.doc.content.size, tr.doc.slice(7, 17))
        assert tr.doc.eq(doc(h("One"), b(p("Two"))))

    def test_will_insert_filler_nodes_before_a_node_when_necessary(self):
        hb = self.hb
        doc = hb["doc"]
        h = hb["h"]
        b = hb["b"]
        p = hb["p"]
        tr = Transform(doc(h("Head"), b(p("One"))))
        tr.replace(0, tr.doc.content.size, tr.doc.slice(6, tr.doc.content.size))
        assert tr.doc.eq(doc(h(), b(p("One"))))


def test_keeps_isolating_nodes_together():
    s = Schema(
        {
            "nodes": {
                **schema.spec["nodes"],
                "iso": {
                    "group": "block",
                    "content": "block+",
                    "isolating": True,
                },
            },
        }
    )
    doc = s.node("doc", None, [s.node("paragraph", None, [s.text("one")])])
    iso = Fragment.from_(
        s.node("iso", None, [s.node("paragraph", None, [s.text("two")])])
    )
    assert (
        Transform(doc)
        .replace(2, 3, Slice(iso, 2, 0))
        .doc.eq(
            s.node(
                "doc",
                None,
                [
                    s.node("paragraph", None, [s.text("o")]),
                    s.node("iso", None, [s.node("paragraph", None, [s.text("two")])]),
                    s.node("paragraph", None, [s.text("e")]),
                ],
            )
        )
    )
    assert (
        Transform(doc)
        .replace(2, 3, Slice(iso, 2, 2))
        .doc.eq(s.node("doc", None, [s.node("paragraph", None, [s.text("otwoe")])]))
    )


@pytest.mark.parametrize(
    "doc,source,expect",
    [
        (doc(p("foo<a>b<b>ar")), p("<a>xx<b>"), doc(p("foo<a>xx<b>ar"))),
        (doc(p("<a>")), doc(h1("<a>text<b>")), doc(h1("text"))),
        (doc(p("<a>abc<b>")), doc(h1("<a>text<b>")), doc(h1("text"))),
        (doc(p("<a>")), doc(ul(li(p("<a>foobar<b>")))), doc(ul(li(p("foobar"))))),
        (
            doc(ul(li(p("<a>")), li(p("b")))),
            doc(h1("<a>h<b>")),
            doc(ul(li(p("h<a>")), li(p("b")))),
        ),
        (
            doc(p("a"), ul(li(p("<a>b")), li(p("c"), blockquote(p("d<b>")))), p("e")),
            doc(h1("<a>x<b>")),
            doc(p("a"), h1("x"), p("e")),
        ),
        (
            doc(p("<a>foo")),
            doc(ul(li(p("<a>one")), li(p("two<b>")))),
            doc(ul(li(p("one")), li(p("twofoo")))),
        ),
        (
            doc(blockquote(p("<a>"))),
            doc(blockquote(p("<a>one<b>"))),
            doc(blockquote(p("one"))),
        ),
        (
            doc("<a>", p("abc"), "<b>"),
            doc(ul(li("<a>")), p("def"), "<b>"),
            doc(ul(li(p())), p("def")),
        ),
    ],
)
def test_replace_range(doc, source, expect, test_transform):
    slice = None
    if source is None:
        slice = Slice.empty
    elif isinstance(source, Slice):
        slice = source
    else:
        slice = source.slice(source.tag.get("a"), source.tag.get("b"), True)
    tr = Transform(doc).replace_range(
        doc.tag.get("a"), doc.tag.get("b") or doc.tag.get("a"), slice
    )
    test_transform(tr, expect)


@pytest.mark.parametrize(
    "doc,node,expect",
    [
        (doc(p("fo<a>o")), img(), doc(p("fo", img(), "<a>o"))),
        (doc(p("<a>fo<b>o")), img(), doc(p("<a>", img(), "o"))),
        (doc("<a>", blockquote(p("a")), "<b>"), img(), doc(p(img()))),
        (doc("<a>", blockquote(p("a")), "<b>"), hr(), doc(hr())),
        (doc(p("foo<a>bar")), hr(), doc(p("foo"), hr(), p("bar"))),
        (doc(blockquote(p("<a>"))), hr(), doc(blockquote(hr()))),
        (doc(h1("foo<a>")), hr(), doc(h1("foo"), hr())),
        (
            doc(p("a"), blockquote(p("<a>b"))),
            hr(),
            doc(p("a"), blockquote(hr(), p("b"))),
        ),
    ],
)
def test_replace_range_with(doc, node, expect, test_transform):
    tr = Transform(doc).replace_range_with(
        doc.tag.get("a"), doc.tag.get("b") or doc.tag.get("a"), node
    )
    test_transform(tr, expect)


@pytest.mark.parametrize(
    "doc,expect",
    [
        (doc(p("fo<a>o"), p("b<b>ar")), doc(p("fo<a><b>ar"))),
        (
            doc(blockquote(ul(li("<a>", p("foo"), "<b>")), p("x"))),
            doc(blockquote("<a><b>", p("x"))),
        ),
        (doc(p("<a>foo<b>")), doc(p("<a><b>"))),
        (doc(p("<a><b>")), doc(p("<a><b>"))),
        (doc(ul(li(p("<a>foo")), li(p("bar<b>"))), p("hi")), doc(p("hi"))),
        (doc(p("a"), p("<a>b<b>")), doc(p("a"), p())),
        (
            doc(p("a"), blockquote(blockquote(p("<a>foo")), p("bar<b>")), p("b")),
            doc(p("a"), p("b")),
        ),
        (doc(h1("<a>foo"), p("bar"), blockquote(p("baz<b>"))), doc(p())),
        (doc(h1("<a>foo"), p("bar"), p("baz<b>")), doc(h1())),
        (doc(h1("<a>foo"), p("b<b>ar")), doc(p("ar"))),
        (
            doc(p("one"), h1("<a>two"), blockquote(p("three<b>")), p("four")),
            doc(p("one"), h1(), p("four")),
        ),
    ],
)
def test_delete_range(doc, expect, test_transform):
    tr = Transform(doc).delete_range(
        doc.tag.get("a"), doc.tag.get("b") or doc.tag.get("a")
    )
    test_transform(tr, expect)


@pytest.mark.parametrize(
    "doc,mark,expect",
    [
        # adds a mark
        (doc(p("<a>", img())), schema.mark("em"), doc(p("<a>", em(img())))),
        # doesn't duplicate a mark
        (doc(p("<a>", em(img()))), schema.mark("em"), doc(p("<a>", em(img())))),
        # replaces a mark
        (
            doc(p("<a>", a(img()))),
            schema.mark("link", {"href": "x"}),
            doc(p("<a>", a({"href": "x"}, img()))),
        ),
    ],
)
def test_add_node_mark(doc, mark, expect, test_transform):
    test_transform(Transform(doc).add_node_mark(doc.tag["a"], mark), expect)


@pytest.mark.parametrize(
    "doc,mark,expect",
    [
        # removes a mark
        (doc(p("<a>", em(img()))), schema.mark("em"), doc(p("<a>", img()))),
        # doesn't do anything when there is no mark
        (doc(p("<a>", img())), schema.mark("em"), doc(p("<a>", img()))),
        # can remove a mark from multiple marks
        (doc(p("<a>", em(a(img())))), schema.mark("em"), doc(p("<a>", a(img())))),
    ],
)
def test_remove_node_mark(doc, mark, expect, test_transform):
    test_transform(Transform(doc).remove_node_mark(doc.tag["a"], mark), expect)
