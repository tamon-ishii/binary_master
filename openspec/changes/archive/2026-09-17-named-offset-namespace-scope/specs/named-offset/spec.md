## ADDED Requirements

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
