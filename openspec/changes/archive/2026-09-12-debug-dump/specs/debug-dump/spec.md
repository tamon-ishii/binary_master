## Purpose
Provides specialized binary debugging, annotated hexdumps, reader stream inspection, tabular traces, and binary diffing capabilities for development and troubleshooting.

## ADDED Requirements

### Requirement: Annotated Hexdump Generation
The system SHALL provide a `hexdump` function and `writer.hexdump()` / `reader.hexdump()` methods that format binary data into standard 16-byte rows showing hex offsets, byte hex values, printable ASCII, and correlated field annotations (field name, type, value) when available.

#### Scenario: Hexdump of raw bytes
- **WHEN** user calls `hexdump(b"\xDE\xAD\xBE\xEF")`
- **THEN** output contains offset `00000000`, hex bytes `de ad be ef`, and ASCII representation

#### Scenario: Annotated hexdump from BinaryWriter
- **WHEN** user writes fields to a `BinaryWriter` and calls `writer.hexdump()`
- **THEN** output includes field names, types, and values correlated to the byte offsets

### Requirement: Reader Stream Inspection and Cursor Highlighting
The system SHALL provide `reader.hexdump()` and `reader.dump()` showing the reader's current byte offset cursor, distinguishing read bytes from remaining unread bytes.

#### Scenario: Reader cursor indication
- **WHEN** user has read 4 bytes from an 8-byte reader and calls `reader.hexdump()`
- **THEN** output clearly indicates cursor position at offset 4 and remaining bytes count

### Requirement: Structured Debug Dump Formats
The system SHALL provide `debug_dump(target, format="hexdump"|"table"|"json")` (and `writer.dump(format=...)`) supporting multiple output formats: annotated hexdump, formatted ASCII/Unicode layout table, and JSON-serializable list of dictionary records.

#### Scenario: Table format dump
- **WHEN** user calls `writer.dump(format="table")`
- **THEN** output is a formatted table containing Offset, Size, Field, Type, Hex, and Value columns

#### Scenario: JSON format dump
- **WHEN** user calls `writer.dump(format="json")`
- **THEN** output is a valid JSON string or Python dict structure representing field traces

### Requirement: Binary Diff Comparison
The system SHALL provide `diff_dump(left, right)` comparing two byte buffers or writers, identifying byte-level differences and correlating them to field names when writer metadata is provided.

#### Scenario: Diff identical buffers
- **WHEN** user diffs two identical buffers
- **THEN** output reports no differences found

#### Scenario: Diff differing buffers
- **WHEN** user diffs two buffers with differing bytes
- **THEN** output highlights differing offsets, expected vs actual hex bytes, and affected field names
