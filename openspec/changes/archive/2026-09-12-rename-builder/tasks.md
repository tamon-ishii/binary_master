## 1. Class and Module Aliasing
- [x] 1.1 In `src/binary_master/manual_builder.py`, rename `ManualBuilder` to `BinaryBuilder` and add `Builder = BinaryBuilder` and `ManualBuilder = BinaryBuilder`
- [x] 1.2 Create `src/binary_master/builder.py` re-exporting `BinaryBuilder`, `Builder`, `ManualBuilder`, and `BuilderReadResult`
- [x] 1.3 In `src/binary_master/__init__.py`, export `BinaryBuilder`, `Builder`, and `ManualBuilder`

## 2. Tests and Verification
- [x] 2.1 Add unit tests for `BinaryBuilder` and `Builder` aliases
- [x] 2.2 Verify existing 110 tests still pass

## 3. Samples and Documentation
- [x] 3.1 Update `sample/05_manual_builder_and_reader.py` to use `Builder`
- [x] 3.2 Update `README.md` to introduce the `Writer`, `Reader`, `Builder` trinity
