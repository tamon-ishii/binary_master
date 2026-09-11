## 1. Project Setup and Architecture

- [x] 1.1 Create package directory `binary_master` with `__init__.py` and configure `tests/` directory; verify module can be imported.
- [x] 1.2 Implement `Endian` enum and normalization utility in `../../../src/binary_master/enums.py`; verify endian parsing tests pass.

## 2. Core BinaryWriter Implementation

- [x] 2.1 Implement `BinaryWriter` class structure with in-memory buffer and external stream support, including context manager and factory methods (`to_memory`, `to_file`); verify stream lifecycle tests pass.
- [x] 2.2 Implement primitive integer write methods (`int8`, `uint8`, `int16`, `uint16`, `int32`, `uint32`, `int64`, `uint64`) with bounds validation and endianness handling; verify integer tests pass.
- [x] 2.3 Implement floating point methods (`float32`, `float64`), boolean (`write_bool`), and raw bytes (`write_bytes`); verify float, boolean, and bytes tests pass.
- [x] 2.4 Implement string serialization helpers (`write_cstring`, `write_prefixed_string`, `write_fixed_string`); verify string tests pass.
- [x] 2.5 Implement positioning, seeking, padding, and boundary alignment (`tell`, `seek`, `pad`, `align`); verify cursor navigation and alignment tests pass.

## 3. Integration, Verification, and Packaging

- [x] 3.1 Export public API (`BinaryWriter`, `Endian`) from `../../../src/binary_master/__init__.py`; verify type hinting and imports.
- [x] 3.2 Implement comprehensive test suite in `tests/test_writer.py` covering all spec scenarios and verify all tests pass with `pytest`.
