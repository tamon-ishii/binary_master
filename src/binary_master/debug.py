"""Specialized binary debugging, annotated hexdumps, tabular traces, and diff utilities."""

from __future__ import annotations

import io
import json
from dataclasses import dataclass
from typing import Any, List, Optional, Sequence, Tuple, Union

# ANSI escape codes for optional terminal coloring
ANSI_RESET = "\033[0m"
ANSI_BOLD = "\033[1m"
ANSI_DIM = "\033[2m"
ANSI_RED = "\033[31m"
ANSI_GREEN = "\033[32m"
ANSI_YELLOW = "\033[33m"
ANSI_BLUE = "\033[34m"
ANSI_MAGENTA = "\033[35m"
ANSI_CYAN = "\033[36m"
ANSI_CURSOR = "\033[1;30;43m"  # Bold black text on yellow background
ANSI_DIFF_LEFT = "\033[31m"    # Red
ANSI_DIFF_RIGHT = "\033[32m"   # Green

_COLOR_CYCLE = [ANSI_CYAN, ANSI_GREEN, ANSI_YELLOW, ANSI_BLUE, ANSI_MAGENTA]


def _format_compact_value(val: Any) -> str:
    """Format a value compactly for terminal inspection without markdown markup."""
    if val is None:
        return "-"
    if isinstance(val, (bytes, bytearray)):
        b = bytes(val)
        if len(b) <= 8:
            return repr(b)
        return f"{b[:6]!r}...({len(b)}B)"
    if isinstance(val, bool):
        return str(val)
    if isinstance(val, int):
        if val >= 0:
            return f"0x{val:X}" if val > 9 else str(val)
        return str(val)
    if isinstance(val, float):
        return f"{val:.4g}"
    s = str(val)
    if len(s) > 12:
        return s[:10] + ".."
    return s


def _extract_target(
    target: Any,
) -> Tuple[bytes, List[Any], Optional[int], Optional[str]]:
    """Extract bytes, layout entries, cursor position, and a description from target.

    Returns:
        (data_bytes, entries_list, cursor_offset_or_None, target_description)
    """
    from binary_master.writer import BinaryWriter
    from binary_master.reader import BinaryReader

    if isinstance(target, BinaryWriter):
        return target.to_bytes(), list(target.entries), target.tell(), "BinaryWriter"
    elif isinstance(target, BinaryReader):
        curr = target.tell()
        # Read full stream without affecting cursor
        stream = target._stream
        pos = stream.tell()
        stream.seek(0)
        data = stream.read()
        stream.seek(pos)
        return data, [], curr, f"BinaryReader (cursor: 0x{curr:04X})"
    elif isinstance(target, (bytes, bytearray, memoryview)):
        return bytes(target), [], None, "bytes"
    elif hasattr(target, "__binary__"):
        w = BinaryWriter()
        w.write_struct(target)
        return w.to_bytes(), list(w.entries), w.tell(), type(target).__name__
    else:
        raise TypeError(
            f"Unsupported target for debug dump: {type(target).__name__}. "
            "Expected BinaryWriter, BinaryReader, bytes, or @binary_struct instance."
        )


def hexdump(
    target: Any,
    *,
    width: int = 16,
    color: bool = False,
    annotate: bool = True,
    show_ascii: bool = True,
    show_header: bool = True,
    cursor: Optional[int] = None,
    max_bytes: Optional[int] = None,
) -> str:
    """Generate an annotated 16-byte hexdump with field correlation and cursor indication.

    Args:
        target: bytes, BinaryWriter, BinaryReader, or @binary_struct instance.
        width: Bytes per line (default: 16).
        color: Whether to use ANSI terminal colors.
        annotate: Whether to print field names and values correlated to byte offsets.
        show_ascii: Whether to include the printable ASCII preview column.
        show_header: Whether to print offset column headers.
        cursor: Explicit cursor offset to highlight (auto-detected for BinaryReader/Writer).
        max_bytes: Optional limit on total bytes displayed.
    """
    data, entries, detected_cursor, desc = _extract_target(target)
    if cursor is None:
        cursor = detected_cursor

    total_len = len(data)
    display_len = total_len if max_bytes is None else min(total_len, max_bytes)

    lines: List[str] = []

    # Map offset to entry
    offset_to_entry: dict[int, Any] = {}
    for entry in entries:
        for b in range(entry.offset, entry.offset + entry.size):
            offset_to_entry[b] = entry

    # Color mapping per entry
    entry_colors: dict[int, str] = {}
    for idx, entry in enumerate(entries):
        entry_colors[id(entry)] = _COLOR_CYCLE[idx % len(_COLOR_CYCLE)]

    # Header
    if show_header:
        hdr_offset = "Offset".ljust(8)
        half = width // 2
        hdr_left = " ".join(f"{i:02X}" for i in range(half))
        hdr_right = " ".join(f"{i:02X}" for i in range(half, width))
        hdr_hex = f"{hdr_left}  {hdr_right}"
        hdr_ascii = "ASCII".center(width)
        header_str = f"{hdr_offset}  {hdr_hex}  |{hdr_ascii}|"
        if annotate and entries:
            header_str += "  Field Annotations"
        sep_len = len(header_str)
        if color:
            header_str = f"{ANSI_BOLD}{header_str}{ANSI_RESET}"
            lines.append(header_str)
            lines.append(f"{ANSI_DIM}{'-' * sep_len}{ANSI_RESET}")
        else:
            lines.append(header_str)
            lines.append("-" * sep_len)

    # Rows
    for row_start in range(0, display_len, width):
        row_end = min(row_start + width, display_len)
        row_bytes = data[row_start:row_end]

        # 1. Offset column
        offset_str = f"{row_start:08X}"
        if color:
            offset_col_str = f"{ANSI_BLUE}{offset_str}{ANSI_RESET}"
        else:
            offset_col_str = offset_str

        # 2. Hex bytes
        hex_tokens: List[str] = []
        for i in range(width):
            byte_idx = row_start + i
            if i < len(row_bytes):
                b = row_bytes[i]
                token = f"{b:02x}"

                if color:
                    is_cursor = (cursor is not None and byte_idx == cursor)
                    entry = offset_to_entry.get(byte_idx)
                    col = entry_colors.get(id(entry), "") if entry else ANSI_CYAN
                    if is_cursor:
                        token = f"{ANSI_CURSOR}{token}{ANSI_RESET}"
                    elif col:
                        token = f"{col}{token}{ANSI_RESET}"
                hex_tokens.append(token)
            else:
                hex_tokens.append("  ")

        left_half = " ".join(hex_tokens[:width // 2])
        right_half = " ".join(hex_tokens[width // 2:])
        hex_str = f"{left_half}  {right_half}"

        # 3. ASCII preview
        ascii_chars: List[str] = []
        for i in range(len(row_bytes)):
            byte_idx = row_start + i
            b = row_bytes[i]
            ch = chr(b) if 32 <= b <= 126 else "."
            if color:
                is_cursor = (cursor is not None and byte_idx == cursor)
                entry = offset_to_entry.get(byte_idx)
                col = entry_colors.get(id(entry), "") if entry else ANSI_GREEN
                if is_cursor:
                    ch = f"{ANSI_CURSOR}{ch}{ANSI_RESET}"
                elif col:
                    ch = f"{col}{ch}{ANSI_RESET}"
            ascii_chars.append(ch)

        # Pad ASCII to width
        ascii_pad = " " * (width - len(row_bytes))
        ascii_str = "".join(ascii_chars) + ascii_pad

        line = f"{offset_col_str}  {hex_str}  |{ascii_str}|"

        # 4. Field annotations
        if annotate:
            # Find entries overlapping this row
            overlapping_entries: List[Any] = []
            seen_entries = set()
            for b in range(row_start, row_end):
                e = offset_to_entry.get(b)
                if e and id(e) not in seen_entries:
                    seen_entries.add(id(e))
                    overlapping_entries.append(e)

            notes: List[str] = []

            # Check if cursor is in this row
            if cursor is not None and row_start <= cursor < row_end:
                notes.append(f"--> CURSOR @ 0x{cursor:04X}")

            for e in overlapping_entries:
                fname = e.name or e.type_name
                ftype = e.type_name
                val_preview = _format_compact_value(e.value)
                note_text = f"{fname}"
                if e.value is not None:
                    note_text += f"={val_preview}"
                if fname != ftype:
                    note_text += f" ({ftype})"
                if color:
                    col = entry_colors.get(id(e), "")
                    note_text = f"{col}{note_text}{ANSI_RESET}"
                notes.append(note_text)

            if notes:
                line += "  " + "; ".join(notes)

        lines.append(line)

    if max_bytes is not None and total_len > max_bytes:
        lines.append(f"... ({total_len - max_bytes} bytes truncated, total {total_len} bytes)")

    # Status footer
    footer_parts = [f"Total: {total_len} bytes (`0x{total_len:04X}`)"]
    if cursor is not None:
        footer_parts.append(f"Cursor: 0x{cursor:04X} ({cursor}/{total_len})")
        if cursor <= total_len:
            footer_parts.append(f"Remaining: {total_len - cursor} bytes")
    lines.append("  [" + " | ".join(footer_parts) + "]")

    return "\n".join(lines)


def dump_table(target: Any, *, color: bool = False) -> str:
    """Generate a clean monospace ASCII table detailing fields, offsets, hex bytes, and values.

    Args:
        target: BinaryWriter, @binary_struct instance, or target with entries.
        color: Whether to use ANSI terminal colors.
    """
    data, entries, cursor, desc = _extract_target(target)
    if not entries:
        return hexdump(target, color=color)

    headers = ["Offset", "Size", "Field Name", "Type", "Endian", "Hex Bytes", "Value / Preview", "Caption"]
    rows: List[List[str]] = []

    for idx, e in enumerate(entries):
        off_str = f"0x{e.offset:04X}"
        size_str = f"{e.size}B"
        fname = e.name or "-"
        ftype = e.type_name
        endian = (e.endian or "-").capitalize() if e.endian else "-"
        raw_b = data[e.offset : e.offset + e.size]
        if len(raw_b) <= 8:
            hex_str = raw_b.hex(" ")
        else:
            hex_str = raw_b[:6].hex(" ") + f" .. ({len(raw_b)}B)"
        val_str = _format_compact_value(e.value)
        caption = e.caption or "-"
        rows.append([off_str, size_str, fname, ftype, endian, hex_str, val_str, caption])

    # Calculate column widths
    col_widths = [len(h) for h in headers]
    for row in rows:
        for i, val in enumerate(row):
            col_widths[i] = max(col_widths[i], len(val))

    # Formatter helpers
    def make_sep(char: str = "-") -> str:
        parts = [char * (w + 2) for w in col_widths]
        return "+" + "+".join(parts) + "+"

    def make_row(cols: List[str]) -> str:
        formatted = []
        for i, c in enumerate(cols):
            # Right-align offset and size, left-align others
            if i in (0, 1):
                formatted.append(f" {c.rjust(col_widths[i])} ")
            else:
                formatted.append(f" {c.ljust(col_widths[i])} ")
        return "|" + "|".join(formatted) + "|"

    out_lines = [
        make_sep("-"),
        make_row(headers),
        make_sep("="),
    ]
    for row in rows:
        out_lines.append(make_row(row))
    out_lines.append(make_sep("-"))

    total_bytes = len(data)
    summary = f"Total: {total_bytes} bytes (0x{total_bytes:04X}) across {len(entries)} fields"
    if cursor is not None:
        summary += f", cursor at 0x{cursor:04X} ({cursor}B)"
    out_lines.append(summary)

    return "\n".join(out_lines)


def dump_dict(target: Any) -> List[dict[str, Any]]:
    """Export serialization trace entries as a structured list of dictionaries."""
    data, entries, cursor, desc = _extract_target(target)
    results: List[dict[str, Any]] = []

    for e in entries:
        raw_b = data[e.offset : e.offset + e.size]
        results.append({
            "offset": e.offset,
            "offset_hex": f"0x{e.offset:04X}",
            "size": e.size,
            "name": e.name,
            "type": e.type_name,
            "endian": e.endian,
            "hex": raw_b.hex(),
            "hex_spaced": raw_b.hex(" "),
            "value": e.value,
            "value_repr": _format_compact_value(e.value),
            "caption": e.caption,
            "description": e.description,
        })
    return results


def dump_json(target: Any, *, indent: int = 2) -> str:
    """Export serialization trace entries as formatted JSON."""
    records = dump_dict(target)
    return json.dumps(records, indent=indent, default=str, ensure_ascii=False)


def debug_dump(
    target: Any,
    format: str = "hexdump",
    **kwargs: Any,
) -> Union[str, List[dict[str, Any]]]:
    """Unified binary debug dumping function.

    Formats:
    - 'hexdump' (default): 16-byte annotated hexdump
    - 'table': monospace aligned field table
    - 'json': JSON string
    - 'dict': list of dictionary records
    """
    fmt = format.lower()
    if fmt == "hexdump":
        return hexdump(target, **kwargs)
    elif fmt == "table":
        table_kwargs = {k: v for k, v in kwargs.items() if k in ("color",)}
        return dump_table(target, **table_kwargs)
    elif fmt == "json":
        json_kwargs = {k: v for k, v in kwargs.items() if k in ("indent",)}
        return dump_json(target, **json_kwargs)
    elif fmt == "dict":
        return dump_dict(target)
    else:
        raise ValueError(
            f"Unsupported format {format!r}. Valid options: 'hexdump', 'table', 'json', 'dict'"
        )


def diff_dump(
    left: Any,
    right: Any,
    *,
    name_left: str = "Expected",
    name_right: str = "Actual",
    color: bool = False,
    context_bytes: int = 4,
) -> str:
    """Compare two binary buffers or writers, reporting byte-level and field-level diffs.

    Args:
        left: First target (bytes, BinaryWriter, etc.)
        right: Second target (bytes, BinaryWriter, etc.)
        name_left: Label for left target
        name_right: Label for right target
        color: Whether to use ANSI terminal colors
        context_bytes: Bytes of matching context before/after diffs
    """
    b1, entries1, _, desc1 = _extract_target(left)
    b2, entries2, _, desc2 = _extract_target(right)

    len1, len2 = len(b1), len(b2)
    min_len = min(len1, len2)

    # Find map of offset to entry name
    def make_entry_map(entries: List[Any]) -> dict[int, str]:
        m = {}
        for e in entries:
            label = f"{e.name or e.type_name} ({e.type_name})"
            for off in range(e.offset, e.offset + e.size):
                m[off] = label
        return m

    map1 = make_entry_map(entries1)
    map2 = make_entry_map(entries2)

    # Identify differing byte positions
    diff_offsets = [i for i in range(min_len) if b1[i] != b2[i]]
    has_length_diff = (len1 != len2)

    if not diff_offsets and not has_length_diff:
        return f"Identical: {name_left} and {name_right} match completely ({len1} bytes)."

    # Group contiguous diffs
    ranges: List[Tuple[int, int]] = []
    if diff_offsets:
        cur_start = diff_offsets[0]
        cur_end = cur_start + 1
        for off in diff_offsets[1:]:
            if off == cur_end:
                cur_end += 1
            else:
                ranges.append((cur_start, cur_end))
                cur_start = off
                cur_end = off + 1
        ranges.append((cur_start, cur_end))

    lines: List[str] = [
        f"--- Binary Diff: {name_left} vs {name_right} ---",
        f"  Size {name_left}:  {len1} bytes (`0x{len1:04X}`)",
        f"  Size {name_right}: {len2} bytes (`0x{len2:04X}`)",
    ]
    if len1 != len2:
        diff_sign = f"+{len2 - len1}" if len2 > len1 else f"-{len1 - len2}"
        lines.append(f"  Length difference: {diff_sign} bytes")
    lines.append(f"  Differing byte count: {len(diff_offsets)} bytes in {len(ranges)} range(s)\n")

    # Header for diff table
    hdr_off = "Offset".ljust(10)
    hdr_l = f"{name_left} Hex".ljust(22)
    hdr_r = f"{name_right} Hex".ljust(22)
    hdr_note = "Field / Context"
    lines.append(f"{hdr_off}  {hdr_l}  {hdr_r}  {hdr_note}")
    lines.append("-" * 75)

    for start, end in ranges:
        l_hex = b1[start:end].hex(" ")
        r_hex = b2[start:end].hex(" ")

        # Annotations
        f_names = set()
        for off in range(start, end):
            if off in map1:
                f_names.add(map1[off])
            if off in map2:
                f_names.add(map2[off])
        note = ", ".join(sorted(f_names)) if f_names else "-"

        if color:
            l_hex = f"{ANSI_DIFF_LEFT}{l_hex}{ANSI_RESET}"
            r_hex = f"{ANSI_DIFF_RIGHT}{r_hex}{ANSI_RESET}"

        lines.append(f"0x{start:04X}..{end:04X}   {l_hex.ljust(22)}  {r_hex.ljust(22)}  {note}")

    # If lengths differ, show extra bytes
    if len1 != len2:
        if len1 < len2:
            extra_hex = b2[len1:len2].hex(" ")
            f_extra = set(map2.get(o, "") for o in range(len1, len2) if o in map2)
            note = f"Extra in {name_right}" + (f" ({', '.join(sorted(f_extra))})" if f_extra else "")
            lines.append(f"0x{len1:04X}..{len2:04X}   {'-'.ljust(22)}  {extra_hex.ljust(22)}  {note}")
        else:
            missing_hex = b1[len2:len1].hex(" ")
            f_miss = set(map1.get(o, "") for o in range(len2, len1) if o in map1)
            note = f"Missing in {name_right}" + (f" ({', '.join(sorted(f_miss))})" if f_miss else "")
            lines.append(f"0x{len2:04X}..{len1:04X}   {missing_hex.ljust(22)}  {'-'.ljust(22)}  {note}")

    return "\n".join(lines)
