# Proposal: NamedOffset, Direct OffsetTable, Automatic Zero-Init, and BinaryStruct Typing

## Why

1. **Direct OffsetTable Pointers**: Complex binary containers frequently utilize pointer tables to reference collections of data chunks or records directly without requiring an intermediate wrapper struct. Previously, users had to create an explicit wrapper struct to nest an `OffsetTable` inside an `Offset`, introducing unnecessary boilerplate.
2. **Streaming and Deferred Offsets (`NamedOffset`)**: When authoring headers or streams where payloads are placed after dynamic metadata, alignment padding, or variable-length sections, the target byte offset cannot be calculated upfront. A named deferred placeholder offset allows callers to reserve an offset slot in a header and resolve it downstream via `writer.write_named_offset("key")`.
3. **Ergonomic Instantiation via Automatic Zero-Initialization**: In binary structures with numerous fields or flags, requiring every field to be explicitly specified upon instantiation causes verbosity. Providing natural zero-initialization (e.g. `0`, `0.0`, `False`, `b"\x00"*N`, `[]`, `None`) allows partial instantiation (`MyStruct(magic=0x1234)`).
4. **Static Typing & IDE Integration**: Decorator-only structures lack explicit type hints for IDEs and type checkers (mypy/pyright). Providing `BinaryStruct` / `Struct` base classes and top-level `to_bytes` / `from_bytes` functions streamlines static analysis.

## What Changes

- Support direct `Offset[OffsetTable[Count, Type, BaseOffset], BaseOffset]` annotations on fields, allowing a raw Python list of structs to be provided and automatically serializing both the offset table and target payloads.
- Support `NamedOffset[Key, OffsetType, BaseOffset]` annotations and `writer.write_named_offset(key)` / `writer.rewrite_named_offset(key)` methods for deferred offset resolution with duplicate/missing error handling.
- Implement automatic zero-initialization for fields without explicit default values in `@binary_struct`, enabling instantiation with any subset of fields.
- Provide `BinaryStruct` (alias `Struct`) base class with class/instance methods and typing stubs (`to_bytes`, `from_bytes`, `offsetof`, `bit_offsetof`, `byte_size`, `write_manual`, `write_c_header`, `write_html`).
- Export `to_bytes`, `from_bytes`, `NamedOffset`, `BinaryStruct`, `Struct`, `DuplicateNamedOffsetError`, `NamedOffsetNotFoundError` from top-level `binary_master`.
- Comprehensive documentation updates in `README.md`, `TUTORIAL.md`, and `FOR_AI.md`.

## Capabilities

### New Capabilities
- `direct-offset-table`: Direct serialization and deserialization of `Offset[OffsetTable[...]]` lists without intermediate wrapper structs.
- `named-offset`: Deferred offset placeholders via `NamedOffset["key"]` and `writer.write_named_offset("key")`.
- `struct-zero-init`: Automatic zero-initialization of omitted struct fields, `BinaryStruct` / `Struct` base classes, and standalone `to_bytes` / `from_bytes`.

### Modified Capabilities
<!-- None -->

## Impact

- Affected APIs: `binary_master` module exports, `@binary_struct` class generation, `BinaryWriter` offset resolution.
- Backward compatibility: Fully backward-compatible; all additions are non-breaking extensions.
