## 1. Type Stubs & PEP 561 Support

- [x] 1.1 Add `src/binary_master/py.typed` marker file and verify package is recognized as typed
- [x] 1.2 Create `src/binary_master/binary_struct.pyi` and `src/binary_master/__init__.pyi` with `Offset[Target] -> Target | None` and primitive types mapping to `int`/`float`/`bool`
- [x] 1.3 Export `Literal` and shorthand alias `L` from `binary_master` and stubs

## 2. Runtime Support & Unwrapping

- [x] 2.1 Implement `_unwrap_literal_int` helper in `src/binary_master/binary_struct.py`
- [x] 2.2 Support unwrapping `Literal[N]` and `L[N]` in `FixedArray` and `OffsetTable` class indexing
- [x] 2.3 Verify full test suite passes with `pytest tests/`

## 3. Documentation & Verification

- [x] 3.1 Update `README.md`, `TUTORIAL.md`, and `FOR_AI.md` with typed `L[N]` examples and IDE completion notes
- [x] 3.2 Verify `example.py` passes with 0 diagnostics under `ty check example.py`
