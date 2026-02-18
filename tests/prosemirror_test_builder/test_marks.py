from prosemirror.model import Schema
from prosemirror.test_builder import eq
from prosemirror.test_builder.build import builders

# This schema has an "a" mark which doesn't exclude itself
test_schema = Schema({
    "nodes": {
        "doc": {"content": "block+"},
        "p": {"content": "inline*", "group": "block"},
        "text": {"group": "inline"},
    },
    "marks": {
        "a": {"attrs": {"href": {}}, "excludes": ""},
    },
})

b = builders(test_schema, {})
doc = b["doc"]
p = b["p"]
a = b["a"]


class TestMultipleMarks:
    def test_deduplicates_identical_marks(self):
        actual = doc(p(a({"href": "/foo"}, a({"href": "/foo"}, "click <p>here"))))
        expected = doc(p(a({"href": "/foo"}, "click here")))

        assert eq(actual, expected)
        assert len(actual.node_at(actual.tag["p"]).marks) == 1

    def test_marks_of_same_type_but_different_attributes_are_distinct(self):
        actual = doc(p(a({"href": "/foo"}, a({"href": "/bar"}, "click <p>here"))))

        assert len(actual.node_at(actual.tag["p"]).marks) == 2
