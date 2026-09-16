## Context

The library supports complex binary structures with declarative field annotations. In recent iterations, direct offset pointer tables, deferred named offsets, and frictionless instantiation with zero-initialization were designed and implemented. See `proposal.md` for complete background.

## Goals / Non-Goals

**Goals:**
- Enable pointer tables pointing directly to lists of target structs without intermediate containers (`Offset[OffsetTable[...]]`).
- Support deferred placeholder offset backpatching via `NamedOffset["key"]` and `writer.write_named_offset("key")`.
- Provide automatic zero-initialization for fields without explicit default values.
- Provide `BinaryStruct` / `Struct` base class with descriptors for IDE autocompletion and static type checkers.
- Provide standalone `to_bytes` and `from_bytes` utility functions.

**Non-Goals:**
- Breaking existing `@binary_struct` syntax or backward compatibility.
- Altering existing `OffsetTable` standalone behavior when not wrapped in `Offset`.

## Decisions

1. **Direct OffsetTable Serialization Integration**:
   - *Choice*: In `_extract_offset_target` and `write_struct`, detect when `Offset` target is `OffsetTable`. In `write_struct`, resolve list length, update linked `LengthOf`/`CountOf`, write table of relative offsets, and write payload structs at the end of the stream.
   - *Rationale*: Allows users to simply pass a Python `list` to the field, making the API idiomatic and reducing boilerplate.

2. **NamedOffset Registry in BinaryWriter**:
   - *Choice*: Use an internal dictionary `_named_offsets: dict[str, NamedOffsetInfo]` in `BinaryWriter`.
   - *Rationale*: Cleanly isolates placeholder tracking and backpatching.
   - *Error Handling*: Raise `DuplicateNamedOffsetError` on collision; raise `NamedOffsetNotFoundError` on unknown key access.

3. **Zero-Initialization in Constructor Generation**:
   - *Choice*: When constructing `__init__` parameter defaults in `_create_init_fn`, evaluate field types and supply suitable default zero values (`0`, `0.0`, `False`, `b"\x00"*N`, `[]`, `None`).
   - *Rationale*: Eliminates the requirement to provide all arguments when creating test structs or partial instances.

4. **BinaryStruct Base Class Descriptors**:
   - *Choice*: Define descriptors on `BinaryStruct` for `.to_bytes()`, `.from_bytes()`, `.offsetof()`, `.bit_offsetof()`, and `.byte_size`.
   - *Rationale*: Enables type-safe IDE autocomplete and static analysis without needing metaclasses.

## Risks / Trade-offs

- **[Risk] Confusion between OffsetTable standalone vs inside Offset**:
  - *Mitigation*: Clearly document both patterns in `TUTORIAL.md` and `FOR_AI.md`.
