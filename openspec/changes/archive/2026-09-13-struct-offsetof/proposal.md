# Proposal: Field Offset and Bit Offset Inspection for @binary_struct

## Why

When working with binary structures, protocols, and hardware memory mappings, developers frequently need to determine the exact byte offset of specific fields from the start of a structure (equivalent to C's `offsetof` macro) and the starting bit position of bitfield members.
With automatic alignment padding (`auto_align=True`), manual padding fields, and nested structures, calculating field offsets manually is error-prone. Providing programmatic `offsetof` and `bit_offsetof` inspection enables precise validation, debug logging, and alignment verification.

## What Changes

- Provide a standalone `offsetof(target, field_name)` function to calculate the byte offset of a field within a `@binary_struct` class or instance.
- Provide a `Cls.offsetof(field_name)` / `instance.offsetof(field_name)` method on decorated structures via a descriptor.
- Support dot-notation access (`"inner.field"`) for deeply nested structures.
- Accurately account for automatic alignment padding (`auto_align=True`), explicit struct alignment (`align=N`), and explicit padding fields.
- Provide `bit_offsetof(target, field_name)` returning a `(byte_offset, bit_offset)` tuple for bitfield structures (`@binary_struct(bits=N)`).
- Export `offsetof` and `bit_offsetof` from `binary_master`.
- Provide complete documentation in `TUTORIAL.md` and AI reference `FOR_AI.md`.

## Capabilities

### New Capabilities
- `struct-offsetof`: Field byte offset and bit offset inspection for `@binary_struct` classes and instances.

### Modified Capabilities
<!-- None -->

## Impact

- Affected APIs: `binary_master` module exports, `@binary_struct` class and instance attributes.
- No breaking changes; all additions are non-breaking extensions.
