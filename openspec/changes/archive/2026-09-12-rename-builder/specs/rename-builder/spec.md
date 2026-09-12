## Purpose

Provides `BinaryBuilder` and its short alias `Builder` as the canonical schema and protocol specification class, unifying manual generation, multi-language code generation, and automated binary reading, while preserving `ManualBuilder` as a backwards-compatible alias.

## ADDED Requirements

### Requirement: BinaryBuilder and Builder Class
The system SHALL provide `BinaryBuilder` and short alias `Builder` representing the unified binary schema, specification builder, multi-language code generator, and automated reader.

#### Scenario: Instantiate BinaryBuilder or Builder
- **WHEN** user imports `from binary_master import Builder, BinaryBuilder`
- **THEN** both `Builder` and `BinaryBuilder` reference the same class and can be instantiated with title and version

### Requirement: Backwards Compatibility with ManualBuilder
The system SHALL keep `ManualBuilder` as an alias of `BinaryBuilder` so that all existing code, imports, and tests continue to work without any modifications.

#### Scenario: Instantiate ManualBuilder
- **WHEN** user imports `from binary_master import ManualBuilder`
- **THEN** `ManualBuilder` behaves identically to `BinaryBuilder` and `issubclass(ManualBuilder, BinaryBuilder)` or `ManualBuilder is BinaryBuilder` is True
