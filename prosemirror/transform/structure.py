from prosemirror.model import Node


def can_cut(node, start, end):
    if start == 0 or node.can_replace(start, node.child_count):
        return (end == node.child_count) or node.can_replace(0, end)
    return False


def lift_target(range_):
    parent = range_.parent
    content = parent.content.cut_by_index(range_.start_index, range_.end_index)
    depth = range_.depth
    while True:
        node = range_.from_.node(depth)
        index = range_.from_.index(depth)
        end_index = range_.to.index_after(depth)
        if depth < range_.depth and node.can_replace(index, end_index, content):
            return depth
        if (
            depth == 0
            or node.type.spec.get("isolating")
            or not can_cut(node, index, end_index)
        ):
            break
        depth -= 1


def find_wrapping(range_, node_type, attrs=None, inner_range=None):
    if inner_range is None:
        inner_range = range_
    around = find_wrapping_outside(range_, node_type)
    inner = False
    if around is not None:
        inner = find_wrapping_inside(inner_range, node_type)
    else:
        return None
    if inner is None:
        return None
    return (
        [with_attrs(item) for item in around]
        + [{"type": node_type, "attrs": attrs}]
        + [with_attrs(item) for item in inner]
    )


def with_attrs(type):
    return {"type": type, "attrs": None}


def find_wrapping_outside(range_, type):
    parent = range_.parent
    start_index = range_.start_index
    end_index = range_.end_index
    around = parent.content_match_at(start_index).find_wrapping(type)
    if around is None:
        return None
    outer = around[0] if len(around) and around[0] else type
    return around if parent.can_replace_with(start_index, end_index, outer) else None


def find_wrapping_inside(range_, type):
    parent = range_.parent
    start_index = range_.start_index
    end_index = range_.end_index
    inner = parent.child(start_index)
    inside = type.content_match.find_wrapping(inner.type)
    if inside is None:
        return None
    last_type = inside[-1] if len(inside) else type
    inner_match = last_type.content_match
    i = start_index
    while inner_match and i < end_index:
        inner_match = inner_match.match_type(parent.child(i).type)
        i += 1
    if not inner_match or not inner_match.valid_end:
        return None
    return inside


def can_change_type(doc, pos, type):
    pos_ = doc.resolve(pos)
    index = pos_.index()
    return pos_.parent.can_replace_with(index, index + 1, type)


def can_split(doc, pos, depth=None, types_after=None):
    if depth is None:
        depth = 1
    pos_ = doc.resolve(pos)
    base = pos_.depth - depth
    inner_type = None
    if types_after:
        inner_type = types_after[-1]
    if not inner_type:
        inner_type = pos_.parent
    if isinstance(inner_type, Node):
        if (
            base < 0
            or pos_.parent.type.spec.get("isolating")
            or not pos_.parent.can_replace(pos_.index(), pos_.parent.child_count)
            or not inner_type.type.valid_content(
                pos_.parent.content.cut_by_index(pos_.index(), pos_.parent.child_count)
            )
        ):
            return False
    elif isinstance(inner_type, dict):
        if (
            base < 0
            or pos_.parent.type.spec.get("isolating")
            or not pos_.parent.can_replace(pos_.index(), pos_.parent.child_count)
            or not inner_type["type"].valid_content(
                pos_.parent.content.cut_by_index(pos_.index(), pos_.parent.child_count)
            )
        ):
            return False
    d = pos_.depth - 1
    i = depth - 2
    while d > base:
        node = pos_.node(d)
        index = pos_.index(d)
        if node.type.spec.get("isolating"):
            return False
        rest = node.content.cut_by_index(index, node.child_count)
        if types_after and len(types_after) > i:
            override_child = types_after[i + 1]
            rest = rest.replace_child(
                0, override_child["type"].create(override_child.get("attrs"))
            )
        after = None
        if types_after and len(types_after) > i:
            after = types_after[i]
        if not after:
            after = node
        if isinstance(after, dict):
            if not node.can_replace(index + 1, node.child_count) or not after[
                "type"
            ].valid_content(rest):
                return False
        if isinstance(after, Node):
            if after != node:
                rest = rest.replace_child(0, after.type.create(after.attrs))
            if not node.can_replace(
                index + 1, node.child_count
            ) or not after.type.valid_content(rest):
                return False
        d -= 1
        i -= 1
    index = pos_.index_after(base)
    base_type = types_after[0] if types_after else None
    return pos_.node(base).can_replace_with(
        index, index, base_type["type"] if base_type else pos_.node(base + 1).type
    )


def can_join(doc, pos):
    pos_ = doc.resolve(pos)
    index = pos_.index()
    return (
        pos_.parent.can_replace(index, index + 1)
        if joinable(pos_.node_before, pos_.node_after)
        else None
    )


def joinable(a, b):
    if a and b and not a.is_leaf:
        return a.can_append(b)
    return False


def join_point(doc, pos, dir=-1):
    pos_ = doc.resolve(pos)
    for d in range(pos_.depth, -1, -1):
        before = None
        after = None
        index = pos_.index(d)
        if d == pos_.depth:
            before = pos_.node_before
            after = pos_.node_after
        elif dir > 0:
            before = pos_.node(d + 1)
            index += 1
            after = pos_.node(d).maybe_child(index)
        else:
            before = pos_.node(d).maybe_child(index - 1)
            after = pos_.node(d + 1)
        if (
            before
            and not before.is_text_block
            and joinable(before, after)
            and pos_.node(d).can_replace(index, index + 1)
        ):
            return pos
        if d == 0:
            break
        pos = pos_.before(d) if dir < 0 else pos_.after(d)


def insert_point(doc, pos, node_type):
    pos_ = doc.resolve(pos)
    if pos_.parent.can_replace_with(pos_.index(), pos_.index(), node_type):
        return pos
    if pos_.parent_offset == 0:
        for d in range(pos_.depth - 1, -1, -1):
            index = pos_.index(d)
            if pos_.node(d).can_replace_with(index, index, node_type):
                return pos_.before(d + 1)
            if index > 0:
                return None
    if pos_.parent_offset == pos_.parent.content.size:
        for d in range(pos_.depth - 1, -1, -1):
            index = pos_.index_after(d)
            if pos_.node(d).can_replace_with(index, index, node_type):
                return pos_.after(d + 1)
            if index < pos_.node(d).child_count:
                return None


def drop_point(doc, pos, slice):
    pos_ = doc.resolve(pos)
    if not slice.content.size:
        return pos
    content = slice.content
    for i in range(slice.open_start):
        content = content.first_child.content
    pass_ = 1
    while pass_ <= (2 if slice.open_start == 0 and slice.size else 1):
        for d in range(pos_.depth, 0, -1):
            if d == pos_.depth:
                bias = 0
            elif pos_.pos <= (pos_.start(d + 1) + pos_.end(d + 1)) / 2:
                bias = -1
            else:
                bias = 1
            insert_pos = pos_.index(d) + (1 if bias > 0 else 0)
            parent = pos_.node(d)
            fits = False
            if pass_ == 1:
                fits = parent.can_replace(insert_pos, insert_pos, content)
            else:
                wrapping = parent.content_match_at(insert_pos).find_wrapping(
                    content.first_child.type
                )
                fits = wrapping and parent.can_replace_with(
                    insert_pos, insert_pos, wrapping[0]
                )
            if fits:
                if bias == 0:
                    return pos_.pos
                elif bias < 0:
                    return pos_.before(d + 1)
                else:
                    return pos_.after(d + 1)
        pass_ += 1
    return None
