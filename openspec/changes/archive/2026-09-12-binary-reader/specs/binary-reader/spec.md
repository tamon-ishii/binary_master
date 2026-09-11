## Purpose

Provides a high-level sequential binary reading interface for parsing, deserializing, and validating binary data from memory buffers and file streams with explicit endianness, type safety, and declarative struct support.

## ADDED Requirements

### Requirement: Read Primitive Integer Types
The binary reader SHALL support reading signed and unsigned integers across standard bit-widths (8-bit, 16-bit, 32-bit, and 64-bit). The reader SHALL respect the configured default endianness (big-endian or little-endian) and allow per-call endianness overrides. If insufficient bytes remain in the stream to satisfy the read request, the reader MUST raise an EOFError.

#### Scenario: Read unsigned and signed integers with specified endianness
- **WHEN** user reads uint16 in little-endian and int32 in big-endian from stream containing `\x34\x12\xFF\xFF\xFF\x9C`
- **THEN** reader returns uint16 `0x1234` and int32 `-100`

#### Scenario: Unexpected end of stream reading integer
- **WHEN** stream has only 2 bytes remaining and user attempts to read a 4-byte uint32
- **THEN** reader raises EOFError and stream position is restored or reports truncated error

### Requirement: Read Floating Point Types
The binary reader SHALL support reading 32-bit single precision (`float32`) and 64-bit double precision (`float64`) IEEE 754 floating point numbers according to the active or specified endianness.

#### Scenario: Read float32 and float64
- **WHEN** user reads float32 and float64 from serialized IEEE 754 byte representations
- **THEN** reader returns the corresponding float values accurately

### Requirement: Read Boolean and Raw Bytes
The binary reader SHALL support reading boolean values (interpreting `0x00` as `False` and any non-zero byte as `True`) and reading exact sequences of raw bytes of specified length `n`.

#### Scenario: Read boolean values
- **WHEN** reader reads two bytes `\x01\x00` as boolean
- **THEN** reader returns `True` followed by `False`

#### Scenario: Read arbitrary byte slice
- **WHEN** reader requests 4 bytes from stream containing `\xDE\xAD\xBE\xEF`
- **THEN** reader returns exact bytes `b"\xDE\xAD\xBE\xEF"` and advances cursor by 4 bytes

### Requirement: Read Encoded Strings
The binary reader SHALL support reading text strings decoded with a configurable character encoding (defaulting to UTF-8) using multiple framing strategies: null-terminated (C-style), length-prefixed (1-byte, 2-byte, or 4-byte prefix), and fixed-length (with trailing pad byte stripped).

#### Scenario: Read null-terminated string
- **WHEN** stream contains `b"hello\x00extra"`
- **THEN** reader returns `"hello"` and leaves cursor positioned at byte immediately after `\x00`

#### Scenario: Read length-prefixed string
- **WHEN** stream contains `\x00\x05` followed by `b"world"` and user specifies 2-byte big-endian prefix
- **THEN** reader returns `"world"` and advances cursor by 7 bytes

#### Scenario: Read fixed-length string with padding stripped
- **WHEN** stream contains `b"cat\x00\x00\x00"` and user reads 6 bytes with null byte padding
- **THEN** reader returns `"cat"` and cursor advances by 6 bytes

### Requirement: Stream and Cursor Positioning
The binary reader SHALL track the current read cursor position (`tell()`), allow moving to arbitrary stream offsets (`seek()`), skipping forward by a relative byte count (`skip()`), and aligning the read cursor to specified byte boundaries.

#### Scenario: Seek and query cursor position
- **WHEN** user reads 4 bytes, checks position `tell()`, seeks back to offset 2, and reads 2 bytes
- **THEN** cursor position reflects the seek, and bytes from offset 2 to 4 are returned

#### Scenario: Align read cursor to boundary
- **WHEN** cursor is at offset 3 and user requests alignment to a 4-byte boundary
- **THEN** reader skips 1 padding byte and cursor becomes 4

### Requirement: Declarative Structure Deserialization
The library SHALL provide mechanisms to deserialize `@binary_struct` annotated classes directly from byte sequences (`Cls.from_bytes(data)`) or from a `BinaryReader` stream (`reader.read_struct(Cls)`). Deserialization SHALL unpack primitive fields, bitfields (`Bits[N]`), fixed-size arrays (`FixedArray`), dynamic arrays (`Array`), nested structures, and resolve `Offset[T]` target structures.

#### Scenario: Deserializing struct from bytes
- **WHEN** user calls `Header.from_bytes(raw_data)` on serialized header bytes
- **THEN** an instance of `Header` is returned with all fields populated with deserialized values

#### Scenario: Round-trip struct serialization and deserialization
- **WHEN** a complex `@binary_struct` instance with bitfields and nested structs is serialized via `to_bytes()` and deserialized via `from_bytes()`
- **THEN** the resulting struct instance has field values identical to the original instance
