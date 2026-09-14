"""Manual and documentation generator with Mermaid diagrams for BinaryWriter."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, List, Optional, Union


@dataclass
class LayoutEntry:
    """Represents a serialized field or binary chunk in the output layout."""

    offset: int
    size: int
    type_name: str
    value: Any = None
    name: str = ""
    endian: Optional[str] = None
    description: str = ""
    struct_name: Optional[str] = None
    target_offset: Optional[int] = None
    subfields: Optional[List[dict]] = None
    caption: Optional[str] = None
    struct_doc: Optional[str] = None
    caption_desc: Optional[str] = None
    subcaption: Optional[str] = None
    subcaption_desc: Optional[str] = None
    caption_variants: Optional[list] = None
    caption_repeat: Optional[Union[int, str, bool]] = None


def create_dummy_instance(struct_cls: type) -> Any:
    """Create a dummy instance of a @binary_struct class for layout inspection."""
    if not hasattr(struct_cls, "__binary__"):
        return None
    from typing import get_origin, get_args, Annotated
    from binary_master.binary_struct import BinaryType, FixedArray, Array, Offset, UInt8, OffsetTable, Bool

    meta: dict[str, Any] = getattr(struct_cls, "__binary__", {})
    fields = meta.get("fields", {})
    if meta.get("bits") is not None:
        dummy_kwargs = {fn: 0 for fn in fields}
        try:
            return struct_cls(**dummy_kwargs)
        except Exception:
            try:
                return struct_cls()
            except Exception:
                return None

    dummy_kwargs = {}
    for fn, ft in fields.items():
        if get_origin(ft) is Annotated:
            ft = get_args(ft)[0]

        is_fixed = (isinstance(ft, tuple) and len(ft) >= 3 and ft[0] is FixedArray) or (get_origin(ft) is FixedArray)
        is_arr = (isinstance(ft, tuple) and len(ft) >= 2 and ft[0] is Array) or (get_origin(ft) is Array)
        is_offset = (isinstance(ft, tuple) and len(ft) >= 1 and ft[0] is Offset) or (get_origin(ft) is Offset)
        is_offset_tbl = (isinstance(ft, tuple) and len(ft) >= 1 and ft[0] is OffsetTable) or (get_origin(ft) is OffsetTable)

        if ft is bool or (isinstance(ft, type) and issubclass(ft, Bool)):
            dummy_kwargs[fn] = False
        elif isinstance(ft, type) and issubclass(ft, BinaryType):
            dummy_kwargs[fn] = 0
        elif is_fixed:
            cnt = ft[2] if isinstance(ft, tuple) else get_args(ft)[1]
            elem_t = ft[1] if isinstance(ft, tuple) else get_args(ft)[0]
            if elem_t is UInt8:
                dummy_kwargs[fn] = b"\x00" * cnt
            elif hasattr(elem_t, "__binary__"):
                dummy_kwargs[fn] = [create_dummy_instance(elem_t)] * cnt
            else:
                dummy_kwargs[fn] = [0] * cnt
        elif is_arr:
            dummy_kwargs[fn] = b""
        elif is_offset:
            dummy_kwargs[fn] = 0
        elif is_offset_tbl:
            dummy_kwargs[fn] = []
        elif hasattr(ft, "__binary__"):
            dummy_kwargs[fn] = create_dummy_instance(ft)
        else:
            dummy_kwargs[fn] = 0

    return struct_cls(**dummy_kwargs)


def inspect_struct_layout(struct_cls: type) -> List[LayoutEntry]:
    """Inspect the memory layout of a @binary_struct class without requiring user data."""
    if not hasattr(struct_cls, "__binary__"):
        return []
    from binary_master.writer import BinaryWriter
    try:
        dummy = create_dummy_instance(struct_cls)
        w = BinaryWriter()
        w.write_struct(dummy)
        return w.entries
    except Exception:
        return []


def format_value_preview(val: Any) -> str:
    """Format a value for display in manual tables and diagrams."""
    if val is None:
        return "-"
    if isinstance(val, (bytes, bytearray)):
        b = bytes(val)
        if len(b) <= 16:
            return f"`{b!r}`"
        return f"`{b[:12]!r}...` ({len(b)} bytes)"
    if isinstance(val, bool):
        return f"`{val}`"
    if isinstance(val, int):
        if val >= 0:
            return f"`{val} (0x{val:X})`"
        return f"`{val}`"
    if isinstance(val, float):
        return f"`{val:.6g}`"
    return f"`{val!r}`"


def _detect_repetition(
    c_entries: List[LayoutEntry],
) -> tuple[bool, Any, List[LayoutEntry], int]:
    """Detect if c_entries represent repeated items.

    Returns:
        (is_repeated, repeat_spec, unit_entries, sample_count)
    """
    if not c_entries:
        return False, None, [], 0

    explicit_repeat = None
    for e in c_entries:
        if e.caption_repeat is not None:
            explicit_repeat = e.caption_repeat
            break

    n = len(c_entries)

    # Search for smallest repeating period L (1 <= L <= n // 2)
    best_l = None
    for l in range(1, n // 2 + 1):
        if n % l == 0:
            matches = True
            for i in range(l, n):
                e_curr = c_entries[i]
                e_base = c_entries[i % l]
                if (
                    e_curr.name != e_base.name
                    or e_curr.type_name != e_base.type_name
                    or e_curr.size != e_base.size
                    or e_curr.struct_name != e_base.struct_name
                ):
                    matches = False
                    break
            if matches:
                best_l = l
                break

    if explicit_repeat is not None:
        if best_l is not None:
            unit_entries = c_entries[:best_l]
            sample_count = n // best_l
        else:
            unit_entries = c_entries
            sample_count = 1
        return True, explicit_repeat, unit_entries, sample_count

    if best_l is not None and (n // best_l) >= 2:
        unit_entries = c_entries[:best_l]
        sample_count = n // best_l
        return True, sample_count, unit_entries, sample_count

    return False, None, c_entries, 1


def _format_repeat_label(rep_spec: Any) -> str:
    """Format the human-readable repetition string for the manual."""
    if rep_spec == -1 or (isinstance(rep_spec, int) and rep_spec < 0):
        return "不定回数 (0回以上 / 可変)"
    if rep_spec is True:
        return "可変 (Variable)"
    if isinstance(rep_spec, str):
        if rep_spec.lower() in ("*", "indefinite", "variable", "不定", "不定回数"):
            return "不定回数 (0回以上 / 可変)"
        return f"`{rep_spec}` 回"
    return f"{rep_spec} 回"


def _format_repeat_tag(rep_spec: Any) -> str:
    """Format the compact repeat tag for Mermaid diagram subgraph labels."""
    if rep_spec == -1 or (isinstance(rep_spec, int) and rep_spec < 0):
        return " 🔁 (不定回数)"
    if rep_spec is True:
        return " 🔁 (可変)"
    if isinstance(rep_spec, str):
        if rep_spec.lower() in ("*", "indefinite", "variable", "不定", "不定回数"):
            return " 🔁 (不定回数)"
        return f" 🔁 x{rep_spec}"
    if rep_spec is not None:
        return f" 🔁 x{rep_spec}"
    return " 🔁"


def generate_mermaid_diagram(
    entries: List[LayoutEntry],
    direction: str = "TD",
) -> str:
    """Generate a Mermaid flowchart visualizing memory layout and structures."""
    lines = [f"```mermaid\nflowchart {direction}"]

    # Consecutive entries with the same group key are grouped together
    groups: List[tuple[Optional[str], List[tuple[int, LayoutEntry]]]] = []
    current_key: Optional[str] = None
    current_items: List[tuple[int, LayoutEntry]] = []

    for idx, entry in enumerate(entries):
        key = entry.caption or entry.struct_name
        if key != current_key:
            if current_items:
                groups.append((current_key, current_items))
            current_key = key
            current_items = [(idx, entry)]
        else:
            current_items.append((idx, entry))
    if current_items:
        groups.append((current_key, current_items))

    node_ids: List[str] = []
    used_subgraph_ids: set[str] = set()

    for group_idx, (group_key, s_entries) in enumerate(groups):
        raw_entries = [e for _, e in s_entries]
        is_rep, rep_spec, u_entries, s_cnt = _detect_repetition(raw_entries)
        unit_len = len(u_entries) if is_rep else len(s_entries)

        if group_key is not None:
            min_off = s_entries[0][1].offset
            max_off = s_entries[-1][1].offset + s_entries[-1][1].size
            total_size = max_off - min_off

            # Generate valid Mermaid subgraph ID
            clean_key = re.sub(r"[^a-zA-Z0-9_]", "_", group_key)
            clean_key = re.sub(r"_+", "_", clean_key).strip("_")
            sg_id = f"SG_{clean_key}" if clean_key else f"SG_grp_{group_idx}"
            if sg_id in used_subgraph_ids:
                sg_id = f"{sg_id}_{group_idx}"
            used_subgraph_ids.add(sg_id)

            if is_rep:
                rep_tag = _format_repeat_tag(rep_spec)
                label = f"{group_key}{rep_tag} (0x{min_off:04X} - 0x{max_off:04X}, {total_size}B)"
            else:
                label = f"{group_key} (0x{min_off:04X} - 0x{max_off:04X}, {total_size}B)"
            lines.append(f'    subgraph {sg_id} ["{label}"]')

            if is_rep:
                base_off = u_entries[0].offset
                for idx, entry in s_entries[:unit_len]:
                    nid = f"N{idx}"
                    node_ids.append(nid)
                    rel = entry.offset - base_off
                    name_label = entry.name or entry.type_name
                    node_label = f"+0x{rel:02X}: {name_label} ({entry.type_name}, {entry.size}B)"
                    lines.append(f'        {nid}["{node_label}"]')
            else:
                for idx, entry in s_entries:
                    nid = f"N{idx}"
                    node_ids.append(nid)
                    name_label = entry.name or entry.type_name
                    node_label = f"0x{entry.offset:04X}: {name_label} ({entry.type_name}, {entry.size}B)"
                    lines.append(f'        {nid}["{node_label}"]')
            lines.append("    end")
        else:
            if is_rep:
                base_off = u_entries[0].offset
                for idx, entry in s_entries[:unit_len]:
                    nid = f"N{idx}"
                    node_ids.append(nid)
                    rel = entry.offset - base_off
                    name_label = entry.name or entry.type_name
                    node_label = f"+0x{rel:02X}: {name_label} ({entry.type_name}, {entry.size}B)"
                    lines.append(f'    {nid}["{node_label}"]')
            else:
                for idx, entry in s_entries:
                    nid = f"N{idx}"
                    node_ids.append(nid)
                    name_label = entry.name or entry.type_name
                    node_label = f"0x{entry.offset:04X}: {name_label} ({entry.type_name}, {entry.size}B)"
                    lines.append(f'    {nid}["{node_label}"]')

    # Sequential connections between adjacent blocks
    for i in range(len(node_ids) - 1):
        lines.append(f"    {node_ids[i]} --> {node_ids[i+1]}")

    # Offset relationships (dotted arrows pointing to referenced target offset)
    for idx, entry in enumerate(entries):
        if entry.target_offset is not None:
            for t_idx, t_entry in enumerate(entries):
                if t_entry.offset == entry.target_offset:
                    if f"N{idx}" in node_ids and f"N{t_idx}" in node_ids:
                        lines.append(
                            f'    N{idx} -.->|"offset: 0x{entry.target_offset:04X}"| N{t_idx}'
                        )
                    break

    lines.append("```")
    return "\n".join(lines)


def generate_bitfield_packet_diagram(
    entry: LayoutEntry,
    bits_per_row: Optional[int] = None,
    bit_width: Optional[int] = None,
    include_values: bool = False,
) -> str:
    """Generate a Mermaid packet-beta diagram for a bitfield entry."""
    subfields = entry.subfields or []
    total_bits = entry.size * 8
    if total_bits <= 0:
        return ""

    if bits_per_row is None:
        if total_bits <= 8:
            bits_per_row = 8
        elif total_bits <= 16:
            bits_per_row = 16
        else:
            bits_per_row = 32

    # Scale bitWidth so narrower rows (8 or 16 bits) expand to a wide, readable layout (~800px)
    if bit_width is None:
        if bits_per_row <= 8:
            bit_width = 96
        elif bits_per_row <= 16:
            bit_width = 50

    lines = ["```mermaid"]
    has_config = (bits_per_row != 32) or (bit_width is not None)
    if has_config:
        lines.append("---")
        lines.append("config:")
        lines.append("  packet:")
        if bits_per_row != 32:
            lines.append(f"    bitsPerRow: {bits_per_row}")
        if bit_width is not None:
            lines.append(f"    bitWidth: {bit_width}")
        lines.append("---")
    lines.append("packet-beta")
    bf_name = entry.name or entry.type_name
    lines.append(f"title {bf_name} ({total_bits} bits)")

    current_bit = 0
    sorted_subs = sorted(subfields, key=lambda s: s.get("bit_start", 0))
    for sub in sorted_subs:
        b_start = sub.get("bit_start", current_bit)
        b_end = sub.get("bit_end", b_start + sub.get("width", 1))
        if b_start > current_bit:
            gap_start = current_bit
            gap_end = b_start - 1
            if gap_start == gap_end:
                lines.append(f'{gap_start}: "(reserved)"')
            else:
                lines.append(f'{gap_start}-{gap_end}: "(reserved)"')
            current_bit = b_start

        s_start = b_start
        s_end = b_end - 1
        s_name = sub.get("name", "field")
        s_val = sub.get("value")
        val_str = f" ({s_val})" if (include_values and s_val is not None) else ""
        label = f"{s_name}{val_str}".replace('"', '\\"')
        if s_start == s_end:
            lines.append(f'{s_start}: "{label}"')
        else:
            lines.append(f'{s_start}-{s_end}: "{label}"')
        current_bit = b_end

    if current_bit < total_bits:
        gap_start = current_bit
        gap_end = total_bits - 1
        if gap_start == gap_end:
            lines.append(f'{gap_start}: "(reserved)"')
        else:
            lines.append(f'{gap_start}-{gap_end}: "(reserved)"')

    lines.append("```")
    return "\n".join(lines)


def generate_packet_diagram(
    entries: List[LayoutEntry],
    title: str = "",
    expand_bitfields: bool = False,
    bits_per_row: int = 32,
    font_size: Optional[str] = None,
    bit_width: Optional[int] = None,
    relative_offset: bool = False,
    include_values: bool = False,
) -> str:
    """Generate a Mermaid packet-beta diagram for the overall binary layout."""
    if not entries:
        return ""

    lines = ["```mermaid"]
    has_packet_config = (bits_per_row != 32) or (bit_width is not None)
    has_config = has_packet_config or (font_size is not None)
    if has_config:
        lines.append("---")
        lines.append("config:")
        if has_packet_config:
            lines.append("  packet:")
            if bits_per_row != 32:
                lines.append(f"    bitsPerRow: {bits_per_row}")
            if bit_width is not None:
                lines.append(f"    bitWidth: {bit_width}")
        if font_size:
            lines.append("  themeVariables:")
            lines.append(f"    fontSize: {font_size}")
        lines.append("---")
    lines.append("packet-beta")
    if title:
        lines.append(f"title {title}")

    base_offset = entries[0].offset if (relative_offset and entries) else 0
    current_bit = 0
    for e in entries:
        entry_start_bit = (e.offset - base_offset) * 8
        entry_end_bit = entry_start_bit + (e.size * 8)

        if entry_start_bit > current_bit:
            gap_start = current_bit
            gap_end = entry_start_bit - 1
            if gap_start == gap_end:
                lines.append(f'{gap_start}: "(padding)"')
            else:
                lines.append(f'{gap_start}-{gap_end}: "(padding)"')
            current_bit = entry_start_bit

        if expand_bitfields and e.subfields:
            sorted_subs = sorted(e.subfields, key=lambda s: s.get("bit_start", 0))
            for sub in sorted_subs:
                b_start = entry_start_bit + sub.get("bit_start", 0)
                b_end = entry_start_bit + sub.get("bit_end", sub.get("bit_start", 0) + sub.get("width", 1))
                if b_start > current_bit:
                    g_start = current_bit
                    g_end = b_start - 1
                    if g_start == g_end:
                        lines.append(f'{g_start}: "(reserved)"')
                    else:
                        lines.append(f'{g_start}-{g_end}: "(reserved)"')
                    current_bit = b_start

                s_start = b_start
                s_end = b_end - 1
                s_name = sub.get("name", "field")
                s_val = sub.get("value")
                val_str = f" ({s_val})" if (include_values and s_val is not None) else ""
                label = f"{s_name}{val_str}".replace('"', '\\"')
                if s_start == s_end:
                    lines.append(f'{s_start}: "{label}"')
                else:
                    lines.append(f'{s_start}-{s_end}: "{label}"')
                current_bit = b_end

            if current_bit < entry_end_bit:
                g_start = current_bit
                g_end = entry_end_bit - 1
                if g_start == g_end:
                    lines.append(f'{g_start}: "(reserved)"')
                else:
                    lines.append(f'{g_start}-{g_end}: "(reserved)"')
                current_bit = entry_end_bit
        else:
            s_start = entry_start_bit
            s_end = entry_end_bit - 1
            name = e.name or e.type_name
            label = f"{name} ({e.type_name})".replace('"', '\\"')
            if s_start == s_end:
                lines.append(f'{s_start}: "{label}"')
            else:
                lines.append(f'{s_start}-{s_end}: "{label}"')
            current_bit = entry_end_bit

    lines.append("```")
    return "\n".join(lines)


def generate_manual(
    entries: List[LayoutEntry],
    default_endian: str = "little",
    title: str = "Binary Specification Manual",
    diagram_direction: str = "TD",
    diagram_type: str = "flowchart",
    bits_per_row: int = 32,
    include_bitfield_diagram: bool = True,
    expand_bitfields: bool = False,
    font_size: Optional[str] = None,
    bit_width: Optional[int] = None,
    section_packet_diagrams: bool = False,
    include_values: bool = False,
) -> str:
    """Generate a comprehensive Markdown manual with Mermaid diagram and tables."""
    if hasattr(entries, "entries"):
        entries = getattr(entries, "entries")
    total_bytes = 0
    if entries:
        total_bytes = max(e.offset + e.size for e in entries)

    sections: List[str] = []
    sections.append(f"# {title}\n")

    # 1. Summary
    sections.append("## Overview\n")
    root_doc = ""
    for e in entries:
        if e.struct_doc:
            root_doc = e.struct_doc
            break
    if root_doc:
        sections.append(f"{root_doc}\n")
    sections.append(f"- **Total Size**: {total_bytes} bytes (`0x{total_bytes:04X}`)")
    sections.append(f"- **Default Endianness**: {default_endian.capitalize()}")
    sections.append(f"- **Total Fields**: {len(entries)}\n")

    # 2. Structure Diagram
    if entries:
        if diagram_type == "flowchart":
            sections.append("## Structure Diagram\n")
            sections.append(generate_mermaid_diagram(entries, direction=diagram_direction))
            sections.append("")
        elif diagram_type == "packet":
            sections.append("## Structure Diagram (Packet)\n")
            sections.append(
                generate_packet_diagram(
                    entries,
                    title=f"{title} Layout",
                    bits_per_row=bits_per_row,
                    expand_bitfields=expand_bitfields,
                    font_size=font_size,
                    bit_width=bit_width,
                    include_values=include_values,
                )
            )
            sections.append("")
        elif diagram_type == "both":
            sections.append("## Structure Diagram (Flowchart)\n")
            sections.append(generate_mermaid_diagram(entries, direction=diagram_direction))
            sections.append("")
            sections.append("## Structure Diagram (Packet)\n")
            sections.append(
                generate_packet_diagram(
                    entries,
                    title=f"{title} Layout",
                    bits_per_row=bits_per_row,
                    expand_bitfields=expand_bitfields,
                    font_size=font_size,
                    bit_width=bit_width,
                    include_values=include_values,
                )
            )
            sections.append("")

    # 3. Layout Table
    sections.append("## Memory Layout Table\n")

    has_captions = any(e.caption for e in entries)

    def _inspect_struct_layout(struct_cls: type) -> List[LayoutEntry]:
        return inspect_struct_layout(struct_cls)


    def _render_variant_table_rows(v_entries: List[LayoutEntry], sec_list: List[str], inc_values: bool) -> None:
        if inc_values:
            sec_list.append(
                "| Relative Offset | Size (B) | Field Name | Type | Endian | Value / Preview | Description |"
            )
            sec_list.append("|---|---|---|---|---|---|---|")
        else:
            sec_list.append(
                "| Relative Offset | Size (B) | Field Name | Type | Endian | Description |"
            )
            sec_list.append("|---|---|---|---|---|---|")

        for entry in v_entries:
            rel_off = f"`+0x{entry.offset:02X}`"
            size_str = str(entry.size)
            name_str = f"`{entry.name}`" if entry.name else "-"
            type_str = f"`{entry.type_name}`"
            endian_str = entry.endian or "-"
            desc_str = entry.description or "-"
            if inc_values:
                val_str = format_value_preview(entry.value)
                sec_list.append(
                    f"| {rel_off} | {size_str} | {name_str} | {type_str} | {endian_str} | {val_str} | {desc_str} |"
                )
            else:
                sec_list.append(
                    f"| {rel_off} | {size_str} | {name_str} | {type_str} | {endian_str} | {desc_str} |"
                )
        sec_list.append("")

    def _render_table_rows(entry_list: List[LayoutEntry]) -> None:
        if include_values:
            sections.append(
                "| Offset (Hex) | Offset (Dec) | Size (B) | Field Name | Type | Endian | Value / Preview | Description |"
            )
            sections.append("|---|---|---|---|---|---|---|---|")
        else:
            sections.append(
                "| Offset (Hex) | Offset (Dec) | Size (B) | Field Name | Type | Endian | Description |"
            )
            sections.append("|---|---|---|---|---|---|---|")

        for entry in entry_list:
            off_hex = f"`0x{entry.offset:04X}`"
            off_dec = str(entry.offset)
            size_str = str(entry.size)
            name_str = f"`{entry.name}`" if entry.name else "-"
            type_str = f"`{entry.type_name}`"
            endian_str = entry.endian or "-"
            desc_str = entry.description or "-"
            if entry.target_offset is not None:
                target_marker = f"`-> 0x{entry.target_offset:04X}`"
                if desc_str != "-":
                    desc_str = f"{desc_str} ({target_marker})"
                else:
                    desc_str = target_marker
            if include_values:
                val_str = format_value_preview(entry.value)
                sections.append(
                    f"| {off_hex} | {off_dec} | {size_str} | {name_str} | {type_str} | {endian_str} | {val_str} | {desc_str} |"
                )
            else:
                sections.append(
                    f"| {off_hex} | {off_dec} | {size_str} | {name_str} | {type_str} | {endian_str} | {desc_str} |"
                )
        sections.append("")

    def _render_relative_table_rows(entry_list: List[LayoutEntry], base_offset: int) -> None:
        if include_values:
            sections.append(
                "| Relative Offset | Size (B) | Field Name | Type | Endian | Value / Preview | Description |"
            )
            sections.append("|---|---|---|---|---|---|---|")
        else:
            sections.append(
                "| Relative Offset | Size (B) | Field Name | Type | Endian | Description |"
            )
            sections.append("|---|---|---|---|---|---|")

        for entry in entry_list:
            rel_bytes = entry.offset - base_offset
            off_hex = f"`+0x{rel_bytes:02X}`" if rel_bytes < 256 else f"`+0x{rel_bytes:04X}`"
            size_str = str(entry.size)
            name_str = f"`{entry.name}`" if entry.name else "-"
            type_str = f"`{entry.type_name}`"
            endian_str = entry.endian or "-"
            desc_str = entry.description or "-"
            if entry.target_offset is not None:
                target_marker = f"`-> 0x{entry.target_offset:04X}`"
                if desc_str != "-":
                    desc_str = f"{desc_str} ({target_marker})"
                else:
                    desc_str = target_marker
            if include_values:
                val_str = format_value_preview(entry.value)
                sections.append(
                    f"| {off_hex} | {size_str} | {name_str} | {type_str} | {endian_str} | {val_str} | {desc_str} |"
                )
            else:
                sections.append(
                    f"| {off_hex} | {size_str} | {name_str} | {type_str} | {endian_str} | {desc_str} |"
                )
        sections.append("")

    if not has_captions:
        is_rep, rep_spec, unit_entries, sample_count = _detect_repetition(entries)
        if is_rep:
            unit_size = sum(e.size for e in unit_entries)
            repeat_label = _format_repeat_label(rep_spec)
            meta_lines = [
                f"- 🔁 **繰り返し**: {repeat_label}",
                f"- **1要素サイズ**: `{unit_size}` bytes (0x{unit_size:X})",
            ]
            if sample_count > 1:
                meta_lines.append(f"- **サンプルデータ**: {sample_count} 件 (合計 `{total_bytes}` bytes)")
            sections.append("\n".join(meta_lines) + "\n")
            if section_packet_diagrams:
                sec_diag = generate_packet_diagram(
                    unit_entries,
                    title=f"{title} (1要素の構造)",
                    bits_per_row=bits_per_row,
                    expand_bitfields=expand_bitfields,
                    font_size=font_size,
                    bit_width=bit_width,
                    relative_offset=True,
                    include_values=False,
                )
                if sec_diag:
                    sections.append(sec_diag)
                    sections.append("")
            _render_relative_table_rows(unit_entries, base_offset=unit_entries[0].offset)
        else:
            if section_packet_diagrams and diagram_type not in ("packet", "both"):
                diag = generate_packet_diagram(
                    entries,
                    title=f"{title} Layout",
                    bits_per_row=bits_per_row,
                    expand_bitfields=expand_bitfields,
                    font_size=font_size,
                    bit_width=bit_width,
                    relative_offset=True,
                    include_values=include_values,
                )
                if diag:
                    sections.append(diag)
                    sections.append("")

            _render_table_rows(entries)
    else:
        # Group by consecutive caption
        caption_groups: List[tuple[Optional[str], List[LayoutEntry]]] = []
        current_cap: Optional[str] = None
        current_cap_entries: List[LayoutEntry] = []

        for entry in entries:
            cap = entry.caption
            if cap != current_cap:
                if current_cap_entries:
                    caption_groups.append((current_cap, current_cap_entries))
                current_cap = cap
                current_cap_entries = [entry]
            else:
                current_cap_entries.append(entry)
        if current_cap_entries:
            caption_groups.append((current_cap, current_cap_entries))

        for cap, c_entries in caption_groups:
            min_off = c_entries[0].offset
            max_off = c_entries[-1].offset + c_entries[-1].size
            total_size = max_off - min_off
            cap_desc = c_entries[0].caption_desc or c_entries[0].struct_doc
            is_rep, rep_spec, unit_entries, sample_count = _detect_repetition(c_entries)

            if is_rep:
                unit_size = sum(e.size for e in unit_entries)
                if cap:
                    sections.append(f"### {cap} (0x{min_off:04X} - 0x{max_off:04X}, {total_size}B)\n")
                else:
                    sections.append(f"### (0x{min_off:04X} - 0x{max_off:04X}, {total_size}B)\n")

                if cap_desc:
                    sections.append(f"{cap_desc}\n")

                repeat_label = _format_repeat_label(rep_spec)
                meta_lines = [
                    f"- 🔁 **繰り返し**: {repeat_label}",
                    f"- **1要素サイズ**: `{unit_size}` bytes (0x{unit_size:X})",
                ]
                if sample_count > 1:
                    meta_lines.append(f"- **サンプルデータ**: {sample_count} 件 (合計 `{total_size}` bytes)")
                else:
                    meta_lines.append(f"- **サンプルデータ**: 1 件 (`{total_size}` bytes)")
                sections.append("\n".join(meta_lines) + "\n")

                if section_packet_diagrams:
                    sec_diag = generate_packet_diagram(
                        unit_entries,
                        title=f"{cap} (1要素の構造)" if cap else "要素構造",
                        bits_per_row=bits_per_row,
                        expand_bitfields=expand_bitfields,
                        font_size=font_size,
                        bit_width=bit_width,
                        relative_offset=True,
                        include_values=False,
                    )
                    if sec_diag:
                        sections.append(sec_diag)
                        sections.append("")

                has_subcaptions = any(e.subcaption for e in unit_entries)
                if has_subcaptions:
                    sub_groups: List[tuple[Optional[str], Optional[str], List[LayoutEntry]]] = []
                    curr_sub: Optional[str] = None
                    curr_sub_desc: Optional[str] = None
                    curr_sub_entries: List[LayoutEntry] = []
                    for entry in unit_entries:
                        if entry.subcaption != curr_sub:
                            if curr_sub_entries:
                                sub_groups.append((curr_sub, curr_sub_desc, curr_sub_entries))
                            curr_sub = entry.subcaption
                            curr_sub_desc = entry.subcaption_desc
                            curr_sub_entries = [entry]
                        else:
                            curr_sub_entries.append(entry)
                    if curr_sub_entries:
                        sub_groups.append((curr_sub, curr_sub_desc, curr_sub_entries))

                    for sub_title, s_desc, s_entries in sub_groups:
                        if sub_title:
                            s_size = sum(e.size for e in s_entries)
                            sections.append(f"#### {sub_title} ({s_size}B)\n")
                            if s_desc:
                                sections.append(f"{s_desc}\n")
                        _render_relative_table_rows(s_entries, base_offset=unit_entries[0].offset)
                else:
                    _render_relative_table_rows(unit_entries, base_offset=unit_entries[0].offset)

            else:
                if cap:
                    sections.append(f"### {cap} (0x{min_off:04X} - 0x{max_off:04X}, {total_size}B)\n")
                else:
                    sections.append(f"### (0x{min_off:04X} - 0x{max_off:04X}, {total_size}B)\n")

                if cap_desc:
                    sections.append(f"{cap_desc}\n")

                if section_packet_diagrams:
                    sec_diag = generate_packet_diagram(
                        c_entries,
                        title=f"{cap} Layout" if cap else "",
                        bits_per_row=bits_per_row,
                        expand_bitfields=expand_bitfields,
                        font_size=font_size,
                        bit_width=bit_width,
                        relative_offset=True,
                        include_values=include_values,
                    )
                    if sec_diag:
                        sections.append(sec_diag)
                        sections.append("")

                # Check if subcaptions exist
                has_subcaptions = any(e.subcaption for e in c_entries)
                if has_subcaptions:
                    sub_groups = []
                    curr_sub = None
                    curr_sub_desc = None
                    curr_sub_entries = []
                    for entry in c_entries:
                        if entry.subcaption != curr_sub:
                            if curr_sub_entries:
                                sub_groups.append((curr_sub, curr_sub_desc, curr_sub_entries))
                            curr_sub = entry.subcaption
                            curr_sub_desc = entry.subcaption_desc
                            curr_sub_entries = [entry]
                        else:
                            curr_sub_entries.append(entry)
                    if curr_sub_entries:
                        sub_groups.append((curr_sub, curr_sub_desc, curr_sub_entries))

                    for sub_title, s_desc, s_entries in sub_groups:
                        if sub_title:
                            s_min = s_entries[0].offset
                            s_max = s_entries[-1].offset + s_entries[-1].size
                            s_size = s_max - s_min
                            sections.append(f"#### {sub_title} (0x{s_min:04X} - 0x{s_max:04X}, {s_size}B)\n")
                            if s_desc:
                                sections.append(f"{s_desc}\n")
                            if section_packet_diagrams:
                                s_diag = generate_packet_diagram(
                                    s_entries,
                                    title=f"{sub_title} Layout",
                                    bits_per_row=bits_per_row,
                                    expand_bitfields=expand_bitfields,
                                    font_size=font_size,
                                    bit_width=bit_width,
                                    relative_offset=True,
                                    include_values=include_values,
                                )
                                if s_diag:
                                    sections.append(s_diag)
                                    sections.append("")
                        _render_table_rows(s_entries)
                else:
                    _render_table_rows(c_entries)

            # Check if variants are registered on this caption
            variants = None
            for e in c_entries:
                if e.caption_variants:
                    variants = e.caption_variants
                    break

            if variants:
                sections.append("この領域には、条件（種別タグ等）に応じて以下のいずれかの構造体が格納されます。\n")
                var_list = []
                if isinstance(variants, dict):
                    for k, v in variants.items():
                        var_list.append((k, v, getattr(v, "__doc__", "") or ""))
                elif isinstance(variants, (list, tuple)):
                    for item in variants:
                        if isinstance(item, tuple) and len(item) == 3:
                            var_list.append(item)
                        elif isinstance(item, tuple) and len(item) == 2:
                            var_list.append((item[0], item[1], getattr(item[1], "__doc__", "") or ""))
                        elif hasattr(item, "__binary__"):
                            var_list.append(("-", item, getattr(item, "__doc__", "") or ""))

                for tag, v_cls, v_desc in var_list:
                    cls_name = getattr(v_cls, "__name__", str(v_cls))
                    tag_str = f"Tag `0x{tag:04X}`" if isinstance(tag, int) else (f"Tag `{tag}`" if tag != "-" else "")
                    header_str = f"#### [Variant] {tag_str + ': ' if tag_str else ''}`{cls_name}`\n"
                    sections.append(header_str)
                    doc_text = v_desc or getattr(v_cls, "__doc__", "") or ""
                    if doc_text:
                        import inspect
                        sections.append(f"{inspect.cleandoc(doc_text)}\n")

                    v_entries = _inspect_struct_layout(v_cls)
                    if v_entries:
                        if section_packet_diagrams:
                            v_diag = generate_packet_diagram(
                                v_entries,
                                title=f"{cls_name} Layout",
                                bits_per_row=bits_per_row,
                                expand_bitfields=expand_bitfields,
                                font_size=font_size,
                                bit_width=bit_width,
                                relative_offset=True,
                                include_values=False,
                            )
                            if v_diag:
                                sections.append(v_diag)
                                sections.append("")
                        _render_variant_table_rows(v_entries, sections, include_values)

    # 4. Bitfield breakdowns if any
    bitfields = []
    seen_bf: set[tuple] = set()
    for e in entries:
        if e.subfields:
            key = (e.struct_name, e.name, e.type_name)
            if key not in seen_bf:
                seen_bf.add(key)
                bitfields.append(e)
    if bitfields:
        sections.append("## Bitfield Details\n")
        for bf in bitfields:
            bf_name = bf.name or bf.type_name
            sections.append(
                f"### `{bf_name}` (Offset: `0x{bf.offset:04X}`, Size: {bf.size}B)\n"
            )
            if bf.struct_doc:
                sections.append(f"{bf.struct_doc}\n")
            if include_bitfield_diagram:
                diag = generate_bitfield_packet_diagram(
                    bf,
                    include_values=include_values,
                )
                if diag:
                    sections.append(diag)
                    sections.append("")
            if include_values:
                sections.append(
                    "| Bit Range | Field Name | Width | Value | Description |"
                )
                sections.append("|---|---|---|---|---|")
            else:
                sections.append(
                    "| Bit Range | Field Name | Width | Description |"
                )
                sections.append("|---|---|---|---|")

            for sub in (bf.subfields or []):
                bit_range = f"`[{sub.get('bit_start', 0)}:{sub.get('bit_end', 0)}]`"
                sub_name = f"`{sub.get('name', '-')}`"
                width_str = f"{sub.get('width', 1)} bit(s)"
                sub_desc = sub.get("description") or "-"
                if include_values:
                    sub_val = format_value_preview(sub.get("value"))
                    sections.append(
                        f"| {bit_range} | {sub_name} | {width_str} | {sub_val} | {sub_desc} |"
                    )
                else:
                    sections.append(
                        f"| {bit_range} | {sub_name} | {width_str} | {sub_desc} |"
                    )
            sections.append("")

    return "\n".join(sections)
