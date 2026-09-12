# chunk-variants Specification

## Purpose
Provides hierarchical subcaptions and polymorphic chunk variant (tagged union) capabilities for documenting, serializing, and deserializing binary formats where multiple struct types share the same memory location.

## Requirements

### Requirement: Hierarchical Subcaptions
The binary writer and manual generator SHALL support hierarchical subcaptions under a parent caption. A subcaption SHALL group subsequent field writes into a subsection of the parent caption.

#### Scenario: Grouping writes under subcaption
- **WHEN** user sets `writer.caption("Payload Section")` and then `writer.subcaption("Header Block")` followed by field writes
- **THEN** manual outputs `### Payload Section` as main section and `#### Header Block` as subsection

### Requirement: Documenting Chunk Variants in Manuals
The manual generator SHALL support documenting multiple variant structures that can occupy the same offset location. When variants are declared on a caption or struct field, the manual SHALL render a subsection for each variant detailing its tag identifier, description, relative packet diagram, and member field layout table.

#### Scenario: Rendering multiple payload variants under common caption
- **WHEN** user configures caption with variants for `SensorPayload` (tag 1) and `LogPayload` (tag 2)
- **THEN** generated manual includes `#### [Variant] Tag 0x0001: SensorPayload` and `#### [Variant] Tag 0x0002: LogPayload` with individual packet diagrams and field tables

### Requirement: Tagged Union Struct Fields (Variant)
The `@binary_struct` system SHALL provide a `Variant[TagField, Mapping]` generic type to define tagged union fields whose concrete struct type depends on an earlier tag field. Serializing an instance containing a `Variant` field SHALL serialize the active concrete struct instance.

#### Scenario: Serializing tagged union struct
- **WHEN** user defines `class Chunk: tag: UInt16; payload: Variant["tag", {1: SensorPayload, 2: LogPayload}]` and creates `Chunk(tag=1, payload=SensorPayload(temperature=20.0))`
- **THEN** `to_bytes()` serializes `tag` followed by the binary fields of `SensorPayload`

### Requirement: Deserializing Tagged Union Structs
The deserializer (`read_struct` and `Cls.from_bytes()`) SHALL support deserializing `Variant` fields by reading the referenced tag field value, looking up the corresponding structure class in the variant mapping, and deserializing the stream into an instance of that class.

#### Scenario: Deserializing variant based on tag value
- **WHEN** byte stream contains serialized tag `0x0002` followed by bytes for `LogPayload`
- **THEN** `Chunk.from_bytes(data)` returns a `Chunk` instance whose `payload` attribute is an instance of `LogPayload`
