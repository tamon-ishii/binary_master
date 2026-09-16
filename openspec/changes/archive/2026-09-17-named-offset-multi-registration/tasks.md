## 1. Core Writer Implementation

- [x] 1.1 Update `self._named_offset_slots` to `dict[str, list[dict[str, Any]]]` and allow multiple slot registrations in `_register_named_offset_slot` and `reserve_named_offset` in `src/binary_master/writer.py`.
- [x] 1.2 Update `write_named_offset` and `rewrite_named_offset` in `src/binary_master/writer.py` to iterate through and backpatch all registered slots for the key.

## 2. Test Updates & Multi-Registration Test Cases

- [x] 2.1 Update duplicate-check tests in `tests/test_offset_to_table.py` to verify multi-registration and joint offset backpatching instead.
- [x] 2.2 Add tests verifying multiple `NamedOffset` slots across different structs and manual reservations pointing to the same key with varying base offsets.

## 3. Documentation & Verification

- [x] 3.1 Update `README.md`, `TUTORIAL.md`, and `FOR_AI.md` to document that `NamedOffset` keys allow multi-registration to target the same point.
- [x] 3.2 Run full test suite with `pytest` to ensure all tests pass.
