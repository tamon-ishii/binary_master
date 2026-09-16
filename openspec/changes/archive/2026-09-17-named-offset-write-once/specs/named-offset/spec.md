## MODIFIED Requirements

### Requirement: Error Handling for Duplicate and Missing Keys
The system SHALL allow multiple `NamedOffset` slots to be registered with the same key identifier within the same write context. When `write_named_offset(key)` is invoked for the first time, all reserved placeholder slots registered under that key SHALL be resolved and backpatched to the target offset. If `write_named_offset(key)` is invoked subsequently on an already resolved key, `DuplicateNamedOffsetError` SHALL be raised to prevent unintentional double-resolution (updating resolved offsets requires explicit use of `rewrite_named_offset`). The system SHALL raise `NamedOffsetNotFoundError` if `write_named_offset` or `rewrite_named_offset` is called with a key that was never registered.

#### Scenario: Writing duplicate named offset
- **WHEN** user invokes `writer.write_named_offset(key)` for a key that has already been resolved
- **THEN** `DuplicateNamedOffsetError` is raised

#### Scenario: Resolving unknown named offset
- **WHEN** user calls `writer.write_named_offset("unknown")`
- **THEN** `NamedOffsetNotFoundError` is raised
