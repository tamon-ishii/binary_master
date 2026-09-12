## Context

`ManualBuilder` defines full binary protocol schemas (structures, bitfields, choices, conditions, documentation). Users need to bridge these Python schemas with C/C++ projects.

## Goals / Non-Goals

**Goals:**
- Provide `builder.to_c_header(...)` and `builder.write_c_header(path_or_file, ...)`.
- Provide standalone `to_c_struct(struct_cls)`.
- Generate ANSI C / C99 / C11 compliant code with `<stdint.h>`, `<stdbool.h>`, and `extern "C"`.
- Use `#pragma pack(push, 1)` and `#pragma pack(pop)` for cross-compiler packing (MSVC, GCC, Clang).
- Accurately translate bitfields to C `: width` syntax.
- Translate polymorphic choices (`add_choice`) into enum tag constants and union definitions.
- Convert docstrings and inline descriptions into Doxygen-compatible C comments.

**Non-Goals:**
- Generating full C serialization/deserialization helper functions (only headers/data definitions).

## Decisions

### 1. Code Generation Module
Implement generation logic in `src/binary_master/c_header.py`, keeping `ManualBuilder` clean and allowing standalone struct generation without requiring a builder instance.

### 2. Type Mapping
- Primitives: `UInt8` -> `uint8_t`, `UInt16` -> `uint16_t`, `UInt32` -> `uint32_t`, `UInt64` -> `uint64_t`, `Int8` -> `int8_t`, `Int16` -> `int16_t`, `Int32` -> `int32_t`, `Int64` -> `int64_t`, `Float32` -> `float`, `Float64` -> `double`.
- Arrays: `FixedArray[T, N]` becomes `c_type name[N]`.
- Pointers/Offsets: `Offset[T]` becomes `uint32_t name; /* Offset to T */`.
- Bitfields: If total bits <= 8, use `uint8_t`; if <= 16, use `uint16_t`; if <= 32, use `uint32_t`; else `uint64_t`. Each field formatted as `base_type name : width;`.

### 3. Choice Translation
For each `ChoiceElement`:
- Generate `typedef enum { ... } ChoiceNameTag;` mapping tag values.
- Emit variant struct definitions (if not already emitted).
- Generate `typedef union { ... } ChoiceNameUnion;` containing an instance of each variant.

### 4. Naming Conventions
- Struct names: PascalCase (matching class name).
- Union member names: snake_case (e.g. `TextMessage` -> `text_message`).
- Enum names: `SCREAMING_SNAKE_CASE` (e.g. `MSG_TYPE_TEXT_MESSAGE = 1`).
