# Proposal: Rename ManualBuilder to BinaryBuilder with Short Alias Builder

## Problem
Initially, `ManualBuilder` was created to construct Markdown specification manuals upfront.
However, with the addition of:
1. Automated schema-driven binary reading (`builder.read(data)`)
2. Multi-language code generation (C, Modern C++, Rust, C#, Go)
the name `ManualBuilder` only reflects a fraction of its capabilities and creates an impression that it is purely for documentation.
Furthermore, the library already has `BinaryWriter` / `Writer` and `BinaryReader` / `Reader`.

## Proposed Solution
Rename the canonical class to `BinaryBuilder`, provide the short alias `Builder` (matching `Writer` and `Reader`), and retain `ManualBuilder` as a backwards-compatible alias.
