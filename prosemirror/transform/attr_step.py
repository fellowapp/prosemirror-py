from typing import Any, cast

from prosemirror.model import Fragment, Node, Schema, Slice
from prosemirror.transform.map import Mappable, StepMap
from prosemirror.transform.step import Step, StepResult, step_json_id
from prosemirror.utils import JSON, JSONDict


class AttrStep(Step):
    def __init__(self, pos: int, attr: str, value: JSON) -> None:
        super().__init__()
        self.pos = pos
        self.attr = attr
        self.value = value

    def apply(self, doc: Node) -> StepResult:
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

    def get_map(self) -> StepMap:
        return StepMap.empty

    def invert(self, doc: Node) -> Step:
        node_at_pos = doc.node_at(self.pos)
        assert node_at_pos is not None
        return AttrStep(self.pos, self.attr, node_at_pos.attrs[self.attr])

    def map(self, mapping: Mappable) -> Step | None:
        pos = mapping.map_result(self.pos, 1)
        return None if pos.deleted_after else AttrStep(pos.pos, self.attr, self.value)

    def to_json(self) -> JSONDict:
        return {
            "stepType": "attr",
            "pos": self.pos,
            "attr": self.attr,
            "value": self.value,
        }

    @staticmethod
    def from_json(schema: Schema[Any, Any], json_data: JSONDict | str) -> "AttrStep":
        if isinstance(json_data, str):
            import json

            json_data = cast(JSONDict, json.loads(json_data))

        if not isinstance(json_data["pos"], int) or not isinstance(
            json_data["attr"], str
        ):
            raise ValueError("Invalid input for AttrStep.from_json")
        return AttrStep(json_data["pos"], json_data["attr"], json_data["value"])


step_json_id("attr", AttrStep)
