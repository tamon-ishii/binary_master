# Proposal: Allow Multiple Registrations for NamedOffset Keys

## Why

In binary formats and streaming protocols, multiple distinct offset fields (e.g. primary and auxiliary pointers, or header and trailer references) may point to the exact same target position or data payload in the stream. Previously, registering a duplicate `NamedOffset` key raised a `DuplicateNamedOffsetError`. Allowing multiple registrations of the same key enables callers to declare multiple offsets pointing to the same point, backpatching all of them when `write_named_offset(key)` is invoked.

## What Changes

- Allow multiple `NamedOffset` slots to be registered with the same key name in `BinaryWriter`.
- When `write_named_offset(key, ...)` or `rewrite_named_offset(key, ...)` is called, backpatch **all** slots associated with `key` to the target position.
- Retain `DuplicateNamedOffsetError` for backward compatibility without raising it on multi-registration.
- Update documentation and test cases to reflect and verify multi-registration behavior.

## Capabilities

### New Capabilities
<!-- None -->

### Modified Capabilities
- `named-offset`: Allow multiple offset slots registered under the same key to resolve to the same target position; resolve unknown keys with `NamedOffsetNotFoundError`.

## Impact

- Affected APIs: `BinaryWriter._register_named_offset_slot`, `BinaryWriter.reserve_named_offset`, `BinaryWriter.write_named_offset`, `BinaryWriter.rewrite_named_offset`.
- Backward compatibility: Completely backward-compatible. Eliminates `DuplicateNamedOffsetError` restriction, broadening valid usage patterns.
