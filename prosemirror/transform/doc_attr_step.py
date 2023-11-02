from .step import Step, StepMap, StepResult


class DocAttrStep(Step):
    def __init__(self, attr, value):
        super().__init__()
        self.attr = attr
        self.value = value

    def apply(self, doc):
        attrs = {}
        for name in doc.attrs:
            attrs[name] = doc.attrs[name]
        attrs[self.attr] = self.value
        updated = doc.type.create(attrs, doc.content, doc.marks)
        return StepResult.ok(updated)

    def get_map(self):
        return StepMap.empty

    def invert(self, doc):
        return DocAttrStep(self.attr, doc.attrs[self.attr])

    def map(self, mapping):
        return self

    def to_json(self):
        json_data = {
            "stepType": "docAttr",
            "attr": self.attr,
            "value": self.value,
        }

        return json_data

    @staticmethod
    def from_json(schema, json_data):
        if isinstance(json_data, str):
            import json

            json_data = json.loads(json_data)
        if not isinstance(json_data["attr"], str):
            raise ValueError("Invalid input for DocAttrStep.from_json")
        return DocAttrStep(json_data["attr"], json_data["value"])


Step.json_id("docAttr", DocAttrStep)
