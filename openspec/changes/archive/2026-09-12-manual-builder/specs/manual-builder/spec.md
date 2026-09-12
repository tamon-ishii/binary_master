## Purpose

Provides a schema-first specification builder (`ManualBuilder`) for documenting binary layouts with conditional and polymorphic branches, narrative documentation chapters, Mermaid diagrams, and automated schema-driven binary deserialization.

## ADDED Requirements

### Requirement: Schema-First Specification Construction
The system SHALL provide a `ManualBuilder` class that constructs a binary format specification directly from `@binary_struct` classes, ad-hoc fields, and sections without requiring runtime instance serialization.

#### Scenario: Register struct class in manual builder
- **WHEN** user adds a struct class using `builder.add_struct(HeaderStruct, desc="File header")`
- **THEN** builder registers the struct fields, types, and offsets into the specification layout

#### Scenario: Register ad-hoc fields and sections
- **WHEN** user adds a section with `builder.add_section("Payload")` and an ad-hoc field with `builder.add_field("magic", "UInt32", 4)`
- **THEN** builder includes the section and ad-hoc field in the specification layout

### Requirement: Branch and Choice Modeling
The system SHALL support conditional structures and polymorphic choice variants with tag-based dispatch, documenting branches in Mermaid flowcharts and relative offset tables.

#### Scenario: Register choice variants
- **WHEN** user registers a choice via `builder.add_choice("body", tag_field="type", variants={1: TextPayload, 2: ImagePayload})`
- **THEN** builder generates flowchart decision nodes branching to each variant and documents variant layouts with relative offsets

#### Scenario: Register conditional struct
- **WHEN** user registers a struct with `condition="flags & 0x01 != 0"`
- **THEN** builder documents the condition in the layout table and generates a decision diamond in the flowchart

### Requirement: Narrative Documentation Chapters
The system SHALL allow embedding freeform narrative markdown chapters into the specification via `builder.add_document(title, markdown_content)`.

#### Scenario: Add narrative document chapter
- **WHEN** user calls `builder.add_document("Protocol Overview", "This protocol transmits chunks...")`
- **THEN** the generated manual includes a dedicated section titled "Protocol Overview" containing the markdown text

### Requirement: Specification Output and File Writing
The system SHALL provide `builder.build()` or `builder.to_markdown()` to return the formatted Markdown specification string, and `builder.write(path_or_file)` to save the specification directly to a file path or writable stream.

#### Scenario: Write manual to file using builder.write
- **WHEN** user calls `builder.write("spec.md", title="My Protocol")`
- **THEN** builder generates the complete Markdown content, writes it to `spec.md`, and returns the markdown string

#### Scenario: Build markdown string in memory
- **WHEN** user calls `builder.build()`
- **THEN** builder returns the markdown string containing overview, diagrams, and layout tables

### Requirement: Schema-Driven Automated Deserialization
The system SHALL support automated reading of binary data using the declared schema via `builder.read(reader_or_bytes)`, dynamically resolving choice variants using parsed tag fields and evaluating conditional structs.

#### Scenario: Automated reading of sequential structs and choice variants
- **WHEN** user provides binary bytes containing a header with `type = 1` followed by a `TextPayload` struct, and invokes `builder.read(data)`
- **THEN** builder automatically reads the header, inspects `type`, selects `TextPayload`, deserializes it, and returns the structured result containing both header and body
