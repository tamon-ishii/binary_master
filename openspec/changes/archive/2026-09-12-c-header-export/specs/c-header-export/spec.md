## Purpose

Provides automatic generation of C/C++ header files (`.h`) from `ManualBuilder` schemas and `@binary_struct` definitions, including packed typedef structs, bitfields, enums, unions, and documentation comments.

## ADDED Requirements

### Requirement: C Struct Generation from Binary Structs
The system SHALL generate standard C99/C11 `typedef struct` definitions from `@binary_struct` classes, correctly mapping primitive integer types, floating point types, nested structs, and fixed-length arrays.

#### Scenario: Generate C struct with primitive fields and array
- **WHEN** user exports a struct with `magic: UInt32`, `version: UInt16`, and `tag: FixedArray[UInt8, 4]`
- **THEN** generator outputs a `typedef struct` with `uint32_t magic;`, `uint16_t version;`, and `uint8_t tag[4];`

### Requirement: C Bitfield Struct Generation
The system SHALL translate `@binary_struct(bits=N)` bitfield classes to C bitfield struct definitions with specified bit widths.

#### Scenario: Generate C bitfield struct
- **WHEN** user exports a struct with `enabled: Bits[1]` and `priority: Bits[3]` in an 8-bit container
- **THEN** generator outputs a `typedef struct` with `uint8_t enabled : 1;` and `uint8_t priority : 3;`

### Requirement: Polymorphic Choice and Union Generation
The system SHALL translate `ManualBuilder.add_choice()` definitions into corresponding C `enum` constants for variant tags, generate individual variant structs, and generate a C `typedef union` encompassing all variants.

#### Scenario: Generate choice enum and union
- **WHEN** user registers a choice `payload` with tag field `msg_type` and variants `1: TextMessage`, `2: SensorReport`
- **THEN** generator outputs an `enum` defining tag values `1` and `2`, outputs `TextMessage` and `SensorReport` structs, and outputs a `typedef union` containing `TextMessage text_message;` and `SensorReport sensor_report;`

### Requirement: Header Formatting and Preprocessor Controls
The system SHALL wrap generated C headers with standard include guards (`#ifndef ... #define ... #endif`), standard library includes (`<stdint.h>`, `<stdbool.h>`), C++ `extern "C"` guards, and `#pragma pack(push, 1)` / `#pragma pack(pop)` pragmas. The system SHALL render `add_document` chapters as C block comments.

#### Scenario: Generate complete C header with guards and pragmas
- **WHEN** user calls `builder.to_c_header(guard="MY_PROTOCOL_H")`
- **THEN** output includes `#ifndef MY_PROTOCOL_H`, `#pragma pack(push, 1)`, `extern "C"`, all structs/unions, `#pragma pack(pop)`, and `#endif`

### Requirement: File Export and In-Memory Generation
The system SHALL provide `builder.to_c_header()` to retrieve the C header string in memory, and `builder.write_c_header(path_or_file)` to write the generated C header directly to a file path or stream.

#### Scenario: Write C header to file path
- **WHEN** user calls `builder.write_c_header("protocol.h")`
- **THEN** generator writes the complete C header code to `protocol.h` and returns the string
