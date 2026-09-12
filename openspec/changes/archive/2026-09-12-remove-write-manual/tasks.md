## 1. Remove write_manual from Core
- [x] 1.1 Remove `write_manual()` method from `src/binary_master/writer.py`
- [x] 1.2 Remove `write_manual()` function from `src/binary_master/manual.py`
- [x] 1.3 Remove `write_manual()` alias from `src/binary_master/builder.py`
- [x] 1.4 Remove `write_manual` from `src/binary_master/__init__.py`

## 2. Update Samples and Tests
- [x] 2.1 Update `sample/04_procedural_writer.py` and `sample/README.md`
- [x] 2.2 Update tests in `tests/test_manual.py`, `tests/test_caption.py`, `tests/test_comments.py`, `tests/test_advanced_features.py`, `tests/test_builder.py`
- [x] 2.3 Verify test suite passes with `uv run pytest`

## 3. Documentation
- [x] 3.1 Update `README.md` to remove all mentions of `write_manual`
