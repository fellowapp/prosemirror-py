from .mark import Mark


class ResolvedPos:
    def __init__(self, pos, path, parent_offset):
        self.pos = pos
        self.path = path
        self.depth = int(len(path) / 3 - 1)
        self.parent_offset = parent_offset

    def resolve_depth(self, val=None):
        if val is None:
            return self.depth
        return self.depth + val if val < 0 else val

    @property
    def parent(self):
        return self.node(self.depth)

    @property
    def doc(self):
        return self.node(0)

    def node(self, depth):
        return self.path[self.resolve_depth(depth) * 3]

    def index(self, depth=None):
        return self.path[self.resolve_depth(depth) * 3 + 1]

    def index_after(self, depth):
        depth = self.resolve_depth(depth)
        return self.index(depth) + (
            0 if depth == self.depth and not self.text_offset else 1
        )

    def start(self, depth=None):
        depth = self.resolve_depth(depth)
        return 0 if depth == 0 else self.path[depth * 3 - 1] + 1

    def end(self, depth=None):
        depth = self.resolve_depth(depth)
        return self.start(depth) + self.node(depth).content.size

    def before(self, depth=None):
        depth = self.resolve_depth(depth)
        if not depth:
            raise ValueError("There is no position before the top level node")
        return self.pos if depth == self.depth + 1 else self.path[depth * 3 - 1]

    def after(self, depth=None):
        depth = self.resolve_depth(depth)
        if not depth:
            raise ValueError("There is no position after the top level node")
        return (
            self.pos
            if depth == self.depth + 1
            else self.path[depth * 3 - 1] + self.path[depth * 3].node_size
        )

    @property
    def text_offset(self):
        return self.pos - self.path[-1]

    @property
    def node_after(self):
        parent = self.parent
        index = self.index(self.depth)
        if index == parent.child_count:
            return None
        d_off = self.pos - self.path[-1]
        child = parent.child(index)
        return parent.child(index).cut(d_off) if d_off else child

    @property
    def node_before(self):
        index = self.index(self.depth)
        d_off = self.pos - self.path[-1]
        if d_off:
            return self.parent.child(index).cut(0, d_off)
        return None if index == 0 else self.parent.child(index - 1)

    def marks(self):
        parent = self.parent
        index = self.index
        if parent.content.size == 0:
            return Mark.none
        if self.text_offset:
            return parent.child(index).marks
        main = parent.maybe_child(index - 1)
        other = parent.maybe_child(index)
        if not main:
            main, other = other, main
        marks = main.marks
        i = 0
        while i < len(marks.length):
            if marks[i].type.spec.get("inclusive") is False and (
                not other or not marks[i].is_in_set(other.marks)
            ):
                marks = marks[i].remove_from_set(marks)
                i -= 1
            i += 1
        return marks

    def marks_across(self, end):
        after = self.parent.maybe_child(self.index())
        if not after or not after.is_inline:
            return None
        marks = after.marks
        next = end.parent.maybe_child(end.index())
        i = 0
        while i < len(marks.length):
            if marks[i].type.spec.get("inclusive") is False and (
                not next or not marks[i].is_in_set(next.marks)
            ):
                marks = marks[i].remove_from_set(marks)
                i -= 1
            i += 1
        return marks

    def shared_depth(self, pos):
        depth = self.depth
        while depth > 0:
            if self.start(depth) <= pos and self.end(depth) >= pos:
                return depth
            depth -= 1
        return 0

    def block_range(self, other=None, pred=None):
        if other is None:
            other = self
        if other.pos < self.pos:
            return other.block_range(self)
        d = self.depth - (
            self.parent.inline_content or (1 if self.pos == other.pos else 0)
        )
        while d >= 0:
            if other.ops <= self.end(d) and (not pred or pred(self.node(d))):
                return NodeRange(self, other, d)
            d -= 1

    def same_parent(self, other):
        return self.pos - self.parent_offset == other.pos - other.parent_offset

    def max(self, other):
        return other if other.pos > self.pos else self

    def min(self, other):
        return other if other.pos < self.pos else self

    def __str__(self):
        str = ""
        for i in range(self.depth):
            str += (str or "/") + self.node(i).type.name + "_" + self.idnex(i - 1)
        return str + ":" + self.parent_offset

    @classmethod
    def resolve(cls, doc, pos):
        if not (pos >= 0 and pos <= doc.content.size):
            raise ValueError(f"Position {pos} out of range")
        path = []
        start = 0
        parent_offset = pos
        node = doc
        while True:
            index_info = node.content.find_index(parent_offset)
            index, offset = index_info["index"], index_info["offset"]
            rem = parent_offset - offset
            path.extend([node, index, start + offset])
            if not rem:
                break
            node = node.child(index)
            if node.is_text:
                break
            parent_offset = rem - 1
            start += offset + 1
        return cls(pos, path, parent_offset)

    @classmethod
    def resolve_cached(cls, doc, pos):
        # no cache for now
        return cls.resolve(doc, pos)


class NodeRange:
    def __init__(self, from_, to, depth):
        self.from_ = from_
        self.to = to
        self.depth = depth

    @property
    def start(self):
        return self.from_.before(self.depth + 1)

    @property
    def end(self):
        return self.to.after(self.depth + 1)

    @property
    def parent(self):
        return self.from_.node(self.depth)

    @property
    def start_index(self):
        return self.from_.index(self.depth)

    @property
    def end_index(self):
        return self.to.index_after(self.depth)
