## 1. Core RelativeBase and Base Implementation

- [x] 1.1 Implement `RelativeBase` and `Base` with operator overloading (`+`, `-`) in `src/binary_master/binary_struct.py`.
- [x] 1.2 Update `Offset.__class_getitem__` and `OffsetTable.__class_getitem__` to support `RelativeBase` and shorthand forms (e.g. `Offset[Target, Base.SELF + 0x20]`).

## 2. Serialization & Deserialization

- [x] 2.1 Update `write_struct` to record `struct_start_pos` and resolve `RelativeBase` for `Offset` and `OffsetTable`.
- [x] 2.2 Update `read_struct` to record `struct_start_pos` and resolve `RelativeBase` when recovering target offsets.
- [x] 2.3 Export `Base` and `RelativeBase` in `src/binary_master/__init__.py`.

## 3. Testing & Verification

- [x] 3.1 Add comprehensive unit tests in `tests/test_advanced_features.py` testing `Base.SELF`, `Base.SELF + delta`, `Base.SELF - delta`, `Base.FIELD`, shorthand syntax, nested structs, serialization, and round-trip deserialization.
- [x] 3.2 Update `README.md` with documentation and examples for `Base.SELF`.
- [x] 3.3 Verify all tests pass with `pytest`.
