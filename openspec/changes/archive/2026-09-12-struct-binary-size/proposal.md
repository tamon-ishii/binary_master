# Proposal: Binary Size Inspection for @binary_struct

## Why
When writing or allocating binary data, developers frequently need to query the byte size of a structure (similar to C's `sizeof`).
Now that `Offset[T]` supports customizable sizes (such as 2-byte offsets via `Offset[Chunk, UInt16]`), developers need to determine the byte size of structures both statically from the class (e.g. `Header.binary_size` or `sizeof(Header)`) and dynamically from an instance (e.g. `header.binary_size`, `sizeof(header)`, or `len(header)`).

## What Changes
- Provide a `sizeof(cls_or_instance)` function (aliased as `binary_size(cls_or_instance)`).
- Provide a `binary_size` property on both `@binary_struct` classes and instances via a descriptor.
- Implement `__len__` on `@binary_struct` instances returning the serialized binary size in bytes (`len(instance)`).
- Calculate static size from `@binary_struct` classes taking field types, sized `Offset`s, `OffsetTable`s, `FixedArray`s, bitfields, and alignment paddings into account.
- Export `sizeof` and `binary_size` in `binary_master`.
