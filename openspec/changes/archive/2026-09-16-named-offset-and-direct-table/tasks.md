## 1. Direct Offset to OffsetTable (Offset[OffsetTable[...]])

- [x] 1.1 Support `Offset[OffsetTable[...]]` type annotation parsing in `_extract_offset_target`.
- [x] 1.2 Implement automatic count extraction and payload serialization on struct serialization in `write_struct`.
- [x] 1.3 Support deserialization of direct offset tables into struct lists in `read_struct`.

## 2. NamedOffset for Deferred Offset Resolution

- [x] 2.1 Implement `NamedOffset` type marker and registration in `BinaryWriter`.
- [x] 2.2 Implement `write_named_offset` and `rewrite_named_offset` with duplicate and missing key validation.
- [x] 2.3 Implement error classes `DuplicateNamedOffsetError` and `NamedOffsetNotFoundError` in `exceptions.py`.

## 3. Automatic Zero-Initialization & Static Typing

- [x] 3.1 Implement zero-value fallback in `@binary_struct` constructor generation when arguments are omitted.
- [x] 3.2 Implement `BinaryStruct` and `Struct` base classes with full method descriptors.
- [x] 3.3 Export standalone `to_bytes` and `from_bytes` utility functions.

## 4. Documentation & Tests

- [x] 4.1 Update `README.md`, `TUTORIAL.md`, and `FOR_AI.md` with detailed examples and API reference.
- [x] 4.2 Add unit tests in `tests/test_offset_to_table.py` and `tests/test_binary_struct.py`.
- [x] 4.3 Verify all tests pass with `pytest`.
