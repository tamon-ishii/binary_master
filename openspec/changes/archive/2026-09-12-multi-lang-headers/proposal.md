## Why

Binary protocols and file formats defined in Python need to interoperate with diverse systems across modern software stacks: Rust for high-performance systems and WebAssembly, C# for Unity game development and .NET desktop/cloud tools, modern C++ (C++17/C++20) for engines and embedded runtimes, and Go for microservice backends. Providing automated code generation for these four languages from `ManualBuilder` ensures exact binary layout synchronization across multi-language architectures.

## What Changes

- Add multi-language code generators in `binary_master`:
  - **Rust** (`to_rust()`, `write_rust(path)`): Outputs `#[repr(C, packed)]` structs, `#[repr(u16)]` tag enums, and Rust enum tagged unions.
  - **C#** (`to_csharp()`, `write_csharp(path)`): Outputs `[StructLayout(LayoutKind.Sequential, Pack = 1)]` structs, enum tags, and `[StructLayout(LayoutKind.Explicit)]` unions.
  - **C++** (`to_cpp()`, `write_cpp(path)`): Outputs modern C++17/20 headers with `enum class`, `std::array`, `std::variant`, and `#pragma pack(push, 1)`.
  - **Go** (`to_go()`, `write_go(path)`): Outputs Go package structs, `[N]byte` arrays, and typed constants.
- Add unified dispatchers `builder.to_code(lang)` and `builder.write_code(path, lang=None)`.
- Add class methods to `@binary_struct`: `Cls.to_rust()`, `Cls.to_csharp()`, `Cls.to_cpp()`, `Cls.to_go()`.

## Capabilities

### New Capabilities
- `multi-lang-headers`: Code generation of header and type definitions for Rust, C#, C++, and Go from binary schemas and structs.

### Modified Capabilities
<!-- None -->

## Impact

- Add `src/binary_master/code_gen/` with generators for each language.
- Expose methods on `ManualBuilder` and `@binary_struct`.
- Add tests in `tests/test_multi_lang.py` (including real compiler verification with `rustc` and `g++`).
- Update samples and documentation.
