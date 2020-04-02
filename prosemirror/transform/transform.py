from prosemirror.model import Fragment, MarkType, Node, Slice

from .map import Mapping
from .mark_step import AddMarkStep, RemoveMarkStep
from .replace import close_fragment, covered_depths, fits_trivially, replace_step
from .replace_step import ReplaceAroundStep, ReplaceStep
from .structure import can_change_type, insert_point
from . import structure
from . import replace


class TransformError(ValueError):
    pass


class Transform:
    # functions from .structure exposed by Transform
    join_point = structure.join_point
    can_join = structure.can_join
    can_split = structure.can_split
    insert_point = structure.insert_point
    drop_point = structure.drop_point
    lift_target = structure.lift_target
    find_wrapping = structure.find_wrapping
    replace_step = replace.replace_step

    def __init__(self, doc):
        self.doc = doc
        self.steps = []
        self.docs = []
        self.mapping = Mapping()

    @property
    def before(self):
        return self.docs[0] if self.docs else self.doc

    def step(self, object):
        result = self.maybe_step(object)
        if result.failed:
            raise TransformError(result.failed)
        return self

    def maybe_step(self, step):
        result = step.apply(self.doc)
        if not result.failed:
            self.add_step(step, result.doc)
        return result

    def doc_changed(self):
        return bool(len(self.steps))

    def add_step(self, step, doc):
        self.docs.append(self.doc)
        self.steps.append(step)
        self.mapping.append_map(step.get_map())
        self.doc = doc

    # mark.js
    def add_mark(self, from_, to, mark):
        removed = []
        added = []
        removing = None
        adding = None

        def iteratee(node, pos, parent, *args):
            nonlocal removing
            nonlocal adding
            if not node.is_inline:
                return
            marks = node.marks
            if not mark.is_in_set(marks) and parent.type.allows_mark_type(mark.type):
                start = max(pos, from_)
                end = min(pos + node.node_size, to)
                new_set = mark.add_to_set(marks)
                for i in range(len(marks)):
                    if not marks[i].is_in_set(new_set):
                        if (
                            removing
                            and removing.to == start
                            and removing.mark.eq(marks[i])
                        ):
                            removing.to = end
                        else:
                            removing = RemoveMarkStep(start, end, marks[i])
                            removed.append(removing)
                if adding and adding.to == start:
                    adding.to = end
                else:
                    adding = AddMarkStep(start, end, mark)
                    added.append(adding)

        self.doc.nodes_between(from_, to, iteratee)
        for item in removed:
            self.step(item)
        for item in added:
            self.step(item)
        return self

    def remove_mark(self, from_, to, mark=None):
        matched = []
        step = 0

        def iteratee(node, pos, *args):
            nonlocal step
            if not node.is_inline:
                return
            step += 1
            to_remove = None
            if isinstance(mark, MarkType):
                found = mark.is_in_set(node.marks)
                if found:
                    to_remove = [found]
            elif mark:
                if mark.is_in_set(node.marks):
                    to_remove = [mark]
            else:
                to_remove = node.marks
            if to_remove:
                end = min(pos + node.node_size, to)
                for style in to_remove:
                    found = None
                    for m in matched:
                        if m["step"] == step - 1 and style.eq(m["style"]):
                            found = m
                    if found:
                        found["to"] = end
                        found["step"] = step
                    else:
                        matched.append(
                            {
                                "style": style,
                                "from": max(pos, from_),
                                "to": end,
                                "step": step,
                            }
                        )

        self.doc.nodes_between(from_, to, iteratee)
        for item in matched:
            self.step(RemoveMarkStep(item["from"], item["to"], item["style"]))
        return self

    def clear_incompatible(self, pos, parent_type, match=None):
        if match is None:
            match = parent_type.content_match
        node = self.doc.node_at(pos)
        del_steps = []
        cur = pos + 1
        for i in range(node.child_count):
            child = node.child(i)
            end = cur + child.node_size
            allowed = match.match_type(child.type, child.attrs)
            if not allowed:
                del_steps.append(ReplaceStep(cur, end, Slice.empty))
            else:
                match = allowed
                for j in range(len(child.marks)):
                    if not parent_type.allows_mark_type(child.marks[j].type):
                        self.step(RemoveMarkStep(cur, end, child.marks[j]))
            cur = end
        if not match.valid_end:
            fill = match.fill_before(Fragment.empty, True)
            self.replace(cur, cur, Slice(fill, 0, 0))
        for item in reversed(del_steps):
            self.step(item)
        return self

    # replace.js
    def replace(self, from_, to=None, slice=None):
        if to is None:
            to = from_
        if slice is None:
            slice = Slice.empty
        step = replace_step(self.doc, from_, to, slice)
        if step:
            self.step(step)
        return self

    def replace_with(self, from_, to, content):
        return self.replace(from_, to, Slice(Fragment.from_(content), 0, 0))

    def delete(self, from_, to):
        return self.replace(from_, to, Slice.empty)

    def insert(self, pos, content):
        return self.replace_with(pos, pos, content)

    def replace_range(self, from_, to, slice):
        if not slice.size:
            return self.delete_range(from_, to)
        from__ = self.doc.resolve(from_)
        to_ = self.doc.resolve(to)
        if fits_trivially(from__, to_, slice):
            return self.step(ReplaceStep(from_, to, slice))
        target_depths = covered_depths(from__, self.doc.resolve(to))
        if target_depths and target_depths[-1] == 0:
            target_depths.pop()
        preferred_target = -(from__.depth + 1)
        target_depths.insert(0, preferred_target)
        d = from__.depth
        pos = from__.pos - 1
        while d > 0:
            spec = from__.node(d).type.spec
            if spec.get("defining") or spec.get("isolating"):
                break
            if d in target_depths:
                preferred_target = d
            elif from__.before(d) == pos:
                target_depths.insert(1, -d)
            d -= 1
            pos -= 1
        preferred_target_index = target_depths.index(preferred_target)
        left_nodes = []
        preferred_depth = slice.open_start
        content = slice.content
        i = 0
        while True:
            node = content.first_child
            left_nodes.append(node)
            if i == slice.open_start:
                break
            content = node.content
            i += 1
        if (
            preferred_depth > 0
            and left_nodes[preferred_depth - 1].type.spec.get("defining")
            and from__.node(preferred_target_index).type.name
            != left_nodes[preferred_depth - 1].type.name
        ):
            preferred_depth -= 1
        elif (
            preferred_depth >= 2
            and left_nodes[preferred_depth - 1].is_text_block
            and left_nodes[preferred_depth - 2].type.spec.get("defining")
            and from__.node(preferred_target_index).type.name
            != left_nodes[preferred_depth - 2].type.name
        ):
            preferred_depth -= 2

        for j in range(slice.open_start, -1, -1):
            open_depth = (j + preferred_depth + 1) % (slice.open_start + 1)
            if len(left_nodes) > open_depth:
                insert = left_nodes[open_depth]
            else:
                continue
            for i in range(len(target_depths)):
                target_depth = target_depths[
                    (i + preferred_target_index) % len(target_depths)
                ]
                expand = True
                if target_depth < 0:
                    expand = False
                    target_depth = -target_depth
                parent = from__.node(target_depth - 1)
                index = from__.index(target_depth - 1)
                if parent.can_replace_with(index, index, insert.type, insert.marks):
                    return self.replace(
                        from__.before(target_depth),
                        to_.after(target_depth) if expand else to,
                        Slice(
                            close_fragment(
                                slice.content, 0, slice.open_start, open_depth, None
                            ),
                            open_depth,
                            slice.open_end,
                        ),
                    )
        return self.replace(from_, to, slice)

    def replace_range_with(self, from_, to, node):
        if (
            not node.is_inline
            and from_ == to
            and self.doc.resolve(from_).parent.content.size
        ):
            point = insert_point(self.doc, from_, node.type)
            if point is not None:
                from_ = to = point
        return self.replace_range(from_, to, Slice(Fragment.from_(node), 0, 0))

    def delete_range(self, from_, to):
        from__ = self.doc.resolve(from_)
        to_ = self.doc.resolve(to)
        covered = covered_depths(from__, to_)
        for i in range(len(covered)):
            depth = covered[i]
            last = len(covered) - 1 == i
            if (last and depth == 0) or from__.node(depth).type.content_match.valid_end:
                return self.delete(from__.start(depth), to_.end(depth))
            if depth > 0 and (
                last
                or from__.node(depth - 1).can_replace(
                    from__.index(depth - 1), to_.index_after(depth - 1)
                )
            ):
                return self.delete(from__.before(depth), to_.after(depth))
        for d in range(1, from__.depth + 1):
            if from_ - from__.start(d) == from__.depth - d and to > from__.end(d):
                return self.delete(from__.before(d), to)
        return self.delete(from_, to)

    # structure.js
    def lift(self, range_, target):
        from__ = range_.from_
        to_ = range_.to
        depth = range_.depth

        gap_start = from__.before(depth + 1)
        gap_end = to_.after(depth + 1)
        start = gap_start
        end = gap_end

        before = Fragment.empty
        open_start = 0
        d = depth
        splitting = False
        while d > target:
            if splitting or from__.index(d) > 0:
                splitting = True
                before = Fragment.from_(from__.node(d).copy(before))
                open_start += 1
            else:
                start -= 1
            d -= 1
        after = Fragment.empty
        open_end = 0
        d = depth
        splitting = False
        while d > target:
            if splitting or to_.after(d + 1) < to_.end(d):
                splitting = True
                after = Fragment.from_(to_.node(d).copy(after))
                open_end += 1
            else:
                end += 1
            d -= 1
        return self.step(
            ReplaceAroundStep(
                start,
                end,
                gap_start,
                gap_end,
                Slice(before.append(after), open_start, open_end),
                before.size - open_start,
                True,
            )
        )

    def wrap(self, range_, wrappers):
        content = Fragment.empty
        i = len(wrappers) - 1
        while i >= 0:
            content = Fragment.from_(
                wrappers[i]["type"].create(wrappers[i].get("attrs"), content)
            )
            i -= 1
        start = range_.start
        end = range_.end
        return self.step(
            ReplaceAroundStep(
                start, end, start, end, Slice(content, 0, 0), len(wrappers), True
            )
        )

    def set_block_type(self, from_, to, type, attrs):
        if to is None:
            to = from_
        if not type.is_text_block:
            raise ValueError("Type given to set_block_type should be a textblock")
        map_from = len(self.steps)

        def iteratee(node: "Node", pos, *args):
            if (
                node.is_text_block
                and not node.has_markup(type, attrs)
                and can_change_type(
                    self.doc, self.mapping.slice(map_from).map(pos), type
                )
            ):
                self.clear_incompatible(self.mapping.slice(map_from).map(pos, 1), type)
                mapping = self.mapping.slice(map_from)
                start_m = mapping.map(pos, 1)
                end_m = mapping.map(pos + node.node_size, 1)
                self.step(
                    ReplaceAroundStep(
                        start_m,
                        end_m,
                        start_m + 1,
                        end_m - 1,
                        Slice(
                            Fragment.from_(type.create(attrs, None, node.marks)), 0, 0
                        ),
                        1,
                        True,
                    )
                )
                return False

        self.doc.nodes_between(from_, to, iteratee)
        return self

    def set_node_markup(self, pos, type, attrs, marks=None):
        node = self.doc.node_at(pos)
        if not node:
            raise ValueError("No node at given position")
        if not type:
            type = node.type
        new_node = type.create(attrs, None, marks or node.marks)
        if node.is_leaf:
            return self.replace_with(pos, pos + node.node_size, new_node)
        if not type.valid_content(node.content):
            raise ValueError(f"Invalid content for node type {type.name}")
        return self.step(
            ReplaceAroundStep(
                pos,
                pos + node.node_size,
                pos + 1,
                pos + node.node_size - 1,
                Slice(Fragment.from_(new_node), 0, 0),
                1,
                True,
            )
        )

    def split(self, pos, depth=None, types_after=None):
        if depth is None:
            depth = 1
        pos_ = self.doc.resolve(pos)
        before = Fragment.empty
        after = Fragment.empty
        d = pos_.depth
        e = pos_.depth - depth
        i = depth - 1
        while d > e:
            before = Fragment.from_(pos_.node(d).copy(before))
            type_after = None
            if types_after and len(types_after) > i:
                type_after = types_after[i]
            after = Fragment.from_(
                type_after["type"].create(type_after.get("attrs"), after)
                if type_after
                else pos_.node(d).copy(after)
            )
            d -= 1
            i -= 1
        return self.step(
            ReplaceStep(pos, pos, Slice(before.append(after), depth, depth), True)
        )

    def join(self, pos, depth=1):
        step = ReplaceStep(pos - depth, pos + depth, Slice.empty, True)
        return self.step(step)
