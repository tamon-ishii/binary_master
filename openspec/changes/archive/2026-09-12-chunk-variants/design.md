## Context

Binary Master enables documenting and serializing binary layouts with `BinaryWriter` and `@binary_struct`. However, real-world formats (chunks, TLV, union records) frequently share a common memory offset among different struct types depending on a preceding tag field.

See [proposal.md](file:///home/ishii/PycharmProjects/binary_master/openspec/changes/chunk-variants/proposal.md) for the motivation and high-level requirements.

## Goals / Non-Goals

**Goals:**
- Provide `writer.subcaption(title, desc)` for hierarchical section breakdown under a primary caption.
- Allow `writer.caption(..., variants=[...])` to document multiple candidate structures for a shared memory region with relative packet diagrams and layout tables.
- Introduce `Variant` type annotation for `@binary_struct` enabling tagged-union serialization and automatic deserialization dispatch.
- Generate clean Markdown specifications with subsections for each variant.

**Non-Goals:**
- C-style un-tagged raw unions (memory overlaps without a discriminating tag field).
- Dynamic schema discovery without explicit Python class definitions.

## Decisions

### Decision 1: Subcaption Tracking in `LayoutEntry`
- **Approach**: Extend `LayoutEntry` with `subcaption: Optional[str] = None` and `subcaption_desc: Optional[str] = None`.
- **Behavior**: Calling `writer.caption(title, desc)` resets `_current_subcaption`. Calling `writer.subcaption(title, desc)` activates a subcaption under the active caption.
- **Rationale**: Simple, non-intrusive model that preserves full backward compatibility with flat captions.

### Decision 2: Variant Declaration and Synthesis in Manuals
- **Approach**: Accept `variants: List[Union[tuple[Any, type, str], tuple[Any, type]]]` in `writer.caption(...)` and attach it to layout entries.
- **Rendering**: In `generate_manual`:
  - Output main caption header `### {caption}`.
  - If variants exist, output introductory note: "この領域には、条件に応じて以下のいずれかの構造体が格納されます。"
  - For each variant `(tag, struct_cls, desc)`:
    - Generate mock layout entries for `struct_cls` to extract field definitions.
    - Render `#### [Variant] Tag {tag}: {struct_cls.__name__}` with `struct_cls.__doc__` or `desc`.
    - Render a relative-offset packet diagram (`packet-beta`) with `relative_offset=True`.
    - Render a relative-offset field table (`+0x00`, `+0x04` etc.).
- **Rationale**: Gives readers a clear RFC-style view of all possible payload shapes without cluttering the main sequential stream table.

### Decision 3: `Variant` Tagged-Union Type for `@binary_struct`
- **Approach**: Define `Variant` generic:
  `Variant[TagField: str, Mapping: dict]`
- **Serialization**: In `write_struct`, when writing a `Variant` field, write the concrete struct instance assigned to that field, and automatically forward the variant candidate mapping to the active caption so `write_manual` documents all candidate shapes.
- **Deserialization**: In `read_struct`, inspect `kwargs[tag_field]`, look up the target class in the mapping, and recursively call `read_struct(target_cls, reader)`.
- **Rationale**: Provides complete type safety and automatic round-trip serialization/deserialization for tagged unions.

## Risks / Trade-offs

- **[Risk: Tag field evaluated before it is deserialized]** → **Mitigation**: Require tag fields to be declared before the `Variant` field in the `@binary_struct` definition (which matches standard binary serialization order). Raise `ValueError` if the tag field has not been read yet.
- **[Risk: Unknown tag value in stream during deserialization]** → **Mitigation**: Raise `ValueError(f"Unknown variant tag {tag_val} for field {name}")` with clear list of known tags.
