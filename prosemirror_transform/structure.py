def can_cut(node, start, end):
    if start == 0 or node.can_replace(start, node.child_count):
        return (end == node.child_count) or node.can_replace(0, end)
    return False


def lift_target(range_):
    parent = range_.parent
    content = parent.content.cut_by_index(range_.start_index, range_.end_index)
    for depth in range(range_.depth, -1, -1):
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


def find_wrapping(range_, node_type, attrs, inner_range=None):
    if inner_range is None:
        inner_range = range_
    around = find_wrapping_outside(range_, node_type)
    inner = False
    if around:
        inner = find_wrapping_inside(inner_range, node_type)
    if not inner:
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
    outer = around[0] if len(around) else type
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


def can_split(doc, pos, depth=1, types_after=None):
    pos_ = doc.resolve(pos)
    base = pos.depth - depth
    if types_after:
        inner_type = types_after[-1]
    else:
        inner_type = pos_.parent
    if (
        base < 0
        or pos_.parent.type.spec.get("isolating")
        or not pos_.parent.can_replace(pos_.index(), pos_.parent.child_count)
        or not inner_type.type.valid_content(
            pos_.parent.content.cut_by_index(pos_.index(), pos_.parent.child_count)
        )
    ):
        return False
    d = pos_.depth
    i = depth - 2
    while d > base:
        node = pos_.node(d)
        index = pos_.index(d)
        if node.type.spec.get("isolating"):
            return False
        rest = node.content.cut_by_index(index, node.child_count)
        if types_after and len(types_after) > i:
            after = types_after[i]
        else:
            after = node
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
        index, index, base_type.type if base_type else pos_.node(base + 1).type
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
        if d == pos_.depth:
            before = pos_.node_before
            after = pos_.node_after
        elif dir > 0:
            before = pos_.node(d + 1)
            after = pos_.node(d).maybe_child(pos_.index(d) + 1)
        else:
            before = pos_.node(d).maybe_child(pos_.index(d) - 1)
            after = pos_.node(d + 1)
        if before and not before.is_text_block and joinable(before, after):
            return pos
        if d == 0:
            break
        pos = pos_.before(d) if dir < 0 else pos_.after(d)


def insert_point(doc, pos, node_type):
    pos_ = doc.resolve(pos)
    if pos_.parent.can_replace_with(pos_.index(), pos_.index(), node_type):
        return pos
    if pos_.parent_offset == 0:
        for d in range(pos_.depth - 1, 0, -1):
            index = pos_.index(d)
            if pos_.node(d).can_replace_with(index, index, node_type):
                return pos_.before(d + 1)
            if index > 0:
                return None
    if pos_.parent_offset == pos_.parent.content.size:
        for d in range(pos_.depth - 1, 0, -1):
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
            if pass_ == 1:
                cond = pos_.node(d).can_replace(insert_pos, insert_pos, content)
            else:
                cond = (
                    pos_.node(d)
                    .content_match_at(insert_pos)
                    .find_wrapping(content.first_child.type)
                )
            if cond:
                if bias == 0:
                    return pos_.pos
                elif bias < 0:
                    return pos_.before(d + 1)
                else:
                    return pos_.after(d + 1)
        pass_ += 1
    return None
