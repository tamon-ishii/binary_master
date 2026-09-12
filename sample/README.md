# Binary Master Samples

Systematic and educational sample scripts demonstrating `binary_master` capabilities from basic declarative structures to schema-first specification generation and automated parsing.

## Directory Overview

| Script | Topic | Key Features Demonstrated |
|---|---|---|
| [`01_basic_struct.py`](./01_basic_struct.py) | Basic Declarative Structs | `@binary_struct`, primitive types (`UInt8`, `UInt16`, `UInt32`, `Float32`), `FixedArray`, `sizeof()`, `read_struct()`, endianness overrides |
| [`02_bitfields_and_alignment.py`](./02_bitfields_and_alignment.py) | Bitfields & Memory Alignment | `Bits[N]` with packed container `bits=16`, struct alignment `align=4`, and automatic natural alignment `auto_align=True` |
| [`03_offsets_and_tables.py`](./03_offsets_and_tables.py) | Relative Pointers & Tables | `Offset[T, Base.SELF]`, offset arithmetic (`Base.SELF + 0x20`), `OffsetTable`, and deferred pointer patching |
| [`04_procedural_writer.py`](./04_procedural_writer.py) | Procedural Writer & Reader | Low-level stream writing, null-terminated/length-prefixed strings, alignment padding, captions, and `writer.write_manual()` |
| [`05_manual_builder_and_reader.py`](./05_manual_builder_and_reader.py) | ManualBuilder & Automated Reader | Schema-first manual design, `builder.add_document()`, polymorphic `builder.add_choice()`, conditional structs, `builder.write("spec.md")`, and automated `builder.read(data)` |
| [`main.py`](./main.py) | Sample Runner | Orchestrates and verifies all samples in sequence |

## Running the Samples

You can run individual samples directly:

```bash
python sample/01_basic_struct.py
python sample/02_bitfields_and_alignment.py
python sample/03_offsets_and_tables.py
python sample/04_procedural_writer.py
python sample/05_manual_builder_and_reader.py
```

Or run all samples together with the runner:

```bash
python sample/main.py
```
