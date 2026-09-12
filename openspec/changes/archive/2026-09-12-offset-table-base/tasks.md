## 1. Writer & OffsetTableHandle Implementation

- [x] 1.1 Add `base_offset: int = 0` parameter to `write_offset_table` in `src/binary_master/writer.py`.
- [x] 1.2 Update `OffsetTableHandle` in `src/binary_master/writer.py` to store `base_offset`, validate `stored_value >= 0`, pack `stored_value`, update layout entries, and provide `base_offset`, `get_target_offset`, and `get_stored_offset`.

## 2. Declarative Struct Support

- [x] 2.1 Update `OffsetTable.__class_getitem__` in `src/binary_master/binary_struct.py` to support optional third argument `base_offset`.
- [x] 2.2 Update `write_struct` in `src/binary_master/binary_struct.py` to forward `base_offset` to `writer.write_offset_table`.

## 3. Testing, Documentation & Verification

- [x] 3.1 Add unit tests for `base_offset` in `tests/test_advanced_features.py` (procedural, error checks, manual rendering, and declarative struct).
- [x] 3.2 Update `README.md` documenting `base_offset`.
- [x] 3.3 Verify all unit tests pass with `pytest`.
