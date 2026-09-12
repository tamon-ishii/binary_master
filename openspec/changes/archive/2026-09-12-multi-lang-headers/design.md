## Context

Users need binary definitions across diverse programming languages. `ManualBuilder` contains the unified metadata necessary to generate definitions for Rust, C#, C++, and Go.

## Goals / Non-Goals

**Goals:**
- Provide language-specific generation functions and methods on `ManualBuilder` and `@binary_struct`:
  - Rust: `to_rust()`, `write_rust(path)`
  - C#: `to_csharp()`, `write_csharp(path)`
  - C++: `to_cpp()`, `write_cpp(path)`
  - Go: `to_go()`, `write_go(path)`
- Provide unified API:
  - `to_code(lang="rust"|"csharp"|"cpp"|"go"|"c")`
  - `write_code(path, lang=None)` with extension auto-detection (`.rs`, `.cs`, `.hpp`/`.cpp`, `.go`, `.h`/`.c`)
- Ensure idiomatic code generation for each language respecting exact memory packing.

**Non-Goals:**
- Full networking or IPC serialization libraries in target languages (only type definitions and binary layouts).

## Decisions

### 1. Code Generation Package Structure
Organize generators in `src/binary_master/code_gen/`:
- `rust.py`: Rust `#[repr(C, packed)]` and tagged enums
- `csharp.py`: C# `[StructLayout(Pack=1)]` and `[FieldOffset(0)]` unions
- `cpp.py`: Modern C++17/20 with `std::array` and `std::variant`
- `go.py`: Go package structs and typed consts
- `__init__.py`: Central dispatcher and extension resolver

### 2. Rust Code Generation Strategy
- Structs: `#[repr(C, packed)]\n#[derive(Debug, Clone, Copy, PartialEq)]\npub struct Name { pub field: type }`.
- Fixed Arrays: `[type; N]`.
- Enums: `#[repr(u16)]\n#[derive(Debug, Clone, Copy, PartialEq, Eq)]\npub enum NameTag { ... }`.
- Tagged Unions: `#[derive(Debug, Clone, Copy, PartialEq)]\npub enum NameUnion { Variant(Variant), ... }`.

### 3. C# Code Generation Strategy
- Structs: `[StructLayout(LayoutKind.Sequential, Pack = 1)]\npublic struct Name { ... }`.
- Arrays: `[MarshalAs(UnmanagedType.ByValArray, SizeConst = N)] public byte[] Field;`.
- Enums: `public enum NameTag : ushort { ... }`.
- Unions: `[StructLayout(LayoutKind.Explicit, Pack = 1)]\npublic struct NameUnion { [FieldOffset(0)] public Variant1 Variant1; ... }`.

### 4. C++ Code Generation Strategy
- Modern C++17: `#pragma once`, `<cstdint>`, `<array>`, `<variant>`.
- Packing: `#pragma pack(push, 1)` and `#pragma pack(pop)`.
- Choices: `enum class NameTag : uint16_t { ... };` and `using NameVariant = std::variant<Variant1, Variant2>;`.

### 5. Go Code Generation Strategy
- Package declaration: `package protocol`.
- Structs: `type Name struct { ... }`.
- Arrays: `[N]type`.
- Choices: typed `const` blocks.
