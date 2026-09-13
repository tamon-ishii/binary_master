## 1. Core Offset Calculation Implementation

- [x] 1.1 Implement `offsetof(target, field_name)` in `src/binary_master/binary_struct.py` supporting alignment, padding, and dot notation.
- [x] 1.2 Implement `bit_offsetof(target, field_name)` in `src/binary_master/binary_struct.py` for bitfield starting bit index inspection.
- [x] 1.3 Implement `_OffsetofDescriptor` and `_BitOffsetofDescriptor` and attach `.offsetof` and `.bit_offsetof` to `@binary_struct` targets.

## 2. Exports & Documentation

- [x] 2.1 Export `offsetof` and `bit_offsetof` in `src/binary_master/__init__.py`.
- [x] 2.2 Add documentation in `TUTORIAL.md` explaining `offsetof` usage, alignment, and nested structs.
- [x] 2.3 Create `FOR_AI.md` AI reference guide covering all library features including `offsetof`.

## 3. Testing & Verification

- [x] 3.1 Add unit tests in `tests/test_binary_struct.py` testing `offsetof`, `bit_offsetof`, alignments, manual padding, dot notation, and error handling.
- [x] 3.2 Verify all tests pass with `pytest`.
