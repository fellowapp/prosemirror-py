from collections.abc import Mapping, Sequence
from typing import TypeAlias

JSONDict: TypeAlias = Mapping[str, "JSON"]
JSONList: TypeAlias = Sequence["JSON"]

JSON: TypeAlias = JSONDict | JSONList | str | int | float | bool | None

Attrs: TypeAlias = JSONDict


def text_length(text: str) -> int:
    return len(text.encode("utf-16-le")) // 2
