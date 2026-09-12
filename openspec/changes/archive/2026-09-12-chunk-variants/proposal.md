## Why

In structured binary formats such as RIFF, PNG, network protocols, and game containers, multiple distinct structures (variants/chunks) can occupy the same offset location depending on a preceding tag or type field. Currently, Binary Master only documents a single concrete struct instance per offset. Users need a way to group these polymorphic structures under a common caption and document each variant with subcaptions, dedicated packet diagrams, and fields in generated specifications, as well as deserialize them automatically based on the tag value.

## What Changes

- Introduce `writer.subcaption(title, desc=None)` to support hierarchical section grouping under a primary `caption`.
- Support specifying `variants=[(tag, StructCls, description), ...]` in `writer.caption(...)` or registering variant structures for a common region.
- Introduce `Variant[TagFieldName, Dict[TagValue, StructCls]]` type hint for `@binary_struct` fields (tagged unions).
- Update manual generation (`generate_manual`, `manual.py`):
  - In Mermaid flowchart, represent variant regions cleanly with variant branch connections or unified variant nodes.
  - In Memory Layout Table, output a common caption header followed by subcaption/variant subsections (`#### [Variant] ...`) containing relative packet diagrams and layout tables for each candidate structure.
- Support automatic deserialization of `Variant` fields in `read_struct` and `Cls.from_bytes()` by inspecting the value of the tag field in the partially-deserialized struct instance.

## Capabilities

### New Capabilities
- `chunk-variants`: Hierarchical subcaptions and polymorphic chunk variants (tagged unions) for documentation, serialization, and deserialization.

### Modified Capabilities
<!-- None -->

## Impact

- **Affected Files**:
  - `src/binary_master/manual.py`: Add subcaption tracking in `LayoutEntry`, render subcaption/variant sections, relative packet diagrams, and layout tables.
  - `src/binary_master/writer.py`: Add `writer.subcaption(...)`, enhance `writer.caption(..., variants=...)`.
  - `src/binary_master/binary_struct.py`: Add `Variant` type annotation, serialization/deserialization dispatch based on tag field.
  - `src/binary_master/__init__.py`: Export `Variant`.
- **Breaking Changes**: None. Existing single-level captions and structs remain 100% compatible.
