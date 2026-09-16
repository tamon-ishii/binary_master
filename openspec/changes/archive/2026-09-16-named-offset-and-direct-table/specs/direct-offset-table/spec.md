## Purpose

Provides direct serialization and deserialization of pointer offset tables (`Offset[OffsetTable[...]]`) to arrays of struct instances without requiring an intermediate wrapper struct.

## ADDED Requirements

### Requirement: Direct Offset to OffsetTable Type Annotation
The system SHALL support `Offset[OffsetTable[Count, Type, TableBase], OffsetBase]` as a field type annotation on `@binary_struct` classes. The field value accepted during instantiation SHALL be a Python `list` of target struct instances.

#### Scenario: Instantiating struct with direct offset table list
- **WHEN** user defines a struct with `table_offset: Offset[OffsetTable["num_items", UInt32, Base.SELF], Base.SELF]`
- **AND** instantiates it with `table_offset=[Target(a=1), Target(a=2)]`
- **THEN** the instance accepts the list of structs without requiring an intermediate container struct

### Requirement: Automatic Offset Table and Payload Serialization
When a struct containing a direct `Offset[OffsetTable[...]]` field is serialized via `to_bytes` or `write_struct`, the system SHALL:
1. Auto-populate any corresponding `LengthOf`/`CountOf` field with the element count if defined.
2. Backpatch the pointer offset to the offset table position.
3. Serialize the offset table containing relative offsets to each payload item.
4. Serialize all payload items at the end of the container.

#### Scenario: Serializing direct offset table container
- **WHEN** user serializes a container with 2 payload items
- **THEN** the output binary stream contains the container header, backpatched table offset, 2-entry offset table, and the consecutive serialized payloads

### Requirement: Deserialization to Struct List
When deserializing data containing an `Offset[OffsetTable[...]]` field via `from_bytes` or `read_struct`, the system SHALL read the offset table entries, follow each pointer, deserialize each payload instance, and return a Python `list` of the target struct type.

#### Scenario: Deserializing binary data with direct offset table
- **WHEN** user deserializes binary data produced by a direct offset table container
- **THEN** `restored.table_offset` is a list containing the deserialized target struct instances
