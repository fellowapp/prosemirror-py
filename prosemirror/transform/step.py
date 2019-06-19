import abc

from prosemirror.model import ReplaceError

from .map import StepMap

# like a registry
STEPS_BY_ID = {}


class Step(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def apply(self, _doc):
        return

    def get_map(self):
        return StepMap.empty

    @abc.abstractmethod
    def invert(self, _doc):
        return

    @abc.abstractmethod
    def map(self, _mapping):
        return

    def merge(self, _other):
        return None

    @abc.abstractmethod
    def to_json(self):
        return

    @staticmethod
    def from_json(schema, json_data):
        if isinstance(json_data, str):
            import json

            json_data = json.loads(json_data)
        if not json_data or not json_data.get("stepType"):
            raise ValueError("Invalid inpit for Step.from_json")
        type = STEPS_BY_ID.get(json_data["stepType"])
        if not type:
            raise ValueError(f'no step type {json_data["stepType"]} defined')
        return type.from_json(schema, json_data)

    @staticmethod
    def json_id(id, step_class):
        if id in STEPS_BY_ID:
            raise ValueError(f"Duplicated JSON ID for step type: {id}")
        STEPS_BY_ID[id] = step_class
        step_class.json_id = id
        return step_class


class StepResult:
    def __init__(self, doc, failed):
        self.doc = doc
        self.failed = failed

    @classmethod
    def ok(cls, doc):
        return cls(doc, None)

    @classmethod
    def fail(cls, message):
        return cls(None, message)

    @classmethod
    def from_replace(cls, doc, from_, to, slice):
        try:
            return cls.ok(doc.replace(from_, to, slice))
        except ReplaceError as e:
            return cls.fail(e.args[0])
