# named-offset Specification

## Purpose
Enables streaming and deferred offset resolution via `NamedOffset["key"]` annotations in structures and `BinaryWriter.write_named_offset("key")` / `rewrite_named_offset("key")`.

## Requirements

### Requirement: NamedOffset Field Annotation
The system SHALL provide a `NamedOffset[Key, OffsetType=UInt32, BaseOffset=0]` type annotation for `@binary_struct` fields, where `Key` is a string identifier designating the target offset slot.

#### Scenario: Defining struct with NamedOffset
- **WHEN** user defines `payload_offset: NamedOffset["payload_key"]`
- **THEN** the field reserves an offset slot of `sizeof(OffsetType)` (default 4 bytes) upon serialization

### Requirement: Deferred Offset Resolution via write_named_offset
The `BinaryWriter` class SHALL provide a `write_named_offset(key)` method. When called, it SHALL calculate the current stream offset relative to the declared base offset and backpatch the reserved slot matching `key`.

#### Scenario: Backpatching named offset in writer
- **WHEN** user writes a struct with `NamedOffset["chunk"]` at stream position 0
- **AND** streams 100 bytes of data
- **AND** calls `writer.write_named_offset("chunk")`
- **THEN** the slot at position 0 is backpatched with the value `100` (or `100 - base_offset`)

### Requirement: Error Handling for Duplicate and Missing Keys
The system SHALL allow multiple `NamedOffset` slots to be registered with the same key identifier within the same write context. When `write_named_offset(key)` is invoked for the first time, all reserved placeholder slots registered under that key SHALL be resolved and backpatched to the target offset. If `write_named_offset(key)` is invoked subsequently on an already resolved key, `DuplicateNamedOffsetError` SHALL be raised to prevent unintentional double-resolution (updating resolved offsets requires explicit use of `rewrite_named_offset`). The system SHALL raise `NamedOffsetNotFoundError` if `write_named_offset` or `rewrite_named_offset` is called with a key that was never registered.

#### Scenario: Writing duplicate named offset
- **WHEN** user invokes `writer.write_named_offset(key)` for a key that has already been resolved
- **THEN** `DuplicateNamedOffsetError` is raised

#### Scenario: Resolving unknown named offset
- **WHEN** user calls `writer.write_named_offset("unknown")`
- **THEN** `NamedOffsetNotFoundError` is raised

### Requirement: Scoped Namespaces via Context Manager
The `BinaryWriter` class SHALL provide a `namespace(name: str = "", *, auto_id: bool = False)` context manager to partition `NamedOffset` key spaces. Inside a namespace block, all registered placeholder keys and resolution lookups SHALL be automatically qualified with the active namespace path (`"/".join(stack)`). The `BinaryWriter.current_namespace` property SHALL return the currently active namespace path (or empty string if at root).

#### Scenario: Scoped NamedOffset keys in independent namespaces
- **WHEN** user writes two structs with identical `NamedOffset["payload"]` keys inside `with writer.namespace("chunk_a"):` and `with writer.namespace("chunk_b"):` respectively
- **THEN** the keys are partitioned into `"chunk_a/payload"` and `"chunk_b/payload"` without collision
- **AND** calling `writer.write_named_offset("payload")` inside each block resolves only its respective scoped offset

#### Scenario: Nested namespaces
- **WHEN** user nests `with writer.namespace("outer"):` and `with writer.namespace("inner"):`
- **THEN** keys inside the inner block are qualified as `"outer/inner/<key>"`
- **AND** `writer.current_namespace` evaluates to `"outer/inner"`

#### Scenario: Root namespace escape with leading slash
- **WHEN** user references a key starting with `/` (e.g. `"/global_footer"`) inside a namespace block
- **THEN** the key resolves against the root namespace (`"global_footer"`) bypassing active prefixes

#### Scenario: Auto-incrementing namespace IDs
- **WHEN** user enters `with writer.namespace("chunk", auto_id=True):` multiple times in succession
- **THEN** the scopes are sequentially named `"chunk_0"`, `"chunk_1"`, etc.
