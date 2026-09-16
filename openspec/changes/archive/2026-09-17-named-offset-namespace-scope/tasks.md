## 1. Core Writer Implementation

- [x] 1.1 Add `_namespace_stack`, `_namespace_counters`, `current_namespace`, and `_qualify_name` in `src/binary_master/writer.py`.
- [x] 1.2 Implement `BinaryWriter.namespace` context manager supporting nesting and `auto_id=True`.
- [x] 1.3 Apply `_qualify_name` to `_register_named_offset_slot`, `reserve_named_offset`, `write_named_offset`, and `rewrite_named_offset` in `src/binary_master/writer.py`.

## 2. Tests & Verification

- [x] 2.1 Add comprehensive tests for scoped namespaces, nesting, `auto_id`, and root `/` escape in `tests/test_offset_to_table.py`.
- [x] 2.2 Run full test suite with `pytest` to ensure all tests pass.

## 3. Documentation

- [x] 3.1 Update `README.md`, `TUTORIAL.md`, and `FOR_AI.md` with examples and API details for `with writer.namespace(...)`.
