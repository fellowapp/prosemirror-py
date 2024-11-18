import re
from functools import cmp_to_key, reduce
from typing import (
    TYPE_CHECKING,
    ClassVar,
    Literal,
    NamedTuple,
    NoReturn,
    Optional,
    TypedDict,
    cast,
)

from .fragment import Fragment

if TYPE_CHECKING:
    from .node import Node
    from .schema import NodeType


class MatchEdge:
    type: "NodeType"
    next: "ContentMatch"

    def __init__(self, type: "NodeType", next: "ContentMatch") -> None:
        self.type = type
        self.next = next


class WrapCacheEntry:
    target: "NodeType"
    computed: list["NodeType"] | None

    def __init__(self, target: "NodeType", computed: list["NodeType"] | None) -> None:
        self.target = target
        self.computed = computed


class Active(TypedDict):
    match: "ContentMatch"
    type: Optional["NodeType"]
    via: Optional["Active"]


class ContentMatch:
    """
    Instances of this class represent a match state of a node type's
    [content expression](#model.NodeSpec.content), and can be used to
    find out whether further content matches here, and whether a given
    position is a valid end of the node.
    """

    empty: ClassVar["ContentMatch"]
    valid_end: bool
    next: list[MatchEdge]
    wrap_cache: list[WrapCacheEntry]

    def __init__(self, valid_end: bool) -> None:
        self.valid_end = valid_end
        self.next = []
        self.wrap_cache = []

    @classmethod
    def parse(cls, string: str, node_types: dict[str, "NodeType"]) -> "ContentMatch":
        stream = TokenStream(string, node_types)
        if stream.next() is None:
            return ContentMatch.empty
        expr = parse_expr(stream)
        if stream.next() is not None:
            stream.err("Unexpected trailing text")
        match = dfa(nfa(expr))
        check_for_dead_ends(match, stream)
        return match

    def match_type(self, type: "NodeType") -> Optional["ContentMatch"]:
        for next in self.next:
            if next.type.name == type.name:
                return next.next
        return None

    def match_fragment(
        self,
        frag: Fragment,
        start: int = 0,
        end: int | None = None,
    ) -> Optional["ContentMatch"]:
        if end is None:
            end = frag.child_count
        cur: ContentMatch | None = self
        i = start
        while cur and i < end:
            cur = cur.match_type(frag.child(i).type)
            i += 1
        return cur

    @property
    def inline_content(self) -> bool:
        return bool(self.next) and self.next[0].type.is_inline

    @property
    def default_type(self) -> Optional["NodeType"]:
        for next in self.next:
            type = next.type
            if not (type.is_text or type.has_required_attrs()):
                return type
        return None

    def compatible(self, other: "ContentMatch") -> bool:
        for i in self.next:
            for j in other.next:
                if i.type.name == j.type.name:
                    return True
        return False

    def fill_before(
        self,
        after: Fragment,
        to_end: bool = False,
        start_index: int = 0,
    ) -> Fragment | None:
        seen = [self]

        def search(match: ContentMatch, types: list["NodeType"]) -> Fragment | None:
            nonlocal seen
            finished = match.match_fragment(after, start_index)
            if finished and (not to_end or finished.valid_end):
                return Fragment.from_([
                    cast("Node", tp.create_and_fill()) for tp in types
                ])
            for i in match.next:
                type = i.type
                next = i.next
                if not (type.is_text or type.has_required_attrs()) and next not in seen:
                    seen.append(next)
                    found = search(next, [*types, type])
                    if found:
                        return found
            return None

        return search(self, [])

    def find_wrapping(self, target: "NodeType") -> list["NodeType"] | None:
        for entry in self.wrap_cache:
            if entry.target.name == target.name:
                return entry.computed
        computed = self.compute_wrapping(target)
        self.wrap_cache.append(WrapCacheEntry(target, computed))
        return computed

    def compute_wrapping(self, target: "NodeType") -> list["NodeType"] | None:
        seen = {}
        active: list[Active] = [{"match": self, "type": None, "via": None}]
        while len(active):
            current = active.pop(0)
            match = current["match"]
            if match.match_type(target):
                result = []
                obj = current
                while obj["type"]:
                    result.append(obj["type"])
                    obj = cast(Active, obj["via"])
                return list(reversed(result))
            for i in range(len(match.next)):
                type = match.next[i].type
                if (
                    not type.is_leaf
                    and not type.has_required_attrs()
                    and type.name not in seen
                    and (not current["type"] or match.next[i].next.valid_end)
                ):
                    active.append({
                        "match": type.content_match,
                        "via": current,
                        "type": type,
                    })
                    seen[type.name] = True
        return None

    @property
    def edge_count(self) -> int:
        return len(self.next)

    def edge(self, n: int) -> MatchEdge:
        if n >= len(self.next):
            msg = f"There's no {n}th edge in this content match"
            raise ValueError(msg)
        return self.next[n]

    def __str__(self) -> str:
        seen = []

        def scan(m: "ContentMatch") -> None:
            nonlocal seen
            seen.append(m)
            for i in m.next:
                if i.next not in seen:
                    scan(i.next)

        scan(self)

        def iteratee(m: "ContentMatch", i: int) -> str:
            out = str(i) + ("*" if m.valid_end else " ") + " "
            for i in range(len(m.next)):
                out += (
                    (", " if i else "")
                    + m.next[i].type.name
                    + "->"
                    + str(seen.index(m.next[i].next))
                )
            return out

        return "\n".join((iteratee(m, i)) for i, m in enumerate(seen))


ContentMatch.empty = ContentMatch(True)


TOKEN_REGEX = re.compile(r"\w+|\W")


class TokenStream:
    inline: bool | None
    tokens: list[str]

    def __init__(self, string: str, node_types: dict[str, "NodeType"]) -> None:
        self.string = string
        self.node_types = node_types
        self.inline = None
        self.pos = 0
        self.tokens = [i for i in TOKEN_REGEX.findall(string) if i.strip()]

    def next(self) -> str | None:
        try:
            return self.tokens[self.pos]
        except IndexError:
            return None

    def eat(self, tok: str) -> int | bool:
        if self.next() == tok:
            pos = self.pos
            self.pos += 1
            return pos or True
        else:
            return False

    def err(self, str: str) -> NoReturn:
        msg = f'{str} (in content expression) "{self.string}"'
        raise SyntaxError(msg)


class ChoiceExpr(TypedDict):
    type: Literal["choice"]
    exprs: list["Expr"]


class SeqExpr(TypedDict):
    type: Literal["seq"]
    exprs: list["Expr"]


class PlusExpr(TypedDict):
    type: Literal["plus"]
    expr: "Expr"


class StarExpr(TypedDict):
    type: Literal["star"]
    expr: "Expr"


class OptExpr(TypedDict):
    type: Literal["opt"]
    expr: "Expr"


class RangeExpr(TypedDict):
    type: Literal["range"]
    min: int
    max: int
    expr: "Expr"


class NameExpr(TypedDict):
    type: Literal["name"]
    value: "NodeType"


Expr = ChoiceExpr | SeqExpr | PlusExpr | StarExpr | OptExpr | RangeExpr | NameExpr


def parse_expr(stream: TokenStream) -> Expr:
    exprs = []
    while True:
        exprs.append(parse_expr_seq(stream))
        if not stream.eat("|"):
            break
    if len(exprs) == 1:
        return exprs[0]
    return {"type": "choice", "exprs": exprs}


def parse_expr_seq(stream: TokenStream) -> Expr:
    exprs = []
    while True:
        exprs.append(parse_expr_subscript(stream))
        next_ = stream.next()
        if not (next_ and next_ != ")" and next_ != "|"):
            break
    if len(exprs) == 1:
        return exprs[0]
    return {"type": "seq", "exprs": exprs}


def parse_expr_subscript(stream: TokenStream) -> Expr:
    expr = parse_expr_atom(stream)
    while True:
        if stream.eat("+"):
            expr = {"type": "plus", "expr": expr}
        elif stream.eat("*"):
            expr = {"type": "star", "expr": expr}
        elif stream.eat("?"):
            expr = {"type": "opt", "expr": expr}
        elif stream.eat("{"):
            expr = parse_expr_range(stream, expr)
        else:
            break
    return expr


NUMBER_REGEX = re.compile(r"\D")


def parse_num(stream: TokenStream) -> int:
    next = stream.next()
    assert next is not None
    if NUMBER_REGEX.match(next):
        stream.err(f'Expected number, got "{next}"')
    result = int(next)
    stream.pos += 1
    return result


def parse_expr_range(stream: TokenStream, expr: Expr) -> Expr:
    min_ = parse_num(stream)
    max_ = min_
    if stream.eat(","):
        max_ = parse_num(stream) if stream.next() != "}" else -1
    if not stream.eat("}"):
        stream.err("Unclosed braced range")
    return {"type": "range", "min": min_, "max": max_, "expr": expr}


def resolve_name(stream: TokenStream, name: str) -> list["NodeType"]:
    types = stream.node_types
    type = types.get(name)
    if type:
        return [type]
    result = []
    for _, type in types.items():
        if name in type.groups:
            result.append(type)
    if not result:
        stream.err(f'No node type or group "{name}" found')
    return result


def parse_expr_atom(
    stream: TokenStream,
) -> Expr:
    if stream.eat("("):
        expr = parse_expr(stream)
        if not stream.eat(")"):
            stream.err("missing closing patren")
        return expr
    elif not re.match(r"\W", cast(str, stream.next())):

        def iteratee(type: "NodeType") -> Expr:
            nonlocal stream
            if stream.inline is None:
                stream.inline = type.is_inline
            elif stream.inline != type.is_inline:
                stream.err("Mixing inline and block content")
            return {"type": "name", "value": type}

        exprs = [
            iteratee(type) for type in resolve_name(stream, cast(str, stream.next()))
        ]
        stream.pos += 1
        if len(exprs) == 1:
            return exprs[0]
        return {"type": "choice", "exprs": exprs}
    else:
        stream.err(f'Unexpected token "{stream.next()}"')


class Edge(TypedDict):
    term: Optional["NodeType"]
    to: int | None


def nfa(
    expr: Expr,
) -> list[list[Edge]]:
    nfa_: list[list[Edge]] = [[]]

    def node() -> int:
        nonlocal nfa_
        nfa_.append([])
        return len(nfa_) - 1

    def edge(
        from_: int,
        to: int | None = None,
        term: Optional["NodeType"] = None,
    ) -> Edge:
        nonlocal nfa_
        edge: Edge = {"term": term, "to": to}
        nfa_[from_].append(edge)
        return edge

    def connect(edges: list[Edge], to: int) -> None:
        for edge in edges:
            edge["to"] = to

    def compile(expr: Expr, from_: int) -> list[Edge]:
        if expr["type"] == "choice":
            return list(
                reduce(
                    lambda out, expr: [*out, *compile(expr, from_)],
                    expr["exprs"],
                    cast(list[Edge], []),
                ),
            )
        elif expr["type"] == "seq":
            i = 0
            while True:
                next_ = compile(expr["exprs"][i], from_)
                if i == len(expr["exprs"]) - 1:
                    return next_
                from_ = node()
                connect(next_, from_)
                i += 1
        elif expr["type"] == "star":
            loop = node()
            edge(from_, loop)
            connect(compile(expr["expr"], loop), loop)
            return [edge(loop)]
        elif expr["type"] == "plus":
            loop = node()
            connect(compile(expr["expr"], from_), loop)
            connect(compile(expr["expr"], loop), loop)
            return [edge(loop)]
        elif expr["type"] == "opt":
            return [edge(from_), *compile(expr["expr"], from_)]
        elif expr["type"] == "range":
            cur = from_
            for _i in range(expr["min"]):
                next = node()
                connect(compile(expr["expr"], cur), next)
                cur = next
            if expr["max"] == -1:
                connect(compile(expr["expr"], cur), cur)
            else:
                for _i in range(expr["min"], expr["max"]):
                    next = node()
                    edge(cur, next)
                    connect(compile(expr["expr"], cur), next)
                    cur = next
            return [edge(cur)]
        elif expr["type"] == "name":
            return [edge(from_, None, expr["value"])]

    connect(compile(expr, 0), node())
    return nfa_


def cmp(a: int, b: int) -> int:
    return b - a


def null_from(
    nfa: list[list[Edge]],
    node: int,
) -> list[int]:
    result = []

    def scan(n: int) -> None:
        nonlocal result
        edges = nfa[n]
        if len(edges) == 1 and not edges[0].get("term"):
            return scan(cast(int, edges[0]["to"]))
        result.append(n)
        for edge in edges:
            term, to = edge.get("term"), edge.get("to")
            if not term and to not in result:
                scan(cast(int, to))

    scan(node)
    return sorted(result)


class DFAState(NamedTuple):
    state: "NodeType"
    next: list[int]


def dfa(nfa: list[list[Edge]]) -> ContentMatch:
    labeled = {}

    def explore(states: list[int]) -> ContentMatch:
        nonlocal labeled
        out: list[DFAState] = []
        for node in states:
            for item in nfa[node]:
                term, to = item.get("term"), item.get("to")
                if not term:
                    continue
                set: list[int] | None = None
                for t in out:
                    if t[0] == term:
                        set = t[1]
                for n in null_from(nfa, cast(int, to)):
                    if set is None:
                        set = []
                        out.append(DFAState(term, set))
                    if n not in set:
                        set.append(n)
        state = ContentMatch((len(nfa) - 1) in states)
        labeled[",".join([str(s) for s in states])] = state
        for i in range(len(out)):
            out[i][1].sort(key=cmp_to_key(cmp))
            states = out[i][1]
            find_by_key = ",".join(str(s) for s in states)
            state.next.append(
                MatchEdge(out[i][0], labeled.get(find_by_key) or explore(states)),
            )
        return state

    return explore(null_from(nfa, 0))


def check_for_dead_ends(match: ContentMatch, stream: TokenStream) -> None:
    work = [match]
    i = 0
    while i < len(work):
        state = work[i]
        dead = not state.valid_end
        nodes = []
        for j in range(len(state.next)):
            node = state.next[j].type
            next = state.next[j].next
            nodes.append(node.name)
            if dead and not (node.is_text or node.has_required_attrs()):
                dead = False
            if next not in work:
                work.append(next)
        if dead:
            stream.err(
                f"Only non-generatable nodes ({', '.join(nodes)}) in a required "
                "position (see https://prosemirror.net/docs/guide/#generatable)",
            )
        i += 1
