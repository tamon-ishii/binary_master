## Why

Currently, documentation and manual generation (`write_manual`) are coupled to active serialization instances via `BinaryWriter`. However, binary protocols frequently include conditional structures, variants, and alternatives that may not all be instantiated in a single concrete serialization run. Furthermore, protocol authors need to document schemas upfront—including narrative documentation chapters and decision branches—without writing dummy data. Having a formal schema representation also enables automated reading directly from the declared schema without manual deserialization code.

## What Changes

- Introduce `ManualBuilder` for schema-first binary specification generation:
  - Register struct classes without requiring runtime instances (`add_struct`)
  - Support conditional structures and branches (`condition` parameter)
  - Register multi-branch choices/variants with tag-field dispatch (`add_choice`)
  - Register narrative documentation sections and markdown chapters (`add_document`)
  - Register logical grouping sections (`add_section`) and ad-hoc fields (`add_field`)
  - Export specification to file via `builder.write(path)` and retrieve markdown via `builder.build()` or `builder.to_markdown()`
  - Generate Mermaid flowcharts with decision diamonds for choices/conditions, packet diagrams, and offset layout tables
- Introduce schema-driven automated reading (`builder.read(reader_or_bytes)`):
  - Automatically parse binary data conforming to the builder's declared schema
  - Dispatch variants dynamically based on parsed tag values
  - Evaluate conditional structures
  - Return structured deserialization results

## Capabilities

### New Capabilities
- `manual-builder`: Schema-first specification generation with condition/choice branches, narrative document chapters, and automated schema-driven reading.

### Modified Capabilities
<!-- None -->

## Impact

- New module `binary_master.manual_builder` and export in `binary_master.__init__`.
- Extends manual generation capabilities without breaking existing `write_manual` or `BinaryWriter.write_manual`.
- Adds automated reader capability `ManualBuilder.read(...)`.
- Updates samples and documentation to showcase systematic schema design and automated parsing.
