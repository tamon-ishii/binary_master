## Context
The library has tripartite symmetry:
- `BinaryWriter` / `Writer`: writes binary data procedurally
- `BinaryReader` / `Reader`: reads binary data procedurally
- `BinaryBuilder` / `Builder`: builds binary protocol schemas, generates specifications (Markdown/Mermaid), exports multi-language code (C/C++/Rust/C#/Go), and reads binary data automatically.

## Decisions
1. In `src/binary_master/manual_builder.py`:
   - Rename class `ManualBuilder` to `BinaryBuilder`.
   - Define aliases `Builder = BinaryBuilder` and `ManualBuilder = BinaryBuilder`.
2. Also create `src/binary_master/builder.py` that imports from `manual_builder` and exports `BinaryBuilder`, `Builder`, `ManualBuilder`, `BuilderReadResult`.
3. In `src/binary_master/__init__.py`:
   - Export `BinaryBuilder`, `Builder`, `ManualBuilder`.
4. Update `sample/05_manual_builder_and_reader.py` and `README.md` to highlight the `Writer` / `Reader` / `Builder` trinity.
