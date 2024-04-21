from typing import Any, cast

from prosemirror.model import Node, Schema
from prosemirror.transform.map import Mappable, StepMap
from prosemirror.transform.step import Step, StepResult, step_json_id
from prosemirror.utils import JSON, JSONDict


class DocAttrStep(Step):
    def __init__(self, attr: str, value: JSON):
        super().__init__()
        self.attr = attr
        self.value = value

    def apply(self, doc: Node) -> StepResult:
        attrs = {}
        for name in doc.attrs:
            attrs[name] = doc.attrs[name]
        attrs[self.attr] = self.value
        updated = doc.type.create(attrs, doc.content, doc.marks)
        return StepResult.ok(updated)

    def get_map(self) -> StepMap:
        return StepMap.empty

    def invert(self, doc: Node) -> Step:
        return DocAttrStep(self.attr, doc.attrs[self.attr])

    def map(self, mapping: Mappable) -> Step | None:
        return self

    def to_json(self) -> JSONDict:
        json_data = {
            "stepType": "docAttr",
            "attr": self.attr,
            "value": self.value,
        }

        return json_data

    @staticmethod
    def from_json(schema: Schema[Any, Any], json_data: JSONDict | str) -> "DocAttrStep":
        if isinstance(json_data, str):
            import json

            json_data = cast(JSONDict, json.loads(json_data))

        if not isinstance(json_data["attr"], str):
            msg = "Invalid input for DocAttrStep.from_json"
            raise ValueError(msg)
        return DocAttrStep(json_data["attr"], json_data["value"])


step_json_id("docAttr", DocAttrStep)
