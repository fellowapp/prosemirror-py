from collections import OrderedDict

from .node import Node, TextNode
from .fragment import Fragment
from .mark import Mark
from .content import ContentMatch


def default_attrs(attrs):
    defaults = {}
    for attr_name, attr in attrs.items():
        if attr.has_default:
            return None
        defaults[attr_name] = attr.default
    return defaults


def compute_attrs(attrs, value):
    built = {}
    for name in attrs:
        given = None
        if value:
            given = value.get(name)
        if given is None:
            attr = attrs.get(name)
            if attr.has_default:
                given = attr.default
            else:
                raise ValueError("No value supplied for attribute" + name)
        built[name] = given
    return built


def init_attrs(attrs):
    result = {}
    if attrs:
        for name in attrs:
            result[name] = Attribute(attrs[name])
    return result


class NodeType:
    def __init__(self, name, schema, spec):
        self.name = name
        self.schema = schema
        self.spec = spec
        self.groups = spec.get("group").split(" ") if "group" in spec else []
        self.attrs = init_attrs(spec.get("attrs"))
        self.default_attrs = default_attrs(self.attrs)
        self.content_match = None
        self.mark_set = None
        self.inline_content = None
        self.is_block = not (spec.get("inline") or name == "text")
        self.is_text = name == "text"

    @property
    def is_inline(self):
        return not self.is_block

    @property
    def is_text_block(self):
        return self.is_block and self.inline_content

    @property
    def is_leaf(self):
        return self.content_match == ContentMatch.empty

    @property
    def is_atom(self):
        return self.is_leaf or self.spec.get("atom")

    def has_required_attrs(self, ignore=None):
        for n in self.attrs:
            if self.attrs[n].is_required and (not ignore or not (n in ignore)):
                return True
        return False

    def compatible_content(self, other):
        return self == other or (self.content_match.compatible(other.content_match))

    def compute_attrs(self, attrs):
        if not attrs and self.default_attrs:
            return self.default_attrs
        return compute_attrs(self.attrs, attrs)

    def create(self, attrs=None, content=None, marks=None):
        if self.is_text:
            raise ValueError("NodeType.create cannot construct text nodes")
        return Node(
            self,
            self.compute_attrs(attrs),
            Fragment.from_(content),
            Mark.set_from(marks),
        )

    def create_checked(self, attrs, content, marks):
        content = Fragment.from_(content)
        if not self.valid_content(content):
            raise ValueError("Invalid content for node " + self.name)
        return Node(self, self.compute_attrs(attrs), content, Mark.set_from(marks))

    def create_and_fill(self, attrs=None, content=None, marks=None):
        attrs = self.compute_attrs(attrs)
        content = Fragment.from_(content)
        if content.size:
            before = self.content_match.fill_before(content)
            if not before:
                return None
            content = before.append(content)
        after = self.content_match.match_fragment(content).fill_before(
            Fragment.empty, True
        )
        if not after:
            return None
        return Node(self, attrs, content.append(after), Mark.set_from(marks))

    def valid_content(self, content):
        result = self.content_match.match_fragment(content)
        if not result or not result.valid_end:
            return False
        for i in range(content.child_count):
            if not self.allows_marks(content.child(i).marks):
                return False
        return True

    def allows_mark_type(self, mark_type):
        return self.mark_set is None or mark_type in self.mark_set

    def allows_marks(self, marks):
        if self.mark_set is None:
            return True
        return all(self.allows_mark_type(mark.type) for mark in marks)

    def allowed_marks(self, marks):
        if self.mark_set is None:
            return marks
        copy = None
        for i, mark in enumerate(marks):
            if not self.allows_mark_type(mark.type):
                if not copy:
                    copy = marks[0:i]
            elif copy:
                copy.append(mark)
        if copy is None:
            return marks
        elif len(copy):
            return copy
        else:
            return Mark.empty

    @classmethod
    def compile(cls, nodes: OrderedDict, schema):
        result = {}

        for name, spec in nodes.items():
            result[name] = NodeType(name, schema, spec)

        top_node = schema.spec.get("topNode") or "doc"
        if not result.get(top_node):
            raise ValueError(f"Schema is missing its top node type {top_node}")
        if not result.get("text"):
            raise ValueError("every schema needs a 'text' type")
        if getattr(result.get("text"), "attrs", {}):
            raise ValueError("the text node type should not have attributes")
        return result

    def __str__(self):
        return f"<NodeType {self.name}>"

    def __repr__(self):
        return self.__str__()


class Attribute:
    def __init__(self, options):
        self.has_default = "default" in options
        self.default = options["default"] if self.has_default else None

    @property
    def is_required(self):
        return not self.has_default


class MarkType:
    def __init__(self, name, rank, schema, spec):
        self.name = name
        self.schema = schema
        self.spec = spec
        self.attrs = init_attrs(spec.get("attrs"))
        self.rank = rank
        self.excluded = None
        defaults = default_attrs(self.attrs)
        self.instance = False
        if defaults:
            self.instance = Mark(self, defaults)

    def create(self, attrs=None):
        if not attrs and self.instance:
            return self.instance
        return Mark(self, compute_attrs(self.attrs, attrs))

    @classmethod
    def compile(cls, marks: OrderedDict, schema):
        result = {}
        rank = 0
        for name, spec in marks.items():
            result[name] = MarkType(name, rank, schema, spec)
            rank += 1
        return result

    def remove_from_set(self, set):
        return [item for item in set if item.type != self]

    def is_in_set(self, set):
        return next((item for item in set if item.type == self), None)

    def excludes(self, other):
        return any(other.name == e.name for e in self.excluded)


class Schema:
    def __init__(self, spec):
        self.spec = {**spec}
        self.spec["nodes"] = OrderedDict(self.spec["nodes"])
        self.spec["marks"] = OrderedDict(self.spec.get("marks", {}))

        self.nodes = NodeType.compile(self.spec["nodes"], self)
        self.marks = MarkType.compile(self.spec["marks"], self)
        content_expr_cache = {}
        for prop in self.nodes:
            if prop in self.marks:
                raise ValueError(f"{prop} can not be both a node and a mark")
            type = self.nodes[prop]
            content_expr = type.spec.get("content", "")
            mark_expr = type.spec.get("marks")
            if content_expr not in content_expr_cache:
                content_expr_cache[content_expr] = ContentMatch.parse(
                    content_expr, self.nodes
                )
            type.content_match = content_expr_cache[content_expr]
            type.inline_content = type.content_match.inline_content
            if mark_expr == "_":
                type.mark_set = None
            elif mark_expr:
                type.mark_set = gather_marks(self, mark_expr.split(" "))
            elif mark_expr == "" or not type.inline_content:
                type.mark_set = []
            else:
                type.mark_set = None
            # type.mark_set = None if mark_expr == "_" else {
            #     gather_marks(self, mark_expr.split(" ")) if mark_expr else (
            #         [] if (mark_expr == "" or not type.inline_content) else None
            #     )
            # }
        for prop in self.marks:
            type = self.marks.get(prop)
            excl = type.spec.get("excludes")
            type.excluded = (
                [type]
                if excl is None
                else ([] if excl == "" else (gather_marks(self, excl.split(" "))))
            )

        self.top_node_type = self.nodes.get((self.spec.get("topNode") or "doc"))
        self.cached = {}
        self.cached["wrappings"] = {}

    def node(self, type, attrs=None, content=None, marks=None):
        if isinstance(type, str):
            type = self.node_type(type)
        elif not isinstance(type, NodeType):
            raise ValueError(f"Invalid node type: {type}")
        elif type.schema != self:
            raise ValueError(f"Node type from different schema used ({type.name})")
        return type.create_checked(attrs, content, marks)

    def text(self, text, marks=None):
        type = self.nodes.get("text")
        return TextNode(type, type.default_attrs, text, Mark.set_from(marks))

    def mark(self, type, attrs=None):
        if isinstance(type, str):
            type = self.marks[type]
        return type.create(attrs)

    def node_from_json(self, json_data):
        return Node.from_json(self, json_data)

    def mark_from_json(self, json_data):
        return Mark.from_json(self, json_data)

    def node_type(self, name):
        found = self.nodes.get(name)
        if not found:
            raise ValueError(f"Unknown node type: {name}")
        return found


def gather_marks(schema, marks):
    found = []
    for name in marks:
        mark = schema.marks.get(name)
        ok = mark
        if mark:
            found.append(mark)
        else:
            for prop in schema.marks:
                mark = schema.marks.get(prop)
                if name == "_" or (
                    mark.spec.get("group") and name in mark.spec["group"].split(" ")
                ):
                    ok = mark
                    found.append(mark)
        if not ok:
            raise SyntaxError(f"unknow mark type: '{mark}'")
    return found
