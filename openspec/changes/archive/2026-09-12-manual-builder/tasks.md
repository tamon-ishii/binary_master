## 1. ManualBuilder Core Implementation

- [x] 1.1 Implement `ManualBuilder` class and element dataclasses (`DocumentElement`, `StructElement`, `ChoiceElement`, `SectionElement`, `FieldElement`) in `src/binary_master/manual_builder.py` and verify imports
- [x] 1.2 Implement markdown generation (`build()`, `to_markdown()`) and file output (`write(path_or_file)`) with Mermaid flowchart decision nodes, packet diagrams, and offset layout tables
- [x] 1.3 Implement schema-driven automated deserialization (`builder.read(reader_or_bytes)`) supporting sequential structs, condition checks, and tag-based choice dispatch returning `BuilderReadResult`
- [x] 1.4 Export `ManualBuilder` and `BuilderReadResult` in `src/binary_master/__init__.py` and verify package public API

## 2. Unit Testing

- [x] 2.1 Create comprehensive unit test suite `tests/test_manual_builder.py` covering schema construction, flowchart decision nodes, markdown generation, file writing, and automated deserialization, and verify with `pytest`

## 3. Sample Reorganization

- [x] 3.1 Clean up redundant and scattered files in `sample/` and implement systematic numbered examples (`01_basic_struct.py`, `02_bitfields_and_alignment.py`, `03_offsets_and_tables.py`, `04_procedural_writer.py`, `05_manual_builder_and_reader.py`, `main.py`)
- [x] 3.2 Execute all sample scripts and verify that each runs without errors and produces expected outputs

## 4. Documentation and Final Verification

- [x] 4.1 Update `README.md` with `ManualBuilder` documentation, automated reader examples, and updated sample listing
- [x] 4.2 Validate and archive OpenSpec change, build wheel package, and verify all unit tests pass with `pytest`
