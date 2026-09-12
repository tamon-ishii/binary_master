## 1. Core C Header Generator Implementation

- [x] 1.1 Implement type mappings, struct translation, bitfield generation, choice enum and union generation in `src/binary_master/c_header.py` and verify syntax rules
- [x] 1.2 Implement `to_c_header()` and `write_c_header()` in `src/binary_master/manual_builder.py` and connect with `ManualBuilder` schema elements
- [x] 1.3 Export `to_c_header`, `write_c_header`, and `to_c_struct` in `src/binary_master/__init__.py` and verify package imports

## 2. Unit Testing

- [x] 2.1 Create test suite `tests/test_c_header.py` covering structs, bitfields, arrays, choice enums/unions, include guards, pragmas, and file writing, and verify with `pytest`

## 3. Sample and Documentation

- [x] 3.1 Update `sample/05_manual_builder_and_reader.py` to demonstrate generating C header files (`telemetry_protocol.h`) and verify execution with `python sample/main.py`
- [x] 3.2 Update `README.md` with C header export documentation, validate and archive OpenSpec change
