from typing import cast

from prosemirror.model.schema import Nodes, NodeSpec

OL_DOM = ["ol", 0]
UL_DOM = ["ul", 0]
LI_DOM = ["li", 0]


orderd_list = NodeSpec(
    attrs={"order": {"default": 1}},
    parseDOM=[{"tag": "ol"}],
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
    nodes: dict["Nodes", "NodeSpec"], item_content: str, list_group: str
) -> dict["Nodes", "NodeSpec"]:
    copy = nodes.copy()
    copy.update({
        cast(Nodes, "ordered_list"): add(
            orderd_list, NodeSpec(content="list_item+", group=list_group)
        ),
        cast(Nodes, "bullet_list"): add(
            bullet_list, NodeSpec(content="list_item+", group=list_group)
        ),
        cast(Nodes, "list_item"): add(list_item, NodeSpec(content=item_content)),
    })
    return copy
