import pytest
from prosemirror_test_builder import out

doc = out["doc"]
p = out["p"]
li = out["li"]
ul = out["ul"]
em = out["em"]
a = out["a"]
blockquote = out["blockquote"]


@pytest.mark.parametrize(
    "doc,expect,open_start,open_end",
    [
        (doc(p("hello<b> world")), doc(p("hello")), 0, 1),
        (doc(p("hello<b>")), doc(p("hello")), 0, 1),
        (doc(p("hello<b> world"), p("rest")), doc(p("hello")), 0, 1),
        (doc(p("hello ", em("WOR<b>LD"))), doc(p("hello ", em("WOR"))), 0, 1),
        (doc(p("a"), p("b<b>")), doc(p("a"), p("b")), 0, 1),
        (doc(p("a"), "<b>", p("b")), doc(p("a")), 0, 0),
        (
            doc(blockquote(ul(li(p("a")), li(p("b<b>"))))),
            doc(blockquote(ul(li(p("a")), li(p("b"))))),
            0,
            4,
        ),
        (doc(p("hello<a> world")), doc(p(" world")), 1, 0),
        (doc(p("<a>hello")), doc(p("hello")), 1, 0),
        (doc(p("foo"), p("bar<a>baz")), doc(p("baz")), 1, 0),
        (
            doc(p("a sentence with an ", em("emphasized ", a("li<a>nk")), " in it")),
            doc(p(em(a("nk")), " in it")),
            1,
            0,
        ),
        (
            doc(p("a ", em("sentence"), " wi<a>th ", em("text"), " in it")),
            doc(p("th ", em("text"), " in it")),
            1,
            0,
        ),
        (doc(p("a"), "<a>", p("b")), doc(p("b")), 0, 0),
        (
            doc(blockquote(ul(li(p("a")), li(p("<a>b"))))),
            doc(blockquote(ul(li(p("b"))))),
            4,
            0,
        ),
        (doc(p("hell<a>o wo<b>rld")), p("o wo"), 0, 0),
        (doc(p("on<a>e"), p("t<b>wo")), doc(p("e"), p("t")), 1, 1),
        (
            doc(p("here's noth<a>ing and ", em("here's e<b>m"))),
            p("ing and ", em("here's e")),
            0,
            0,
        ),
        (
            doc(ul(li(p("hello")), li(p("wo<a>rld")), li(p("x"))), p(em("bo<b>o"))),
            doc(ul(li(p("rld")), li(p("x"))), p(em("bo"))),
            3,
            1,
        ),
        (
            doc(
                blockquote(
                    p("foo<a>bar"), ul(li(p("a")), li(p("b"), "<b>", p("c"))), p("d")
                )
            ),
            blockquote(p("bar"), ul(li(p("a")), li(p("b")))),
            1,
            2,
        ),
    ],
)
def test_slice_cut(doc, expect, open_start, open_end):
    slice = doc.slice(doc.tag.get("a", 0), doc.tag.get("b"))
    assert slice.content.eq(expect.content)
    assert slice.open_start == open_start
    assert slice.open_end == open_end


def test_slice_can_include_parents():
    d = doc(blockquote(p("fo<a>o"), p("bar<b>")))
    slice = d.slice(d.tag["a"], d.tag["b"], True)
    assert str(slice) == '<blockquote(paragraph("o"), paragraph("bar"))>(2,2)'
