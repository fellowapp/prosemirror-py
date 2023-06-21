from typing import Mapping, MutableMapping, MutableSequence, Sequence, Union

from typing_extensions import TypeAlias

JSONDict: TypeAlias = Mapping[str, "JSON"]
JSONList: TypeAlias = Sequence["JSON"]

JSON: TypeAlias = Union[JSONDict, JSONList, str, int, float, bool, None]

MutableJSONDict: TypeAlias = MutableMapping[str, "MutableJSON"]
MutableJSONList: TypeAlias = MutableSequence["MutableJSON"]

MutableJSON: TypeAlias = Union[
    MutableJSONDict, MutableJSONList, str, int, float, bool, None
]


def text_length(text: str) -> int:
    return len(text.encode("utf-16-le")) // 2
