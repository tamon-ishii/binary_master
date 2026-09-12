# Design: Dedicated Binary Debug Dump & Inspection Tools

## Architecture

A new dedicated module `src/binary_master/debug.py` will implement:
1. `hexdump(data_or_target, *, width=16, color=False, annotate=True, cursor=None) -> str`
   - Accepts `bytes`, `bytearray`, `BinaryWriter`, or `BinaryReader`.
   - If `BinaryWriter`: extracts `writer.to_bytes()` and `writer.entries`.
   - If `BinaryReader`: extracts buffer, current cursor via `reader.tell()`, and remaining bytes.
   - 16 bytes per line: `OFFSET (8 hex digits) | 16 HEX BYTES (grouped 8+8) | ASCII | [ANNOTATIONS]`
   - Annotations list field names spanning the line, with compact values and types.
   - ANSI color highlighting: alternating field hues, cursor highlight.
2. `dump_table(target, *, color=False) -> str`
   - Formats a clean monospace table:
     `| Offset (hex/dec) | Size | Field Name | Type | Hex Bytes | Value / Preview | Caption |`
3. `dump_json(target, *, indent=2) -> str` and `dump_dict(target) -> list[dict]`
   - Serializes layout entries into structured JSON / dictionary list with hex string previews.
4. `debug_dump(target, format="hexdump"|"table"|"json"|"dict", **kwargs)`
   - Dispatches to corresponding dump generator.
5. `diff_dump(left, right, *, name_left="Expected", name_right="Actual", color=False) -> str`
   - Compares bytes from left and right.
   - Shows byte offsets that differ, side-by-side hex representation, and corresponding field from left/right if writer is passed.
6. Integration into `BinaryWriter` and `BinaryReader`:
   - `BinaryWriter.hexdump(...)` -> calls `debug.hexdump(self, ...)`
   - `BinaryWriter.dump(format="hexdump", ...)` -> calls `debug.debug_dump(self, format=format, ...)`
   - `BinaryWriter.diff(other, ...)` -> calls `debug.diff_dump(self, other, ...)`
   - `BinaryReader.hexdump(...)` -> calls `debug.hexdump(self, ...)`
   - `BinaryReader.dump(format="hexdump", ...)` -> calls `debug.debug_dump(self, format=format, ...)`
