## 1. Core Size Calculation Implementation

- [x] 1.1 Implement `sizeof(target)` and `binary_size(target)` in `src/binary_master/binary_struct.py`, handling `BinaryType`, static `@binary_struct` classes (including sized `Offset`, `OffsetTable`, `FixedArray`, alignment), and instances.
- [x] 1.2 Implement `_BinarySizeDescriptor` and attach `binary_size` and `__len__` to `@binary_struct` targets.

## 2. Exports & Integration

- [x] 2.1 Export `sizeof` and `binary_size` in `src/binary_master/__init__.py`.

## 3. Testing & Documentation

- [x] 3.1 Add unit tests in `tests/test_binary_struct.py` testing `Cls.binary_size`, `instance.binary_size`, `sizeof(...)`, `len(instance)`, sized `Offset`s, alignments, and error handling.
- [x] 3.2 Update `README.md` documentation with `sizeof` and `binary_size`.
- [x] 3.3 Verify all tests pass with `pytest`.
