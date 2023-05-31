import itertools
import re
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Literal, Tuple, cast

import lxml
from lxml.cssselect import CSSSelector
from lxml.html import HtmlElement as DOMNode

from .content import ContentMatch
from .fragment import Fragment
from .mark import Mark
from .node import Node, TextNode
from .replace import Slice
from .resolvedpos import ResolvedPos
from .schema import Attrs, MarkType, NodeType, Schema

WSType = bool | Literal["full"] | None


@dataclass
class DOMPosition:
    node: DOMNode
    offset: int
    pos: int | None = None


@dataclass(frozen=True)
class ParseOptions:
    preserve_whitespace: WSType = None
    find_positions: List[DOMPosition] | None = None
    from_: int | None = None
    to_: int | None = None
    top_node: Node | None = None
    top_match: ContentMatch | None = None
    context: ResolvedPos | None = None
    rule_from_node: Callable[[DOMNode], "ParseRule"] | None = None
    top_open: bool | None = None


@dataclass
class ParseRule:
    tag: str | None
    namespace: str | None
    style: str | None
    priority: int | None
    consuming: bool | None
    context: str | None
    node: str | None
    mark: str | None
    clear_mark: Callable[[Mark], bool] | None
    ignore: bool | None
    close_parent: bool | None
    skip: bool | None
    attrs: Attrs | None
    get_attrs: Callable[[DOMNode], None | Attrs | Literal[False]] | None
    content_element: str | DOMNode | Callable[[DOMNode], DOMNode] | None
    get_content: Callable[[DOMNode, Schema], Fragment] | None
    preserve_whitespace: WSType

    @classmethod
    def from_json(cls, data: Dict[str, Any]) -> "ParseRule":
        return ParseRule(
            data.get("tag"),
            data.get("namespace"),
            data.get("style"),
            data.get("priority"),
            data.get("consuming"),
            data.get("context"),
            data.get("node"),
            data.get("mark"),
            data.get("clear_mark"),
            data.get("ignore"),
            data.get("close_parent"),
            data.get("skip"),
            data.get("attrs"),
            data.get("getAttrs"),
            data.get("contentElement"),
            data.get("getContent"),
            data.get("preserveWhitespace"),
        )


class DOMParser:
    _tags: List[ParseRule]
    _styles: List[ParseRule]
    _normalize_lists: bool

    schema: Schema
    rules: List[ParseRule]

    def __init__(self, schema: Schema, rules: List[ParseRule]) -> None:
        self.schema = schema
        self.rules = rules
        self._tags = [rule for rule in rules if rule.tag is not None]

        self._styles = [rule for rule in rules if rule.style is not None]

        self.normalize_lists = not any(
            [
                schema.nodes[r.node].content_match.match_type(schema.nodes[r.node])
                for r in self._tags
                if r.node is not None
                and r.tag is not None
                and re.match(r"^(ul|ol)\b", r.tag) is not None
            ]
        )

    def parse(
        self, dom_: lxml.html.HtmlElement, options: ParseOptions | None = None
    ) -> Node:
        if options is None:
            options = ParseOptions()

        context = ParseContext(self, options, False)

        for d in itertools.chain([dom_], dom_.iterdescendants()):
            if d.text is not None and d.text.strip() and d.tag.lower() != "lxmltext":
                d.insert(0, lxml.html.fromstring(f"<lxmltext>{d.text}</lxmltext>"))
                d.text = None

            if d.tail is not None and d.tail.strip():
                parent = d.getparent()
                parent.insert(
                    parent.index(d) + 1,
                    lxml.html.fromstring(f"<lxmltext>{d.tail}</lxmltext>"),
                )
                d.tail = None

        context.add_all(dom_, options.from_, options.to_)

        return cast(Node, context.finish())

    def parse_slice(self, dom_: DOMNode, options: ParseOptions | None = None) -> Slice:
        if options is None:
            options = ParseOptions(preserve_whitespace=True)

        context = ParseContext(self, options, True)

        context.add_all(dom_, options.from_, options.to_)

        return Slice.max_open(cast(Fragment, context.finish()))

    def match_tag(
        self, dom_: DOMNode, context: "ParseContext", after: ParseRule | None = None
    ) -> ParseRule | None:
        try:
            i = self._tags.index(after) + 1 if after is not None else 0
        except ValueError:
            i = 0

        for rule in self._tags[i:]:
            if (
                rule.tag
                and matches(dom_, rule.tag)
                and (
                    rule.namespace is None
                    or (dom_.prefix and dom_.nsmap[dom_.prefix] == rule.namespace)
                )
                and (not rule.context or context.matches_context(rule.context))
            ):
                if rule.get_attrs is not None:
                    result = rule.get_attrs(dom_)
                    if result is False:
                        continue
                    rule.attrs = result

                return rule

            i += 1

        return None

    def match_style(
        self,
        prop: str,
        value: str,
        context: "ParseContext",
        after: ParseRule | None = None,
    ) -> ParseRule | None:
        i = self._styles.index(after) + 1 if after is not None else 0

        for rule in self._styles[i:]:
            style = rule.style

            if (
                style is None
                or style.index(prop) != 0
                or rule.context
                and not context.matches_context(rule.context)
                or len(style) > len(prop)
                and (ord(style[len(prop)]) != 61 or style[len(prop) + 1 :] != value)
            ):
                continue

            if rule.get_attrs is not None:
                result = rule.get_attrs(value)

                if result is False:
                    continue

                rule.attrs = result

            return rule

        return None

    @classmethod
    def schema_rules(cls, schema: Schema) -> List[ParseRule]:
        result: List[ParseRule] = []

        def insert(rule: ParseRule) -> None:
            priority = rule.priority if rule.priority is not None else 50
            i = 0

            while i < len(result):
                next = result[i]
                next_priority = next.priority if next.priority is not None else 50
                if next_priority < priority:
                    break
                i += 1

            result.insert(i, rule)
            return

        for name in schema.marks:
            rules = schema.marks[name].spec["parseDOM"]

            if rules:
                for rule in rules:
                    copied_rule = ParseRule.from_json(rule)
                    insert(copied_rule)
                    if not (
                        copied_rule.mark or copied_rule.ignore or copied_rule.clear_mark
                    ):
                        copied_rule.mark = name

        for name in schema.nodes:
            rules = schema.nodes[name].spec.get("parseDOM")

            if rules:
                for rule in rules:
                    copied_rule = ParseRule.from_json(rule)
                    insert(copied_rule)
                    if not (
                        copied_rule.mark or copied_rule.ignore or copied_rule.clear_mark
                    ):
                        copied_rule.node = name

        return result

    @classmethod
    def from_schema(cls, schema: Schema) -> "DOMParser":
        if "dom_parser" not in schema.cached:
            schema.cached["dom_parser"] = DOMParser(
                schema, DOMParser.schema_rules(schema)
            )

        return schema.cached["dom_parser"]


BLOCK_TAGS: Dict[str, bool] = {
    "address": True,
    "article": True,
    "aside": True,
    "blockquote": True,
    "canvas": True,
    "dd": True,
    "div": True,
    "dl": True,
    "fieldset": True,
    "figcaption": True,
    "figure": True,
    "footer": True,
    "form": True,
    "h1": True,
    "h2": True,
    "h3": True,
    "h4": True,
    "h5": True,
    "h6": True,
    "header": True,
    "hgroup": True,
    "hr": True,
    "li": True,
    "noscript": True,
    "ol": True,
    "output": True,
    "p": True,
    "pre": True,
    "section": True,
    "table": True,
    "tfoot": True,
    "ul": True,
}

IGNORE_TAGS: Dict[str, bool] = {
    "head": True,
    "noscript": True,
    "object": True,
    "script": True,
    "style": True,
    "title": True,
}

LIST_TAGS: Dict[str, bool] = {"ol": True, "ul": True}


OPT_PRESERVE_WS = 1
OPT_PRESERVE_WS_FULL = 2
OPT_OPEN_LEFT = 4


def ws_options_for(
    _type: NodeType | None, preserve_whitespace: WSType, base: int
) -> int:
    if preserve_whitespace is not None:
        return (OPT_PRESERVE_WS if preserve_whitespace else 0) | (
            OPT_PRESERVE_WS_FULL if preserve_whitespace == "full" else 0
        )

    return (
        OPT_PRESERVE_WS | OPT_PRESERVE_WS_FULL
        if _type is not None and _type.whitespace == "pre"
        else base & ~OPT_OPEN_LEFT
    )


class NodeContext:
    match: ContentMatch | None
    content: List[Node]

    active_marks: List[Mark]
    stash_marks: List[Mark]

    type: NodeType | None
    options: int

    attrs: Attrs | None
    marks: List[Mark]
    pending_marks: List[Mark]

    solid: bool

    def __init__(
        self,
        _type: NodeType | None,
        attrs: Attrs | None,
        marks: List[Mark],
        pending_marks: List[Mark],
        solid: bool,
        match: ContentMatch | None,
        options: int,
    ) -> None:
        self.type = _type
        self.options = options
        self.attrs = attrs
        self.marks = marks
        self.pending_marks = pending_marks
        self.solid = solid

        if match is not None:
            self.match = match
        else:
            self.match = (
                None
                if options & OPT_OPEN_LEFT or _type is None
                else _type.content_match
            )

        self.content = []

        self.active_marks = Mark.none
        self.stash_marks = []

    def find_wrapping(self, node: Node) -> List[NodeType] | None:
        if not self.match:
            if not self.type:
                return []

            fill = self.type.content_match.fill_before(Fragment.from_(node))

            if fill is not None:
                self.match = self.type.content_match.match_fragment(fill)
            else:
                start = self.type.content_match
                wrap = start.find_wrapping(node.type)

                if wrap is not None:
                    self.match = start
                    return wrap
                else:
                    return None

        if not self.match:
            return None

        return self.match.find_wrapping(node.type)

    def finish(self, open_end: bool) -> Node | Fragment:
        if not self.options & OPT_PRESERVE_WS:
            try:
                last: Node | None = self.content[-1]
            except IndexError:
                last = None

            if last is not None and last.is_text:
                last = cast(TextNode, last)
                m = re.findall(r"[ \t\r\n\u000c]+$", last.text)

                if m:
                    text = cast(TextNode, last)
                    if len(last.text) == len(m[0]):
                        self.content.pop()
                    else:
                        self.content[-1] = text.with_text(text.text[0 : -len(m[0])])

        content = Fragment.from_(self.content)
        if not open_end and self.match is not None:
            content = content.append(self.match.fill_before(Fragment.empty, True))

        return (
            self.type.create(self.attrs, content, self.marks) if self.type else content
        )

    def pop_from_stash_mark(self, mark: Mark) -> Mark | None:
        found_mark: Mark | None = None
        for stash_mark in self.stash_marks[::-1]:
            if mark.eq(stash_mark):
                found_mark = stash_mark

        if found_mark is not None:
            self.stash_marks.remove(found_mark)

        return found_mark

    def apply_pending(self, next_type: NodeType) -> None:
        pending = self.pending_marks
        for mark in pending:
            if (
                (self.type is not None and self.type.allows_mark_type(mark.type))
                or mark_may_apply(mark.type, next_type)
            ) and not mark.is_in_set(self.active_marks):
                self.active_marks = mark.add_to_set(self.active_marks)
                self.pending_marks = mark.remove_from_set(self.pending_marks)

    def inline_context(self, node: DOMNode) -> bool:
        if self.type:
            return self.type.inline_content
        if self.content:
            return self.content[0].is_inline

        return node.getparent() and node.getparent().tag.lower() not in BLOCK_TAGS


class ParseContext:
    open: int = 0
    find: List[DOMPosition] | None
    needs_block: bool
    nodes: List[NodeContext]
    options: ParseOptions
    is_open: bool
    parser: DOMParser

    def __init__(self, parser: DOMParser, options: ParseOptions, is_open: bool) -> None:
        self.parser = parser
        self.options = options
        self.is_open = is_open

        top_node = options.top_node
        top_options = ws_options_for(None, options.preserve_whitespace, 0) | (
            OPT_OPEN_LEFT if is_open else 0
        )

        if top_node:
            top_context: NodeContext = NodeContext(
                top_node.type,
                top_node.attrs,
                Mark.none,
                Mark.none,
                True,
                options.top_match or top_node.type.content_match,
                top_options,
            )
        elif is_open:
            top_context = NodeContext(
                None, None, Mark.none, Mark.none, True, None, top_options
            )
        else:
            top_context = NodeContext(
                parser.schema.top_node_type,
                None,
                Mark.none,
                Mark.none,
                True,
                None,
                top_options,
            )

        self.nodes = [top_context]
        self.find = options.find_positions
        self.needs_block = False

    @property
    def top(self) -> NodeContext:
        return self.nodes[self.open]

    def add_DOM(self, dom_: DOMNode) -> None:
        if get_node_type(dom_) == 3:
            self.add_text_node(dom_)
        elif get_node_type(dom_) == 1:
            style = ";".join(dom_.get("style", [""]))

            if not style:
                self.add_element(dom_)
            else:
                marks = self.read_styles(parse_styles(style))

                if marks is None:
                    return None

                add_marks, remove_marks = marks
                top = self.top

                for remove_mark in remove_marks:
                    self.remove_pending_mark(remove_mark, top)
                for add_mark in add_marks:
                    self.add_pending_mark(add_mark)

                self.add_element(dom_)

                for add_mark in add_marks:
                    self.remove_pending_mark(add_mark, top)
                for remove_mark in remove_marks:
                    self.add_pending_mark(remove_mark)

        return None

    def add_text_node(self, dom_: DOMNode) -> None:
        value = dom_.text
        top = self.top

        if (
            top.options & OPT_PRESERVE_WS_FULL
            or top.inline_context(dom_)  # type: ignore
            or re.search(r"[^ \t\r\n\u000c]", value) is not None
        ):
            if not (top.options & OPT_PRESERVE_WS):
                value = re.sub(r"[ \t\r\n\u000c]+", " ", value)

                if (
                    re.search(r"^[ \t\r\n\u000c]", value) is not None
                    and self.open == len(self.nodes) - 1
                ):
                    node_before = top.content[-1]
                    dom_node_before = dom_.getprevious()
                    if (
                        node_before is None
                        or (
                            dom_node_before is not None
                            and dom_node_before.tag.upper() == "BR"
                        )
                        or (
                            node_before.is_text
                            and re.search(
                                r"[ \t\r\n\u000c]$", cast(TextNode, node_before).text
                            )
                            is not None
                        )
                    ):
                        value = value[1:]

            elif not (top.options & OPT_PRESERVE_WS_FULL):
                value = re.sub(r"\r?\n|\r", " ", value)
            else:
                value = re.sub(r"\r\n?", "\n", value)

            if value:
                self.insert_node(self.parser.schema.text(value))

            self.find_in_text(dom_)
        else:
            self.find_inside(dom_)  # type: ignore

    def add_element(self, dom_: DOMNode, match_after: ParseRule | None = None) -> None:
        name = dom_.tag.lower()

        if name in LIST_TAGS and self.parser.normalize_lists:
            normalize_list(dom_)

        rule_id = self.parser.match_tag(dom_, self, match_after)
        rule = (
            self.options.rule_from_node(dom_)
            if self.options.rule_from_node
            else rule_id
        )

        if (rule and rule.ignore) or name in IGNORE_TAGS:
            self.find_inside(dom_)
            self.ignore_fallback(dom_)
        elif rule is None or rule.skip or rule.close_parent:
            if rule is not None and rule.close_parent:
                self.open = max(0, self.open - 1)
            elif rule is not None and get_node_type(cast(DOMNode, rule.skip)):
                dom_ = cast(DOMNode, rule.skip)

            top = self.top
            sync = False
            old_needs_block = self.needs_block
            if name in BLOCK_TAGS:
                if top.content and top.content[0].is_inline and self.open:
                    self.open -= 1
                    top = self.top

                sync = True

                if top.type is None:
                    self.needs_block = True

            elif not list(dom_):
                self.leaf_fallback(dom_)
                return

            self.add_all(dom_)

            if sync:
                self.sync(top)

            self.needs_block = old_needs_block

        else:
            self.add_element_by_rule(
                dom_, rule, rule_id if rule.consuming is False else None
            )

    def leaf_fallback(self, dom_: DOMNode) -> None:
        if dom_.tag.upper() == "BR" and self.top.type and self.top.type.inline_content:
            self.add_text_node(lxml.html.fromstring("<lxmltext>\n</lxmltext>"))

    def ignore_fallback(self, dom_: DOMNode) -> None:
        if dom_.tag.upper() == "BR" and (
            not self.top.type or self.top.type.inline_content
        ):
            self.find_place(self.parser.schema.text("-"))

    def read_styles(self, styles: List[str]) -> Tuple[List[Mark], List[Mark]] | None:
        add: List[Mark] = Mark.none
        remove: List[Mark] = Mark.none

        for i, style in enumerate(styles):
            after: ParseRule | None = None
            while i < len(styles) - 1:
                rule = self.parser.match_style(styles[i], styles[i + 1], self, after)
                if not rule:
                    break
                if rule.ignore:
                    return None
                if rule.clear_mark is not None:
                    for m in self.top.pending_marks + self.top.active_marks:
                        if rule.clear_mark(m):
                            remove = m.add_to_set(remove)
                else:
                    add = (
                        self.parser.schema.marks[rule.mark]
                        .create(rule.attrs)
                        .add_to_set(add)
                    )

                if rule.consuming is False:
                    after = rule
                else:
                    break
            i += 2

        return add, remove

    def add_element_by_rule(
        self, dom_: DOMNode, rule: ParseRule, continue_after: ParseRule | None = None
    ) -> None:
        sync: bool = False
        mark: Mark | None = None
        node_type: NodeType | None = None

        if rule.node is not None:
            node_type = self.parser.schema.nodes[rule.node]
            if node_type and not node_type.is_leaf:
                sync = self.enter(node_type, rule.attrs, rule.preserve_whitespace)
            elif node_type and not self.insert_node(node_type.create(rule.attrs)):
                self.leaf_fallback(dom_)
        elif rule.mark is not None:
            mark_type = self.parser.schema.marks[rule.mark]
            mark = mark_type.create(rule.attrs)
            if mark is not None:
                self.add_pending_mark(mark)

        start_in = self.top
        if node_type and node_type.is_leaf:
            self.find_inside(dom_)
        elif continue_after is not None:
            self.add_element(dom_, continue_after)
        elif rule.get_content is not None:
            self.find_inside(dom_)
            rule.get_content(dom_, self.parser.schema).for_each(
                lambda node: self.insert_node(node)
            )
        else:
            content_dom = dom_

            if isinstance(rule.content_element, str):
                content_dom = dom_.cssselect(rule.content_element)
            elif callable(rule.content_element):
                content_dom = rule.content_element(dom_)
            elif rule.content_element is not None:
                content_dom = rule.content_element

            self.find_around(dom_, content_dom, True)
            self.add_all(content_dom)

        if sync and self.sync(start_in):
            self.open -= 1

        if mark is not None:
            self.remove_pending_mark(mark, start_in)

    def add_all(
        self,
        parent: DOMNode,
        start_index: int | None = None,
        end_index: int | None = None,
    ) -> None:
        index = start_index if start_index is not None else 0

        try:
            dom_ = list(parent)[index]
        except IndexError:
            pass
        else:
            end = None if end_index is None else list(parent)[end_index]

            while dom_ != end:
                self.find_at_point(parent, index)
                self.add_DOM(dom_)

                dom_ = dom_.getnext()
                index += 1

        self.find_at_point(parent, index)

    def find_place(self, node: Node) -> bool:
        route: List[NodeType] | None = None
        sync: NodeContext | None = None

        depth = self.open
        while depth >= 0:
            cx = self.nodes[depth]
            found = cx.find_wrapping(node)
            if found is not None and (route is None or len(route) > len(found)):
                route = found
                sync = cx

                if found is None:
                    break

            if cx.solid:
                break

            depth -= 1

        if route is None:
            return False

        if sync is not None:
            self.sync(sync)

        for r in route:
            self.enter_inner(r, None, False)

        return True

    def insert_node(self, node: Node) -> bool:
        if node.is_inline and self.needs_block and self.top.type is None:
            block = self.textblock_from_context()
            if block is not None:
                self.enter_inner(block)

        if self.find_place(node):
            self.close_extra()

            top = self.top
            top.apply_pending(node.type)

            if top.match is not None:
                top.match = top.match.match_type(node.type)

            marks = top.active_marks
            for mark in node.marks:
                if top.type is None or top.type.allows_mark_type(mark.type):
                    marks = mark.add_to_set(marks)

            top.content.append(node.mark(marks))

            return True

        return False

    def enter(
        self, type_: NodeType, attrs: Attrs | None = None, preserve_ws: WSType = None
    ) -> bool:
        ok = self.find_place(type_.create(attrs))
        if ok:
            self.enter_inner(type_, attrs, True, preserve_ws)

        return ok

    def enter_inner(
        self,
        type_: NodeType,
        attrs: Attrs | None = None,
        solid: bool = False,
        preserve_ws: WSType = None,
    ) -> None:
        self.close_extra()

        top = self.top
        top.apply_pending(type_)

        if top.match is not None:
            top.match = top.match.match_type(type_)

        options = ws_options_for(type_, preserve_ws, top.options)

        if (top.options & OPT_OPEN_LEFT) and len(top.content) == 0:
            options |= OPT_OPEN_LEFT

        self.nodes.append(
            NodeContext(
                type_, attrs, top.active_marks, top.pending_marks, solid, None, options
            )
        )

        self.open += 1

    def close_extra(self, open_end: bool = False) -> None:
        i = len(self.nodes) - 1

        if i > self.open:
            while i > self.open:
                self.nodes[i - 1].content.append(
                    cast(Node, self.nodes[i].finish(open_end))
                )
                i -= 1

            self.nodes = self.nodes[: self.open + 1]

    def finish(self) -> Node | Fragment:
        self.open = 0
        self.close_extra(self.is_open)
        return self.nodes[0].finish(self.is_open or bool(self.options.top_open))

    def sync(self, to_: NodeContext) -> bool:
        i = self.open
        while i >= 0:
            if self.nodes[i] == to_:
                self.open = i
                return True
            i -= 1

        return False

    @property
    def current_pos(self) -> int:
        self.close_extra()
        pos = 0

        i = self.open
        while i >= 0:
            content = self.nodes[i].content

            for c in content[::-1]:
                pos += c.node_size

            if i:
                pos += 1

            i -= 1

        return pos

    def find_at_point(self, parent: DOMNode, offset: int) -> None:
        if self.find is not None:
            for f in self.find:
                if f.node == parent and f.offset == offset:
                    f.pos = self.current_pos

    def find_inside(self, parent: DOMNode) -> None:
        if self.find is not None:
            for f in self.find:
                if (
                    f.pos is None
                    and get_node_type(parent) == 1
                    and node_contains(parent, f.node)
                ):
                    f.pos = self.current_pos

    def find_around(self, parent: DOMNode, content: DOMNode, before: bool) -> None:
        if parent != content and self.find is not None:
            for f in self.find:
                if (
                    f.pos is None
                    and get_node_type(parent) == 1
                    and node_contains(parent, f.node)
                ):
                    pos = compare_document_position(content, f.node)
                    if pos & (2 if before else 4):
                        f.pos = self.current_pos

    def find_in_text(self, text_node: DOMNode) -> None:
        if self.find is not None:
            for f in self.find:
                if f.node == text_node:
                    f.pos = self.current_pos - (len(text_node.text) - f.offset)

    def matches_context(self, context: str) -> bool:
        if "|" in context:
            return any(
                [self.matches_context(s) for s in re.split(r"\s*\|\s*", context)]
            )

        parts = context.split("/")
        option = self.options.context
        use_root = not self.is_open and (
            option is None or option.parent.type == self.nodes[0].type
        )
        min_depth = -(option.depth + 1 if option is not None else 0) + int(not use_root)

        def match(i: int, depth: int) -> bool:
            while i >= 0:
                part = parts[i]

                if part == "":
                    if i == len(parts) - 1 or i == 0:
                        continue
                    while depth >= min_depth:
                        if match(i - 1, depth):
                            return True
                        depth -= 1
                    return False
                else:
                    if depth > 0 or (depth == 0 and use_root):
                        next: NodeType | None = self.nodes[depth].type
                    elif option is not None and depth >= min_depth:
                        next = option.node(depth - min_depth).type
                    else:
                        next = None

                    if next is None:
                        return False

                    try:
                        next.groups.index(part)
                    except IndexError:
                        if next.name != part:
                            return False

                    depth -= 1
                i -= 1
            return True

        return match(len(parts) - 1, self.open)

    def textblock_from_context(self) -> NodeType | None:
        context = self.options.context

        if context:
            d = context.depth
            while d >= 0:
                default = (
                    context.node(d)
                    .content_match_at(context.index_after(d))
                    .default_type
                )

                if (
                    default is not None
                    and default.is_textblock
                    and default.default_attrs
                ):
                    return default

                d -= 1

        for name, type_ in self.parser.schema.nodes.iteritems():
            if type_.is_textblock and type_.default_attrs:
                return type_

        return None

    def add_pending_mark(self, mark: Mark) -> None:
        found = find_same_mark_in_set(mark, self.top.pending_marks)

        if found is not None:
            self.top.stash_marks.append(found)

        self.top.pending_marks = mark.add_to_set(self.top.pending_marks)

    def remove_pending_mark(self, mark: Mark, upto: NodeContext) -> None:
        depth = self.open
        while depth >= 0:
            level = self.nodes[depth]
            try:
                level.pending_marks.index(mark)
            except ValueError:
                level.active_marks = mark.remove_from_set(level.active_marks)
                stash_mark = level.pop_from_stash_mark(mark)

                if (
                    stash_mark is not None
                    and level.type is not None
                    and level.type.allows_mark_type(stash_mark.type)
                ):
                    level.active_marks = stash_mark.add_to_set(level.active_marks)
            else:
                level.pending_marks = mark.remove_from_set(level.pending_marks)

            if level == upto:
                break

            depth -= 1


def normalize_list(dom_: DOMNode) -> None:
    child = list(dom_)[0]
    prev_item = None

    while child is not None:
        name = child.tag.lower() if get_node_type(child) == 1 else None  # type: ignore

        if name and name in LIST_TAGS and prev_item:
            prev_item.append(child)
            child = prev_item
        elif name == "li":
            prev_item = child
        elif name:
            prev_item = None

        child = child.getnext()


def matches(dom_: DOMNode, selector_str: str) -> bool:
    selector = CSSSelector(selector_str)

    return bool(dom_ in selector(dom_))  # type: ignore


def parse_styles(style: str) -> List[str]:
    regex = r"\s*([\w-]+)\s*:\s*([^;]+)"
    result: List[str] = []

    for m in re.findall(regex, style):
        result.append(m[0])
        result.append(m[1])

    return result


def mark_may_apply(mark_type: MarkType, node_type: NodeType) -> bool:
    nodes = node_type.schema.nodes

    for name, parent in nodes.items():
        if not parent.allows_mark_type(mark_type):
            continue

        seen: List[ContentMatch] = []

        def scan(match: ContentMatch) -> bool:
            seen.append(match)
            i = 0
            while i < match.edge_count:
                result = match.edge(i)
                _type = result["type"]
                _next = result["next"]

                if _type == node_type:
                    return True
                if _next not in seen and scan(_next):
                    return True

                i += 1
            return False

        if scan(parent.content_match):
            return True

    return False


def find_same_mark_in_set(mark: Mark, mark_set: List[Mark]) -> Mark | None:
    for comp in mark_set:
        if mark.eq(comp):
            return comp

    return None


def node_contains(node: DOMNode, find: DOMNode) -> bool:
    for child_node in node.iterdescendants():
        if child_node == find:
            return True

    return False


def compare_document_position(node1: DOMNode, node2: DOMNode) -> int:
    if not isinstance(node1, lxml.etree._Element) or not isinstance(
        node2, lxml.etree._Element
    ):
        raise ValueError("Both arguments must be lxml Element objects.")

    tree = lxml.etree.ElementTree(node1)

    # Get the XPath for the nodes
    xpath_node1 = tree.getpath(node1)
    xpath_node2 = tree.getpath(node2)

    found = []
    for nnode in tree.getroot().iterdescendants():
        if nnode in [node1, node2]:
            found.append(nnode)

    if len(found) == 2 and found[0] == node1:
        return 4
    elif len(found) == 2 and found[0] == node2:
        return 2

    # Compare the XPaths
    if xpath_node1 == xpath_node2:
        return 0  # Same node
    elif xpath_node1.startswith(xpath_node2):
        return 8  # Contains
    elif xpath_node2.startswith(xpath_node1):
        return 16  # Contained by
    else:
        return 1  # Disconnected


def get_node_type(element: DOMNode) -> int:
    if not isinstance(element, lxml.etree._Element):
        raise ValueError("The provided element is not an lxml HtmlElement.")

    if isinstance(element, lxml.etree._Comment):
        return 8  # Comment node type
    elif isinstance(element, lxml.etree._Entity):
        return 6  # Entity reference node type
    elif element.tag.lower() == "lxmltext":
        return 3  # Faked text node type
    elif element.tag.lower() == "document-fragment":
        return 11
    elif isinstance(element, lxml.etree._Element):
        return 1
    elif element.text and element.text.strip():
        return 3

    return 8


def from_html(schema: Schema, html: str) -> Dict[str, Any]:
    fragment = lxml.html.fragment_fromstring(html, create_parent="document-fragment")

    prose_doc = DOMParser.from_schema(schema).parse(fragment)

    return prose_doc.to_json()
