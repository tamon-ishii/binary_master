## 1. Core Writer & Manual Enhancements (Subcaptions & Caption Variants)

- [x] 1.1 Add `subcaption` and `subcaption_desc` attributes to `LayoutEntry` in `src/binary_master/manual.py` and `BinaryWriter` in `src/binary_master/writer.py`; implement `writer.subcaption(title, desc=None)`.
- [x] 1.2 Enhance `writer.caption(title, desc=None, variants=None)` to store and associate variant structure specifications with layout entries.
- [x] 1.3 Update `generate_manual` in `src/binary_master/manual.py` to render hierarchical subcaptions and detailed variant subsections (with relative packet diagrams and tables); verify with manual output tests.

## 2. Declarative Tagged Union Support (Variant)

- [x] 2.1 Define `Variant` generic type in `src/binary_master/binary_struct.py` supporting `Variant["tag_field", {tag: Cls}]`.
- [x] 2.2 Update `write_struct` in `src/binary_master/binary_struct.py` to serialize concrete instances for `Variant` fields and forward variant metadata to the manual generator.
- [x] 2.3 Update `read_struct` in `src/binary_master/binary_struct.py` to inspect the deserialized tag field and dispatch deserialization to the matching variant structure class.

## 3. Integration, Verification, and Documentation

- [x] 3.1 Export `Variant` in `src/binary_master/__init__.py`.
- [x] 3.2 Write comprehensive unit tests in `tests/test_variants.py` verifying subcaptions, caption variants manual output, and `Variant` round-trip serialization/deserialization.
- [x] 3.3 Update `README.md` with subcaption and chunk variant documentation and examples.
