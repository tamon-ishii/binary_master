## Context
`Writer` serializes concrete binary streams. Generating documentation from runtime runs produces incomplete manuals whenever branching occurs. `Builder` is the schema-level builder that understands the complete protocol space.

## Decisions
1. In `src/binary_master/writer.py`: Remove `BinaryWriter.write_manual()`. Keep `_entries` if needed for `write_offset_table` backpatching.
2. In `src/binary_master/manual.py`: Remove `write_manual()` function. Retain low-level diagram generators (`generate_packet_diagram`, `generate_bitfield_packet_diagram`, `inspect_struct_layout`) which are used by `Builder`.
3. In `src/binary_master/builder.py`: Remove `write_manual()` alias; retain `write(path_or_file)` and `to_markdown()`.
4. In `src/binary_master/__init__.py`: Remove `write_manual` from imports and `__all__`.
5. Update tests and samples that relied on `writer.write_manual()`.
