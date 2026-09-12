## Why

Binary protocols defined in Python are frequently consumed or implemented in C/C++ environments, including embedded firmware, network daemons, game engines, and low-level drivers. Manually writing and maintaining corresponding C header files leads to human errors in data types, bitfields, and alignment. Generating C language header files (`.h`) directly from `ManualBuilder` schemas and `@binary_struct` definitions guarantees binary compatibility and single-source-of-truth consistency across Python and C/C++.

## What Changes

- Add `builder.to_c_header(...)` and `builder.write_c_header(path_or_file, ...)` to `ManualBuilder`:
  - Output standard C99/C11 types via `<stdint.h>` and `<stdbool.h>`
  - Map primitive types (`UInt8` -> `uint8_t`, `Float32` -> `float`, etc.) and fixed arrays (`FixedArray[UInt8, 16]` -> `uint8_t field[16];`)
  - Support C bitfields (`type name : N;`) matching `@binary_struct(bits=...)`
  - For `add_choice`, generate `enum` tag constants, variant structs, and a `union` container
  - Convert `add_document` chapters into formatted C block comments
  - Add standard include guards, `extern "C"` linkage wrappers for C++, and `#pragma pack(push, 1)` / `#pragma pack(pop)`
  - Provide standalone `to_c_struct(struct_cls)` and class helper for individual struct export

## Capabilities

### New Capabilities
- `c-header-export`: Automatic C header file generation with packed structs, bitfields, enums, unions, and documentation comments.

### Modified Capabilities
<!-- None -->

## Impact

- Add `binary_master.c_header` module.
- Add `to_c_header()` and `write_c_header()` to `ManualBuilder`.
- Export `to_c_header`, `write_c_header`, and `to_c_struct` in `binary_master`.
- Add unit tests in `tests/test_c_header.py`.
- Add a demonstration in `sample/` and update `README.md`.
