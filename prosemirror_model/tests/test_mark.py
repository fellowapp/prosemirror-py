import pytest
from prosemirror_model import Mark, Schema, Node
from prosemirror_test_builder import schema, out


doc = out["doc"]
p = out["p"]
em = out["em"]
a = out["a"]

em_ = schema.mark("em")
strong = schema.mark("strong")


def link(href, title=None):
    return schema.mark("link", {"href": href, "title": title})


code = schema.mark("code")


custom_schema = Schema(
    {
        "nodes": {
            "doc": {"content": "paragraph+"},
            "paragraph": {"content": "text*"},
            "text": {},
        },
        "marks": {
            "remark": {"attrs": {"id": {}}, "excludes": "", "inclusive": False},
            "user": {"attrs": {"id": {}}, "excludes": "_"},
            "strong": {"excludes": "em-group"},
            "em": {"group": "em-group"},
        },
    }
)

custom = custom_schema.marks
remark1 = custom["remark"].create({"id": 1})
remark2 = custom["remark"].create({"id": 2})
user1 = custom["user"].create({"id": 1})
user2 = custom["user"].create({"id": 2})
custom_em = custom["em"].create()
custom_strong = custom["strong"].create()


@pytest.mark.parametrize(
    "a,b,res",
    [
        ([em_, strong], [em_, strong], True),
        ([em_, strong], [em_, code], False),
        ([em_, strong], [em_, strong, code], False),
        ([link("http://foo"), code], [link("http://foo"), code], True),
        ([link("http://foo"), code], [link("http://bar"), code], False),
    ],
)
def test_same_set(a, b, res):
    assert Mark.same_set(a, b) is res


@pytest.mark.parametrize(
    "a,b,res",
    [
        (link("http://foo"), (link("http://foo")), True),
        (link("http://foo"), link("http://bar"), False),
        (link("http://foo", "A"), link("http://foo", "B"), False),
    ],
)
def test_eq(a, b, res):
    assert a.eq(b) is res


def test_add_to_set(ist):

    ist(em_.add_to_set([]), [em_], Mark.same_set)
    ist(em_.add_to_set([em_]), [em_], Mark.same_set)
    ist(em_.add_to_set([strong]), [em_, strong], Mark.same_set)
    ist(strong.add_to_set([em_]), [em_, strong], Mark.same_set)
    ist(
        link("http://bar").add_to_set([link("http://foo"), em_]),
        [link("http://bar"), em_],
        Mark.same_set,
    )
    ist(
        link("http://foo").add_to_set([em_, link("http://foo")]),
        [em_, link("http://foo")],
        Mark.same_set,
    )
    ist(
        code.add_to_set([em_, strong, link("http://foo")]),
        [em_, strong, link("http://foo"), code],
        Mark.same_set,
    )
    ist(strong.add_to_set([em_, code]), [em_, strong, code], Mark.same_set)
    ist(remark2.add_to_set([remark1]), [remark1, remark2], Mark.same_set)
    ist(remark1.add_to_set([remark1]), [remark1], Mark.same_set)
    ist(user1.add_to_set([remark1, custom_em]), [user1], Mark.same_set)
    ist(custom_em.add_to_set([user1]), [user1], Mark.same_set)
    ist(user2.add_to_set([user1]), [user2], Mark.same_set)
    ist(
        custom_em.add_to_set([remark1, custom_strong]),
        [remark1, custom_strong],
        Mark.same_set,
    )
    ist(
        custom_strong.add_to_set([remark1, custom_em]),
        [remark1, custom_strong],
        Mark.same_set,
    )


def test_remove_form_set(ist):
    ist(Mark.same_set(em_.remove_from_set([]), []))
    ist(Mark.same_set(em_.remove_from_set([em_]), []))
    ist(Mark.same_set(strong.remove_from_set([em_]), [em_]))
    ist(Mark.same_set(link("http://foo").remove_from_set([link("http://foo")]), []))
    ist(
        Mark.same_set(
            link("http://foo", "title").remove_from_set([link("http://foo")]),
            [link("http://foo")],
        )
    )


class TestResolvedPosMarks:

    custom_doc = Node.from_json(
        custom_schema,
        {
            "type": "doc",
            "content": [
                {
                    "type": "paragraph",
                    "content": [
                        {
                            "type": "text",
                            "marks": [
                                {"type": "remark", "attrs": {"id": 1}},
                                {"type": "strong"},
                            ],
                            "text": "one",
                        },
                        {"type": "text", "text": "two"},
                    ],
                },
                {
                    "type": "paragraph",
                    "content": [
                        {"type": "text", "text": "one"},
                        {
                            "type": "text",
                            "marks": [{"type": "remark", "attrs": {"id": 1}}],
                            "text": "twothree",
                        },
                    ],
                },
                {
                    "type": "paragraph",
                    "content": [
                        {
                            "type": "text",
                            "marks": [{"type": "remark", "attrs": {"id": 2}}],
                            "text": "one",
                        },
                        {
                            "type": "text",
                            "marks": [{"type": "remark", "attrs": {"id": 1}}],
                            "text": "two",
                        },
                    ],
                },
            ],
        },
    )

    @pytest.mark.parametrize(
        "doc,mark,result",
        [
            (doc(p(em("fo<a>o"))), em_, True),
            (doc(p(em("fo<a>o"))), strong, False),
            (doc(p(em("hi"), "<a> there")), em_, True),
            (doc(p("one <a>", em("two"))), em_, False),
            (doc(p(em("<a>one"))), em_, True),
            (doc(p(a("li<a>nk"))), link("http://baz"), False),
        ],
    )
    def test_is_at(self, doc, mark, result):
        assert mark.is_in_set(doc.resolve(doc.tag["a"]).marks()) is result

    @pytest.mark.parametrize(
        "a,b",
        [
            (custom_doc.resolve(4).marks(), [custom_strong]),
            (custom_doc.resolve(3).marks(), [remark1, custom_strong]),
            (custom_doc.resolve(20).marks(), []),
            (custom_doc.resolve(15).marks(), [remark1]),
            (custom_doc.resolve(25).marks(), []),
        ],
    )
    def test_with_custom_doc(self, a, b):
        assert Mark.same_set(a, b)
