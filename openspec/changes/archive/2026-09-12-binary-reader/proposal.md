## Why

Currently `binary-master` provides comprehensive binary construction and documentation capabilities via `BinaryWriter` and `@binary_struct`. However, it lacks symmetric reading and deserialization support. To inspect, parse, round-trip, and validate binary streams and files, a complementary `BinaryReader` and `@binary_struct` deserialization capability is required.

## What Changes

- Introduce `BinaryReader` (and alias `Reader`) for sequential reading from bytes or binary streams (`io.BufferedIOBase` or files).
- Provide type-safe primitive read methods: `read_uint8`, `read_int8`, `read_uint16`, `read_int16`, `read_uint32`, `read_int32`, `read_uint64`, `read_int64`, `read_float32`, `read_float64`, `read_bool`, and `read_bytes(n)`.
- Support reading strings with standard strategies: `read_cstring()` (null-terminated), `read_prefixed_string(prefix_bytes)` (length-prefixed), and `read_fixed_string(length, pad_byte)`.
- Provide cursor positioning, seeking, skipping, and alignment checks: `tell()`, `seek()`, `skip(n)`, and `align(boundary)`.
- Support declarative deserialization on `@binary_struct`:
  - `Cls.from_bytes(data, endian=None)` class method
  - `reader.read_struct(Cls, endian=None)` method
  - Automatic unpacking of primitive fields, bitfields (`Bits[N]`), fixed and variable arrays (`FixedArray`, `Array`), nested structs, and offset target resolution (`Offset[T]`).

## Capabilities

### New Capabilities
- `binary-reader`: Sequential binary reading and declarative structure deserialization for primitives, strings, bitfields, arrays, and offsets.

### Modified Capabilities
<!-- None -->

## Impact

- **New Files**: `src/binary_master/reader.py`
- **Updated Files**:
  - `src/binary_master/binary_struct.py`: Add `read_struct` and `from_bytes` classmethod generation to `@binary_struct`.
  - `src/binary_master/__init__.py`: Export `BinaryReader`, `Reader`, and `read_struct`.
- **Dependencies**: No external dependencies needed (uses standard library `struct` and `io`).
- **Breaking Changes**: None. Fully backward-compatible.
