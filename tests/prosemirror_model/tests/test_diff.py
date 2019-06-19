import pytest

from prosemirror.test_builder import out

doc = out["doc"]
blockquote = out["blockquote"]
h1 = out["h1"]
h2 = out["h2"]
p = out["p"]
em = out["em"]
strong = out["strong"]


@pytest.mark.parametrize(
    "a,b",
    [
        (
            doc(p("a", em("b")), p("hello"), blockquote(h1("bye"))),
            doc(p("a", em("b")), p("hello"), blockquote(h1("bye"))),
        ),
        (
            doc(p("a", em("b")), p("hello"), blockquote(h1("bye")), "<a>"),
            doc(p("a", em("b")), p("hello"), blockquote(h1("bye")), p("oops")),
        ),
        (
            doc(p("a", em("b")), p("hello"), blockquote(h1("bye")), "<a>", p("oops")),
            doc(p("a", em("b")), p("hello"), blockquote(h1("bye"))),
        ),
        (doc(p("a<a>", em("b"))), doc(p("a", strong("b")))),
        (doc(p("foo<a>bar", em("b"))), doc(p("foo", em("b")))),
        (doc(p("foo<a>bar")), doc(p("foocar"))),
        (doc(p("a"), "<a>", p("b")), doc(p("a"), h1("b"))),
        (doc("<a>", p("b")), doc(h1("b"))),
        (doc(p("a"), "<a>", h1("foo")), doc(p("a"), h2("foo"))),
    ],
)
def test_find_diff_start(a, b):
    assert a.content.find_diff_start(b.content) == a.tag.get("a")


@pytest.mark.parametrize(
    "a,b",
    [
        (
            doc(p("a", em("b")), p("hello"), blockquote(h1("bye"))),
            doc(p("a", em("b")), p("hello"), blockquote(h1("bye"))),
        ),
        (
            doc("<a>", p("a", em("b")), p("hello"), blockquote(h1("bye"))),
            doc(p("oops"), p("a", em("b")), p("hello"), blockquote(h1("bye"))),
        ),
        (
            doc(p("oops"), "<a>", p("a", em("b")), p("hello"), blockquote(h1("bye"))),
            doc(p("a", em("b")), p("hello"), blockquote(h1("bye"))),
        ),
        (doc(p("a", em("b"), "<a>c")), doc(p("a", strong("b"), "c"))),
        (doc(p("bar<a>foo", em("b"))), doc(p("foo", em("b")))),
        (doc(p("foob<a>ar")), doc(p("foocar"))),
        (doc(p("a"), "<a>", p("b")), doc(h1("a"), p("b"))),
        (doc(p("b"), "<a>"), doc(h1("b"))),
        (doc("<a>", p("hello")), doc(p("hey"), p("hello"))),
    ],
)
def test_find_diff_end(a, b):
    found = a.content.find_diff_end(b.content)
    if a == b:
        assert not found
    if found:
        assert found.get("a") == a.tag.get("a")
