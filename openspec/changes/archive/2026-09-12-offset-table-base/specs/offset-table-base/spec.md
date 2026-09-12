## Purpose
Provides configurable base offset (origin) capability for offset tables in `BinaryWriter` and `@binary_struct`, enabling section-relative and table-relative offset calculations.

## ADDED Requirements

### Requirement: Configurable Base Offset in write_offset_table
The `BinaryWriter.write_offset_table` method SHALL accept an optional `base_offset: int = 0` parameter specifying the origin byte position from which offsets in the table are measured. If `base_offset < 0`, a `ValueError` SHALL be raised.

#### Scenario: Default base offset at file start
- **WHEN** user calls `write_offset_table(count=3)` without specifying `base_offset`
- **THEN** `base_offset` defaults to `0`, calculating offsets from the beginning of the stream

#### Scenario: Custom base offset at section start
- **WHEN** user calls `write_offset_table(count=3, base_offset=100)`
- **THEN** subsequent offset calculations subtract `100` from the absolute stream position

### Requirement: Relative Offset Storage in OffsetTableHandle
The `OffsetTableHandle` SHALL store the configured `base_offset` and calculate the stored relative offset as `target_offset - base_offset` when `set_offset(index, target_offset)` or `write_target(index, target)` is called. If `target_offset < base_offset`, a `ValueError` SHALL be raised.

#### Scenario: Setting offset with custom base
- **WHEN** handle is configured with `base_offset=64` and user calls `handle.set_offset(0, 80)`
- **THEN** the value `16` is written into the reserved table slot in the binary stream
- **AND** `handle.get_stored_offset(0)` returns `16`
- **AND** `handle.get_target_offset(0)` returns `80`

### Requirement: Layout Entry and Manual Generation with Base Offset
When generating documentation via `write_manual` or `generate_manual`, the memory layout table SHALL display the stored relative value in the value column, while target offset markers (`-> 0xXXXX`) and Mermaid arrows point to the absolute target byte position.

#### Scenario: Generating manual for offset table with base offset
- **WHEN** an offset table with `base_offset=100` points to a target at absolute offset `150`
- **THEN** manual table displays stored value `50` (`0x0032`) and points to target `0x0096` (`-> 0x0096`)

### Requirement: Declarative Struct OffsetTable Base Offset
The `@binary_struct` system SHALL support an optional third parameter in `OffsetTable[Count, Type, BaseOffset]` specifying the base offset. When serialized via `write_struct`, this base offset SHALL be forwarded to `write_offset_table`.

#### Scenario: Serializing struct with relative OffsetTable
- **WHEN** user defines `class Container: offsets: OffsetTable[2, UInt32, 32]` and targets are at offset 48 and 64
- **THEN** the serialized binary table contains relative values `16` and `32`
