from prosemirror.model import Slice, Fragment

from .step import Step, StepResult, StepMap


class AttrStep(Step):
    def __init__(self, pos, attr, value):
        super().__init__()
        self.pos = pos
        self.attr = attr
        self.value = value

    def apply(self, doc):
        node = doc.node_at(self.pos)
        if not node:
            return StepResult.fail("No node at attribute step's position")
        attrs = {}
        for name in node.attrs:
            attrs[name] = node.attrs[name]
        attrs[self.attr] = self.value
        updated = node.type.create(attrs, None, node.marks)
        return StepResult.from_replace(
            doc,
            self.pos,
            self.pos + 1,
            Slice(Fragment.from_(updated), 0, 0 if node.is_leaf else 1),
        )

    def get_map(self):
        return StepMap.empty

    def invert(self, doc):
        return AttrStep(self.pos, self.attr, doc.node_at(self.pos).attrs[self.attr])

    def map(self, mapping):
        pos = mapping.map_result(self.pos, 1)
        return None if pos.deleted_after else AttrStep(pos.pos, self.attr, self.value)

    def to_json(self):
        json_data = {
            "stepType": "attr",
            "pos": self.pos,
            "attr": self.attr,
            "value": self.value,
        }

        return json_data

    @staticmethod
    def from_json(schema, json_data):
        if isinstance(json_data, str):
            import json

            json_data = json.loads(json_data)
        if not isinstance(json_data["pos"], int) or not isinstance(
            json_data["attr"], str
        ):
            raise ValueError("Invalid input for AttrStep.from_json")
        return AttrStep(json_data["pos"], json_data["attr"], json_data["value"])


Step.json_id("attr", AttrStep)
