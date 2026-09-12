## 1. Type Support & Alignment

- [x] 1.1 Implement `__class_getitem__` on `Offset` in `src/binary_master/binary_struct.py` supporting `Offset[Target, OffsetType=UInt32, BaseOffset=0]`.
- [x] 1.2 Implement `_normalize_offset_type` helper supporting `UInt8`, `UInt16`, `UInt32`, `UInt64`, and byte sizes `1`, `2`, `4`, `8`.
- [x] 1.3 Update `_get_field_alignment` in `src/binary_master/binary_struct.py` to use the size of `OffsetType`.

## 2. Serialization & Deserialization

- [x] 2.1 Update `write_struct` in `src/binary_master/binary_struct.py` to write placeholders and deferred backpatches with the customized offset width, packing `target_pos - base_offset`.
- [x] 2.2 Update `read_struct` in `src/binary_master/binary_struct.py` to unpack the configured offset width and resolve target objects at `stored_offset + base_offset`.

## 3. Testing & Documentation

- [x] 3.1 Add unit tests in `tests/test_advanced_features.py` for 1-byte, 2-byte, 4-byte, and 8-byte offsets, integer size syntax (`Offset[T, 2]`), and round-trip serialization/deserialization.
- [x] 3.2 Update `README.md` documentation.
- [x] 3.3 Verify all tests pass with `pytest`.
