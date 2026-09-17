# ide-typing-and-stubs Specification

## Purpose
Provides PEP 561 compliant type stubs, strict zero-diagnostic type checking compatibility, and IDE attribute autocompletion for declarative binary structures and offset pointers.

## Requirements

### Requirement: PEP 561 Type Stubs and IDE Autocompletion
The `binary_master` package SHALL include PEP 561 marker `py.typed` and stub files (`.pyi`) defining statically typed representations of binary types. Type checkers and IDEs SHALL resolve `Offset[Target, ...]` to `Target | None` for static analysis and code autocompletion.

#### Scenario: Autocompleting dereferenced offset attributes
- **WHEN** user accesses a deserialized struct field declared as `image_offset: Offset[ImagePayload]`
- **THEN** IDE provides autocompletion for attributes of `ImagePayload` (e.g. `width`, `height`)
- **AND** static type checkers report no unresolved attribute diagnostics

#### Scenario: Assigning target payload in header-first pattern
- **WHEN** user assigns an instance of `ImagePayload` to `header.image_offset` where `image_offset` is defined with default `None`
- **THEN** static type checkers accept the assignment without type incompatibility errors

### Requirement: Literal and L FixedArray Sizing Support
The `binary_master` package SHALL export `Literal` and shorthand alias `L`. The `FixedArray` and `OffsetTable` types SHALL accept `Literal[N]` and `L[N]` type parameters in type expressions without raising `invalid-type-form` errors in static type checkers.

#### Scenario: Declaring FixedArray with L shorthand
- **WHEN** user defines a field as `pixels: FixedArray[UInt8, L[4]]`
- **THEN** static type checkers accept the integer parameter without syntax or typing diagnostics
- **AND** the runtime binary serialization correctly serializes and deserializes exactly 4 elements

#### Scenario: Backward-compatible bare numeric arguments
- **WHEN** user defines a field as `pixels: FixedArray[UInt8, 4]`
- **THEN** runtime execution unpacks the numeric size and operates identically to `Literal[4]`
