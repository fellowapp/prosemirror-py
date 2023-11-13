from typing import cast

from prosemirror.model import Node, Schema, Slice
from prosemirror.transform.map import Mappable, StepMap
from prosemirror.transform.step import Step, StepResult, step_json_id
from prosemirror.utils import JSONDict


class ReplaceStep(Step):
    def __init__(
        self, from_: int, to: int, slice: Slice, structure: bool | None = None
    ) -> None:
        super().__init__()
        self.from_ = from_
        self.to = to
        self.slice = slice
        self.structure = bool(structure)

    def apply(self, doc: Node) -> StepResult:
        if self.structure and content_between(doc, self.from_, self.to):
            return StepResult.fail("Structure replace would overrite content")
        return StepResult.from_replace(doc, self.from_, self.to, self.slice)

    def get_map(self) -> StepMap:
        return StepMap([self.from_, self.to - self.from_, self.slice.size])

    def invert(self, doc: Node) -> "ReplaceStep":
        return ReplaceStep(
            self.from_, self.from_ + self.slice.size, doc.slice(self.from_, self.to)
        )

    def map(self, mapping: Mappable) -> "ReplaceStep | None":
        from_ = mapping.map_result(self.from_, 1)
        to = mapping.map_result(self.to, -1)
        if from_.deleted and to.deleted:
            return None
        return ReplaceStep(from_.pos, max(from_.pos, to.pos), self.slice)

    def merge(self, other: "Step") -> "ReplaceStep | None":
        if not isinstance(other, ReplaceStep) or other.structure or self.structure:
            return None
        if (
            self.from_ + self.slice.size == other.from_
            and not self.slice.open_end
            and not other.slice.open_start
        ):
            if self.slice.size + other.slice.size == 0:
                slice = Slice.empty
            else:
                slice = Slice(
                    self.slice.content.append(other.slice.content),
                    self.slice.open_start,
                    other.slice.open_end,
                )
            return ReplaceStep(
                self.from_, self.to + (other.to - other.from_), slice, self.structure
            )
        elif (
            other.to == self.from_
            and not self.slice.open_start
            and not other.slice.open_end
        ):
            if self.slice.size + other.slice.size == 0:
                slice = Slice.empty
            else:
                slice = Slice(
                    other.slice.content.append(self.slice.content),
                    other.slice.open_start,
                    self.slice.open_end,
                )
            return ReplaceStep(other.from_, self.to, slice, self.structure)
        return None

    def to_json(self) -> JSONDict:
        json_data: JSONDict = {"stepType": "replace", "from": self.from_, "to": self.to}
        if self.slice.size:
            json_data = {
                **json_data,
                "slice": self.slice.to_json(),
            }
        if self.structure:
            json_data = {
                **json_data,
                "structure": True,
            }
        return json_data

    @staticmethod
    def from_json(schema: Schema[str, str], json_data: JSONDict | str) -> "ReplaceStep":
        if isinstance(json_data, str):
            import json

            json_data = cast(JSONDict, json.loads(json_data))

        if not isinstance(json_data["from"], int) or not isinstance(
            json_data["to"], int
        ):
            raise ValueError("Invlid input for ReplaceStep.from_json")
        return ReplaceStep(
            json_data["from"],
            json_data["to"],
            Slice.from_json(schema, cast(JSONDict | None, json_data.get("slice"))),
            bool(json_data.get("structure")),
        )


step_json_id("replace", ReplaceStep)


class ReplaceAroundStep(Step):
    def __init__(
        self,
        from_: int,
        to: int,
        gap_from: int,
        gap_to: int,
        slice: Slice,
        insert: int,
        structure: bool | None = None,
    ) -> None:
        super().__init__()
        self.from_ = from_
        self.to = to
        self.gap_from = gap_from
        self.gap_to = gap_to
        self.slice = slice
        self.insert = insert
        self.structure = bool(structure)

    def apply(self, doc: Node) -> StepResult:
        if self.structure and (
            content_between(doc, self.from_, self.gap_from)
            or content_between(doc, self.gap_to, self.to)
        ):
            return StepResult.fail("Structure gap-replace would overwrite content")
        gap = doc.slice(self.gap_from, self.gap_to)
        if gap.open_start or gap.open_end:
            return StepResult.fail("Gap is not a flat range")
        inserted = self.slice.insert_at(self.insert, gap.content)
        if not inserted:
            return StepResult.fail("Content does not fit in gap")
        return StepResult.from_replace(doc, self.from_, self.to, inserted)

    def get_map(self) -> StepMap:
        return StepMap(
            [
                self.from_,
                self.gap_from - self.from_,
                self.insert,
                self.gap_to,
                self.to - self.gap_to,
                self.slice.size - self.insert,
            ]
        )

    def invert(self, doc: Node) -> "ReplaceAroundStep":
        gap = self.gap_to - self.gap_from
        return ReplaceAroundStep(
            self.from_,
            self.from_ + self.slice.size + gap,
            self.from_ + self.insert,
            self.from_ + self.insert + gap,
            doc.slice(self.from_, self.to).remove_between(
                self.gap_from - self.from_, self.gap_to - self.from_
            ),
            self.gap_from - self.from_,
            self.structure,
        )

    def map(self, mapping: Mappable) -> "ReplaceAroundStep | None":
        from_ = mapping.map_result(self.from_, 1)
        to = mapping.map_result(self.to, -1)
        gap_from = mapping.map(self.gap_from, -1)
        gap_to = mapping.map(self.gap_to, 1)
        if (from_.deleted and to.deleted) or gap_from < from_.pos or gap_to > to.pos:
            return None
        return ReplaceAroundStep(
            from_.pos, to.pos, gap_from, gap_to, self.slice, self.insert, self.structure
        )

    def to_json(self) -> JSONDict:
        json_data: JSONDict = {
            "stepType": "replaceAround",
            "from": self.from_,
            "to": self.to,
            "gapFrom": self.gap_from,
            "gapTo": self.gap_to,
            "insert": self.insert,
        }
        if self.slice.size:
            json_data = {
                **json_data,
                "slice": self.slice.to_json(),
            }
        if self.structure:
            json_data = {
                **json_data,
                "structure": True,
            }
        return json_data

    @staticmethod
    def from_json(
        schema: Schema[str, str], json_data: JSONDict | str
    ) -> "ReplaceAroundStep":
        if isinstance(json_data, str):
            import json

            json_data = cast(JSONDict, json.loads(json_data))

        if (
            not isinstance(json_data["from"], int)
            or not isinstance(json_data["to"], int)
            or not isinstance(json_data["gapFrom"], int)
            or not isinstance(json_data["gapTo"], int)
            or not isinstance(json_data["insert"], int)
        ):
            raise ValueError("Invlid input for ReplaceAroundStep.from_json")
        return ReplaceAroundStep(
            json_data["from"],
            json_data["to"],
            json_data["gapFrom"],
            json_data["gapTo"],
            Slice.from_json(schema, cast(JSONDict | None, json_data.get("slice"))),
            json_data["insert"],
            bool(json_data.get("structure")),
        )


step_json_id("replaceAround", ReplaceAroundStep)


def content_between(doc: Node, from_: int, to: int) -> bool:
    from__ = doc.resolve(from_)
    dist = to - from_
    depth = from__.depth
    while (
        dist > 0
        and depth > 0
        and from__.index_after(depth) == from__.node(depth).child_count
    ):
        depth -= 1
        dist -= 1
    if dist > 0:
        next = from__.node(depth).maybe_child(from__.index_after(depth))
        while dist > 0:
            if not next or next.is_leaf:
                return True
            next = next.first_child
            dist -= 1
    return False
