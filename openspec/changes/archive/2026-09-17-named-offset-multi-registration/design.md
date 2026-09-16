## Context

`BinaryWriter` previously maintained a 1:1 mapping in `self._named_offset_slots: dict[str, dict[str, Any]]`, raising `DuplicateNamedOffsetError` if a key was registered more than once. See `proposal.md` for motivation to support multiple offsets targeting the same location.

## Goals / Non-Goals

**Goals:**
- Store multiple slot descriptors per key name in `BinaryWriter`.
- Iterate through and backpatch all slots registered for `key` when `write_named_offset` or `rewrite_named_offset` is called.
- Preserve backward compatibility by keeping `DuplicateNamedOffsetError` exported.

**Non-Goals:**
- Allowing multiple targets to be written for a single key (one target position resolves all associated offset slots).
- Modifying behavior of standard `Offset` or `OffsetTable`.

## Decisions

1. **Slots Storage Model**:
   - *Choice*: Change `self._named_offset_slots` to `dict[str, list[dict[str, Any]]]`.
   - *Rationale*: A dictionary of lists cleanly supports arbitrary numbers of placeholders per key without additional data structures.
   - *Alternative*: Keeping single slot with fallback list. Rejected as inconsistent.

2. **Unified Backpatch Iteration**:
   - *Choice*: In `write_named_offset` and `rewrite_named_offset`, calculate `target_pos` once, then iterate over `for slot in self._named_offset_slots[name]:`.
   - *Rationale*: Each slot calculates its own relative offset (`target_pos - slot["actual_base"]`) according to its own base offset, format, and endianness, and patches its corresponding placeholder and layout entry.

## Risks / Trade-offs

- **[Risk] Multiple calls to write_named_offset for the same key**:
  - *Mitigation*: The first call backpatches all current slots. Subsequent calls to `rewrite_named_offset` will update all slots. If a user registers a new slot after `write_named_offset` was already called, resolving it again updates all slots to the new target.
