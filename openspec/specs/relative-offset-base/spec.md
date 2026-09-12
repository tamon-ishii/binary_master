# relative-offset-base Specification

## Purpose
Enables defining relative offset bases in `@binary_struct` using `Base.SELF` and `Base.FIELD` with operator overloading (`+`, `-`), allowing offsets and offset tables to be computed relative to the start of their containing structure or field location.

## Requirements

### Requirement: Base.SELF and Base.FIELD with Operator Overloading
The system SHALL provide `Base.SELF` (aliased as `Base.STRUCT`) and `Base.FIELD` objects supporting addition (`+`) and subtraction (`-`) with integers, producing a `RelativeBase` object that stores the target origin and integer displacement.

#### Scenario: Adding displacement to Base.SELF
- **WHEN** user evaluates `Base.SELF + 0x20` or `Base.SELF - 0x10`
- **THEN** a `RelativeBase` object is returned representing a displacement of `+32` or `-16` from the start of the containing struct

#### Scenario: Using Base.FIELD
- **WHEN** user evaluates `Base.FIELD + 4`
- **THEN** a `RelativeBase` object is returned representing a displacement of `+4` from the offset field position

### Requirement: Declarative Offset with RelativeBase
The system SHALL support `RelativeBase` as the `BaseOffset` parameter in `Offset[Target, OffsetType, BaseOffset]` and shorthand `Offset[Target, BaseOffset]`.
When serialized via `write_struct` or `instance.to_bytes()`, the stored offset SHALL be calculated as `target_pos - (struct_start_pos + delta)` for `Base.SELF` (or `field_pos + delta` for `Base.FIELD`).
When deserialized via `read_struct` or `Cls.from_bytes()`, the target object's absolute address SHALL be reconstructed as `stored_val + (struct_start_pos + delta)` for `Base.SELF` (or `field_pos + delta` for `Base.FIELD`).

#### Scenario: Serializing struct with Base.SELF offset
- **WHEN** a struct is written starting at byte position 100, containing `body_offset: Offset[Body, UInt32, Base.SELF + 0x20]`
- **AND** the target `Body` is written at byte position 150
- **THEN** the base origin is resolved to `100 + 32 = 132`
- **AND** the stored offset value is `150 - 132 = 18`

#### Scenario: Deserializing struct with Base.SELF offset
- **WHEN** a stream contains the serialized struct at position 100 with stored offset 18
- **THEN** `Cls.from_bytes()` or `read_struct()` resolves the target at `18 + (100 + 32) = 150`
- **AND** deserializes the `Body` instance automatically

### Requirement: Declarative OffsetTable with RelativeBase
The system SHALL support `RelativeBase` as the `BaseOffset` parameter in `OffsetTable[Count, OffsetType, BaseOffset]` and shorthand `OffsetTable[Count, BaseOffset]`.

#### Scenario: Serializing OffsetTable with Base.SELF
- **WHEN** user defines `chunk_offsets: OffsetTable[2, UInt32, Base.SELF + 16]`
- **AND** the containing struct starts at byte position 200
- **THEN** the offset table uses base origin `216` for all entries in the table

### Requirement: Export Base and RelativeBase
The library SHALL export `Base` and `RelativeBase` from `binary_master`.

#### Scenario: Importing Base from top-level module
- **WHEN** user imports `from binary_master import Base, RelativeBase`
- **THEN** both symbols are available for use in struct definitions and offset calculations
