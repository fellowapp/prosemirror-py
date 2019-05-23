from prosemirror_model import Fragment, Slice
from .step import Step, StepResult


def map_fragment(fragment: Fragment, f, parent=None):
    mapped = []
    for i in range(fragment.child_count):
        child = fragment.child(i)
        if child.content.size:
            child = child.copy(map_fragment(child.content, f, child))
        if child.is_inline:
            child = f(child, parent, i)
        mapped.append(child)
    return fragment.from_array(mapped)


class AddMarkStep(Step):
    def __init__(self, from_, to, mark):
        super().__init__()
        self.from_ = from_
        self.to = to
        self.mark = mark

    def apply(self, doc):
        old_slice = doc.slice(self.from_, self.to)
        from__ = doc.resolve(self.from_)
        parent = from__.node(from__.shared_depth(self.to))

        def iteratee(node, parent, *args):
            if not parent.type.allows_mark_type(self.mark.type):
                return node
            return node.mark(self.mark.add_to_set(node.marks))

        slice = Slice(
            map_fragment(old_slice.content, iteratee, parent),
            old_slice.open_start,
            old_slice.open_end,
        )
        return StepResult.from_replace(doc, self.from_, self.to, slice)

    def invert(self):
        return RemoveMarkStep(self.from_, self.to, self.mark)

    def map(self, mapping):
        from_ = mapping.map_result(self.from_, 1)
        to = mapping.map_result(self.to, -1)
        if from_.deleted and to.deleted or from_.pos > to.pos:
            return None
        return AddMarkStep(from_.pos, to.pos, self.mark)

    def merge(self, other: "AddMarkStep"):
        if (
            isinstance(other, AddMarkStep)
            and other.mark.eq(self.mark)
            and self.from_ <= other.to
            and self.to >= other.from_
        ):
            return AddMarkStep(
                min(self.from_, other.from_), max(self.to, other.to), self.mark
            )

    def to_json(self):
        json_data = {
            "stepType": "addMark",
            "mark": self.mark.to_json(),
            "from": self.from_,
            "to": self.to,
        }
        return json_data

    @staticmethod
    def from_json(schema, json_data):
        if isinstance(json_data, str):
            import json

            json_data = json.loads(json_data)
        if not isinstance(json_data["from"], int) or not isinstance(
            json_data["to"], int
        ):
            raise ValueError("Invalid input for AddMarkStep.from_json")
        return AddMarkStep(
            json_data["from"], json_data["to"], schema.mark_from_json(json["mark"])
        )


Step.json_id("addMark", AddMarkStep)


class RemoveMarkStep(Step):
    def __init__(self, from_, to, mark):
        super().__init__()
        self.from_ = from_
        self.to = to
        self.mark = mark

    def apply(self, doc):
        old_slice = doc.slice(self.from_, self.to)

        def iteratee(node, *args):
            return node.mark(self.mark.remove_from_set(node.marks))

        slice = Slice(
            map_fragment(old_slice.content, iteratee),
            old_slice.open_start,
            old_slice.open_end,
        )
        return StepResult.from_replace(doc, self.from_, self.to, slice)

    def invert(self):
        return AddMarkStep(self.from_, self.to, self.mark)

    def map(self, mapping):
        from_ = mapping.map_result(self.from_, 1)
        to = mapping.map_result(self.to, -1)
        if (from_.deleted and to.deleted) or (from_.pos > to.pos):
            return None
        return RemoveMarkStep(from_.pos, to.pos, self.mark)

    def merge(self, other: "RemoveMarkStep"):
        if (
            isinstance(other, RemoveMarkStep)
            and (other.mark.eq(self.mark))
            and (self.from_ <= other.to)
            and self.to >= other.from_
        ):
            return RemoveMarkStep(
                min(self.from_, other.from_), max(self.to, other.to), self.mark
            )

    def to_json(self):
        json_data = {
            "stepType": "removeMark",
            "mark": self.mark.to_json(),
            "from": self.from_,
            "to": self.to,
        }
        return json_data

    @staticmethod
    def from_json(schema, json_data):
        if isinstance(json_data, str):
            import json

            json_data = json.loads(json_data)
        if not isinstance(json_data["from"], int) or not isinstance(
            json_data["to"], int
        ):
            raise ValueError("Invalid input for RemoveMarkStep.from_json")
        return RemoveMarkStep(
            json_data["from"], json_data["to"], schema.mark_from_json(json["mark"])
        )
