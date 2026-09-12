## 1. Implementation
- [x] 1.1 Create `src/binary_master/debug.py` with `hexdump`, `dump_table`, `dump_json`, `dump_dict`, `debug_dump`, and `diff_dump`
- [x] 1.2 Add `hexdump`, `dump`, `diff` methods to `BinaryWriter` in `src/binary_master/writer.py`
- [x] 1.3 Add `hexdump`, `dump` methods to `BinaryReader` in `src/binary_master/reader.py`
- [x] 1.4 Export debug functions from `src/binary_master/__init__.py`

## 2. Testing
- [x] 2.1 Create `tests/test_debug.py` covering raw bytes hexdump, annotated writer hexdump, reader cursor dump, table dump, json dump, and diff dump
- [x] 2.2 Verify full test suite passes with `uv run pytest`

## 3. Samples & Documentation
- [x] 3.1 Update `sample/04_procedural_writer.py` to showcase `writer.hexdump()` and `reader.hexdump()`
- [x] 3.2 Update `README.md` with debug dump documentation
