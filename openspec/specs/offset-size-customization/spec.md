# offset-size-customization Specification

## Purpose
Enables specifying custom byte sizes and types (e.g. 1-byte, 2-byte, 4-byte, 8-byte) and optional base offsets for scalar `Offset[T]` pointers in `@binary_struct`.

## Requirements

### Requirement: Configurable Size for Scalar Offset Types
The `Offset` type in `@binary_struct` SHALL accept an optional offset type/size as its second parameter: `Offset[Target, OffsetType=UInt32, BaseOffset=0]`.
`OffsetType` MAY be specified as a `BinaryType` subclass (`UInt8`, `UInt16`, `UInt32`, `UInt64`) or an integer byte size (`1`, `2`, `4`, `8`). If omitted, it SHALL default to `UInt32` (4 bytes).

#### Scenario: Declaring a 2-byte offset
- **WHEN** user defines `class Header: next_chunk: Offset[Chunk, UInt16]` or `next_chunk: Offset[Chunk, 2]`
- **THEN** `next_chunk` occupies 2 bytes in memory and aligns to a 2-byte boundary when auto-alignment is active

#### Scenario: Declaring default 4-byte offset
- **WHEN** user defines `class Header: next_chunk: Offset[Chunk]`
- **THEN** `next_chunk` occupies 4 bytes and defaults to `UInt32` behavior

### Requirement: Custom Offset Serialization and Backpatching
When serializing an `@binary_struct` instance containing a sized `Offset[Target, OffsetType, BaseOffset]`:
- The serializer SHALL allocate a placeholder matching the byte width of `OffsetType`.
- When the target object is written, the serializer SHALL pack the calculated offset (`target_pos - BaseOffset`) using the appropriate format (`B`, `H`, `I`, or `Q`).
- If the calculated offset exceeds the maximum representable value for the offset size, or if `target_pos < BaseOffset`, a `ValueError` SHALL be raised.

#### Scenario: Serializing a 2-byte offset to a target object
- **WHEN** user writes a struct with `Offset[Chunk, UInt16]` and the target `Chunk` is positioned at byte 100
- **THEN** the placeholder at the offset field is updated with the 2-byte integer `100` (`0x0064`)

### Requirement: Custom Offset Deserialization
When deserializing via `read_struct` or `Cls.from_bytes()`:
- The deserializer SHALL read the offset integer using the specified width (`UInt8` -> 1 byte, `UInt16` -> 2 bytes, `UInt32` -> 4 bytes, `UInt64` -> 8 bytes).
- If the target type is a `@binary_struct` class and the offset is valid, the reader SHALL seek to `offset + BaseOffset`, deserialize the target struct, and return the reader to the stream position immediately following the offset field.

#### Scenario: Deserializing a struct with a 2-byte offset
- **WHEN** byte stream contains a 2-byte offset pointing to a nested struct
- **THEN** `read_struct` reads 2 bytes and successfully instantiates the target struct
