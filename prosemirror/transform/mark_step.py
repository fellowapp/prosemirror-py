from prosemirror.model import Fragment, Slice

from .step import Step, StepResult


def map_fragment(fragment: Fragment, f, parent=None):
    mapped = []
    for i in range(fragment.child_count):
        child = fragment.child(i)
        if getattr(child.content, "size", None):
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
            if not node.is_atom or not parent.type.allows_mark_type(self.mark.type):
                return node
            return node.mark(self.mark.add_to_set(node.marks))

        slice = Slice(
            map_fragment(old_slice.content, iteratee, parent),
            old_slice.open_start,
            old_slice.open_end,
        )
        return StepResult.from_replace(doc, self.from_, self.to, slice)

    def invert(self, doc=None):
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
            json_data["from"], json_data["to"], schema.mark_from_json(json_data["mark"])
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

    def invert(self, doc=None):
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
            json_data["from"], json_data["to"], schema.mark_from_json(json_data["mark"])
        )


Step.json_id("removeMark", RemoveMarkStep)


class AddNodeMarkStep(Step):
    def __init__(self, pos, mark):
        super().__init__()
        self.pos = pos
        self.mark = mark

    def apply(self, doc):
        node = doc.node_at(self.pos)
        if not node:
            return StepResult.fail("No node at mark step's position")
        updated = node.type.create(node.attrs, None, self.mark.add_to_set(node.marks))
        return StepResult.from_replace(
            doc,
            self.pos,
            self.pos + 1,
            Slice(Fragment.from_(updated), 0, 0 if node.is_leaf else 1),
        )

    def invert(self, doc):
        node = doc.node_at(self.pos)
        if node:
            new_set = self.mark.add_to_set(node.marks)
            if len(new_set) == len(node.marks):
                for i in range(len(node.marks)):
                    if not node.marks[i].is_in_set(new_set):
                        return AddNodeMarkStep(self.pos, node.marks[i])
                return AddNodeMarkStep(self.pos, self.mark)
        return RemoveNodeMarkStep(self.pos, self.mark)

    def map(self, mapping):
        pos = mapping.map_result(self.pos, 1)
        return None if pos.deleted_after else AddNodeMarkStep(pos.pos, self.mark)

    def to_json(self):
        return {
            "stepType": "addNodeMark",
            "pos": self.pos,
            "mark": self.mark.to_json(),
        }

    @staticmethod
    def from_json(schema, json_data):
        if isinstance(json_data, str):
            import json

            json_data = json.loads(json_data)
        if not isinstance(json_data["pos"], int):
            raise ValueError("Invalid input for AddNodeMarkStep.from_json")
        return AddNodeMarkStep(
            json_data["pos"], schema.mark_from_json(json_data["mark"])
        )


Step.json_id("addNodeMark", AddNodeMarkStep)


class RemoveNodeMarkStep(Step):
    def __init__(self, pos, mark):
        super().__init__()
        self.pos = pos
        self.mark = mark

    def apply(self, doc):
        node = doc.node_at(self.pos)
        if not node:
            return StepResult.fail("No node at mark step's position")
        updated = node.type.create(
            node.attrs, None, self.mark.remove_from_set(node.marks)
        )
        return StepResult.from_replace(
            doc,
            self.pos,
            self.pos + 1,
            Slice(Fragment.from_(updated), 0, 0 if node.is_leaf else 1),
        )

    def invert(self, doc):
        node = doc.node_at(self.pos)
        if not node or not self.mark.is_in_set(node.marks):
            return self
        return AddNodeMarkStep(self.pos, self.mark)

    def map(self, mapping):
        pos = mapping.map_result(self.pos, 1)
        return None if pos.deleted_after else RemoveNodeMarkStep(pos.pos, self.mark)

    def to_json(self):
        return {
            "stepType": "removeNodeMark",
            "pos": self.pos,
            "mark": self.mark.to_json(),
        }

    @staticmethod
    def from_json(schema, json_data):
        if isinstance(json_data, str):
            import json

            json_data = json.loads(json_data)
        if not isinstance(json_data["pos"], int):
            raise ValueError("Invalid input for RemoveNodeMarkStep.from_json")
        return RemoveNodeMarkStep(
            json_data["pos"], schema.mark_from_json(json_data["mark"])
        )


Step.json_id("removeNodeMark", RemoveNodeMarkStep)
