## Context

`binary_master.manual` provides `generate_manual` and `write_manual`, which operate on serialized `LayoutEntry` items recorded during `BinaryWriter` execution. While effective for concrete binary dumps, it cannot document branches that did not execute, nor narrative documentation chapters, nor upfront schemas before serialization.

## Goals / Non-Goals

**Goals:**
- Provide `ManualBuilder` class to define binary schemas declaratively.
- Support `add_struct`, `add_choice`, `add_document`, `add_section`, and `add_field`.
- Provide `builder.write(path_or_file, ...)` to write to file or stream, and `builder.build()` / `builder.to_markdown()` for string output.
- Generate Mermaid diagrams with choice decision nodes and condition diamonds, plus packet diagrams and offset layout tables.
- Implement `builder.read(reader_or_bytes)` to automatically parse binary data conforming to the schema and return a `BuilderReadResult` dictionary/namespace.
- Reorganize `sample/` into clean, numbered, educational scripts.

**Non-Goals:**
- Deprecating or breaking `BinaryWriter.write_manual` (both work together).
- Arbitrary full programming language AST execution in conditions (use callables or simple boolean / attribute comparisons).

## Decisions

### 1. Element Representation in ManualBuilder
Represent builder contents as an ordered list of elements:
- `DocumentElement(title, markdown)`
- `StructElement(struct_cls, name, desc, condition)`
- `ChoiceElement(name, tag_field, variants, desc, condition)`
- `SectionElement(title, desc)`
- `FieldElement(name, type_name, size, desc, endian, condition)`

### 2. Mermaid Flowchart Branch Modeling
For conditional structs and choice branches:
- A choice element creates a decision diamond: `Choice_{id}{"Choice: {tag_field}?"}`.
- Outgoing labeled edges connect to variant nodes: `Choice_{id} -->|{tag}| Variant_{tag}`.
- A conditional struct creates a condition diamond: `Cond_{id}{"{condition}?"}` with `-->|yes| Struct_{id}`.

### 3. Automated Deserialization (`builder.read`)
`ManualBuilder.read(reader_or_bytes)` takes `bytes`, `bytearray`, or `BinaryReader`:
- Maintains a context dict `result` and tracks read values.
- Sequential `StructElement`: executes `reader.read_struct(cls)` and stores in `result[name or cls.__name__]`.
- `ChoiceElement`: looks up `tag_field` from previously read structs or context, determines matching variant class, calls `reader.read_struct(variant_cls)`, and stores in `result[name]`.
- Evaluates conditions (if condition callable or expression returns false, struct is skipped).
- Wraps output in `BuilderReadResult` providing attribute (`result.header`) and item (`result["header"]`) access.

### 4. Output API
Use `builder.write(path_or_file, ...)` as requested by the user, while keeping `write_manual` as an alias. `builder.build(...)` and `builder.to_markdown(...)` return the markdown string directly.

## Risks / Trade-offs

- [Risk] Dynamic sizing for variable-length arrays when inspecting struct layout without instances.
  → Mitigation: `_inspect_struct_layout` uses type reflection defaults (already well-tested in `manual.py`). For variable payloads in choices, relative offset displays (`+0x00`, `+0x04`) document layout accurately.
- [Risk] Tag field resolution in `builder.read` if tag field is nested in a prior struct.
  → Mitigation: Search for `tag_field` across previously read struct attributes as well as root result dict.
