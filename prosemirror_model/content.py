import re
from functools import reduce

from .fragment import Fragment


class ContentMatch:
    def __init__(self, valid_end):
        self.valid_end = valid_end
        self.next = []
        self.wrap_cache = []

    @classmethod
    def parse(cls, string, node_types):
        stream = TokenStream(string, node_types)
        if stream.next is None:
            return ContentMatch.empty
        expr = parse_expr(stream)
        if stream.next:
            stream.err("Unexpected traling text")
        match = dfa(nfa(expr))
        check_for_dead_ends(match, stream)
        return match

    def match_type(self, type):
        for i in range(0, len(self.next), 2):
            if self.next[i].name == type.name:
                return self.next[i + 1]
        return None

    def match_fragment(self, frag, start=0, end=None):
        if end is None:
            end = frag.child_count
        cur = self
        i = start
        while cur and i < end:
            cur = cur.match_type(frag.child(i).type)
            i += 1
        return cur

    @property
    def inline_content(self):
        if not self.next:
            return None
        first = self.next[0]
        return first.is_inline if first else False

    @property
    def default_type(self):
        for i in range(0, len(self.next), 2):
            type = self.next[i]
            if not (type.is_text or type.has_required_attrs()):
                return type

    def compatible(self, other):
        for i in range(0, len(self.next), 2):
            for j in range(0, len(other.next), 2):
                if self.next[i] == other.next[j]:
                    return True
        return False

    def fill_before(self, after, to_end=False, start_index=0):
        seen = [self]

        def search(match, types):
            nonlocal seen
            finished = match.match_fragment(after, start_index)
            if finished and (not to_end or finished.valid_end):
                return Fragment.from_([tp.create_and_fill() for tp in types])
            for i in range(0, len(match.next), 2):
                type = match.next[i]
                next = match.next[i + 1]
                if not (type.is_text or type.has_required_attrs()) and next not in seen:
                    seen.append(next)
                    found = search(next, types + [type])
                    if found:
                        return found

        return search(self, [])

    def find_wrapping(self, target):
        for i in range(0, len(self.wrap_cache), 2):
            if self.wrap_cache[i] == target:
                return self.wrap_cache[i + 1]
        computed = self.compute_wrapping(target)
        self.wrap_cache.extend([target, computed])
        return computed

    def compute_wrapping(self, target):
        seen = {}
        active = [{"match": self, "type": None, "via": None}]
        while len(active):
            current = active.pop(0)
            match = current["match"]
            if match.match_type(target):
                result = []
                obj = current
                while obj["type"]:
                    result.append(obj["type"])
                    obj = obj["via"]
                return list(reversed(result))
            for i in range(0, len(match.next), 2):
                type = match.next[i]
                if (
                    not type.is_leaf
                    and not type.has_required_attrs()
                    and type.name not in seen
                    and (not current["type"] or match.next[i + 1].valid_end)
                ):
                    active.append({"match": type.content_match, "via": current, "type": type})
                    seen[type.name] = True

    @property
    def edge_count(self):
        return len(self.next) >> 1

    def edge(self, n):
        i = n << 1
        if i > len(self.next):
            raise ValueError(f"There's no {n}th edge in this content match")
        return {"type": self.next[i], "next": self.next[i + 1]}

    def __str__(self):
        seen = []

        def scan(m):
            nonlocal seen
            for i in range(1, len(m.next), 2):
                if m.next[i] in seen:
                    scan(m.next[i])

        scan(self)

        def iteratee(m, i):
            out = i + ("*" if m.valid_end else " ") + " "
            for i in range(0, len(m.next), 2):
                out += (
                    (", " if i else "") + m.next(i) + "->" + seen.index(m.next[i + 1])
                )

        return "\n".join((iteratee(m, i)) for m, i in enumerate(seen))

    def __repr__(self):
        return f'ContentMatch<{dict(valid_end=self.valid_end, next=self.next, cache=self.wrap_cache)}>'


ContentMatch.empty = ContentMatch(True)


TOKEN_REGEX = re.compile(r"\s*(?=\b|\W|$)")


class TokenStream:
    def __init__(self, string, node_types):
        self.string = string
        self.node_types = node_types
        self.inline = None
        self.pos = 0
        self.tokens = [i for i in TOKEN_REGEX.split(string) if i]

    @property
    def next(self):
        try:
            return self.tokens[self.pos]
        except IndexError:
            return None

    def eat(self, tok):
        if self.next == tok:
            pos = self.pos
            self.pos += 1
            return pos or True
        else:
            return False

    def err(self, str):
        raise SyntaxError(f'{str} (in content expression) "{self.string}"')


def parse_expr(stream):
    exprs = []
    while True:
        exprs.append(parse_expr_seq(stream))
        if not stream.eat("|"):
            break
    if len(exprs) == 1:
        return exprs[0]
    return {"type": "choice", "exprs": exprs}


def parse_expr_seq(stream):
    exprs = []
    while True:
        exprs.append(parse_expr_subscript(stream))
        if not (stream.next and stream.next != ")" and stream.next != "|"):
            break
    if len(exprs) == 1:
        return exprs[0]
    return {"type": "seq", "exprs": exprs}


def parse_expr_subscript(stream):
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


NUMBER_REGEX = re.compile(r"\d")


def parse_num(stream: TokenStream):
    if NUMBER_REGEX.match(stream.next):
        stream.err(f'Expected number, got "{stream.next}"')
    result = int(stream.next)
    stream.pos += 1
    return result


def parse_expr_range(stream: TokenStream, expr):
    min_ = parse_num(stream)
    max_ = min_
    if stream.eat(","):
        if stream.next != "}":
            max_ = parse_num(stream)
        else:
            max_ = -1
    if not stream.eat("}"):
        stream.err("Unclosed braced range")
    return {"type": "range", "min": min_, "max": max_, "expr": expr}


def resolve_name(stream: TokenStream, name):
    types = stream.node_types
    type = types.get(name)
    if type:
        return [type]
    result = []
    for typeName, type in types.items():
        if name in type.groups:
            result.append(type)
    if not result:
        stream.err(f'No node type or group "{name}" found')
    return result


def parse_expr_atom(stream: TokenStream):
    if stream.eat("("):
        expr = parse_expr(stream)
        if not stream.eat(")"):
            stream.err("missing closing patren")
        return expr
    elif not re.match(r"\W", stream.next):

        def iteratee(type):
            nonlocal stream
            if stream.inline is None:
                stream.inline = type.is_inline
            elif stream.inline != type.is_inline:
                stream.err("Mixing inline and block content")
            return {"type": "name", "value": type}

        exprs = [iteratee(type) for type in resolve_name(stream, stream.next)]
        stream.pos += 1
        if len(exprs) == 1:
            return exprs[0]
        return {"type": "choice", "exprs": exprs}
    else:
        stream.err(f'Unexpected token "{stream.next}"')


def nfa(expr):
    nfa_ = [[]]

    def node():
        nonlocal nfa_
        nfa_.append([])
        return len(nfa_) - 1

    def edge(from_, to=None, term=None):
        nonlocal nfa_
        edge = {"term": term, "to": to}
        nfa_[from_].append(edge)
        return edge

    def connect(edges, to):
        for edge in edges:
            edge["to"] = to

    def compile(expr, from_):
        if expr["type"] == "choice":
            return list(reduce(
                lambda out, expr: out + compile(expr, from_), expr["exprs"], []
            ))
        elif expr["type"] == "seq":
            i = 0
            while True:
                next = compile(expr["exprs"][i], from_)
                if i == len(expr["exprs"]) - 1:
                    return next
                from_ = node()
                connect(next, from_)
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
            return [edge(from_)] + compile(expr["expr"], from_)
        elif expr["type"] == "range":
            cur = from_
            for i in range(expr["min"]):
                next = node()
                connect(compile(expr["expr"], cur), next)
                cur = next
            if expr["max"] == -1:
                connect(compile(expr["expr"], cur), cur)
            else:
                for i in range(expr["min"], expr["max"]):
                    next = node()
                    edge(cur, next)
                    connect(compile(expr["expr"], cur), next)
                    cur = next
            return [edge(cur)]
        elif expr["type"] == "name":
            return [edge(from_, None, expr["value"])]

    connect(compile(expr, 0), node())
    return nfa_


def cmp(a, b):
    return a - b


def null_from(nfa, node):
    result = []

    def scan(n):
        nonlocal result
        edges = nfa[n]
        if len(edges) == 1 and not edges[0].get("term"):
            return scan(edges[0].get("to"))
        result.append(n)
        for edge in edges:
            term, to = edge.get("term"), edge.get("to")
            if not term and to not in result:
                scan(to)

    scan(node)
    return sorted(result)


def dfa(nfa):
    labeled = {}

    def explore(states):
        nonlocal labeled
        out = []
        for node in states:
            for item in nfa[node]:
                term, to = item.get("term"), item.get("to")
                if not term:
                    continue
                known = term in out
                if known:
                    set = out[out.index(term) + 1]
                else:
                    set = False
                for n in null_from(nfa, to):
                    if not set:
                        set = []
                        out.extend([term, set])
                    if n not in set:
                        set.append(n)
        state = ContentMatch((len(nfa) - 1) in states)
        labeled[",".join([str(s) for s in states])] = state
        for i in range(0, len(out), 2):
            states = sorted(out[i + 1])
            find_by_key = ",".join(str(s) for s in states)
            items_to_extend = [
                out[i],
                labeled.get(find_by_key) or explore(states),
            ]
            state.next.extend(items_to_extend)
        return state

    return explore(null_from(nfa, 0))


def check_for_dead_ends(match, stream):
    work = [match]
    i = 0
    while i < len(work):
        state = work[i]
        dead = not state.valid_end
        nodes = []
        for j in range(0, len(state.next), 2):
            node = state.next[j]
            next = state.next[j + 1]
            nodes.append(node.name)
            if dead and not (node.is_text or node.has_required_attrs()):
                dead = False
            if next not in work:
                work.append(next)
        if dead:
            stream.err(
                f'Only non-generatable nodes ({", ".join(nodes)}) in a required position'
            )
        i += 1
