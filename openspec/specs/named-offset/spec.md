# named-offset Specification

## Purpose
Enables streaming and deferred offset resolution via `NamedOffset["key"]` annotations in structures and `BinaryWriter.write_named_offset("key")` / `rewrite_named_offset("key")`.

## Requirements

### Requirement: NamedOffset Field Annotation
The system SHALL provide a `NamedOffset[Key, OffsetType=UInt32, BaseOffset=0]` type annotation for `@binary_struct` fields, where `Key` is a string identifier designating the target offset slot.

#### Scenario: Defining struct with NamedOffset
- **WHEN** user defines `payload_offset: NamedOffset["payload_key"]`
- **THEN** the field reserves an offset slot of `sizeof(OffsetType)` (default 4 bytes) upon serialization

### Requirement: Deferred Offset Resolution via write_named_offset
The `BinaryWriter` class SHALL provide a `write_named_offset(key)` method. When called, it SHALL calculate the current stream offset relative to the declared base offset and backpatch the reserved slot matching `key`.

#### Scenario: Backpatching named offset in writer
- **WHEN** user writes a struct with `NamedOffset["chunk"]` at stream position 0
- **AND** streams 100 bytes of data
- **AND** calls `writer.write_named_offset("chunk")`
- **THEN** the slot at position 0 is backpatched with the value `100` (or `100 - base_offset`)

### Requirement: Error Handling for Duplicate and Missing Keys
The system SHALL allow multiple `NamedOffset` slots to be registered with the same key identifier within the same write context. When `write_named_offset(key)` is invoked for the first time, all reserved placeholder slots registered under that key SHALL be resolved and backpatched to the target offset. If `write_named_offset(key)` is invoked subsequently on an already resolved key, `DuplicateNamedOffsetError` SHALL be raised to prevent unintentional double-resolution (updating resolved offsets requires explicit use of `rewrite_named_offset`). The system SHALL raise `NamedOffsetNotFoundError` if `write_named_offset` or `rewrite_named_offset` is called with a key that was never registered.

#### Scenario: Writing duplicate named offset
- **WHEN** user invokes `writer.write_named_offset(key)` for a key that has already been resolved
- **THEN** `DuplicateNamedOffsetError` is raised

#### Scenario: Resolving unknown named offset
- **WHEN** user calls `writer.write_named_offset("unknown")`
- **THEN** `NamedOffsetNotFoundError` is raised
