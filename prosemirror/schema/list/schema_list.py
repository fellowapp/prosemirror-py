from typing import cast

from prosemirror.model import Fragment, NodeRange, NodeType, Slice
from prosemirror.model.schema import AttributeSpec, Nodes, NodeSpec
from prosemirror.transform import ReplaceAroundStep, Transform, can_split, find_wrapping
from prosemirror.transform.structure import NodeTypeWithAttrs
from prosemirror.utils import Attrs

OL_DOM = ["ol", 0]
UL_DOM = ["ul", 0]
LI_DOM = ["li", 0]


ordered_list = NodeSpec(
    attrs={"order": AttributeSpec(default=1, validate="number")},
    parseDOM=[
        {
            "tag": "ol",
            "getAttrs": lambda dom: {
                "order": int(dom.get("start")) if dom.get("start") else 1,
            },
        }
    ],
    toDOM=lambda node: (
        OL_DOM
        if node.attrs.get("order") == 1
        else ["ol", {"start": node.attrs["order"]}, 0]
    ),
)

bullet_list = NodeSpec(parseDOM=[{"tag": "ul"}], toDOM=lambda _: UL_DOM)

list_item = NodeSpec(parseDOM=[{"tag": "li"}], defining=True, toDOM=lambda _: LI_DOM)


def add(obj: "NodeSpec", props: "NodeSpec") -> "NodeSpec":
    return {**obj, **props}


def add_list_nodes(
    nodes: dict["Nodes", "NodeSpec"],
    item_content: str,
    list_group: str | None = None,
) -> dict["Nodes", "NodeSpec"]:
    copy = nodes.copy()
    list_props = NodeSpec(content="list_item+")
    if list_group is not None:
        list_props["group"] = list_group
    copy.update({
        cast(Nodes, "ordered_list"): add(ordered_list, list_props),
        cast(Nodes, "bullet_list"): add(bullet_list, list_props),
        cast(Nodes, "list_item"): add(list_item, NodeSpec(content=item_content)),
    })
    return copy


def wrap_range_in_list(
    tr: Transform | None,
    range_: NodeRange,
    list_type: NodeType,
    attrs: Attrs | None = None,
) -> bool:
    """Try to wrap the given node range in a list of the given type.
    Return True when this is possible, False otherwise. When `tr` is
    non-None, the wrapping is added to that transaction. When it is
    None, the function only queries whether the wrapping is possible.
    """
    do_join = False
    outer_range = range_
    doc = range_.from_.doc
    # This is at the top of an existing list item
    if (
        range_.depth >= 2
        and range_.from_.node(range_.depth - 1).type.compatible_content(list_type)
        and range_.start_index == 0
    ):
        # Don't do anything if this is the top of the list
        if range_.from_.index(range_.depth - 1) == 0:
            return False
        insert = doc.resolve(range_.start - 2)
        outer_range = NodeRange(insert, insert, range_.depth)
        if range_.end_index < range_.parent.child_count:
            range_ = NodeRange(
                range_.from_, doc.resolve(range_.to.end(range_.depth)), range_.depth
            )
        do_join = True
    wrap = find_wrapping(outer_range, list_type, attrs, range_)
    if not wrap:
        return False
    if tr:
        _do_wrap_in_list(tr, range_, wrap, do_join, list_type)
    return True


def _do_wrap_in_list(
    tr: Transform,
    range_: NodeRange,
    wrappers: list[NodeTypeWithAttrs],
    join_before: bool,
    list_type: NodeType,
) -> Transform:
    content = Fragment.empty
    for i in range(len(wrappers) - 1, -1, -1):
        content = Fragment.from_(wrappers[i].type.create(wrappers[i].attrs, content))

    tr.step(
        ReplaceAroundStep(
            range_.start - (2 if join_before else 0),
            range_.end,
            range_.start,
            range_.end,
            Slice(content, 0, 0),
            len(wrappers),
            True,
        )
    )

    found = 0
    for i in range(len(wrappers)):
        if wrappers[i].type == list_type:
            found = i + 1
    split_depth = len(wrappers) - found

    split_pos = range_.start + len(wrappers) - (2 if join_before else 0)
    parent = range_.parent
    first = True
    for i in range(range_.start_index, range_.end_index):
        if not first and can_split(tr.doc, split_pos, split_depth):
            tr.split(split_pos, split_depth)
            split_pos += 2 * split_depth
        first = False
        split_pos += parent.child(i).node_size
    return tr
