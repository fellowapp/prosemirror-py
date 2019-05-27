# from prosemirror_transform import find_wrapping, lift_target, can_split, ReplaceAroundStep
# from prosemirror_model import Slice, Fragment, NodeRange


OL_DOM = ['ol', 0]
UL_DOM = ['ul', 0]
LI_DOM = ['li', 0]


orderd_list = {
    'attrs': {
        'order': {'default': 1},
    },
    'parseDOM': [{'tag': 'ol'}],
}

bullet_list = {
    'parseDOM': [{"tag": "ul"}]
}

list_item = {
    "parseDOM": [{"tag": "li"}],
    "defining": True,
}


def add(obj, props):
    return {**obj, **props}


def add_list_nodes(nodes, item_content, list_group):
    copy = nodes.copy()
    copy.update({
        "ordered_list": add(orderd_list, {"content": "list_item+", "group": list_group}),
        "bullet_list": add(bullet_list, {"content": "list_item+", "group": list_group}),
        "list_item": add(list_item, {"content": item_content}),
    })
    return copy
