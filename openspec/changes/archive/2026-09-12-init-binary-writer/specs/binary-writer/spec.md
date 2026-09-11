## Purpose

Provides a high-level sequential binary writing interface for constructing binary data in memory buffers and file streams with explicit endianness, type safety, and formatting options.

## ADDED Requirements

### Requirement: Write Primitive Integer Types
The binary writer SHALL support writing signed and unsigned integers across standard bit-widths (8-bit, 16-bit, 32-bit, and 64-bit). The writer SHALL respect the configured default endianness (big-endian or little-endian) and allow per-call endianness overrides. Values outside the representable range for the specified integer type MUST raise a ValueError or OverflowError.

#### Scenario: Write unsigned and signed integers with specified endianness
- **WHEN** user writes uint16 `0x1234` in little-endian and int32 `-100` in big-endian
- **THEN** writer appends `\x34\x12` followed by the 4-byte big-endian representation of `-100`

#### Scenario: Integer value out of range
- **WHEN** user writes value `300` as uint8 (range 0 to 255)
- **THEN** writer raises an error indicating the value exceeds the type range and leaves the position unmodified

### Requirement: Write Floating Point Types
The binary writer SHALL support writing 32-bit single precision (`float32`) and 64-bit double precision (`float64`) IEEE 754 floating point numbers according to the active or specified endianness.

#### Scenario: Write float32 and float64
- **WHEN** user writes float32 `1.5` and float64 `3.141592653589793`
- **THEN** writer serializes standard IEEE 754 representations in the requested endianness

### Requirement: Write Boolean and Raw Bytes
The binary writer SHALL support writing boolean values (encoding `True` as `0x01` and `False` as `0x00` by default or custom byte) and arbitrary byte sequences.

#### Scenario: Write boolean values
- **WHEN** user writes `True` and `False`
- **THEN** writer writes single bytes `0x01` and `0x00` respectively

#### Scenario: Write raw byte payloads
- **WHEN** user writes bytes `b"\xDE\xAD\xBE\xEF"`
- **THEN** writer appends the exact byte sequence to the output stream

### Requirement: Write Encoded Strings
The binary writer SHALL support writing text strings with configurable character encoding (defaulting to UTF-8) using multiple serialization strategies: null-terminated (C-style), length-prefixed (1-byte, 2-byte, or 4-byte prefix), and fixed-length (padded or truncated).

#### Scenario: Write null-terminated string
- **WHEN** user writes string `"hello"` as null-terminated with UTF-8 encoding
- **THEN** writer writes `b"hello\x00"` to the stream

#### Scenario: Write length-prefixed string
- **WHEN** user writes string `"world"` with a 2-byte unsigned integer prefix in big-endian
- **THEN** writer writes `\x00\x05` followed by `b"world"`

#### Scenario: Write fixed-length padded string
- **WHEN** user writes string `"cat"` into a fixed length of 6 bytes with null byte padding
- **THEN** writer writes `b"cat\x00\x00\x00"`

### Requirement: Buffer and Stream Output Management
The binary writer SHALL support operating on an in-memory dynamic buffer or writing directly to a provided writable file-like binary stream (`io.BufferedIOBase`). When operating on an in-memory buffer, the writer SHALL provide a method to retrieve the complete accumulated data as immutable `bytes` or `bytearray`.

#### Scenario: In-memory buffer accumulation and retrieval
- **WHEN** user creates an in-memory writer, writes several data types, and calls `to_bytes()`
- **THEN** writer returns the complete accumulated binary output as `bytes`

#### Scenario: Writing to an external file stream
- **WHEN** user creates a writer wrapping a writable file or stream object and writes data
- **THEN** writer writes bytes directly into the stream object without buffering everything exclusively in a separate buffer

### Requirement: Cursor Positioning, Seeking, and Alignment
The binary writer SHALL track the current write position (cursor offset) and support seeking to specific offsets within the stream or buffer. The writer SHALL support padding bytes and aligning the write position to a specified byte boundary (e.g. 2-byte, 4-byte, 8-byte, 16-byte).

#### Scenario: Query cursor position and seek
- **WHEN** user writes 4 bytes, checks position `tell()`, seeks back to offset 0, and overwrites 2 bytes
- **THEN** position reports `4` after initial write, and the first 2 bytes are overwritten after seeking

#### Scenario: Align cursor to boundary with padding
- **WHEN** write cursor is at offset 3 and user requests alignment to a 4-byte boundary using pad byte `0x00`
- **THEN** writer writes 1 padding byte `0x00` and cursor position becomes 4
