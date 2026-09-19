# Binary Master Interactive Samples (Jupyter Notebooks)

Interactive Jupyter notebooks demonstrating `binary_master` capabilities from basic declarative structures to schema-first specification generation and automated parsing.

> 📖 **Looking for a guided walkthrough?** Check out the comprehensive **[Step-by-Step Tutorial](../TUTORIAL.md)**.

## Notebook Overview

All notebooks are pre-executed with formatted outputs, diagrams, and annotated hexdumps so you can view them directly on GitHub, VSCode, or in JupyterLab:

| Notebook | Topic | Key Features Demonstrated |
|---|---|---|
| [`01_basic_struct.ipynb`](./01_basic_struct.ipynb) | Basic Declarative Structs | `@binary_struct`, primitive types (`UInt8`, `UInt16`, `UInt32`, `Float32`, `Bool`), `FixedString`, `offsetof()` byte offsets, `sizeof()`, `read_struct()`, endianness overrides |
| [`02_bitfields_and_alignment.ipynb`](./02_bitfields_and_alignment.ipynb) | Bitfields & Memory Alignment | `Bits[N]` with packed container `bits=16`, struct alignment `align=4`, and automatic natural alignment `auto_align=True` |
| [`03_offsets_and_tables.ipynb`](./03_offsets_and_tables.ipynb) | Relative Pointers & Tables | `Offset[T, Base.SELF]`, offset arithmetic (`Base.SELF + 0x20`), `OffsetTable`, deferred pointer patching, and `with writer.namespace(...)` |
| [`04_procedural_writer.ipynb`](./04_procedural_writer.ipynb) | Procedural Writer, Variants & Repeats | Stream writing, string strategies, candidate-validated polymorphic variants (`write_variant`), repeating chunk aggregation (`repeat`), one-stop Markdown spec and C header export directly from Writer, debug dumps |
| [`05_builder_and_reader.ipynb`](./05_builder_and_reader.ipynb) | Schema-First Builder & Automated Reader | Schema-first protocol design (no dummy data needed), sections & captions, Mermaid subgraphs, multi-language code export (C, Rust, C++, C#, Go), `builder.write("spec.md")`, automated `builder.read(data)`, and debug inspection (`hexdump`, `dump`) |
| [`06_advanced_v2_features.ipynb`](./06_advanced_v2_features.ipynb) | Advanced Reliability Features | `Magic`, `Constant`, `BinaryEnum`, `CRC32` automated checksums, `VarUInt`/`VarInt` LEB128 variable-length integers, arbitrary `BitWriter`/`BitReader` |
| [`07_v0_3_0_features.ipynb`](./07_v0_3_0_features.ipynb) | Modern v0.3.0+ Features | `Float16` (IEEE 754 half-precision float), `LengthOf`/`CountOf` (auto-calculation & linked reading), `total_size`/`pad_to` (fixed total size & padding), `Range` validation, standalone interactive HTML documentation (`write_html()`) |
| [`main.py`](./main.py) | Central Notebook Runner | Programmatically executes and validates all 7 notebooks in sequence |

## Running the Notebooks

### 1. Interactive Execution (JupyterLab / VSCode)
Open any `.ipynb` file in VSCode, PyCharm, or JupyterLab:

```bash
jupyter lab sample/
```

### 2. Automated CLI Verification
Run all notebooks in sequence with the automated test runner:

```bash
python sample/main.py
```
