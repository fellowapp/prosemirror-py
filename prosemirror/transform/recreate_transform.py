from __future__ import annotations

import copy
import json
import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Iterable, Mapping, MutableMapping, MutableSequence, cast

from typing_extensions import NotRequired, TypedDict

from prosemirror.model import Node

from .replace_step import ReplaceStep
from .step import Step
from .transform import Transform
from prosemirror.utils import JSON, text_length


class RecreateOptions(TypedDict, total=False):
    complex_steps: bool
    word_diffs: bool
    simplify_diff: bool
    complexSteps: bool
    wordDiffs: bool
    simplifyDiff: bool


class Operation(TypedDict):
    op: str
    path: str
    value: NotRequired[JSON]


@dataclass
class Change:
    value: str
    added: bool = False
    removed: bool = False


def recreate_transform(
    from_doc: Node,
    to_doc: Node,
    options: RecreateOptions | None = None,
) -> Transform:
    recreator = RecreateTransform(from_doc, to_doc, options)
    return recreator.init()


class RecreateTransform:
    def __init__(
        self,
        from_doc: Node,
        to_doc: Node,
        options: RecreateOptions | None = None,
    ) -> None:
        self.from_doc = from_doc
        self.to_doc = to_doc

        complex_steps, word_diffs, simplify_diff = _parse_options(options)
        self.complex_steps = complex_steps
        self.word_diffs = word_diffs
        self.simplify_diff = simplify_diff

        self.schema = from_doc.type.schema
        self.tr = Transform(from_doc)

        # current working document data, may get updated while recalculating node steps
        self.current_json: dict[str, JSON] = {}
        # final document as json data
        self.final_json: dict[str, JSON] = {}
        self.ops: list[Operation] = []

    def init(self) -> Transform:
        if self.complex_steps:
            self.current_json = cast(dict[str, JSON], remove_marks(self.from_doc).to_json())
            self.final_json = cast(dict[str, JSON], remove_marks(self.to_doc).to_json())
            self.ops = create_patch(self.current_json, self.final_json)
            self.recreate_change_content_steps()
            self.recreate_change_mark_steps()
        else:
            self.current_json = cast(dict[str, JSON], self.from_doc.to_json())
            self.final_json = cast(dict[str, JSON], self.to_doc.to_json())
            self.ops = create_patch(self.current_json, self.final_json)
            self.recreate_change_content_steps()

        if self.simplify_diff:
            simplified = simplify_transform(self.tr)
            if simplified is not None:
                self.tr = simplified

        return self.tr

    def recreate_change_content_steps(self) -> None:
        ops: list[Operation] = []
        while self.ops:
            op = self.ops.pop(0)
            ops.append(op)

            to_doc: Node | None = None
            after_step_json = copy_value(self.current_json)
            path_parts = op["path"].split("/")

            while to_doc is None:
                apply_patch(after_step_json, [op])
                try:
                    to_doc = self.schema.node_from_json(after_step_json)
                    to_doc.check()
                except Exception:
                    to_doc = None
                    if self.ops:
                        op = self.ops.pop(0)
                        ops.append(op)
                    else:
                        raise ValueError(f"No valid diff possible applying {op['path']}")

            if (
                self.complex_steps
                and len(ops) == 1
                and ("attrs" in path_parts or "type" in path_parts)
            ):
                self.add_set_node_markup()
                ops = []
            elif (
                len(ops) == 1
                and op["op"] == "replace"
                and path_parts[-1] == "text"
            ):
                self.add_replace_text_steps(op, after_step_json)
                ops = []
            elif self.add_replace_step(to_doc, after_step_json):
                ops = []

    def add_set_node_markup(self) -> bool:
        from_doc = self.schema.node_from_json(self.current_json)
        to_doc = self.schema.node_from_json(self.final_json)
        start = to_doc.content.find_diff_start(from_doc.content)

        if start is None:
            return False

        from_node = from_doc.node_at(start)
        to_node = to_doc.node_at(start)

        if not from_node or not to_node:
            return False

        node_type = None if from_node.type == to_node.type else to_node.type
        try:
            self.tr.set_node_markup(start, node_type, to_node.attrs, to_node.marks)
        except ValueError as exc:
            if node_type and "Invalid content" in str(exc):
                self.tr.replace_with(start, start + from_node.node_size, to_node)
            else:
                raise

        self.current_json = cast(dict[str, JSON], remove_marks(self.tr.doc).to_json())
        self.ops = create_patch(self.current_json, self.final_json)
        return True

    def recreate_change_mark_steps(self) -> None:
        self.to_doc.descendants(self._apply_mark_diff)

    def _apply_mark_diff(
        self,
        target_node: Node,
        target_pos: int,
        _parent: Node | None,
        _i: int,
    ) -> bool | None:
        if not target_node.is_inline:
            return True

        def iteratee(node: Node, pos: int, _parent: Node | None, _i: int) -> bool | None:
            if not node.is_inline:
                return True
            from_pos = max(target_pos, pos)
            to_pos = min(
                target_pos + target_node.node_size,
                pos + node.node_size,
            )
            for node_mark in node.marks:
                if not node_mark.is_in_set(target_node.marks):
                    self.tr.remove_mark(from_pos, to_pos, node_mark)
            for node_mark in target_node.marks:
                if not node_mark.is_in_set(node.marks):
                    self.tr.add_mark(from_pos, to_pos, node_mark)
            return None

        self.tr.doc.nodes_between(
            target_pos,
            target_pos + target_node.node_size,
            iteratee,
        )
        return None

    def add_replace_step(self, to_doc: Node, after_step_json: dict[str, JSON]) -> bool:
        from_doc = self.schema.node_from_json(self.current_json)
        step = get_replace_step(from_doc, to_doc)

        if not step:
            return False

        if not self.tr.maybe_step(step).failed:
            self.current_json = after_step_json
            return True

        raise ValueError("No valid step found.")

    def add_replace_text_steps(
        self,
        op: Operation,
        after_step_json: dict[str, JSON],
    ) -> None:
        op1: Operation = {**op, "value": "xx"}
        op2: Operation = {**op, "value": "yy"}

        after_op1_json = copy_value(self.current_json)
        after_op2_json = copy_value(self.current_json)
        apply_patch(after_op1_json, [op1])
        apply_patch(after_op2_json, [op2])

        op1_doc = self.schema.node_from_json(after_op1_json)
        op2_doc = self.schema.node_from_json(after_op2_json)

        final_text = cast(str, op.get("value"))
        current_text = cast(str, get_from_path(self.current_json, op["path"]))

        text_diffs = (
            diff_words_with_space(current_text, final_text)
            if self.word_diffs
            else diff_chars(current_text, final_text)
        )

        offset = op1_doc.content.find_diff_start(op2_doc.content)
        if offset is None:
            raise ValueError("Unable to determine text diff start.")

        marks = op1_doc.resolve(offset + 1).marks()

        while text_diffs:
            diff = text_diffs.pop(0)
            diff_len = text_length(diff.value)
            if diff.added:
                text_node = self.schema.text(diff.value, marks)
                if text_diffs and text_diffs[0].removed:
                    next_diff = text_diffs.pop(0)
                    self.tr.replace_with(
                        offset,
                        offset + text_length(next_diff.value),
                        text_node,
                    )
                else:
                    self.tr.insert(offset, text_node)
                offset += diff_len
            elif diff.removed:
                if text_diffs and text_diffs[0].added:
                    next_diff = text_diffs.pop(0)
                    text_node = self.schema.text(next_diff.value, marks)
                    self.tr.replace_with(
                        offset,
                        offset + diff_len,
                        text_node,
                    )
                    offset += text_length(next_diff.value)
                else:
                    self.tr.delete(offset, offset + diff_len)
            else:
                offset += diff_len

        self.current_json = after_step_json


def simplify_transform(tr: Transform) -> Transform | None:
    if not tr.steps:
        return None

    new_tr = Transform(tr.docs[0])
    old_steps: list[Step] = list(tr.steps)

    while old_steps:
        step = old_steps.pop(0)
        while old_steps:
            merged = step.merge(old_steps[0])
            if not merged:
                break
            added_step = old_steps.pop(0)
            if isinstance(step, ReplaceStep) and isinstance(added_step, ReplaceStep):
                intermediate = step.apply(new_tr.doc).doc
                if intermediate is None:
                    raise ValueError("Failed to apply step while simplifying transform.")
                final_doc = added_step.apply(intermediate).doc
                if final_doc is None:
                    raise ValueError("Failed to apply step while simplifying transform.")
                next_step = get_replace_step(new_tr.doc, final_doc)
                if not next_step:
                    step = merged
                else:
                    step = next_step
            else:
                step = cast(Step, merged)
        new_tr.step(step)
    return new_tr


def get_replace_step(from_doc: Node, to_doc: Node) -> ReplaceStep | None:
    start = to_doc.content.find_diff_start(from_doc.content)
    if start is None:
        return None

    diff = to_doc.content.find_diff_end(from_doc.content)
    if diff is None:
        return None

    end_a = diff["a"]
    end_b = diff["b"]
    overlap = start - min(end_a, end_b)
    if overlap > 0:
        if from_doc.resolve(start - overlap).depth < to_doc.resolve(end_a + overlap).depth:
            start -= overlap
        else:
            end_a += overlap
            end_b += overlap

    return ReplaceStep(start, end_b, to_doc.slice(start, end_a))


def remove_marks(doc: Node) -> Node:
    tr = Transform(doc)
    tr.remove_mark(0, doc.node_size - 2)
    return tr.doc


def diff_words_with_space(a: str, b: str) -> list[Change]:
    return diff_tokens(
        re.findall(r"\s+|[^\s]+", a),
        re.findall(r"\s+|[^\s]+", b),
    )


def diff_chars(a: str, b: str) -> list[Change]:
    return diff_tokens(list(a), list(b))


def diff_tokens(a: list[str], b: list[str]) -> list[Change]:
    changes: list[Change] = []
    matcher = SequenceMatcher(a=a, b=b, autojunk=False)

    def push(change: Change) -> None:
        if not change.value:
            return
        if changes and changes[-1].added == change.added and changes[-1].removed == change.removed:
            changes[-1].value += change.value
        else:
            changes.append(change)

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            push(Change(value="".join(a[i1:i2])))
        elif tag == "delete":
            push(Change(value="".join(a[i1:i2]), removed=True))
        elif tag == "insert":
            push(Change(value="".join(b[j1:j2]), added=True))
        elif tag == "replace":
            push(Change(value="".join(a[i1:i2]), removed=True))
            push(Change(value="".join(b[j1:j2]), added=True))

    return changes


def create_patch(from_value: JSON, to_value: JSON) -> list[Operation]:
    ops: list[Operation] = []
    _diff(from_value, to_value, "", ops)
    return ops


def _diff(a: JSON, b: JSON, path: str, ops: list[Operation]) -> None:
    if a == b:
        return

    if _node_markup_only_change(a, b):
        key = "type" if cast(Mapping[str, JSON], a).get("type") != cast(Mapping[str, JSON], b).get("type") else "attrs"
        ops.append({
            "op": "replace",
            "path": f"{path}/{_escape_path_part(key)}" if path else f"/{_escape_path_part(key)}",
            "value": copy_value(cast(Mapping[str, JSON], b).get(key)),
        })
        return

    if (
        isinstance(a, dict)
        and isinstance(b, dict)
        and "type" in a
        and "type" in b
        and a.get("type") != b.get("type")
    ):
        ops.append({
            "op": "replace",
            "path": path,
            "value": copy_value(b),
        })
        return

    if isinstance(a, dict) and isinstance(b, dict):
        _diff_dict(a, b, path, ops)
        return

    if isinstance(a, list) and isinstance(b, list):
        _diff_list(a, b, path, ops)
        return

    ops.append({
        "op": "replace",
        "path": path,
        "value": copy_value(b),
    })


def _diff_dict(
    a: Mapping[str, JSON],
    b: Mapping[str, JSON],
    path: str,
    ops: list[Operation],
) -> None:
    for key in a:
        if key not in b:
            ops.append({
                "op": "remove",
                "path": f"{path}/{_escape_path_part(key)}" if path else f"/{_escape_path_part(key)}",
            })
            continue

        if key in {"attrs", "type"}:
            if a[key] != b[key]:
                ops.append({
                    "op": "replace",
                    "path": f"{path}/{_escape_path_part(key)}" if path else f"/{_escape_path_part(key)}",
                    "value": copy_value(b[key]),
                })
            continue

        _diff(
            a[key],
            b[key],
            f"{path}/{_escape_path_part(key)}" if path else f"/{_escape_path_part(key)}",
            ops,
        )

    for key in b:
        if key not in a:
            ops.append({
                "op": "add",
                "path": f"{path}/{_escape_path_part(key)}" if path else f"/{_escape_path_part(key)}",
                "value": copy_value(b[key]),
            })


def _diff_list(
    a: list[JSON],
    b: list[JSON],
    path: str,
    ops: list[Operation],
) -> None:
    a_keys = [_sequence_key(item) for item in a]
    b_keys = [_sequence_key(item) for item in b]
    matcher = SequenceMatcher(a=a_keys, b=b_keys, autojunk=False)
    offset = 0

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue

        if tag == "delete":
            remove_index = i1 + offset
            for _ in range(i2 - i1):
                ops.append({
                    "op": "remove",
                    "path": f"{path}/{remove_index}",
                })
            offset -= i2 - i1
            continue

        if tag == "insert":
            insert_index = i1 + offset
            for item in b[j1:j2]:
                ops.append({
                    "op": "add",
                    "path": f"{path}/{insert_index}",
                    "value": copy_value(item),
                })
                insert_index += 1
                offset += 1
            continue

        if tag == "replace":
            common = min(i2 - i1, j2 - j1)
            for index in range(common):
                _diff(
                    a[i1 + index],
                    b[j1 + index],
                    f"{path}/{i1 + offset + index}",
                    ops,
                )
            if i2 - i1 > common:
                remove_index = i1 + offset + common
                for _ in range(i2 - i1 - common):
                    ops.append({
                        "op": "remove",
                        "path": f"{path}/{remove_index}",
                    })
                offset -= i2 - i1 - common
            if j2 - j1 > common:
                insert_index = i1 + offset + common
                for item in b[j1 + common : j2]:
                    ops.append({
                        "op": "add",
                        "path": f"{path}/{insert_index}",
                        "value": copy_value(item),
                    })
                    insert_index += 1
                    offset += 1


def _sequence_key(value: JSON) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def apply_patch(doc: JSON, ops: Iterable[Operation]) -> JSON:
    for op in ops:
        _apply_op(doc, op)
    return doc


def _apply_op(doc: JSON, op: Operation) -> None:
    path = op["path"]
    if path == "":
        _apply_root_op(doc, op)
        return

    parts = _split_path(path)
    if not parts:
        _apply_root_op(doc, op)
        return

    parent, last = _resolve_parent(doc, parts)
    if isinstance(parent, list):
        index = len(parent) if last == "-" else int(last)
        if op["op"] == "add":
            parent.insert(index, copy_value(op.get("value")))
        elif op["op"] == "remove":
            parent.pop(index)
        elif op["op"] == "replace":
            parent[index] = copy_value(op.get("value"))
        else:
            raise ValueError(f"Unsupported op: {op['op']}")
        return

    if op["op"] == "add" or op["op"] == "replace":
        parent[last] = copy_value(op.get("value"))
    elif op["op"] == "remove":
        del parent[last]
    else:
        raise ValueError(f"Unsupported op: {op['op']}")


def _apply_root_op(doc: JSON, op: Operation) -> None:
    if op["op"] == "remove":
        if isinstance(doc, list):
            doc.clear()
        elif isinstance(doc, dict):
            doc.clear()
        return

    if op["op"] not in {"add", "replace"}:
        raise ValueError(f"Unsupported op: {op['op']}")

    value = copy_value(op.get("value"))
    if isinstance(doc, list):
        doc.clear()
        if isinstance(value, list):
            doc.extend(value)
        else:
            doc.append(value)
    elif isinstance(doc, dict):
        doc.clear()
        if isinstance(value, dict):
            doc.update(value)
        else:
            doc["value"] = value


def get_from_path(obj: JSON, path: str) -> JSON:
    parts = _split_path(path)
    cur: JSON = obj
    for part in parts:
        if isinstance(cur, list):
            cur = cur[int(part)]
        elif isinstance(cur, dict):
            cur = cur[part]
        else:
            raise ValueError("Invalid path for JSON value.")
    return cur


def copy_value(value: JSON) -> JSON:
    return copy.deepcopy(value)


def _escape_path_part(part: str) -> str:
    return part.replace("~", "~0").replace("/", "~1")


def _unescape_path_part(part: str) -> str:
    return part.replace("~1", "/").replace("~0", "~")


def _split_path(path: str) -> list[str]:
    if path == "":
        return []
    if not path.startswith("/"):
        raise ValueError(f"Invalid JSON pointer: {path}")
    return [_unescape_path_part(part) for part in path.split("/")[1:]]


def _resolve_parent(
    doc: JSON,
    parts: list[str],
) -> tuple[MutableMapping[str, JSON] | MutableSequence[JSON], str]:
    if not parts:
        raise ValueError("Path cannot be empty.")

    parent: JSON = doc
    for part in parts[:-1]:
        if isinstance(parent, list):
            parent = parent[int(part)]
        elif isinstance(parent, dict):
            parent = parent[part]
        else:
            raise ValueError("Invalid path for JSON value.")
    if not isinstance(parent, (list, dict)):
        raise ValueError("Invalid path for JSON value.")
    return parent, parts[-1]


def _node_markup_only_change(a: JSON, b: JSON) -> bool:
    if not isinstance(a, dict) or not isinstance(b, dict):
        return False
    if "type" not in a or "type" not in b:
        return False

    other_keys = (set(a.keys()) | set(b.keys())) - {"type", "attrs"}
    for key in other_keys:
        if a.get(key) != b.get(key):
            return False

    return a.get("type") != b.get("type") or a.get("attrs") != b.get("attrs")


def _parse_options(options: RecreateOptions | None) -> tuple[bool, bool, bool]:
    complex_steps = True
    word_diffs = False
    simplify_diff = True

    if not options:
        return complex_steps, word_diffs, simplify_diff

    if "complex_steps" in options:
        complex_steps = bool(options["complex_steps"])
    elif "complexSteps" in options:
        complex_steps = bool(options["complexSteps"])

    if "word_diffs" in options:
        word_diffs = bool(options["word_diffs"])
    elif "wordDiffs" in options:
        word_diffs = bool(options["wordDiffs"])

    if "simplify_diff" in options:
        simplify_diff = bool(options["simplify_diff"])
    elif "simplifyDiff" in options:
        simplify_diff = bool(options["simplifyDiff"])

    return complex_steps, word_diffs, simplify_diff


__all__ = [
    "Change",
    "Operation",
    "RecreateOptions",
    "RecreateTransform",
    "create_patch",
    "diff_chars",
    "diff_words_with_space",
    "get_from_path",
    "get_replace_step",
    "recreate_transform",
    "remove_marks",
    "simplify_transform",
]
