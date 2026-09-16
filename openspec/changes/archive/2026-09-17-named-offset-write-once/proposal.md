# Proposal: Prevent Multiple write_named_offset Resolutions via DuplicateNamedOffsetError

## Why

While `NamedOffset` allows multiple offset slots to be registered under the same key to point to a common target position, calling `write_named_offset(key)` multiple times on an already resolved key often indicates an accidental double-resolution bug. Re-updating an already resolved named offset should require explicit use of `rewrite_named_offset(key)`. Raising `DuplicateNamedOffsetError` when `write_named_offset` is invoked on an already resolved key restores safety against accidental repeated updates.

## What Changes

- In `BinaryWriter.write_named_offset`, check if any slots for `name` have already been resolved. If so, raise `DuplicateNamedOffsetError`.
- Allow intentional overwrites / re-patching only via `rewrite_named_offset(name)`.
- Update tests and documentation to reflect that multiple registrations are allowed, but multiple `write_named_offset` invocations raise `DuplicateNamedOffsetError`.

## Capabilities

### New Capabilities
<!-- None -->

### Modified Capabilities
- `named-offset`: Raise `DuplicateNamedOffsetError` when calling `write_named_offset` on an already resolved key; require `rewrite_named_offset` for explicit updates.

## Impact

- Affected APIs: `BinaryWriter.write_named_offset`.
- Prevents silent overwriting when `write_named_offset` is inadvertently called multiple times for the same key.
