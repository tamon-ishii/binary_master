# Proposal: Configurable Base Offset for Offset Tables

## Problem
In many binary formats (such as archive files, multimedia containers, or structured chunks), offset tables store offsets calculated from a specific origin rather than the absolute beginning of the file (0).
For example, offsets may be relative to the start of the payload section, the start of the offset table itself, or the end of a fixed header.
Currently, `write_offset_table` calculates offsets strictly from the start of the file (offset 0), which requires manual calculation or workarounds when relative base offsets are needed.

## Proposed Solution
Add an optional `base_offset: int = 0` parameter to `BinaryWriter.write_offset_table` and `OffsetTableHandle`.
- Default to `0` (start of the file / stream) to preserve 100% backward compatibility.
- When `base_offset` is specified, recorded offsets written into the binary stream will be `target_offset - base_offset`.
- The handle will track both the relative stored offset and the absolute target position, ensuring manual diagrams and layout tables accurately link to the absolute target while reflecting the relative stored value.
- Support `base_offset` in `@binary_struct`'s `OffsetTable[Count, Type, BaseOffset]` as an optional third argument.

## Impact
- Developers can effortlessly generate binary formats with section-relative or table-relative offset tables.
- No breaking changes; default parameter value is 0.
