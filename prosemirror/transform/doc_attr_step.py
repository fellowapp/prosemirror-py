from typing import Any, Optional

from prosemirror.model import Node, Schema
from prosemirror.transform.map import Mappable
from prosemirror.utils import JSON, JSONDict

from .step import Step, StepMap, StepResult, step_json_id


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

    def invert(self, doc: Node) -> "DocAttrStep":
        return DocAttrStep(self.attr, doc.attrs[self.attr])

    def map(self, mapping: Mappable) -> Optional[Step]:
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

            json_data = json.loads(json_data)
        if not isinstance(json_data["attr"], str):
            raise ValueError("Invalid input for DocAttrStep.from_json")
        return DocAttrStep(json_data["attr"], json_data["value"])


step_json_id("docAttr", DocAttrStep)
