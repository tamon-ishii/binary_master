# Proposal: Scoped Namespaces for NamedOffset Keys

## Why

When authoring complex binary formats or files with multiple repeated chunks/sections, multiple struct instances often declare identical generic `NamedOffset` keys (e.g. `NamedOffset["payload"]`, `NamedOffset["data"]`). Without namespace scoping, these keys live in a flat global space, causing key collisions and unintended multi-slot bindings across independent sections.

Introducing a scoped namespace context manager (`with writer.namespace("scope_name"):`) allows callers to cleanly partition keys by scope without modifying struct definitions.

## What Changes

- Add `BinaryWriter.namespace(name: str = "", *, auto_id: bool = False)` context manager.
- Add `BinaryWriter.current_namespace` property returning the active namespace path string.
- Transparently qualify registered and resolved `NamedOffset` keys with the active namespace path (e.g. `"chunk_0/payload"`).
- Support leading `/` (e.g. `"/global_footer"`) to escape the active namespace and access/resolve root-level keys.
- Support `auto_id=True` for automatic sequential numbering (e.g. `"chunk_0"`, `"chunk_1"`).
- Support nesting of namespaces (`with writer.namespace("section"): with writer.namespace("sub"): ...`).
- Comprehensive documentation updates in `README.md`, `TUTORIAL.md`, and `FOR_AI.md`.

## Capabilities

### New Capabilities
<!-- None -->

### Modified Capabilities
- `named-offset`: Add hierarchical namespace scoping via `BinaryWriter.namespace` context manager with nesting, `auto_id`, and root escape (`/`) support.

## Impact

- Affected APIs: `BinaryWriter` methods (`namespace`, `current_namespace`, `reserve_named_offset`, `write_named_offset`, `rewrite_named_offset`, `_register_named_offset_slot`).
- Fully backward-compatible: when not using `writer.namespace()`, keys remain unscoped and behave identically to previous releases.
