## Context

`binary-master` currently implements `BinaryWriter` for low-level sequential binary packing and `@binary_struct` for high-level declarative binary layout definition. Every `@binary_struct` retains metadata in `__binary__` describing field types, bitfield configurations, default endianness, and alignment constraints.

See [proposal.md](file:///home/ishii/PycharmProjects/binary_master/openspec/changes/binary-reader/proposal.md) for the motivation and high-level scope.

## Goals / Non-Goals

**Goals:**
- Provide `BinaryReader` (and alias `Reader`) that mirrors `BinaryWriter` with symmetric read operations for primitives, strings, raw bytes, and cursor navigation.
- Support strict bounds and EOF checking, raising `EOFError` on truncated stream inputs.
- Implement declarative structure deserialization via `read_struct(cls, reader)` and `Cls.from_bytes(data)`.
- Support reading bitfields, fixed arrays, variable arrays, nested structs, and resolving `Offset[T]` targets.

**Non-Goals:**
- Zero-copy parsing via external C extensions or mmap optimizations (keep pure Python 3.14+ implementation).
- Lazy evaluation or streaming parsing generators.

## Decisions

### Decision 1: Stream Encapsulation
- **Approach**: Accept `Union[bytes, bytearray, BinaryIO, str, Path]` in `BinaryReader.__init__` and factory methods (`to_memory`, `from_file`, etc.). In-memory byte sequences are wrapped in `io.BytesIO`.
- **Rationale**: Allows a single unified reading implementation across in-memory buffers and external file streams.
- **Alternatives considered**: Operating directly on byte slices via indices. Rejected because it would duplicate read logic for file streams.

### Decision 2: Strict Byte Reading with `_read_exact(n)`
- **Approach**: Implement an internal `_read_exact(n: int) -> bytes` method that verifies `len(data) == n`. If fewer bytes are returned, raise `EOFError(f"Unexpected EOF: requested {n} bytes, got {len(data)}")`.
- **Rationale**: Standard library `read(n)` returns partial bytes on EOF without raising an exception, which could silently corrupt data or cause ambiguous `struct.error`.

### Decision 3: Symmetrical Type Mapping
- **Approach**: Reuse existing `normalize_endian` and format mappings from `binary_master.enums` and `BinaryType._fmt` in `binary_master.binary_struct`.
- **Rationale**: Guarantees bit-exact symmetry with `BinaryWriter` without maintaining parallel format string tables.

### Decision 4: Declarative Deserialization Architecture
- **Approach**:
  1. Add `read_struct(cls: type[T], reader: BinaryReader, endian: EndianType = None) -> T` in `src/binary_master/binary_struct.py`.
  2. Synthesize `from_bytes(cls, data: Union[bytes, bytearray], endian: EndianType = None) -> T` and attach it to `@binary_struct` decorated classes.
  3. When an `Offset[T]` field is encountered during struct reading:
     - Read the offset integer value.
     - Save current stream position `return_pos = reader.tell()`.
     - Seek to `target_offset`.
     - Recursively call `read_struct(TargetClass, reader)`.
     - Seek back to `return_pos` so subsequent struct fields continue in linear sequence.
- **Rationale**: Provides an intuitive, symmetrical API where `struct.to_bytes()` and `Cls.from_bytes()` perfectly round-trip.

## Risks / Trade-offs

- **[Risk: Out-of-bounds or cyclic offsets]** → **Mitigation**: Validate offset targets against stream length before seeking; raise `ValueError` if offset is negative or exceeds available stream size.
- **[Risk: Seeking on non-seekable streams]** → **Mitigation**: Detect `stream.seekable()` on file objects and raise descriptive `io.UnsupportedOperation` if offset targets require seeking on a unidirectional pipe.
