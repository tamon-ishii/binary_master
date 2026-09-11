## Context

See `proposal.md` for motivation. The project is a greenfield Python library targeting modern Python (>=3.10, tested on 3.14). The design emphasizes zero external dependencies, relying entirely on the standard library (`struct`, `io`, `enum`, `typing`).

## Goals / Non-Goals

**Goals:**
- Provide an intuitive, fluent, and type-annotated `BinaryWriter` class.
- Support unified stream handling for both in-memory buffers (`io.BytesIO`) and writable binary streams or file paths (`io.BufferedIOBase`).
- Provide consistent endianness support via `Endian` enum and string literals (`"little"`, `"big"`, `"native"`).
- Provide context manager support (`with BinaryWriter.to_file(path) as writer: ...`).
- Provide robust error handling for integer range violations and stream operations.

**Non-Goals:**
- Binary reading/parsing (`BinaryReader`) is deferred to a future change.
- Arbitrary bit-level writing (e.g., packing 3-bit ints) is excluded from this initial version.
- Schema compilation or serialization frameworks (e.g., Protobuf, ASN.1).

## Decisions

### 1. Underlying Serialization Engine
- **Choice**: Use Python's built-in `struct.pack` and `io.BytesIO` / file streams.
- **Rationale**: Leverages optimized C implementations in CPython, avoids external dependencies, and provides standard IEEE 754 float representation and integer endianness conversions.
- **Alternatives considered**: Manual bitwise byte shifting in pure Python (slower and more error-prone).

### 2. Unified Stream Abstraction
- **Choice**: `BinaryWriter` accepts an optional writable stream (`io.BufferedIOBase`). If omitted, it automatically instantiates and manages an internal `io.BytesIO`. Factory class methods `BinaryWriter.to_memory()` and `BinaryWriter.to_file(path_or_file)` provide clean entry points.
- **Rationale**: Keeps the core API unified so callers do not need distinct classes for in-memory vs. stream writing.
- **Alternatives considered**: Separate `BufferWriter` and `StreamWriter` classes. Rejected because the method set is 95% identical.

### 3. Endianness Representation
- **Choice**: Define `Endian` enum with values matching `struct` format characters (`LITTLE = "<"`, `BIG = ">"`, `NATIVE = "="`), while accepting case-insensitive string aliases (`"little"`, `"big"`, `"be"`, `"le"`).
- **Rationale**: Provides both IDE auto-completion via enum and ease of use with strings.

### 4. String Serialization Strategies
- **Choice**: Method `write_string(text, encoding="utf-8", strategy="null_terminated", prefix_bytes=2, fixed_length=None, pad_byte=b"\x00")` plus dedicated helpers `write_cstring`, `write_prefixed_string`, `write_fixed_string`.
- **Rationale**: Common binary formats vary widely in string storage conventions; dedicated helpers make intent clear at call sites.

## Risks / Trade-offs

- **[Risk] Non-seekable stream targets**: Streams like network sockets or pipes may not support `seek()` or `tell()`.
  - **Mitigation**: Check `stream.seekable()` when seeking or aligning; raise clear `io.UnsupportedOperation` with actionable error message.
- **[Risk] Integer out-of-bounds**: `struct.pack` raises `struct.error` with generic messages.
  - **Mitigation**: Wrap integer writes with explicit range checks to provide user-friendly error messages specifying the value, expected bounds, and type name.
