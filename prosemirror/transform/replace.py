from typing import cast

from prosemirror.model import (
    ContentMatch,
    Fragment,
    Node,
    NodeType,
    ResolvedPos,
    Slice,
)
from prosemirror.transform.replace_step import ReplaceAroundStep, ReplaceStep
from prosemirror.transform.step import Step
from prosemirror.utils import Attrs


def replace_step(
    doc: Node,
    from_: int,
    to: int | None = None,
    slice: Slice | None = None,
) -> Step | None:
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
    return Fitter(from__, to_, slice).fit()


def fits_trivially(
    from__: ResolvedPos,
    to_: ResolvedPos,
    slice: Slice,
) -> bool:
    if not slice.open_start and not slice.open_end and from__.start() == to_.start():
        return from__.parent.can_replace(from__.index(), to_.index(), slice.content)
    return False


class _FrontierItem:
    __slots__ = ("match", "type")

    def __init__(self, type_: NodeType, match: ContentMatch) -> None:
        self.type = type_
        self.match = match


class _Fittable:
    __slots__ = ("frontier_depth", "inject", "parent", "slice_depth", "wrap")

    def __init__(
        self,
        slice_depth: int,
        frontier_depth: int,
        parent: Node | None,
        inject: Fragment | None = None,
        wrap: list[NodeType] | None = None,
    ) -> None:
        self.slice_depth = slice_depth
        self.frontier_depth = frontier_depth
        self.parent = parent
        self.inject = inject
        self.wrap = wrap


class _CloseLevel:
    __slots__ = ("depth", "fit", "move")

    def __init__(
        self,
        depth: int,
        fit: Fragment,
        move: ResolvedPos,
    ) -> None:
        self.depth = depth
        self.fit = fit
        self.move = move


class Fitter:
    __slots__ = ("from__", "frontier", "placed", "to_", "unplaced")

    def __init__(self, from__: ResolvedPos, to_: ResolvedPos, slice: Slice) -> None:
        self.to_ = to_
        self.from__ = from__
        self.unplaced = slice

        self.frontier: list[_FrontierItem] = []
        for i in range(from__.depth + 1):
            node = from__.node(i)
            self.frontier.append(
                _FrontierItem(node.type, node.content_match_at(from__.index_after(i))),
            )

        self.placed: Fragment = Fragment.empty
        for i in range(from__.depth, 0, -1):
            self.placed = Fragment.from_(from__.node(i).copy(self.placed))

    @property
    def depth(self) -> int:
        return len(self.frontier) - 1

    def fit(self) -> Step | None:
        while self.unplaced.size:
            fit = self.find_fittable()
            if fit:
                self.place_nodes(fit)
            elif not self.open_more():
                self.drop_node()

        move_inline = self.must_move_inline()
        placed_size = self.placed.size - self.depth - self.from__.depth
        from__ = self.from__
        to_ = self.close(
            self.to_ if move_inline < 0 else from__.doc.resolve(move_inline)
        )
        if not to_:
            return None

        content = self.placed
        open_start = from__.depth
        open_end = to_.depth
        while open_start and open_end and content.child_count == 1:
            first_child = content.first_child
            assert first_child
            content = first_child.content
            open_start -= 1
            open_end -= 1

        slice = Slice(content, open_start, open_end)
        if move_inline > -1:
            return ReplaceAroundStep(
                from__.pos,
                move_inline,
                self.to_.pos,
                self.to_.end(),
                slice,
                placed_size,
            )
        if slice.size or from__.pos != self.to_.pos:
            return ReplaceStep(from__.pos, to_.pos, slice)
        return None

    def find_fittable(self) -> _Fittable | None:
        start_depth = self.unplaced.open_start
        cur = self.unplaced.content
        open_end = self.unplaced.open_end
        for d in range(start_depth):
            node = cast("Node", cur.first_child)
            if cur.child_count > 1:
                open_end = 0
            if node.type.spec.get("isolating") and open_end <= d:
                start_depth = d
                break
            cur = node.content

        for pass_ in [1, 2]:
            for slice_depth in range(
                start_depth if pass_ == 1 else self.unplaced.open_start, -1, -1
            ):
                if slice_depth:
                    parent = content_at(
                        self.unplaced.content, slice_depth - 1
                    ).first_child
                    assert parent
                    fragment = parent.content
                else:
                    parent = None
                    fragment = self.unplaced.content
                first = fragment.first_child
                for frontier_depth in range(self.depth, -1, -1):
                    type_ = self.frontier[frontier_depth].type
                    match = self.frontier[frontier_depth].match

                    _nothing = object()
                    inject = _nothing
                    wrap = _nothing

                    def _lazy_inject() -> Fragment | None:
                        nonlocal inject
                        if inject is _nothing:
                            inject = match.fill_before(Fragment.from_(first), False)
                        return cast(Fragment | None, inject)

                    def _lazy_wrap() -> list[NodeType] | None:
                        nonlocal wrap
                        assert first is not None
                        if wrap is _nothing:
                            wrap = match.find_wrapping(first.type)
                        return cast(list[NodeType] | None, wrap)

                    if pass_ == 1 and (
                        (match.match_type(first.type) or _lazy_inject())
                        if first
                        else parent and type_.compatible_content(parent.type)
                    ):
                        return _Fittable(
                            slice_depth,
                            frontier_depth,
                            parent,
                            inject=_lazy_inject(),
                        )
                    elif pass_ == 2 and first and _lazy_wrap():
                        return _Fittable(
                            slice_depth,
                            frontier_depth,
                            parent,
                            wrap=_lazy_wrap(),
                        )
                    if parent and match.match_type(parent.type):
                        break
        return None

    def open_more(self) -> bool:
        content = self.unplaced.content
        open_start = self.unplaced.open_start
        open_end = self.unplaced.open_end
        inner = content_at(content, open_start)
        if not inner.child_count or cast("Node", inner.first_child).is_leaf:
            return False
        self.unplaced = Slice(
            content,
            open_start + 1,
            max(
                open_end,
                open_start + 1
                if inner.size + open_start >= content.size - open_end
                else 0,
            ),
        )
        return True

    def drop_node(self) -> None:
        content = self.unplaced.content
        open_start = self.unplaced.open_start
        open_end = self.unplaced.open_end
        inner = content_at(content, open_start)
        if inner.child_count <= 1 and open_start > 0:
            open_at_end = content.size - open_start <= open_start + inner.size
            self.unplaced = Slice(
                drop_from_fragment(content, open_start - 1, 1),
                open_start - 1,
                open_start - 1 if open_at_end else open_end,
            )
        else:
            self.unplaced = Slice(
                drop_from_fragment(content, open_start, 1),
                open_start,
                open_end,
            )

    def place_nodes(self, fittable: _Fittable) -> None:
        slice_depth = fittable.slice_depth
        frontier_depth = fittable.frontier_depth
        parent = fittable.parent
        inject = fittable.inject
        wrap = fittable.wrap

        while self.depth > frontier_depth:
            self.close_frontier_node()

        if wrap:
            for w in wrap:
                self.open_frontier_node(w)

        slice = self.unplaced
        fragment = parent.content if parent else slice.content
        open_start = slice.open_start - slice_depth
        taken = 0
        add = []
        frontier_item = self.frontier[frontier_depth]
        match, type_ = frontier_item.match, frontier_item.type
        if inject:
            for i in range(inject.child_count):
                add.append(inject.child(i))
            matched_fragment = match.match_fragment(inject)
            assert matched_fragment is not None
            match = matched_fragment

        open_end_count = (fragment.size + slice_depth) - (
            slice.content.size - slice.open_end
        )

        while taken < fragment.child_count:
            next_ = fragment.child(taken)
            matches = match.match_type(next_.type)
            if not matches:
                break
            taken += 1
            if taken > 1 or open_start == 0 or next_.content.size:
                match = matches
                add.append(
                    close_node_start(
                        next_.mark(type_.allowed_marks(next_.marks)),
                        open_start if taken == 1 else 0,
                        open_end_count if taken == fragment.child_count else -1,
                    )
                )

        to_end = taken == fragment.child_count
        if not to_end:
            open_end_count = -1

        self.placed = add_to_fragment(
            self.placed,
            frontier_depth,
            Fragment.from_(add),
        )
        self.frontier[frontier_depth].match = match

        if (
            to_end
            and open_end_count < 0
            and parent
            and parent.type == self.frontier[self.depth].type
            and len(self.frontier) > 1
        ):
            self.close_frontier_node()

        cur = fragment
        for _ in range(open_end_count):
            node = cur.last_child
            assert node is not None
            self.frontier.append(
                _FrontierItem(node.type, node.content_match_at(node.child_count))
            )
            cur = node.content

        if not to_end:
            self.unplaced = Slice(
                drop_from_fragment(slice.content, slice_depth, taken),
                slice.open_start,
                slice.open_end,
            )
        elif slice_depth == 0:
            self.unplaced = Slice.empty
        else:
            self.unplaced = Slice(
                drop_from_fragment(slice.content, slice_depth - 1, 1),
                slice_depth - 1,
                slice.open_end if open_end_count < 0 else slice_depth - 1,
            )

    def must_move_inline(self) -> int:
        if not self.to_.parent.is_text_block:
            return -1
        top = self.frontier[self.depth]

        _nothing = object()
        level = _nothing

        def _lazy_level() -> _CloseLevel | None:
            nonlocal level
            if level is _nothing:
                level = self.find_close_level(self.to_)
            return cast(_CloseLevel | None, level)

        if (
            not top.type.is_text_block
            or not content_after_fits(
                self.to_, self.to_.depth, top.type, top.match, False
            )
            or (
                self.to_.depth == self.depth
                and (lazy_level := _lazy_level())
                and lazy_level.depth == self.depth
            )
        ):
            return -1

        depth = self.to_.depth
        after = self.to_.after(depth)
        while depth > 1:
            depth -= 1
            if after != self.to_.end(depth):
                break
            after += 1
        return after

    def find_close_level(self, to_: ResolvedPos) -> _CloseLevel | None:
        for i in range(min(self.depth, to_.depth), -1, -1):
            match = self.frontier[i].match
            type_ = self.frontier[i].type
            drop_inner = i < to_.depth and to_.end(i + 1) == to_.pos + (
                to_.depth - (i + 1)
            )
            fit = content_after_fits(to_, i, type_, match, drop_inner)
            if not fit:
                continue
            for d in range(i - 1, -1, -1):
                match2, type2 = self.frontier[d].match, self.frontier[d].type
                matches = content_after_fits(to_, d, type2, match2, True)
                if not matches or matches.child_count:
                    break
            else:
                return _CloseLevel(
                    depth=i,
                    fit=fit,
                    move=to_.doc.resolve(to_.after(i + 1)) if drop_inner else to_,
                )
        return None

    def close(self, to_: ResolvedPos) -> ResolvedPos | None:
        close = self.find_close_level(to_)
        if not close:
            return None

        while self.depth > close.depth:
            self.close_frontier_node()
        if close.fit.child_count:
            self.placed = add_to_fragment(self.placed, close.depth, close.fit)
        to_ = close.move
        for d in range(close.depth + 1, to_.depth + 1):
            node = to_.node(d)
            add = node.type.content_match.fill_before(node.content, True, to_.index(d))
            self.open_frontier_node(node.type, node.attrs, add)
        return to_

    def open_frontier_node(
        self,
        type_: NodeType,
        attrs: Attrs | None = None,
        content: Fragment | None = None,
    ) -> None:
        top = self.frontier[self.depth]
        top_match = top.match.match_type(type_)
        assert top_match is not None
        top.match = top_match
        self.placed = add_to_fragment(
            self.placed, self.depth, Fragment.from_(type_.create(attrs, content))
        )
        self.frontier.append(_FrontierItem(type_, type_.content_match))

    def close_frontier_node(self) -> None:
        open_ = self.frontier.pop()
        add = open_.match.fill_before(Fragment.empty, True)
        if add and add.child_count:
            self.placed = add_to_fragment(self.placed, len(self.frontier), add)


def drop_from_fragment(fragment: Fragment, depth: int, count: int) -> Fragment:
    if depth == 0:
        return fragment.cut_by_index(count)
    first_child = fragment.first_child
    assert first_child
    return fragment.replace_child(
        0,
        first_child.copy(drop_from_fragment(first_child.content, depth - 1, count)),
    )


def add_to_fragment(fragment: Fragment, depth: int, content: Fragment) -> Fragment:
    if depth == 0:
        return fragment.append(content)
    last_child = fragment.last_child
    assert last_child
    return fragment.replace_child(
        fragment.child_count - 1,
        last_child.copy(add_to_fragment(last_child.content, depth - 1, content)),
    )


def content_at(fragment: Fragment, depth: int) -> Fragment:
    for _ in range(depth):
        fragment = cast(Node, fragment.first_child).content
    return fragment


def close_node_start(node: Node, open_start: int, open_end: int) -> Node:
    if open_start <= 0:
        return node
    frag = node.content
    if open_start > 1:
        assert frag.first_child is not None
        frag = frag.replace_child(
            0,
            close_node_start(
                frag.first_child,
                open_start - 1,
                open_end - 1 if frag.child_count == 1 else 0,
            ),
        )
    if open_start > 0:
        fill_before_frag = node.type.content_match.fill_before(frag)
        assert fill_before_frag is not None
        frag = fill_before_frag.append(frag)
        if open_end <= 0:
            matched_fragment = node.type.content_match.match_fragment(frag)
            assert matched_fragment is not None
            fill_before_frag = matched_fragment.fill_before(Fragment.empty, True)
            assert fill_before_frag is not None
            frag = frag.append(fill_before_frag)
    return node.copy(frag)


def content_after_fits(
    to_: ResolvedPos,
    depth: int,
    type_: NodeType,
    match: ContentMatch,
    open_: bool,
) -> Fragment | None:
    node = to_.node(depth)
    index = to_.index_after(depth) if open_ else to_.index(depth)
    if index == node.child_count and not type_.compatible_content(node.type):
        return None
    fit = match.fill_before(node.content, True, index)
    return fit if fit and not invalid_marks(type_, node.content, index) else None


def invalid_marks(type_: NodeType, fragment: Fragment, start: int) -> bool:
    for i in range(start, fragment.child_count):
        if not type_.allows_marks(fragment.child(i).marks):
            return True
    return False


def close_fragment(
    fragment: Fragment,
    depth: int,
    old_open: int,
    new_open: int,
    parent: Node | None,
) -> Fragment:
    if depth < old_open:
        first = fragment.first_child
        assert first is not None
        fragment = fragment.replace_child(
            0,
            first.copy(
                close_fragment(first.content, depth + 1, old_open, new_open, first)
            ),
        )
    if depth > new_open:
        assert parent is not None
        match = parent.content_match_at(0)
        fill_before_frag = match.fill_before(fragment)
        assert fill_before_frag is not None
        start = fill_before_frag.append(fragment)
        matched_fragment = match.match_fragment(start)
        assert matched_fragment is not None
        matched_fragment_fill_before = matched_fragment.fill_before(
            Fragment.empty, True
        )
        assert matched_fragment_fill_before is not None
        fragment = start.append(matched_fragment_fill_before)

    return fragment


def covered_depths(
    from__: ResolvedPos,
    to_: ResolvedPos,
) -> list[int]:
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
        if start == to_.start(d) or (
            d == from__.depth
            and d == to_.depth
            and from__.parent.inline_content
            and to_.parent.inline_content
            and d
            and to_.start(d - 1) == start - 1
        ):
            result.append(d)
    return result
