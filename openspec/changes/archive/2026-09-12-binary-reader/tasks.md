## 1. Core BinaryReader Implementation

- [x] 1.1 Create `src/binary_master/reader.py` with `BinaryReader` class, stream initialization (`bytes`, `bytearray`, files), and `_read_exact` method; verify basic instantiation.
- [x] 1.2 Implement primitive integer read methods (`read_uint8`, `read_int8`, `read_uint16`, `read_int16`, `read_uint32`, `read_int32`, `read_uint64`, `read_int64`), floating-point readers, `read_bool`, and `read_bytes`; verify with primitive read unit tests.
- [x] 1.3 Implement string readers (`read_cstring`, `read_prefixed_string`, `read_fixed_string`) and stream navigation (`tell`, `seek`, `skip`, `align`); verify with string and navigation unit tests.

## 2. Declarative Structure Deserialization

- [x] 2.1 Implement `read_struct` in `src/binary_master/binary_struct.py` to deserialize `@binary_struct` classes with primitive fields, bitfields (`Bits`), fixed arrays (`FixedArray`), and alignment padding; verify with struct unit tests.
- [x] 2.2 Implement `Offset[T]` target resolution in `read_struct` by reading offset, seeking to target, recursively reading target struct, and restoring cursor position; verify with offset struct tests.
- [x] 2.3 Synthesize `from_bytes(cls, data, endian=None)` class method in `@binary_struct`; verify round-trip serialization and deserialization (`to_bytes` -> `from_bytes`).

## 3. Integration, Verification, and Documentation

- [x] 3.1 Export `BinaryReader`, `Reader`, and `read_struct` in `src/binary_master/__init__.py`; verify exports and public API access.
- [x] 3.2 Add comprehensive unit tests in `tests/test_reader.py` covering all reader scenarios, error cases, and EOF handling; verify all tests pass with `pytest`.
- [x] 3.3 Update `README.md` with `BinaryReader` and `from_bytes` usage documentation.
