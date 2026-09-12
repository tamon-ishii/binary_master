# Proposal: Remove write_manual and Unify Specification Generation in Builder

## Why
Documentation generated from `BinaryWriter` (`writer.write_manual()`) only records the single concrete path executed during serialization. It cannot document unexecuted conditional branches (`if`), alternative choice variants (`Variant`), or narrative documentation chapters. Consequently, documentation produced by `Writer` is inherently incomplete as a protocol specification.

With `Builder` (`BinaryBuilder`) now serving as the single source of truth for full protocol schemas—including documents, conditional branches, choice variants, and multi-language exports—having `writer.write_manual()` creates confusion and misleading, incomplete manuals.

## What Changes
1. Remove `BinaryWriter.write_manual()` from `src/binary_master/writer.py`.
2. Remove standalone `write_manual()` function from `src/binary_master/manual.py` and `src/binary_master/__init__.py`.
3. Remove `write_manual()` alias from `BinaryBuilder` in `src/binary_master/builder.py`, standardizing on `builder.write(path)` and `builder.to_markdown()`.
4. Update samples (`sample/04_procedural_writer.py`, `sample/README.md`), documentation (`README.md`), and test suite to use `Builder`.
