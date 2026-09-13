## Purpose

Enables querying the exact byte offset and bit position of fields within `@binary_struct` structures both statically from classes and dynamically from instances.

## ADDED Requirements

### Requirement: Field Byte Offset Calculation via offsetof
The system SHALL provide an `offsetof(target, field_name)` function that calculates the byte offset of a field from the beginning of a `@binary_struct` class or instance, accurately accounting for field sizes, explicit alignments (`align=N`), automatic natural alignments (`auto_align=True`), and padding fields.

#### Scenario: Calculating offset of a field in an auto-aligned struct
- **WHEN** user evaluates `offsetof(Sample, "b")` where `Sample` has `a: UInt8` and `b: UInt16` with `auto_align=True`
- **THEN** the function returns `2` (1 byte for `a` plus 1 byte padding)

#### Scenario: Calculating offset on an instance with manual padding
- **WHEN** user evaluates `offsetof(inst, "b")` where `_pad: UInt8` precedes `b: UInt8` at offset 1
- **THEN** the function returns `2`

### Requirement: Nested Field Offset with Dot Notation
The system SHALL support dot-notation path strings (`"parent.child"`) in `offsetof` to resolve the cumulative byte offset of nested `@binary_struct` members.

#### Scenario: Calculating nested member offset
- **WHEN** user evaluates `offsetof(Outer, "inner.y")` where `inner` starts at offset 1 and `y` starts at offset 2 inside `Inner`
- **THEN** the function returns `3`

### Requirement: Bitfield Offset Calculation via bit_offsetof
The system SHALL provide a `bit_offsetof(target, field_name)` function that returns a `(byte_offset, bit_offset)` tuple for fields in a `@binary_struct` class or instance. For standard fields, `bit_offset` SHALL be `0`. For bitfield structures (`@binary_struct(bits=N)`), `byte_offset` SHALL be `0` and `bit_offset` SHALL be the starting bit index of the field.

#### Scenario: Querying bit offset in a packed bitfield
- **WHEN** user evaluates `bit_offsetof(TestBits, "flag_b")` where `flag_a: Bits[1]` precedes `flag_b: Bits[3]`
- **THEN** the function returns `(0, 1)`

### Requirement: Struct Method offsetof and bit_offsetof
The system SHALL expose `.offsetof(field_name)` and `.bit_offsetof(field_name)` methods on both `@binary_struct` classes and instances via descriptors.

#### Scenario: Calling offsetof directly on struct class and instance
- **WHEN** user calls `Sample.offsetof("c")` or `instance.offsetof("c")`
- **THEN** the exact byte offset of field `"c"` is returned

### Requirement: Standalone offsetof and bit_offsetof Exports
The library SHALL export `offsetof` and `bit_offsetof` from the top-level `binary_master` module.

#### Scenario: Importing offset functions from binary_master
- **WHEN** user imports `from binary_master import offsetof, bit_offsetof`
- **THEN** both functions are available and callable
