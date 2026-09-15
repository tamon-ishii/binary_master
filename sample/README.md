# Binary Master Samples

Systematic and educational sample scripts demonstrating `binary_master` capabilities from basic declarative structures to schema-first specification generation and automated parsing.

> 📖 **Looking for a guided walkthrough?** Check out the comprehensive **[Step-by-Step Tutorial](../TUTORIAL.md)**.

## Directory Overview

| Script | Topic | Key Features Demonstrated |
|---|---|---|
| [`01_basic_struct.py`](./01_basic_struct.py) | Basic Declarative Structs | `@binary_struct`, primitive types (`UInt8`, `UInt16`, `UInt32`, `Float32`, `Bool`), `FixedArray`, `offsetof()` byte offsets, `sizeof()`, `read_struct()`, endianness overrides |
| [`02_bitfields_and_alignment.py`](./02_bitfields_and_alignment.py) | Bitfields & Memory Alignment | `Bits[N]` with packed container `bits=16`, struct alignment `align=4`, and automatic natural alignment `auto_align=True` |
| [`03_offsets_and_tables.py`](./03_offsets_and_tables.py) | Relative Pointers & Tables | `Offset[T, Base.SELF]`, offset arithmetic (`Base.SELF + 0x20`), `OffsetTable`, and deferred pointer patching |
| [`04_procedural_writer.py`](./04_procedural_writer.py) | Procedural Writer, Variants & Repeats | Stream writing, string strategies, candidate-validated polymorphic variants (`write_variant`), repeating chunk aggregation (`repeat`), one-stop Markdown spec and C header export directly from Writer, debug dumps |
| [`05_builder_and_reader.py`](./05_builder_and_reader.py) | Schema-First Builder & Automated Reader | Schema-first protocol design (no dummy data needed), sections & captions, Mermaid subgraphs, multi-language code export (C, Rust, C++, C#, Go), `builder.write("spec.md")`, automated `builder.read(data)`, and debug inspection (`hexdump`, `dump`) |
| [`06_advanced_v2_features.py`](./06_advanced_v2_features.py) | Advanced v2.0 Features | `Magic`, `Constant`, `BinaryEnum`, `CRC32` automated checksums, `VarUInt`/`VarInt` LEB128 variable-length integers, arbitrary `BitWriter`/`BitReader` |
| [`07_v0_3_0_features.py`](./07_v0_3_0_features.py) | v0.3.0 New Features | `Float16` (IEEE 754 half-precision float), `LengthOf`/`CountOf` (auto-calculation & linked reading), `total_size`/`pad_to` (fixed total size & padding), `Range` validation, standalone interactive HTML documentation (`to_html()`) |
| [`main.py`](./main.py) | Sample Runner | Orchestrates and verifies all samples in sequence |

## Running the Samples

You can run individual samples directly:

```bash
python sample/01_basic_struct.py
python sample/02_bitfields_and_alignment.py
python sample/03_offsets_and_tables.py
python sample/04_procedural_writer.py
python sample/05_builder_and_reader.py
python sample/06_advanced_v2_features.py
python sample/07_v0_3_0_features.py
```

Or run all samples together with the runner:

```bash
python sample/main.py
```
