import abc
from typing import Any, Literal, Optional, TypeVar, cast, overload

from prosemirror.model import Node, ReplaceError, Schema, Slice
from prosemirror.transform.map import Mappable, StepMap
from prosemirror.utils import JSONDict

# like a registry
STEPS_BY_ID: dict[str, type["Step"]] = {}
StepSubclass = TypeVar("StepSubclass", bound="Step")


class Step(metaclass=abc.ABCMeta):
    json_id: str

    @abc.abstractmethod
    def apply(self, _doc: Node) -> "StepResult": ...

    def get_map(self) -> StepMap:
        return StepMap.empty

    @abc.abstractmethod
    def invert(self, _doc: Node) -> "Step": ...

    @abc.abstractmethod
    def map(self, _mapping: Mappable) -> Optional["Step"]: ...

    def merge(self, _other: "Step") -> Optional["Step"]:
        return None

    @abc.abstractmethod
    def to_json(self) -> JSONDict: ...

    @staticmethod
    def from_json(schema: Schema[Any, Any], json_data: JSONDict | str) -> "Step":
        if isinstance(json_data, str):
            import json

            json_data = cast(JSONDict, json.loads(json_data))

        if not json_data or not json_data.get("stepType"):
            raise ValueError("Invalid inpit for Step.from_json")
        type = STEPS_BY_ID.get(cast(str, json_data["stepType"]))
        if not type:
            raise ValueError(f'no step type {json_data["stepType"]} defined')
        return type.from_json(schema, json_data)


def step_json_id(id: str, step_class: type[StepSubclass]) -> type[StepSubclass]:
    if id in STEPS_BY_ID:
        raise ValueError(f"Duplicated JSON ID for step type: {id}")

    STEPS_BY_ID[id] = step_class
    step_class.json_id = id

    return step_class


class StepResult:
    @overload
    def __init__(self, doc: Node, failed: Literal[None]) -> None: ...

    @overload
    def __init__(self, doc: None, failed: str) -> None: ...

    def __init__(self, doc: Node | None, failed: str | None) -> None:
        self.doc = doc
        self.failed = failed

    @classmethod
    def ok(cls, doc: Node) -> "StepResult":
        return cls(doc, None)

    @classmethod
    def fail(cls, message: str) -> "StepResult":
        return cls(None, message)

    @classmethod
    def from_replace(cls, doc: Node, from_: int, to: int, slice: Slice) -> "StepResult":
        try:
            return cls.ok(doc.replace(from_, to, slice))
        except ReplaceError as e:
            return cls.fail(e.args[0])
