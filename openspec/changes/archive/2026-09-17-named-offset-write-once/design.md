## Context

`BinaryWriter.write_named_offset` resolves all slots associated with a given key name. To prevent accidental double resolution, subsequent calls to `write_named_offset(name)` must raise `DuplicateNamedOffsetError`. Re-patching is explicitly allowed via `rewrite_named_offset(name)`.

## Goals / Non-Goals

**Goals:**
- Raise `DuplicateNamedOffsetError` when `write_named_offset(name)` is called on a key that has already been resolved.
- Allow re-patching via `rewrite_named_offset(name)` without raising an error.

**Non-Goals:**
- Preventing multiple slot declarations or registrations under the same key.

## Decisions

1. **Resolution State Tracking**:
   - *Choice*: Check `any(slot.get("resolved") for slot in self._named_offset_slots[name])` at the start of `write_named_offset`.
   - *Rationale*: Each slot tracks `"resolved": bool`. If resolved, raise `DuplicateNamedOffsetError`.
   - *Rewrite Support*: Add an internal parameter `_allow_rewrite: bool = False` so `rewrite_named_offset` can call `write_named_offset` when writing target objects without triggering the guard.

## Risks / Trade-offs

- **[Risk] User expecting write_named_offset to overwrite**:
  - *Mitigation*: The error message clearly directs the user to `rewrite_named_offset()`.
