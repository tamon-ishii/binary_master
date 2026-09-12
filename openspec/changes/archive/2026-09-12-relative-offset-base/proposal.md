# Proposal: Struct-Relative and Field-Relative Offset Base via Base.SELF

## Why
Currently, `Offset[Target, OffsetType, BaseOffset]` and `OffsetTable[Count, OffsetType, BaseOffset]` only accept static integer absolute byte offsets for `BaseOffset` (defaulting to 0).
In structured binary formats, headers or sections frequently use offsets relative to the start address of the containing structure (`struct_start`), or with a fixed displacement from the struct start (e.g., `struct_start + 0x20`), regardless of where that structure is placed in the overall binary stream or file.

Using a static absolute integer fails when the structure is placed at an arbitrary or dynamically determined offset in the file (e.g., inside an archive or nested chunk).
Developers need a clean, Pythonic, and type-safe way to declare relative offsets using operator notation such as `Base.SELF + 0x20` or `Base.SELF - 0x10`.

## What Changes
- Introduce `Base` and `RelativeBase` in `binary_master`:
  - `Base.SELF` (aliased as `Base.STRUCT`) representing the start position of the containing `@binary_struct`.
  - `Base.FIELD` representing the byte position of the offset field itself.
  - Support operator overloading: `Base.SELF + delta`, `Base.SELF - delta`, `Base.FIELD + delta`, `Base.FIELD - delta`.
- Update `Offset` and `OffsetTable` type parameter parsing to accept `RelativeBase` (and integer deltas).
- Also allow shorthand `Offset[Target, Base.SELF + 0x20]` where `OffsetType` defaults to `UInt32` when omitted.
- Update `write_struct` to dynamically resolve `RelativeBase` relative to `struct_start_pos = writer.tell()` (and `field_pos` for `Base.FIELD`) during serialization and deferred offset resolution.
- Update `read_struct` to dynamically resolve `RelativeBase` relative to `struct_start_pos = reader.tell()` (and `field_pos` for `Base.FIELD`) when deserializing target structures.
- Export `Base` and `RelativeBase` in `binary_master`.
