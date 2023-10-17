# prosemirror-py

[![CI](https://github.com/fellowapp/prosemirror-py/actions/workflows/test.yml/badge.svg)](https://github.com/fellowapp/prosemirror-py/actions/workflows/test.yml)
[![Code Coverage](https://codecov.io/gh/fellowapp/prosemirror-py/branch/master/graph/badge.svg?style=flat)](https://codecov.io/gh/fellowapp/prosemirror-py)
[![Python Version](https://img.shields.io/pypi/pyversions/prosemirror.svg?style=flat)](https://pypi.org/project/prosemirror/)
[![PyPI Package](https://img.shields.io/pypi/v/prosemirror.svg?style=flat)](https://pypi.org/project/prosemirror/)
[![License](https://img.shields.io/pypi/l/prosemirror.svg?style=flat)](https://github.com/fellowapp/prosemirror-py/blob/master/LICENSE.md)
[![Fellow Careers](https://img.shields.io/badge/fellow.app-hiring-576cf7.svg?style=flat)](https://fellow.app/careers/)

This package provides Python implementations of the following
[ProseMirror](https://prosemirror.net/) packages:

- [`prosemirror-model`](https://github.com/ProseMirror/prosemirror-model) version 1.18.1
- [`prosemirror-transform`](https://github.com/ProseMirror/prosemirror-transform) version 1.7.4
- [`prosemirror-test-builder`](https://github.com/ProseMirror/prosemirror-test-builder)
- [`prosemirror-schema-basic`](https://github.com/ProseMirror/prosemirror-schema-basic) version 1.1.2
- [`prosemirror-schema-list`](https://github.com/ProseMirror/prosemirror-schema-list)

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
only supports Python 3. There are no type annotations at the moment, although
the original has annotations available in doc comments.

## Usage

Since this library is a direct port, the best place to learn how to use it is
the [official ProseMirror documentation](https://prosemirror.net/docs/guide/).
Here is a simple example using the included "basic" schema:

```python
from prosemirror.transform import Transform
from prosemirror.schema.basic import schema

# Create a document containing a single paragraph with the text "Hello, world!"
doc = schema.node("doc", {}, [
    schema.node("paragraph", {}, [
        schema.text("Hello, world!")
    ])
])

# Create a Transform which will be applied to the document.
tr = Transform(doc)

# Delete the text from position 3 to 5. Adds a ReplaceStep to the transform.
tr.delete(3, 5)

# Make the first three characters bold. Adds an AddMarkStep to the transform.
tr.add_mark(1, 4, schema.mark("strong"))

# This transform can be converted to JSON to be sent and applied elsewhere.
assert [step.to_json() for step in tr.steps] == [{
    'stepType': 'replace',
    'from': 3,
    'to': 5
}, {
    'stepType': 'addMark',
    'mark': {'type': 'strong', 'attrs': {}},
    'from': 1,
    'to': 4
}]

# The resulting document can also be converted to JSON.
assert tr.doc.to_json() == {
    'type': 'doc',
    'content': [{
        'type': 'paragraph',
        'content': [{
            'type': 'text',
            'marks': [{'type': 'strong', 'attrs': {}}],
            'text': 'Heo'
        }, {
            'type': 'text',
            'text': ', world!'
        }]
    }]
}
```
