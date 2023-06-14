from prosemirror.utils import JSON


def compare_deep(a: JSON, b: JSON) -> bool:
    return a == b
