# Proposal: Dedicated Binary Debug Dump & Inspection Tools

## Motivation
With specification manual generation successfully centralized into `Builder`, runtime serialization and deserialization in `BinaryWriter` and `BinaryReader` require specialized, developer-focused debugging tools. When debugging binary serialization bugs, protocol mismatches, or stream offsets, developers need:
1. An annotated hexdump that displays raw bytes side-by-side with the field names, types, and values that generated them.
2. Direct reader stream inspection showing where the cursor is currently positioned, what bytes have been consumed, and what remains.
3. Structured tabular and JSON/dictionary dumps suitable for log emission and automated test assertions.
4. Binary diffing between two buffers or writer layouts with field-level mismatch annotations.

## Scope of Changes
1. **New Module `src/binary_master/debug.py`**:
   - `hexdump(target, ...)`: formats raw bytes, `BinaryWriter`, or `BinaryReader` into a clean, annotated 16-byte hex layout with ASCII decoding, field annotations, and optional ANSI color coding.
   - `debug_dump(target, format="hexdump"|"table"|"json")`: unified dump dispatcher supporting annotated hexdump, ASCII/Unicode layout table, or JSON-serializable list of dicts.
   - `diff_dump(left, right, ...)`: byte-by-byte and field-by-field diff comparison tool.
2. **Methods on `BinaryWriter` and `BinaryReader`**:
   - `writer.hexdump(...)`, `writer.dump(format=...)`, `writer.diff(other)`
   - `reader.hexdump(...)`, `reader.dump()`
3. **Module-level Exports in `binary_master`**:
   - Export `hexdump`, `debug_dump`, `diff_dump`.
4. **Comprehensive Tests and Documentation**.
