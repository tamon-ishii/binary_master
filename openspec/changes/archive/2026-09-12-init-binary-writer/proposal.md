## Why

Writing structured binary data in Python using low-level `struct` operations or manual byte concatenation is error-prone, verbose, and difficult to maintain. Developers frequently need to write binary formats (network protocols, file formats, firmware payloads) with specific endianness, variable-width numbers, strings, and alignments.

`binary_master` provides a clean, sequential, and type-safe `BinaryWriter` library that supports both in-memory buffers and file/stream targets.

## What Changes

- Introduce the `binary_master` library module and core `BinaryWriter` interface.
- Support writing integer types (`int8`, `uint8`, `int16`, `uint16`, `int32`, `uint32`, `int64`, `uint64`) with configurable endianness (`little`, `big`, `native`).
- Support floating point numbers (`float32`, `float64`) with configurable endianness.
- Support boolean values and raw byte sequences.
- Support string writing strategies: null-terminated (C-string), length-prefixed (1, 2, or 4-byte prefix), and fixed-width padded strings with configurable encoding.
- Support output destinations: in-memory dynamic buffer (`bytearray` / `bytes`) and file/stream destinations (`io.BufferedIOBase` or file path).
- Support position management, seeking, padding, and byte boundary alignment.
- Provide comprehensive unit tests and type annotations.

## Capabilities

### New Capabilities
- `binary-writer`: Core sequential binary writing capabilities for primitive numeric types, strings, raw bytes, endianness handling, position tracking/alignment, and in-memory or stream output.

### Modified Capabilities
<!-- None -->

## Impact

- New package directory `../../../src/binary_master/` containing the core library implementation.
- Public exports in `../../../src/binary_master/__init__.py`.
- New test suite under `tests/`.
- No breaking changes (initial greenfield library implementation).
