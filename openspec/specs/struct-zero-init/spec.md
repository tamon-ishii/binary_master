# struct-zero-init Specification

## Purpose
Provides automatic zero-initialization of omitted fields in `@binary_struct`, a `BinaryStruct` / `Struct` base class for static typing, and top-level `to_bytes` and `from_bytes` utility functions.

## Requirements

### Requirement: Automatic Zero-Initialization of Omitted Fields
When instantiating a `@binary_struct` class, any field without an explicit default value that is omitted in constructor keyword arguments SHALL automatically default to a type-appropriate zero value (`0`, `0.0`, `False`, `b"\x00"*N`, `""`, `[]`, or `None`).

#### Scenario: Instantiating struct without arguments
- **WHEN** user defines `class Header: magic: UInt32; flags: UInt16`
- **AND** instantiates `Header()` without arguments
- **THEN** `magic` defaults to `0` and `flags` defaults to `0`

### Requirement: BinaryStruct Base Class and Method Descriptors
The library SHALL provide a `BinaryStruct` base class (and alias `Struct`) providing method descriptors and static typing signatures for `@binary_struct` operations including `to_bytes()`, `from_bytes()`, `offsetof()`, `bit_offsetof()`, and `byte_size`.

#### Scenario: Subclassing BinaryStruct for IDE autocomplete
- **WHEN** user inherits from `BinaryStruct` and decorates with `@binary_struct`
- **THEN** IDEs and type checkers recognize `.to_bytes()`, `.from_bytes()`, and other descriptor methods

### Requirement: Standalone to_bytes and from_bytes Functions
The library SHALL export `to_bytes(struct_instance)` and `from_bytes(StructCls, data)` from `binary_master`.

#### Scenario: Calling top-level serialization functions
- **WHEN** user calls `to_bytes(inst)` or `from_bytes(MyStruct, raw)`
- **THEN** the struct is serialized to `bytes` or deserialized from bytes respectively
