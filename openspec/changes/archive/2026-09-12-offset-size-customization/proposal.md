# Proposal: Configurable Offset Size for Offset[T]

## Why
Currently, the scalar `Offset[T]` type in `@binary_struct` is hard-coded to a 4-byte (`UInt32`) unsigned integer. However, many compact binary formats, embedded systems, chunk headers, and legacy file specifications use 2-byte (`UInt16`), 1-byte (`UInt8`), or 8-byte (`UInt64`) offsets for pointers.
Allowing users to specify the offset type/size (e.g. `Offset[Image, UInt16]` or `Offset[Image, 2]`) enables direct modeling of these specifications with complete bidirectional serialization, deserialization, and documentation support.

## What Changes
- Allow `Offset` to accept optional size/type and base offset: `Offset[Target, OffsetType=UInt32, BaseOffset=0]`.
- Support specifying `OffsetType` as either a `BinaryType` class (`UInt8`, `UInt16`, `UInt32`, `UInt64`) or byte count integer (`1`, `2`, `4`, `8`).
- Update `_get_field_alignment` so field alignment dynamically reflects the offset size (e.g. 2-byte alignment for 2-byte offsets).
- Update `write_struct` to reserve and backpatch the placeholder with the correct integer width (`B`, `H`, `I`, `Q`), subtracting `base_offset` if specified.
- Update `read_struct` to unpack the offset using the matching width and seek to `target_offset + base_offset` when resolving nested target structs.
- Support bidirectional round-trip serialization and deserialization.
