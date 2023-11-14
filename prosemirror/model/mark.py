import copy
from typing import TYPE_CHECKING, Any, Final, cast

from prosemirror.utils import Attrs, JSONDict

if TYPE_CHECKING:
    from .schema import MarkType, Schema


class Mark:
    none: Final[list["Mark"]] = []

    def __init__(self, type: "MarkType", attrs: Attrs) -> None:
        self.type = type
        self.attrs = attrs

    def add_to_set(self, set: list["Mark"]) -> list["Mark"]:
        copy: list["Mark"] | None | None = None
        placed = False
        for i in range(len(set)):
            other = set[i]
            if self.eq(other):
                return set
            if self.type.excludes(other.type):
                if copy is None:
                    copy = set[0:i]
            elif other.type.excludes(self.type):
                return set
            else:
                if not placed and other.type.rank > self.type.rank:
                    if copy is None:
                        copy = set[0:i]
                    copy.append(self)
                    placed = True
                if copy:
                    copy.append(other)
        if copy is None:
            copy = set[:]
        if not placed:
            copy.append(self)
        return copy

    def remove_from_set(self, set: list["Mark"]) -> list["Mark"]:
        return [item for item in set if not item.eq(self)]

    def is_in_set(self, set: list["Mark"]) -> bool:
        return any(item.eq(self) for item in set)

    def eq(self, other: "Mark") -> bool:
        if self == other:
            return True
        return self.type.name == other.type.name and self.attrs == other.attrs

    def to_json(self) -> JSONDict:
        return {"type": self.type.name, "attrs": copy.deepcopy(self.attrs)}

    @classmethod
    def from_json(
        cls,
        schema: "Schema[Any, Any]",
        json_data: JSONDict,
    ) -> "Mark":
        if not json_data:
            raise ValueError("Invalid input for Mark.fromJSON")
        name = json_data["type"]
        type = schema.marks.get(name)
        if not type:
            raise ValueError(f"There is no mark type {name} in this schema")
        return type.create(cast(JSONDict | None, json_data.get("attrs")))

    @classmethod
    def same_set(cls, a: list["Mark"], b: list["Mark"]) -> bool:
        if a == b:
            return True
        if len(a) != len(b):
            return False
        return all(item_a.eq(item_b) for (item_a, item_b) in zip(a, b))

    @classmethod
    def set_from(cls, marks: "list[Mark] | Mark | None") -> list["Mark"]:
        if not marks:
            return cls.none
        if isinstance(marks, Mark):
            return [marks]
        copy = marks[:]
        return sorted(copy, key=lambda item: item.type.rank)
