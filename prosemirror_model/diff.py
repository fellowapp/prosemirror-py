def find_diff_start(a, b, pos):
    i = 0
    while True:
        if a.child_count == i or b.child_count == i:
            return None if a.child_count == b.child_count else pos
        child_a, child_b = a.child(i), b.child(i)
        if child_a == child_b:
            pos += child_a.node_size
            continue
        if not child_a.same_markup(child_b):
            return pos
        if child_a.is_text and child_a.text != child_b.text:
            if child_b.text.startswith(child_a.text):
                return pos + len(child_a.text)
            if child_a.text.startswith(child_b.text):
                return pos + len(child_b.text)
            next_index = next(
                (
                    index_a
                    for ((index_a, char_a), (_, char_b)) in zip(
                        enumerate(child_a.text), enumerate(child_b.text)
                    )
                    if char_a != char_b
                ),
                None,
            )
            if next_index is not None:
                return pos + next_index
        if child_a.content.size or child_b.content.size:
            inner = find_diff_start(child_a.content, child_b.content, pos + 1)
            if inner:
                return inner
        pos += child_a.node_size
        i += 1


def find_diff_end(a, b, pos_a, pos_b):
    i_a, i_b = a.child_count, b.child_count
    while True:
        if i_a == 0 or i_b == 0:
            if i_a == i_b:
                return None
            else:
                return {"a": pos_a, "b": pos_b}
        i_a -= 1
        i_b -= 1
        child_a, child_b = a.child(i_a), b.child(i_b)
        size = child_a.node_size
        if child_a == child_b:
            pos_a -= size
            pos_b -= size
            continue

        if not child_a.same_markup(child_b):
            return {"a": pos_a, "b": pos_b}

        if child_a.is_text and child_a.text != child_b.text:
            same, min_size = 0, min(len(child_a.text), len(child_b.text))
            while (
                same < min_size
                and child_a.text[len(child_a.text) - same - 1]
                == child_b.text[len(child_b.text) - same - 1]
            ):
                same += 1
                pos_a -= 1
                pos_b -= 1
            return {"a": pos_a, "b": pos_b}

        if child_a.content.size or child_b.content.size:
            inner = find_diff_end(
                child_a.content, child_b.content, pos_a - 1, pos_b - 1
            )
            if inner:
                return inner

        pos_a -= size
        pos_b -= size
