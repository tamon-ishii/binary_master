## 1. Core Writer Guard

- [x] 1.1 Add resolved check in `write_named_offset` raising `DuplicateNamedOffsetError` if already resolved, with `_allow_rewrite: bool = False` support in `src/binary_master/writer.py`.
- [x] 1.2 Pass `_allow_rewrite=True` from `rewrite_named_offset` when delegating target writes in `src/binary_master/writer.py`.

## 2. Tests & Verification

- [x] 2.1 Add unit tests verifying `write_named_offset` raises `DuplicateNamedOffsetError` on second invocation, while `rewrite_named_offset` succeeds.
- [x] 2.2 Run full test suite with `pytest` to ensure all tests pass.

## 3. Documentation

- [x] 3.1 Update documentation in `README.md`, `TUTORIAL.md`, and `FOR_AI.md` to explain that repeated calls to `write_named_offset` raise `DuplicateNamedOffsetError` and require `rewrite_named_offset`.
