import pytest
from prosemirror_test_builder import schema, out, builders
from prosemirror_transform import Transform


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
        # (
        #     doc(p("hello ", strong("<a>there"), "!<b>")),
        #     schema.mark("strong"),
        #     doc(p("hello ", strong("there!"))),
        # ),
    ],
)
def test_add_mark(doc, mark, expect, test_transform):
    test_transform(Transform(doc).add_mark(doc.tag["a"], doc.tag["b"], mark), expect)
