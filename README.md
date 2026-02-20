# prosemirror-py

[![CI](https://github.com/fellowapp/prosemirror-py/actions/workflows/test.yml/badge.svg)](https://github.com/fellowapp/prosemirror-py/actions/workflows/test.yml)
[![Code Coverage](https://codecov.io/gh/fellowapp/prosemirror-py/branch/master/graph/badge.svg?style=flat)](https://codecov.io/gh/fellowapp/prosemirror-py)
[![PyPI Package](https://img.shields.io/pypi/v/prosemirror.svg?style=flat)](https://pypi.org/project/prosemirror/)
[![License](https://img.shields.io/pypi/l/prosemirror.svg?style=flat)](https://github.com/fellowapp/prosemirror-py/blob/master/LICENSE.md)
[![Fellow Careers](https://img.shields.io/badge/fellow.app-hiring-576cf7.svg?style=flat)](https://fellow.app/careers/)

This package provides Python implementations of the following
[ProseMirror](https://prosemirror.net/) packages:

- [`prosemirror-model`](https://github.com/ProseMirror/prosemirror-model) version 1.25.4
- [`prosemirror-transform`](https://github.com/ProseMirror/prosemirror-transform) version 1.11.0
- [`prosemirror-test-builder`](https://github.com/ProseMirror/prosemirror-test-builder) version 1.1.1
- [`prosemirror-schema-basic`](https://github.com/ProseMirror/prosemirror-schema-basic) version 1.2.4
- [`prosemirror-schema-list`](https://github.com/ProseMirror/prosemirror-schema-list) version 1.5.1 (node specs and `wrapRangeInList` only; command functions that depend on `prosemirror-state` are excluded)

The original implementation has been followed as closely as possible during
translation to simplify keeping this package up-to-date with any upstream
changes.

## Why?

ProseMirror provides a powerful toolkit for building rich-text editors, but it's
JavaScript-only. Until now, the only option for manipulating and working with
ProseMirror documents from Python was to embed a JS runtime. With this
translation, you can now define schemas, parse documents, and apply transforms
directly via a native Python API.

## Status

The full ProseMirror test suite has been translated and passes. This project
only supports Python 3. The code has type annotations to support mypy or other
typechecking tools.

## Usage

Since this library is a direct port, the best place to learn how to use it is
the [official ProseMirror documentation](https://prosemirror.net/docs/guide/).
Here is a simple example using the included "basic" schema:

```python
from prosemirror.transform import Transform
from prosemirror.schema.basic import schema

# Create a document containing a single paragraph with the text "Hello, world!"
doc = schema.node(
    "doc", {}, [schema.node("paragraph", {}, [schema.text("Hello, world!")])]
)

# Create a Transform which will be applied to the document.
tr = Transform(doc)

# Delete the text from position 3 to 5. Adds a ReplaceStep to the transform.
tr.delete(3, 5)

# Make the first three characters bold. Adds an AddMarkStep to the transform.
tr.add_mark(1, 4, schema.mark("strong"))

# This transform can be converted to JSON to be sent and applied elsewhere.
assert [step.to_json() for step in tr.steps] == [
    {"stepType": "replace", "from": 3, "to": 5},
    {"stepType": "addMark", "mark": {"type": "strong"}, "from": 1, "to": 4},
]

# The resulting document can also be converted to JSON.
assert tr.doc.to_json() == {
    "type": "doc",
    "content": [
        {
            "type": "paragraph",
            "content": [
                {"type": "text", "marks": [{"type": "strong"}], "text": "Heo"},
                {"type": "text", "text": ", world!"},
            ],
        }
    ],
}
```

## Differences from Upstream

While the translation follows the original TypeScript implementation as closely
as possible, some adaptations were necessary for Python. These are documented
here for reference.

### Naming Conventions

Python's snake_case naming is used throughout:

- `camelCase` methods/properties become `snake_case` (e.g. `nodeSize` ->
  `node_size`, `isBlock` -> `is_block`, `textBetween` -> `text_between`)
- `from` (a Python keyword) becomes `from_` in parameter names and the
  `Fragment.from_()` static method

### DOM Handling

The upstream uses browser DOM APIs. The Python port uses
[lxml](https://lxml.de/) for parsing and a lightweight custom `Element` /
`DocumentFragment` model for serialization:

- **`DOMParser`**: Uses `lxml.html` for HTML parsing. Text nodes are wrapped in
  `<lxmltext>` pseudo-elements since lxml doesn't represent text nodes as
  separate child elements. CSS selector matching uses `lxml.cssselect`.
- **`DOMSerializer`**: Outputs HTML strings via custom `Element` and
  `DocumentFragment` classes rather than creating real DOM nodes.
- **XML namespaces**: Not supported (raises `NotImplementedError`). This only
  affects SVG or MathML node serialization.

### String Length and Slicing (UTF-16 Semantics)

JavaScript strings use UTF-16 encoding, so `string.length` counts UTF-16 code
units (surrogate pairs count as 2). The Python port preserves these semantics
using a `text_length()` helper and UTF-16 encode/decode for slicing in:

- `Node.node_size` / `TextNode.node_size`
- `TextNode.cut()`
- `TextNode.text_between()`
- `Fragment.findIndex()` / `Fragment.cut()`
- `diff.py` (character-by-character comparison)

### Deep Comparison

The upstream uses a custom `compareDeep` function for recursive comparison of
arrays/objects. The Python port uses native `==`, which already performs deep
comparison of dicts and lists.

### Resolve Cache

The upstream uses a `WeakMap<Node, ResolveCache>` for caching resolved
positions. Python uses a `dict[int, _ResolveCache]` keyed by `id(doc)` with a
`weakref.ref` callback to clean up entries when the document node is garbage
collected.

### Type System

- TypeScript interfaces (`NodeSpec`, `MarkSpec`, `ParseOptions`, etc.) are
  translated as `TypedDict` or frozen `dataclass` types.
- Union types use `X | Y` syntax (Python 3.10+).

### Additional Conveniences

These are Python-specific additions not present in the upstream:

- `Fragment.from_json()` accepts a JSON `str` and parses it automatically.
- `from_dom.py` includes a `from_html()` helper to parse an HTML string
  directly to a ProseMirror document.
- `DOMSerializer` output type is named `HTMLOutputSpec` (instead of
  `DOMOutputSpec`) to reflect that it produces HTML strings.

## AI Disclosure

The initial version of this translation was written manually in 2019. AI is now
used to help keep this translation up-to-date with upstream changes.
