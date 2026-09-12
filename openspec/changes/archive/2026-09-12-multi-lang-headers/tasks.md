## 1. Multi-Language Code Generators Implementation

- [x] 1.1 Implement Rust code generator in `src/binary_master/code_gen/rust.py`
- [x] 1.2 Implement C# code generator in `src/binary_master/code_gen/csharp.py`
- [x] 1.3 Implement Modern C++ code generator in `src/binary_master/code_gen/cpp.py`
- [x] 1.4 Implement Go code generator in `src/binary_master/code_gen/go.py`
- [x] 1.5 Implement central dispatcher and extension resolver in `src/binary_master/code_gen/__init__.py`

## 2. ManualBuilder and @binary_struct Integration

- [x] 2.1 Add language-specific export methods (`to_rust`, `write_rust`, `to_csharp`, `write_csharp`, `to_cpp`, `write_cpp`, `to_go`, `write_go`, `to_code`, `write_code`) to `ManualBuilder`
- [x] 2.2 Add per-struct export methods (`to_rust`, `to_csharp`, `to_cpp`, `to_go`) to `@binary_struct` and export in `src/binary_master/__init__.py`

## 3. Testing and Compiler Verification

- [x] 3.1 Implement unit test suite `tests/test_multi_lang.py` verifying code generation for all 4 languages, and test compilation with `rustc` and `g++`

## 4. Sample and Documentation

- [x] 4.1 Update `sample/05_manual_builder_and_reader.py` to output all header files and verify execution with `python sample/main.py`
- [x] 4.2 Update `README.md` with multi-language export instructions, validate and archive OpenSpec change
