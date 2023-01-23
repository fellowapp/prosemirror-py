OL_DOM = ["ol", 0]
UL_DOM = ["ul", 0]
LI_DOM = ["li", 0]


orderd_list = {
    "attrs": {"order": {"default": 1}},
    "parseDOM": [{"tag": "ol"}],
    "toDOM": lambda node: (
        OL_DOM
        if node.attrs.get("order") == 1
        else ["ol", {"start": node.attrs["order"]}, 0]
    ),
}

bullet_list = {"parseDOM": [{"tag": "ul"}], "toDOM": lambda _: UL_DOM}

list_item = {"parseDOM": [{"tag": "li"}], "defining": True, "toDOM": lambda _: LI_DOM}


def add(obj, props):
    return {**obj, **props}


def add_list_nodes(nodes, item_content, list_group):
    copy = nodes.copy()
    copy.update(
        {
            "ordered_list": add(
                orderd_list, {"content": "list_item+", "group": list_group}
            ),
            "bullet_list": add(
                bullet_list, {"content": "list_item+", "group": list_group}
            ),
            "list_item": add(list_item, {"content": item_content}),
        }
    )
    return copy
