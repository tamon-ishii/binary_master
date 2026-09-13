## Context

`@binary_struct` supports field definitions with custom types, alignment padding (`align`, `auto_align`), bitfields, and nested structs. See `proposal.md` for motivation. To inspect field layout programmatically, we implement `offsetof` and `bit_offsetof`.

## Goals / Non-Goals

**Goals:**
- Provide static and dynamic byte offset calculation (`offsetof`).
- Support nested dot-notation access (`"inner.field"`).
- Provide bitfield starting bit index inspection (`bit_offsetof`).
- Attach `offsetof` and `bit_offsetof` to `@binary_struct` classes and instances via descriptors.

**Non-Goals:**
- Modifying runtime serialization or deserialization behavior.
- Supporting runtime dynamic restructuring of classes.

## Decisions

1. **Descriptor Implementation for Class & Instance Methods**:
   - *Choice*: Implement `_OffsetofDescriptor` and `_BitOffsetofDescriptor` with `__get__` returning a callable lambda.
   - *Rationale*: Allows both `Cls.offsetof("field")` and `instance.offsetof("field")` to work seamlessly.
   - *Alternative*: Standard method or `@classmethod`. Rejected because standard methods don't work cleanly from classes without metaclass complexity, while classmethods don't receive instance context for variable-length fields.

2. **Recursive Dot-Notation Resolution**:
   - *Choice*: Split on the first dot (`first, rest = field_name.split(".", 1)`), calculate `base = offsetof(target, first)`, and recursively call `offsetof(child, rest)`.
   - *Rationale*: Clean, intuitive navigation for arbitrary nesting depth.

3. **Bitfield Handling**:
   - *Choice*: In `bit_offsetof`, return `(byte_offset, bit_shift)`. In `offsetof` for bitfields, return byte offset 0.
   - *Rationale*: Bitfields share the enclosing container's byte address.

## Risks / Trade-offs

- **[Risk] Variable-length fields prior to target field**: If a struct contains `Array[T]` or variable strings before the queried field, static class-level `offsetof` cannot be determined.
  - *Mitigation*: Raise `ValueError` when called on the class; when called on an instance, calculate offset dynamically using the actual length of the field.
