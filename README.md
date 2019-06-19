# prosemirror-py

[![Build Status](https://travis-ci.org/fellowinsights/prosemirror-py.svg?branch=master)](https://travis-ci.org/fellowinsights/prosemirror-py)

This package provides Python implementations of the following [ProseMirror](https://prosemirror.net/) packages:

-   [`prosemirror-model`](https://github.com/ProseMirror/prosemirror-model)
-   [`prosemirror-transform`](https://github.com/ProseMirror/prosemirror-transform)
-   [`prosemirror-test-builder`](https://github.com/ProseMirror/prosemirror-test-builder)
-   [`prosemirror-schema-basic`](https://github.com/ProseMirror/prosemirror-schema-basic)
-   [`prosemirror-schema-list`](https://github.com/ProseMirror/prosemirror-schema-list)

The original implementation has been followed as closely as possible during translation to simplify keeping this package up-to-date with any upstream changes.

## Why?

ProseMirror provides a powerful toolkit for building rich-text editors, but it's JavaScript-only. Until now, the only option for manipulating and working with ProseMirror documents from Python was to embed a JS runtime. With this translation, you can now define schemas, parse documents, and apply transforms directly via a native Python API.

## Status

The full ProseMirror test suite has been translated and passes. This project only supports Python 3. There are no type annotations at the moment, although the original has annotations available in doc comments.
