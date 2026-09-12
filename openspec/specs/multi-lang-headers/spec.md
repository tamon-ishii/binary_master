# multi-lang-headers Specification

## Purpose
Provides automated code generation for Rust, C#, C++, and Go from `ManualBuilder` schemas and `@binary_struct` classes, ensuring consistent binary packing and type definitions across multiple programming languages.

## Requirements

### Requirement: Rust Code Generation
The system SHALL generate valid Rust definitions using `#[repr(C, packed)]` for structs, fixed arrays `[T; N]`, primitive types (`u8`, `u16`, `u32`, `u64`, `i8`, `i16`, `i32`, `i64`, `f32`, `f64`), `#[repr(u16)]` enums for choice tags, and tagged union enums for choice variants.

#### Scenario: Generate Rust structs and enums
- **WHEN** user calls `builder.to_rust()` on a schema with a header struct and choice variants
- **THEN** generator outputs Rust code with `#[repr(C, packed)] pub struct` definitions, `pub enum` tags, and a tagged union enum

### Requirement: C# Code Generation
The system SHALL generate valid C# definitions with `[StructLayout(LayoutKind.Sequential, Pack = 1)]` for structs, fixed buffers or array attributes, primitive types (`byte`, `ushort`, `uint`, `ulong`, `sbyte`, `short`, `int`, `long`, `float`, `double`), `enum` tags, and `[StructLayout(LayoutKind.Explicit, Pack = 1)]` unions.

#### Scenario: Generate C# structs and explicit union
- **WHEN** user calls `builder.to_csharp()` on a schema
- **THEN** generator outputs C# code with `[StructLayout]` sequential structs, enum tags, and explicit layout union

### Requirement: Modern C++ Code Generation
The system SHALL generate modern C++17/20 headers using `#pragma once`, `#pragma pack(push, 1)`, standard integer types (`<cstdint>`), fixed arrays (`std::array`), strongly-typed `enum class`, and polymorphic variants (`std::variant`).

#### Scenario: Generate C++ header with std::variant
- **WHEN** user calls `builder.to_cpp()` on a schema with a choice
- **THEN** generator outputs C++ code with `enum class`, `std::array`, and `std::variant`

### Requirement: Go Code Generation
The system SHALL generate valid Go code with package declaration, exported PascalCase struct definitions with correct primitive types (`uint8`, `uint16`, `uint32`, `uint64`, `int8`, `int16`, `int32`, `int64`, `float32`, `float64`), fixed arrays `[N]T`, and `const` declarations for choice tags.

#### Scenario: Generate Go package structs
- **WHEN** user calls `builder.to_go(package_name="protocol")`
- **THEN** generator outputs Go code with `package protocol`, `type Struct struct`, and `const` tags

### Requirement: Language Export APIs and File Writing
The system SHALL provide dedicated methods (`to_rust()`, `write_rust()`, `to_csharp()`, `write_csharp()`, `to_cpp()`, `write_cpp()`, `to_go()`, `write_go()`) and unified methods (`to_code(lang)`, `write_code(path)`) on `ManualBuilder`, as well as per-struct export methods on `@binary_struct`.

#### Scenario: Export code by file extension inference
- **WHEN** user calls `builder.write_code("output.rs")` or `builder.write_code("output.cs")`
- **THEN** system automatically detects the language from the file extension and writes the corresponding code
