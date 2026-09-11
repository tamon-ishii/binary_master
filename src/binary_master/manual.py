"""Manual and documentation generator with Mermaid diagrams for BinaryWriter."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, IO, List, Optional, Union


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

            label = f"{group_key} (0x{min_off:04X} - 0x{max_off:04X}, {total_size}B)"
            lines.append(f'    subgraph {sg_id} ["{label}"]')
            for idx, entry in s_entries:
                nid = f"N{idx}"
                node_ids.append(nid)
                name_label = entry.name or entry.type_name
                node_label = f"0x{entry.offset:04X}: {name_label} ({entry.type_name}, {entry.size}B)"
                lines.append(f'        {nid}["{node_label}"]')
            lines.append("    end")
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
    total_bytes = 0
    if entries:
        total_bytes = max(e.offset + e.size for e in entries)

    sections: List[str] = []
    sections.append(f"# {title}\n")

    # 1. Summary
    sections.append("## Overview\n")
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

    if not has_captions:
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
            if cap:
                sections.append(f"### {cap} (0x{min_off:04X} - 0x{max_off:04X}, {total_size}B)\n")
            else:
                sections.append(f"### (0x{min_off:04X} - 0x{max_off:04X}, {total_size}B)\n")

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

            _render_table_rows(c_entries)

    # 4. Bitfield breakdowns if any
    bitfields = [e for e in entries if e.subfields]
    if bitfields:
        sections.append("## Bitfield Details\n")
        for bf in bitfields:
            bf_name = bf.name or bf.type_name
            sections.append(
                f"### `{bf_name}` (Offset: `0x{bf.offset:04X}`, Size: {bf.size}B)\n"
            )
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

            for sub in bf.subfields:
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


def write_manual(
    writer_or_struct: Any,
    path_or_file: Optional[Union[str, Path, IO[str]]] = None,
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
    """Convenience helper to write a manual from a BinaryWriter or @binary_struct instance."""
    from binary_master.writer import BinaryWriter

    if isinstance(writer_or_struct, BinaryWriter):
        return writer_or_struct.write_manual(
            path_or_file=path_or_file,
            title=title,
            diagram_direction=diagram_direction,
            diagram_type=diagram_type,
            bits_per_row=bits_per_row,
            include_bitfield_diagram=include_bitfield_diagram,
            expand_bitfields=expand_bitfields,
            font_size=font_size,
            bit_width=bit_width,
            section_packet_diagrams=section_packet_diagrams,
            include_values=include_values,
        )

    if hasattr(writer_or_struct, "__binary__"):
        writer = BinaryWriter()
        writer.write_struct(writer_or_struct)
        return writer.write_manual(
            path_or_file=path_or_file,
            title=title,
            diagram_direction=diagram_direction,
            diagram_type=diagram_type,
            bits_per_row=bits_per_row,
            include_bitfield_diagram=include_bitfield_diagram,
            expand_bitfields=expand_bitfields,
            font_size=font_size,
            bit_width=bit_width,
            section_packet_diagrams=section_packet_diagrams,
            include_values=include_values,
        )

    raise TypeError(
        f"Expected BinaryWriter or @binary_struct instance, got {type(writer_or_struct).__name__}"
    )
