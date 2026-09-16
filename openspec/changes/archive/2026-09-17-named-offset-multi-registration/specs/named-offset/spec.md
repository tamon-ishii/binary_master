## MODIFIED Requirements

### Requirement: Error Handling for Duplicate and Missing Keys
The system SHALL allow multiple `NamedOffset` slots to be registered with the same key identifier within the same write context. When `write_named_offset(key)` or `rewrite_named_offset(key)` is invoked, all reserved placeholder slots registered under that key SHALL be resolved and backpatched to the target offset. The system SHALL raise `NamedOffsetNotFoundError` if `write_named_offset` or `rewrite_named_offset` is called with a key that was never registered.

#### Scenario: Writing duplicate named offset
- **WHEN** user registers the same named offset key multiple times in a writer
- **AND** `writer.write_named_offset(key)` is called
- **THEN** all registered slots for that key are backpatched with their respective relative offsets to the target position without raising DuplicateNamedOffsetError

#### Scenario: Resolving unknown named offset
- **WHEN** user calls `writer.write_named_offset("unknown")`
- **THEN** `NamedOffsetNotFoundError` is raised
