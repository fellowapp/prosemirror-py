import itertools
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal, cast

import lxml.etree
import lxml.html
from lxml.cssselect import CSSSelector
from lxml.html import HtmlElement as DOMNode

from prosemirror.utils import Attrs, JSONDict

from .content import ContentMatch
from .fragment import Fragment
from .mark import Mark
from .node import Node, TextNode
from .replace import Slice
from .resolvedpos import ResolvedPos
from .schema import MarkType, NodeType, Schema

WSType = bool | Literal["full"] | None


@dataclass
class DOMPosition:
    node: DOMNode
    offset: int
    pos: int | None = None


@dataclass(frozen=True)
class ParseOptions:
    preserve_whitespace: WSType = None
    find_positions: list[DOMPosition] | None = None
    from_: int | None = None
    to_: int | None = None
    top_node: Node | None = None
    top_match: ContentMatch | None = None
    context: ResolvedPos | None = None
    rule_from_node: Callable[[DOMNode], "TagParseRule"] | None = None
    top_open: bool | None = None


@dataclass
class GenericParseRule:
    priority: int | None
    consuming: bool | None
    context: str | None
    mark: str | None
    ignore: bool | None
    close_parent: bool | None
    skip: bool | None
    attrs: Attrs | None

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "ParseRule":
        kwargs = {
            "priority": data.get("priority"),
            "consuming": data.get("consuming"),
            "context": data.get("context"),
            "mark": data.get("mark"),
            "ignore": data.get("ignore"),
            "close_parent": data.get("close_parent"),
            "skip": data.get("skip"),
            "attrs": data.get("attrs"),
        }
        if data.get("tag"):
            return TagParseRule(
                tag=data["tag"],
                namespace=data.get("namespace"),
                node=data.get("node"),
                get_attrs=data.get("getAttrs"),
                content_element=data.get("contentElement"),
                get_content=data.get("getContent"),
                preserve_whitespace=data.get("preserveWhitespace"),
                **kwargs,
            )
        else:
            return StyleParseRule(
                style=data.get("style"),
                clear_mark=data.get("clearMark"),
                get_attrs=data.get("getAttrs"),
                **kwargs,
            )


@dataclass
class TagParseRule(GenericParseRule):
    tag: str
    namespace: str | None
    node: str | None

    get_attrs: Callable[[DOMNode], Attrs | Literal[False] | None] | None
    content_element: str | DOMNode | Callable[[DOMNode], DOMNode] | None
    get_content: Callable[[DOMNode, Schema[Any, Any]], Fragment] | None
    preserve_whitespace: WSType


@dataclass
class StyleParseRule(GenericParseRule):
    style: str | None
    clear_mark: Callable[[Mark], bool] | None

    get_attrs: Callable[[str], Attrs | Literal[False] | None] | None


ParseRule = TagParseRule | StyleParseRule


class DOMParser:
    _tags: list[TagParseRule]
    _styles: list[StyleParseRule]
    _normalize_lists: bool

    schema: Schema[Any, Any]
    rules: list[ParseRule]

    def __init__(self, schema: Schema[Any, Any], rules: list[ParseRule]) -> None:
        self.schema = schema
        self.rules = rules
        self._tags: list[TagParseRule] = []
        self._styles: list[StyleParseRule] = []
        self.matched_styles: list[str] = []

        for rule in rules:
            if isinstance(rule, TagParseRule):
                self._tags.append(rule)
            elif isinstance(rule, StyleParseRule):
                if rule.style is not None:
                    prop = re.match(r"[^=]*", rule.style)
                    prop_name = prop.group(0) if prop else ""
                    if prop_name and prop_name not in self.matched_styles:
                        self.matched_styles.append(prop_name)
                self._styles.append(rule)

        self.normalize_lists = not any([
            schema.nodes[r.node].content_match.match_type(schema.nodes[r.node])
            for r in self._tags
            if r.node is not None and re.match(r"^(ul|ol)\b", r.tag) is not None
        ])

    def parse(
        self,
        dom_: lxml.html.HtmlElement,
        options: ParseOptions | None = None,
    ) -> Node:
        if options is None:
            options = ParseOptions()

        context = ParseContext(self, options, False)

        for d in itertools.chain([dom_], dom_.iterdescendants()):
            if (
                d.text is not None
                and d.text.strip()
                and str(d.tag).lower() != "lxmltext"
            ):
                child = lxml.html.Element("lxmltext")
                child.text = d.text
                d.insert(0, child)
                d.text = None

            if d.tail is not None and d.tail.strip():
                parent = d.getparent()
                if parent is not None:
                    child = lxml.html.Element("lxmltext")
                    child.text = d.tail
                    parent.insert(parent.index(d) + 1, child)
                    d.tail = None

        context.add_all(dom_, Mark.none, options.from_, options.to_)

        return cast(Node, context.finish())

    def parse_slice(self, dom_: DOMNode, options: ParseOptions | None = None) -> Slice:
        if options is None:
            options = ParseOptions(preserve_whitespace=True)

        context = ParseContext(self, options, True)

        context.add_all(dom_, Mark.none, options.from_, options.to_)

        return Slice.max_open(cast(Fragment, context.finish()))

    def match_tag(
        self,
        dom_: DOMNode,
        context: "ParseContext",
        after: TagParseRule | None = None,
    ) -> TagParseRule | None:
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

        return None

    def match_style(
        self,
        prop: str,
        value: str,
        context: "ParseContext",
        after: StyleParseRule | None = None,
    ) -> StyleParseRule | None:
        i = self._styles.index(after) + 1 if after is not None else 0

        for rule in self._styles[i:]:
            style = rule.style

            if (
                style is None
                or style.index(prop) != 0
                or (rule.context and not context.matches_context(rule.context))
                or (
                    len(style) > len(prop)
                    and (ord(style[len(prop)]) != 61 or style[len(prop) + 1 :] != value)
                )
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
    def schema_rules(cls, schema: Schema[Any, Any]) -> list[ParseRule]:
        result: list[ParseRule] = []

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
            rules = schema.marks[name].spec.get("parseDOM")

            if rules:
                for rule in rules:
                    copied_rule = GenericParseRule.from_json(rule)
                    insert(copied_rule)
                    if not (
                        copied_rule.mark
                        or copied_rule.ignore
                        or (
                            isinstance(copied_rule, StyleParseRule)
                            and copied_rule.clear_mark
                        )
                    ):
                        copied_rule.mark = name

        for name in schema.nodes:
            rules = schema.nodes[name].spec.get("parseDOM")

            if rules:
                for rule in rules:
                    copied_rule = cast(TagParseRule, GenericParseRule.from_json(rule))
                    insert(copied_rule)
                    if not (copied_rule.node or copied_rule.ignore or copied_rule.mark):
                        copied_rule.node = name

        return result

    @classmethod
    def from_schema(cls, schema: Schema[Any, Any]) -> "DOMParser":
        if "dom_parser" not in schema.cached:
            schema.cached["dom_parser"] = DOMParser(
                schema,
                DOMParser.schema_rules(schema),
            )

        return cast("DOMParser", schema.cached["dom_parser"])


BLOCK_TAGS: dict[str, bool] = {
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

IGNORE_TAGS: dict[str, bool] = {
    "head": True,
    "noscript": True,
    "object": True,
    "script": True,
    "style": True,
    "title": True,
}

LIST_TAGS: dict[str, bool] = {"ol": True, "ul": True}


OPT_PRESERVE_WS = 1
OPT_PRESERVE_WS_FULL = 2
OPT_OPEN_LEFT = 4


def ws_options_for(
    _type: NodeType | None,
    preserve_whitespace: WSType,
    base: int,
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
    content: list[Node]

    active_marks: list[Mark]

    type: NodeType | None
    options: int

    attrs: Attrs | None
    marks: list[Mark]

    solid: bool

    def __init__(
        self,
        _type: NodeType | None,
        attrs: Attrs | None,
        marks: list[Mark],
        solid: bool,
        match: ContentMatch | None,
        options: int,
    ) -> None:
        self.type = _type
        self.options = options
        self.attrs = attrs
        self.marks = marks
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

    def find_wrapping(self, node: Node) -> list[NodeType] | None:
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
                    if len(last.text) == len(m[0]):
                        self.content.pop()
                    else:
                        self.content[-1] = last.with_text(last.text[0 : -len(m[0])])

        content = Fragment.from_(self.content)
        if not open_end and self.match is not None:
            content = content.append(
                cast(Fragment, self.match.fill_before(Fragment.empty, True)),
            )

        return (
            self.type.create(self.attrs, content, self.marks) if self.type else content
        )

    def inline_context(self, node: DOMNode) -> bool:
        if self.type:
            return self.type.inline_content
        if self.content:
            return self.content[0].is_inline

        parent = node.getparent()
        if parent:
            return str(parent.tag).lower() not in BLOCK_TAGS
        return False


class ParseContext:
    open: int = 0
    find: list[DOMPosition] | None
    needs_block: bool
    nodes: list[NodeContext]
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
                True,
                options.top_match or top_node.type.content_match,
                top_options,
            )
        elif is_open:
            top_context = NodeContext(
                None,
                None,
                Mark.none,
                True,
                None,
                top_options,
            )
        else:
            top_context = NodeContext(
                parser.schema.top_node_type,
                None,
                Mark.none,
                True,
                None,
                top_options,
            )

        self.nodes = [top_context]
        self.find = options.find_positions
        self.needs_block = False
        self.local_preserve_ws = False

    @property
    def top(self) -> NodeContext:
        return self.nodes[self.open]

    def add_dom(self, dom_: DOMNode, marks: list[Mark]) -> None:
        if get_node_type(dom_) == 3:
            self.add_text_node(dom_, marks)
        elif get_node_type(dom_) == 1:
            self.add_element(dom_, marks)

    def add_text_node(self, dom_: DOMNode, marks: list[Mark]) -> None:
        value = dom_.text or ""
        top = self.top
        preserve_ws: WSType = (
            "full"
            if (top.options & OPT_PRESERVE_WS_FULL)
            else (self.local_preserve_ws or bool(top.options & OPT_PRESERVE_WS))
        )
        schema = self.parser.schema

        if (
            preserve_ws == "full"
            or top.inline_context(dom_)
            or re.search(r"[^ \t\r\n\u000c]", value) is not None
        ):
            if not preserve_ws:
                value = re.sub(r"[ \t\r\n\u000c]+", " ", value)

                if (
                    re.search(r"^[ \t\r\n\u000c]", value) is not None
                    and self.open == len(self.nodes) - 1
                ):
                    node_before = top.content[-1] if top.content else None
                    dom_node_before = dom_.getprevious()
                    if (
                        node_before is None
                        or (
                            dom_node_before is not None
                            and str(dom_node_before.tag).upper() == "BR"
                        )
                        or (
                            node_before.is_text
                            and re.search(
                                r"[ \t\r\n\u000c]$",
                                cast(TextNode, node_before).text,
                            )
                            is not None
                        )
                    ):
                        value = value[1:]

            elif preserve_ws == "full":
                value = re.sub(r"\r\n?", "\n", value)
            elif (
                schema.linebreak_replacement
                and re.search(r"[\r\n]", value)
                and self.top.find_wrapping(
                    schema.linebreak_replacement.create(),
                )
                is not None
            ):
                lines = re.split(r"\r?\n|\r", value)
                for i, line in enumerate(lines):
                    if i:
                        self.insert_node(
                            schema.linebreak_replacement.create(),
                            marks,
                            True,
                        )
                    if line:
                        self.insert_node(
                            schema.text(line),
                            marks,
                            not re.search(r"\S", line),
                        )
                value = ""
            else:
                value = re.sub(r"\r?\n|\r", " ", value)

            if value:
                self.insert_node(
                    schema.text(value),
                    marks,
                    not re.search(r"\S", value),
                )

            self.find_in_text(dom_)
        else:
            self.find_inside(dom_)

    def add_element(
        self,
        dom_: DOMNode,
        marks: list[Mark],
        match_after: TagParseRule | None = None,
    ) -> None:
        outer_ws = self.local_preserve_ws
        top = self.top
        name = str(dom_.tag).lower()

        if name == "pre" or re.search(r"white-space\s*:\s*pre", dom_.get("style", "")):
            self.local_preserve_ws = True

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
            self.ignore_fallback(dom_, marks)
        elif rule is None or rule.skip or rule.close_parent:
            if rule is not None and rule.close_parent:
                self.open = max(0, self.open - 1)
            elif rule is not None and get_node_type(cast(DOMNode, rule.skip)):
                dom_ = cast(DOMNode, rule.skip)

            sync = False
            old_needs_block = self.needs_block
            leaf_fallback_done = False
            if name in BLOCK_TAGS:
                if top.content and top.content[0].is_inline and self.open:
                    self.open -= 1
                    top = self.top

                sync = True

                if top.type is None:
                    self.needs_block = True

            elif not list(dom_):
                self.leaf_fallback(dom_, marks)
                leaf_fallback_done = True

            if not leaf_fallback_done:
                inner_marks = (
                    marks
                    if (rule and rule.skip)
                    else self.read_styles(
                        dom_,
                        marks,
                    )
                )
                if inner_marks is not None:
                    self.add_all(dom_, inner_marks)

                if sync:
                    self.sync(top)

                self.needs_block = old_needs_block

        else:
            inner_marks = self.read_styles(dom_, marks)
            if inner_marks is not None:
                self.add_element_by_rule(
                    dom_,
                    rule,
                    inner_marks,
                    rule_id if rule.consuming is False else None,
                )

        self.local_preserve_ws = outer_ws

    def leaf_fallback(self, dom_: DOMNode, marks: list[Mark]) -> None:
        if (
            str(dom_.tag).upper() == "BR"
            and self.top.type
            and self.top.type.inline_content
        ):
            child = lxml.html.Element("lxmltext")
            child.text = "\n"
            self.add_text_node(child, marks)

    def ignore_fallback(self, dom_: DOMNode, marks: list[Mark]) -> None:
        if str(dom_.tag).upper() == "BR" and (
            not self.top.type or self.top.type.inline_content
        ):
            self.find_place(self.parser.schema.text("-"), marks, True)

    def read_styles(
        self,
        dom_: DOMNode,
        marks: list[Mark],
    ) -> list[Mark] | None:
        style = dom_.get("style", "")
        if not style:
            return marks
        styles = parse_styles(style)
        style_dict: dict[str, str] = {}
        for i in range(0, len(styles), 2):
            style_dict[styles[i]] = styles[i + 1]

        for name in self.parser.matched_styles:
            value = style_dict.get(name)
            if not value:
                continue
            after: StyleParseRule | None = None
            while True:
                rule = self.parser.match_style(name, value, self, after)
                if not rule:
                    break
                if rule.ignore:
                    return None
                if rule.clear_mark is not None:
                    marks = [m for m in marks if not rule.clear_mark(m)]
                else:
                    marks = [
                        *marks,
                        self.parser.schema.marks[cast(str, rule.mark)].create(
                            rule.attrs
                        ),
                    ]

                if rule.consuming is False:
                    after = rule
                else:
                    break

        return marks

    def add_element_by_rule(
        self,
        dom_: DOMNode,
        rule: TagParseRule,
        marks: list[Mark],
        continue_after: TagParseRule | None = None,
    ) -> None:
        sync: bool = False
        node_type: NodeType | None = None

        if rule.node is not None:
            node_type = self.parser.schema.nodes[rule.node]
            if node_type and not node_type.is_leaf:
                inner = self.enter(
                    node_type,
                    rule.attrs,
                    marks,
                    rule.preserve_whitespace,
                )
                if inner is not None:
                    sync = True
                    marks = inner
            elif node_type and not self.insert_node(
                node_type.create(rule.attrs),
                marks,
                str(dom_.tag).upper() == "BR",
            ):
                self.leaf_fallback(dom_, marks)
        elif rule.mark is not None:
            mark_type = self.parser.schema.marks[rule.mark]
            marks = [*marks, mark_type.create(rule.attrs)]

        start_in = self.top
        if node_type and node_type.is_leaf:
            self.find_inside(dom_)
        elif continue_after is not None:
            self.add_element(dom_, marks, continue_after)
        elif rule.get_content is not None:
            self.find_inside(dom_)
            rule.get_content(dom_, self.parser.schema).for_each(
                lambda node, offset, index: self.insert_node(node, marks, False),
            )
        else:
            content_dom = dom_

            if isinstance(rule.content_element, str):
                content_dom = dom_.cssselect(rule.content_element)[0]
            elif callable(rule.content_element):
                content_dom = rule.content_element(dom_)
            elif rule.content_element is not None:
                content_dom = rule.content_element

            self.find_around(dom_, content_dom, True)
            self.add_all(content_dom, marks)
            self.find_around(dom_, content_dom, False)

        if sync and self.sync(start_in):
            self.open -= 1

    def add_all(
        self,
        parent: DOMNode,
        marks: list[Mark],
        start_index: int | None = None,
        end_index: int | None = None,
    ) -> None:
        index = start_index if start_index is not None else 0

        children = list(parent)
        dom_: lxml.html.HtmlElement | None = (
            children[index] if index < len(children) else None
        )
        end = None if end_index is None else children[end_index]

        while dom_ is not None and dom_ != end:
            self.find_at_point(parent, index)
            self.add_dom(dom_, marks)

            dom_ = dom_.getnext()
            index += 1

        self.find_at_point(parent, index)

    def find_place(
        self,
        node: Node,
        marks: list[Mark],
        cautious: bool = False,
    ) -> list[Mark] | None:
        route: list[NodeType] | None = None
        sync: NodeContext | None = None

        depth = self.open
        penalty = 0
        while depth >= 0:
            cx = self.nodes[depth]
            found = cx.find_wrapping(node)
            if found is not None and (
                route is None or len(route) > len(found) + penalty
            ):
                route = found
                sync = cx

                if not found:
                    break

            if cx.solid:
                if cautious:
                    break
                penalty += 2

            depth -= 1

        if route is None:
            return None

        if sync is not None:
            self.sync(sync)

        for r in route:
            marks = self.enter_inner(r, None, marks, False)

        return marks

    def insert_node(
        self,
        node: Node,
        marks: list[Mark],
        cautious: bool = False,
    ) -> bool:
        if node.is_inline and self.needs_block and self.top.type is None:
            block = self.textblock_from_context()
            if block is not None:
                marks = self.enter_inner(block, None, marks)

        inner_marks = self.find_place(node, marks, cautious)
        if inner_marks is not None:
            self.close_extra()

            top = self.top
            if top.match is not None:
                top.match = top.match.match_type(node.type)

            node_marks: list[Mark] = Mark.none
            for m in [*inner_marks, *node.marks]:
                if (
                    top.type.allows_mark_type(m.type)
                    if top.type
                    else mark_may_apply(m.type, node.type)
                ):
                    node_marks = m.add_to_set(node_marks)

            top.content.append(node.mark(node_marks))

            return True

        return False

    def enter(
        self,
        type_: NodeType,
        attrs: Attrs | None,
        marks: list[Mark],
        preserve_ws: WSType = None,
    ) -> list[Mark] | None:
        inner_marks = self.find_place(type_.create(attrs), marks, False)
        if inner_marks is not None:
            inner_marks = self.enter_inner(type_, attrs, marks, True, preserve_ws)
        return inner_marks

    def enter_inner(
        self,
        type_: NodeType,
        attrs: Attrs | None,
        marks: list[Mark],
        solid: bool = False,
        preserve_ws: WSType = None,
    ) -> list[Mark]:
        self.close_extra()

        top = self.top
        top.match = top.match.match_type(type_) if top.match else None

        options = ws_options_for(type_, preserve_ws, top.options)

        if (top.options & OPT_OPEN_LEFT) and len(top.content) == 0:
            options |= OPT_OPEN_LEFT

        apply_marks: list[Mark] = Mark.none
        remaining_marks: list[Mark] = []
        for m in marks:
            if (
                top.type.allows_mark_type(m.type)
                if top.type
                else mark_may_apply(m.type, type_)
            ):
                apply_marks = m.add_to_set(apply_marks)
            else:
                remaining_marks.append(m)

        self.nodes.append(
            NodeContext(
                type_,
                attrs,
                apply_marks,
                solid,
                None,
                options,
            ),
        )

        self.open += 1
        return remaining_marks

    def close_extra(self, open_end: bool = False) -> None:
        i = len(self.nodes) - 1

        if i > self.open:
            while i > self.open:
                self.nodes[i - 1].content.append(
                    cast(Node, self.nodes[i].finish(open_end)),
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
            elif self.local_preserve_ws:
                self.nodes[i].options |= OPT_PRESERVE_WS
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
                    f.pos = self.current_pos - (len(text_node.text or "") - f.offset)

    def matches_context(self, context: str) -> bool:
        if "|" in context:
            return any([
                self.matches_context(s) for s in re.split(r"\s*\|\s*", context)
            ])

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

                    if next.name != part and not next.is_in_group(part):
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
                    context
                    .node(d)
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

        for type_ in self.parser.schema.nodes.values():
            if type_.is_textblock and type_.default_attrs:
                return type_

        return None


def normalize_list(dom_: DOMNode) -> None:
    child: lxml.html.HtmlElement | None = next(iter(dom_), None)
    prev_item: DOMNode | None = None

    while child is not None:
        name = str(child.tag).lower() if get_node_type(child) == 1 else None

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

    return bool(dom_ in selector(dom_))


def parse_styles(style: str) -> list[str]:
    regex = r"\s*([\w-]+)\s*:\s*([^;]+)"
    result: list[str] = []

    for m in re.findall(regex, style):
        result.append(m[0])
        result.append(m[1])

    return result


def mark_may_apply(mark_type: MarkType, node_type: NodeType) -> bool:
    nodes = node_type.schema.nodes

    for parent in nodes.values():
        if not parent.allows_mark_type(mark_type):
            continue

        seen: list[ContentMatch] = []

        def scan(match: ContentMatch) -> bool:
            seen.append(match)  # noqa: B023
            i = 0
            while i < match.edge_count:
                result = match.edge(i)
                type_ = result.type
                next_ = result.next

                if type_ == node_type:
                    return True
                if next_ not in seen and scan(next_):  # noqa: B023
                    return True

                i += 1
            return False

        if scan(parent.content_match):
            return True

    return False


def node_contains(node: DOMNode, find: DOMNode) -> bool:
    return any(child_node == find for child_node in node.iterdescendants())


def compare_document_position(node1: DOMNode, node2: DOMNode) -> int:
    if not isinstance(node1, lxml.etree._Element) or not isinstance(
        node2,
        lxml.etree._Element,
    ):
        msg = "Both arguments must be lxml Element objects."
        raise ValueError(msg)

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
        msg = "The provided element is not an lxml HtmlElement."
        raise ValueError(msg)

    if isinstance(element, lxml.etree._Comment):
        return 8  # Comment node type
    elif isinstance(element, lxml.etree._Entity):
        return 6  # Entity reference node type
    elif str(element.tag).lower() == "lxmltext":
        return 3  # Faked text node type
    elif str(element.tag).lower() == "document-fragment":
        return 11
    elif isinstance(element, lxml.etree._Element):
        return 1
    elif element.text and element.text.strip():
        return 3

    return 8


def from_html(schema: Schema[Any, Any], html: str) -> JSONDict:
    fragment = lxml.html.fragment_fromstring(html, create_parent="document-fragment")

    prose_doc = DOMParser.from_schema(schema).parse(fragment)

    return prose_doc.to_json()
