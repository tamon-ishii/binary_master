# struct-binary-size Specification

## Purpose
Enables querying the binary byte size of `@binary_struct` structures both statically from classes and dynamically from instances.

## Requirements

### Requirement: Static Binary Size from Struct Class
The system SHALL provide the binary byte size of a `@binary_struct` class via `Cls.binary_size` and `sizeof(Cls)`.
For structures with fixed-size fields (primitives, sized `Offset`s, `OffsetTable`s, `FixedArray`s, bitfields, and alignment paddings), the exact byte size SHALL be calculated statically. If a class contains variable-length fields (`Array[T]`, `str`, `bytes`), a `ValueError` SHALL be raised when querying class-level size.

#### Scenario: Querying static size of a struct with 2-byte offset
- **WHEN** user defines `class Header: magic: UInt32; offset: Offset[Chunk, UInt16]`
- **THEN** `Header.binary_size` and `sizeof(Header)` return `6`

#### Scenario: Querying static size with automatic alignment
- **WHEN** user defines `class Aligned: a: UInt8; b: UInt32` with `auto_align=True`
- **THEN** `Aligned.binary_size` returns `8` (1 byte + 3 bytes padding + 4 bytes)

### Requirement: Dynamic Binary Size from Struct Instance
The system SHALL provide the binary byte size of a `@binary_struct` instance via `instance.binary_size`, `sizeof(instance)`, and `len(instance)`. The size SHALL equal the exact number of bytes serialized by `instance.to_bytes()`.

#### Scenario: Querying instance binary size
- **WHEN** user creates an instance `header = Header(...)`
- **THEN** `header.binary_size`, `sizeof(header)`, and `len(header)` return the exact serialized byte length

### Requirement: Standalone sizeof and binary_size Functions
The library SHALL export `sizeof(target)` and `binary_size(target)` functions from `binary_master`, accepting either a `@binary_struct` class, an instance, or a `BinaryType` primitive (e.g. `UInt16`).

#### Scenario: Using sizeof function on primitive and struct
- **WHEN** user calls `sizeof(UInt16)`
- **THEN** `sizeof(UInt16)` returns `2`
