# remove-write-manual Specification

## Purpose
Removes `write_manual` from `BinaryWriter` and module exports, unifying all specification document generation into `Builder` (`BinaryBuilder`) to ensure specifications are complete and single-sourced.

## Requirements

### Requirement: Unified Specification Generation via Builder
The system SHALL centralize all protocol specification document generation into `Builder` (`BinaryBuilder`), and SHALL NOT provide `write_manual` on `BinaryWriter`, `Builder`, or as a module-level function in `binary_master`.

#### Scenario: Writer has no write_manual method
- **WHEN** user inspects a `BinaryWriter` instance
- **THEN** `hasattr(writer, "write_manual")` is False

#### Scenario: Builder has no write_manual alias
- **WHEN** user inspects a `Builder` instance
- **THEN** `hasattr(builder, "write_manual")` is False

#### Scenario: Module has no write_manual export
- **WHEN** user inspects `binary_master`
- **THEN** `hasattr(binary_master, "write_manual")` is False
