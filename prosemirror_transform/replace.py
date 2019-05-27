from prosemirror_model import Fragment, Slice
from .replace_step import ReplaceAroundStep, ReplaceStep


def replace_step(doc, from_, to=None, slice=None):
    if to is None:
        to = from_
    if slice is None:
        slice = Slice.empty
    if from_ == to and not slice.size:
        return None

    from__ = doc.resolve(from_)
    to_ = doc.resolve(to)
    if fits_trivially(from__, to_, slice):
        return ReplaceStep(from_, to, slice)
    placed = place_slice(from__, slice)
    fitted_left = fit_left(from__, placed)
    fitted = fit_right(from__, to_, fitted_left)
    if not fitted:
        return None
    if fitted_left.size != fitted.size and can_move_text(from__, to_, fitted_left):
        d = to_.depth
        after = to_.after(d)
        while d > 1 and after == to_.end(d - 1):
            d -= 1
            after += 1
        fittedAfter = fit_right(from__, doc.resolve(after), fitted_left)
        if fittedAfter:
            return ReplaceAroundStep(
                from_, after, to, to_.end(), fittedAfter, fitted_left.size
            )
    return ReplaceStep(from_, to, fitted, None) if (fitted or from_ != to) else None


def fit_left_innter(from__, depth, placed, placed_below):
    content = Fragment.empty
    open_end = 0
    placed_here = placed[depth] if len(placed) > depth else None
    if from__.depth > depth:
        inner = fit_left_innter(from__, depth + 1, placed, placed_below or placed_here)
        open_end = inner["open_end"] + 1
        content = Fragment.from_(from__.node(depth + 1).copy(inner["content"]))
    if placed_here:
        content = content.append(placed_here["content"])
        open_end = placed_here["open_end"]
    if placed_below:
        content = content.append(
            from__.node(depth)
            .content_match_at(from__.index_after(depth))
            .fill_before(Fragment.empty, True)
        )

    return {"content": content, "open_end": open_end}


def fit_left(from__, placed):
    inner_res = fit_left_innter(from__, 0, placed, False)
    content = inner_res["content"]
    open_end = inner_res["open_end"]
    return Slice(content, from__.depth, open_end or 0)


def fit_right_join(content, parent, from__, to_, depth, open_start, open_end):
    match = None
    count = content.child_count
    match_count = count - (1 if open_end > 0 else 0)
    parent_node = parent if open_start < 0 else from__.node(depth)
    if open_start < 0:
        match = parent_node.content_match_at(match_count)
    elif count == 1 and open_end > 0:
        match = parent_node.content_match_at(
            from__.index(depth) if open_start else from__.index_after(depth)
        )
    else:
        match = parent_node.content_match_at(from__.index_after(depth)).match_fragment(
            content, (1 if count > 0 and open_start else 0), match_count
        )
    to_node = to_.node(depth)
    if open_end > 0 and depth < to_.depth:
        after = to_node.content.cut_by_index(to_.index_after(depth)).add_to_start(
            content.last_child
        )
        joinable = match.fill_before(after, True)
        if joinable and joinable.size and open_start > 0 and count == 1:
            joinable = None
        if joinable:
            inner = fit_right_join(
                content.last_child.content,
                content.last_child,
                from__,
                to_,
                depth + 1,
                (open_start - 1 if count == 1 else -1),
                open_end - 1,
            )
            if inner:
                last = content.last_child.copy(inner)
                if joinable.size:
                    return (
                        content.cut_by_index(0, count - 1)
                        .append(joinable)
                        .add_to_end(last)
                    )
                return content.replace_child(count - 1, last)
    if open_end > 0:
        match = match.match_type(
            (
                from__.node(depth + 1)
                if count == 1 and open_start > 0
                else content.last_child
            ).type
        )
    to_index = to_.index(depth)
    if to_index == to_node.child_count and not to_node.type.compatible_content(
        parent.type
    ):
        return None
    joinable = match.fill_before(to_node.content, True, to_index)
    i = to_index
    while i < to_node.content.child_count:
        if not parent_node.type.allows_marks(to_node.content.child(i).marks):
            joinable = None
        i += 1
    if not joinable:
        return None

    if open_end > 0:
        closed = fit_right_closed(
            content.last_child,
            open_end - 1,
            from__,
            depth + 1,
            (open_start - 1 if count == 1 else -1),
        )
        content = content.replace_child(count - 1, closed)
    content = content.append(joinable)
    if to_.depth > depth:
        content = content.add_to_end(fit_right_separate(to_, depth + 1))
    return content


def fit_right_closed(node, open_end, from__, depth, open_start):
    match = None
    content = node.content
    count = content.child_count
    if open_start >= 0:
        match = (
            from__.node(depth)
            .content_match_at(from__.index_after(depth))
            .match_fragment(content, 1 if open_start > 0 else 0, count)
        )
    else:
        match = node.content_match_at(count)
    if open_end > 0:
        closed = fit_right_closed(
            content.last_child,
            open_end - 1,
            from__,
            depth + 1,
            open_start - 1 if count == 1 else -1,
        )
        content = content.replace_child(count - 1, closed)
    return node.copy(content.append(match.fill_before(Fragment.empty, True)))


def fit_right_separate(to_, depth):
    node = to_.node(depth)
    fill = node.content_match_at(0).fill_before(node.content, True, to_.index(depth))
    if to_.depth > depth:
        fill = fill.add_to_end(fit_right_separate(to_, depth + 1))
    return node.copy(fill)


def normalize_slice(content, open_start, open_end):
    while open_start > 0 and open_end > 0 and content.child_count == 1:
        content = content.first_child.content
        open_start -= 1
        open_end -= 1
    return Slice(content, open_start, open_end)


def fit_right(from__, to_, slice):
    fitted = fit_right_join(
        slice.content, from__.node(0), from__, to_, 0, slice.open_start, slice.open_end
    )
    if not fitted:
        return None
    return normalize_slice(fitted, slice.open_start, to_.depth)


def fits_trivially(from__, to_, slice):
    if not slice.open_start and not slice.open_end and from__.start() == to_.start():
        return from__.parent.can_replace(from__.index(), to_.index(), slice.content)
    return False


def can_move_text(from__, to_, slice):
    if not to_.parent.is_text_block:
        return False
    parent = (
        node_right(slice.content, slice.open_end)
        if slice.open_end
        else from__.node(from__.depth - (slice.open_start - slice.open_end))
    )
    if not parent.is_text_block:
        return False
    for i in range(to_.index(), to_.parent.child_count):
        if not parent.type.allows_marks(to_.parent.child(i).marks):
            return False
    match = None
    if slice.open_end:
        match = parent.content_match_at(parent.child_count)
    else:
        match = parent.content_match_at(parent.child_count)
        if slice.size:
            match = match.match_fragment(slice.content, 1 if slice.open_start else 0)

    match = match.match_fragment(to_.parent.content, to_.index())
    return match.valid_end if match else False


def node_right(content, depth):
    for i in range(1, depth):
        content = content.last_child.content
    return content.last_child


def place_slice(from__, slice):
    frontier = Frontier(from__)
    pass_ = 1
    while slice.size and pass_ <= 3:
        slice = frontier.place_slice(
            slice.content, slice.open_start, slice.open_end, pass_
        )
        pass_ += 1
    while len(frontier.open):
        frontier.close_node()
    return frontier.placed


class SparseList(list):
    def __setitem__(self, index, value):
        missing = index - len(self) + 1
        if missing > 0:
            self.extend([None] * missing)
        list.__setitem__(self, index, value)

    def __getitem__(self, index):
        try:
            return list.__getitem__(self, index)
        except IndexError:
            return None


class Frontier:
    def __init__(self, pos_):
        self.open = []
        for d in range(pos_.depth + 1):
            parent = pos_.node(d)
            match = parent.content_match_at(pos_.index_after(d))
            self.open.append(
                {
                    "parent": parent,
                    "match": match,
                    "content": Fragment.empty,
                    "wrapper": False,
                    "open_end": 0,
                    "depth": d,
                }
            )
        self.placed = SparseList()

    def place_slice(self, fragment, open_start, open_end, pass_, parent=None):
        if open_start > 0:
            first = fragment.first_child
            inner = self.place_slice(
                first.content,
                max(0, open_start - 1),
                (open_end - 1 if open_end and fragment.child_count == 1 else 0),
                pass_,
                first,
            )
            if inner.content != first.content:
                if inner.content.size:
                    fragment = fragment.replace_child(0, first.copy(inner.content))
                    open_start = inner.open_start + 1
                else:
                    if fragment.child_count == 1:
                        open_end = 0
                    fragment = fragment.cut_by_index(1)
                    open_start = 0
        result = self.place_content(fragment, open_start, open_end, pass_, parent)
        if pass_ > 2 and result.size and open_start == 0:
            for i in range(result.content.child_count):
                child = result.content.child(i)
                self.place_content(
                    child.content,
                    0,
                    (
                        open_end - 1
                        if open_end and i == result.content.child_count - 1
                        else 0
                    ),
                    pass_,
                    child,
                )
            result = Fragment.empty
        return result

    def place_content(self, fragment, open_start, open_end, pass_, parent=None):
        i = 0
        while i < fragment.child_count:
            child = fragment.child(i)
            placed = False
            last = i == (fragment.child_count - 1)
            d = len(self.open) - 1
            while d >= 0:
                open = self.open[d]
                wrap = None
                if pass_ > 1:
                    wrap = open["match"].find_wrapping(child.type)
                    if wrap and not (parent and len(wrap) and wrap[-1] == parent.type):
                        while len(self.open) - 1 > d:
                            self.close_node()
                        w = 0
                        while w < len(wrap):
                            open["match"] = open["match"].match_type(wrap[w])
                            d += 1
                            open = {
                                "parent": wrap[w].create(),
                                "match": wrap[w].content_match,
                                "content": Fragment.empty,
                                "wrapper": True,
                                "open_end": 0,
                                "depth": d + w,
                            }
                            self.open.append(open)
                            w += 1
                match = open["match"].match_type(child.type)
                if not match:
                    fill = open["match"].fill_before(Fragment.from_(child))
                    if fill:
                        for j in range(fill.child_count):
                            ch = fill.child(j)
                            self.add_node(open, ch, 0)
                            match = open["match"].match_fragment(ch)
                    elif parent and open["match"].match_type(parent.type):
                        break
                    else:
                        d -= 1
                        continue
                while len(self.open) - 1 > d:
                    self.close_node()
                child = child.mark(open["parent"].type.allowed_marks(child.marks))
                if open_start:
                    child = close_node_start(child, open_start, open_end if last else 0)
                    open_start = 0
                self.add_node(open, child, open_end if last else 0)
                open["match"] = match
                if last:
                    open_end = 0
                placed = True
                break
            if not placed:
                break
            i += 1
        if len(self.open) > 1 and (
            i > 0
            and i == fragment.child_count
            or parent
            and self.open[-1]["parent"].type == parent.type
        ):
            self.close_node()
        return Slice(fragment.cut_by_index(i), open_start, open_end)

    def add_node(self, open, node, open_end):
        open["content"] = close_fragment_end(
            open["content"], open["open_end"]
        ).add_to_end(node)
        open["open_end"] = open_end

    def close_node(self):
        open = self.open.pop()
        if open["content"].size == 0:
            pass
        elif open["wrapper"]:
            self.add_node(
                self.open[-1],
                open["parent"].copy(open["content"]),
                open["open_end"] + 1,
            )
        else:
            self.placed[open["depth"]] = {
                "depth": open["depth"],
                "content": open["content"],
                "open_end": open["open_end"],
            }


def close_node_start(node, open_start, open_end):
    content = node.content
    if open_start > 1:
        first = close_node_start(
            node.first_child,
            open_start - 1,
            open_end - 1 if node.child_count == 1 else 0,
        )
        content = node.content.replace_child(0, first)
    fill = node.type.content_match.fill_before(content, open_end == 0)
    return node.copy(fill.append(content))


def close_node_end(node, depth):
    content = node.content
    if depth > 1:
        last = close_node_end(node.last_child, depth - 1)
        content = node.content.replace_child(node.child_count - 1, last)
    fill = node.content_match_at(node.child_count).fill_before(Fragment.empty, True)
    return node.copy(content.append(fill))


def close_fragment_end(fragment, depth):
    if depth:
        return fragment.replace_child(
            fragment.child_count - 1, close_node_end(fragment.last_child, depth)
        )
    else:
        return fragment


def close_fragment(fragment, depth, old_open, new_open, parent):
    if depth < old_open:
        first = fragment.first_child
        fragment = fragment.replace_child(
            0,
            first.copy(
                close_fragment(first.content, depth + 1, old_open, new_open, first)
            ),
        )
    if depth > new_open:
        fragment = (
            parent.content_match_at(0).fill_before(fragment, True).append(fragment)
        )
    return fragment


def covered_depths(from__, to_):
    result = []
    min_depth = min(from__.depth, to_.depth)
    for d in range(min_depth, -1, -1):
        start = from__.start(d)
        if (
            (start < from__.pos - (from__.depth - d))
            or (to_.end(d) > to_.pos + (to_.depth - d))
            or (from__.node(d).type.spec.get("isolation"))
            or (to_.node(d).type.spec.get("isolation"))
        ):
            break
        if start == to_.start(d):
            result.append(d)
    return result
