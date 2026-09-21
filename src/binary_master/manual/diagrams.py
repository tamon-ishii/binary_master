"""Mermaid flowchart and packet diagram generators for binary layout."""

from __future__ import annotations

import re
from typing import Dict, List, Literal, Optional

from binary_master.layout import LayoutEntry
from binary_master.manual.helpers import (
    _aggregate_entries_for_diagram,
    _detect_repetition,
    _format_indexed_type_name,
    _format_repeat_tag,
    _is_offset_table_entries,
)
from binary_master.manual.i18n import resolve_language


def generate_mermaid_diagram(
    entries: List[LayoutEntry],
    direction: str = "TD",
    include_section_offsets: bool = False,
    lang: Literal["auto", "en", "ja"] = "auto",
) -> str:
    """Generate a Mermaid flowchart visualizing memory layout and structures."""
    is_ja = resolve_language(lang) == "ja"
    lines = [f"```mermaid\nflowchart {direction}"]

    # Consecutive entries with the same group key are grouped together
    groups: List[tuple[Optional[str], List[tuple[int, LayoutEntry]]]] = []
    current_key: Optional[str] = None
    current_items: List[tuple[int, LayoutEntry]] = []

    for idx, entry in enumerate(entries):
        key = entry.caption or entry.struct_name
        if not key:
            if entry.type_name and entry.type_name.startswith("Offset["):
                m = re.match(r"^(.+)\[\d+\]$", entry.name) if entry.name else None
                base_name = m.group(1) if m else ""
                if not base_name or base_name in ("offsets", "offset_table"):
                    key = "オフセットテーブル" if is_ja else "Offset Table"
                else:
                    key = base_name

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
    rep_node_map: Dict[int, str] = {}

    for group_idx, (group_key, s_entries) in enumerate(groups):
        raw_entries = [e for _, e in s_entries]
        is_rep, rep_spec, u_entries, s_cnt = _detect_repetition(raw_entries)
        unit_len = len(u_entries) if is_rep else len(s_entries)

        def _render_flowchart_nodes(indent: str) -> None:
            if is_rep:
                base_off = u_entries[0].offset
                for (idx, _), entry in zip(s_entries[:unit_len], u_entries):
                    nid = f"N{idx}"
                    node_ids.append(nid)
                    rel = entry.offset - base_off
                    name_label = entry.name or entry.type_name
                    node_label = f"+0x{rel:02X}: {name_label} ({entry.type_name}, {entry.size}B)"
                    lines.append(f'{indent}{nid}["{node_label}"]')
                # Map all entries in this repeated group to the representative nodes
                for k, (orig_i, _) in enumerate(s_entries):
                    rep_i = s_entries[k % unit_len][0]
                    rep_node_map[orig_i] = f"N{rep_i}"
            else:
                i = 0
                n = len(s_entries)
                while i < n:
                    orig_idx, curr = s_entries[i]
                    m = re.match(r"^(.+)\[(\d+)\]$", curr.name) if curr.name else None
                    if not m:
                        nid = f"N{orig_idx}"
                        node_ids.append(nid)
                        name_label = curr.name or curr.type_name
                        node_label = f"0x{curr.offset:04X}: {name_label} ({curr.type_name}, {curr.size}B)"
                        lines.append(f'{indent}{nid}["{node_label}"]')
                        i += 1
                        continue

                    base_name = m.group(1)
                    idx_val = int(m.group(2))
                    j = i + 1
                    expected_idx = idx_val + 1
                    while j < n:
                        _, nxt = s_entries[j]
                        m_nxt = re.match(r"^(.+)\[(\d+)\]$", nxt.name) if nxt.name else None
                        if not m_nxt or m_nxt.group(1) != base_name or int(m_nxt.group(2)) != expected_idx:
                            break
                        if nxt.type_name != curr.type_name or nxt.size != curr.size:
                            break
                        expected_idx += 1
                        j += 1

                    count = j - i
                    if count >= 3:
                        nid = f"N{orig_idx}"
                        node_ids.append(nid)
                        for k in range(i, j):
                            rep_node_map[s_entries[k][0]] = nid
                        total_size = sum(s_entries[k][1].size for k in range(i, j))
                        type_label = _format_indexed_type_name(curr.type_name, count)
                        node_label = f"0x{curr.offset:04X}: {base_name} ({type_label}, {total_size}B)"
                        lines.append(f'{indent}{nid}["{node_label}"]')
                        i = j
                    else:
                        for k in range(i, j):
                            idx_k, e_k = s_entries[k]
                            nid = f"N{idx_k}"
                            node_ids.append(nid)
                            name_label = e_k.name or e_k.type_name
                            node_label = f"0x{e_k.offset:04X}: {name_label} ({e_k.type_name}, {e_k.size}B)"
                            lines.append(f'{indent}{nid}["{node_label}"]')
                        i = j

        if group_key is not None:
            min_off = s_entries[0][1].offset
            max_off = s_entries[-1][1].offset + s_entries[-1][1].size
            total_size = max_off - min_off

            display_key = group_key
            if not display_key:
                if _is_offset_table_entries(raw_entries):
                    display_key = "オフセットテーブル" if is_ja else "Offset Table"
                else:
                    display_key = "データ領域" if is_ja else "Data Section"

            # Generate valid Mermaid subgraph ID
            clean_key = re.sub(r"[^a-zA-Z0-9_]", "_", display_key)
            clean_key = re.sub(r"_+", "_", clean_key).strip("_")
            sg_id = f"SG_{clean_key}" if clean_key else f"SG_grp_{group_idx}"
            if sg_id in used_subgraph_ids:
                sg_id = f"{sg_id}_{group_idx}"
            used_subgraph_ids.add(sg_id)

            if is_rep:
                rep_tag = _format_repeat_tag(rep_spec)
                if include_section_offsets:
                    label = f"{display_key}{rep_tag} (0x{min_off:04X} - 0x{max_off:04X}, {total_size}B)"
                else:
                    label = f"{display_key}{rep_tag}"
            else:
                if include_section_offsets:
                    label = f"{display_key} (0x{min_off:04X} - 0x{max_off:04X}, {total_size}B)"
                else:
                    label = f"{display_key}"
            lines.append(f'    subgraph {sg_id} ["{label}"]')
            _render_flowchart_nodes(indent="        ")
            lines.append("    end")
        else:
            _render_flowchart_nodes(indent="    ")

    # Offset relationships (dotted arrows pointing to referenced target offset)
    seen_links: set[tuple[str, str]] = set()
    offset_lines: List[str] = []
    for idx, entry in enumerate(entries):
        if entry.target_offset is not None:
            for t_idx, t_entry in enumerate(entries):
                if t_entry.offset == entry.target_offset:
                    source_nid = rep_node_map.get(idx, f"N{idx}")
                    target_nid = rep_node_map.get(t_idx, f"N{t_idx}")
                    if source_nid in node_ids and target_nid in node_ids and source_nid != target_nid:
                        link_key = (source_nid, target_nid)
                        if link_key not in seen_links:
                            seen_links.add(link_key)
                            offset_lines.append(
                                f'    {source_nid} -.->|"offset: 0x{entry.target_offset:04X}"| {target_nid}'
                            )
                    break

    # Sequential connections between adjacent blocks (suppress if an offset dotted link connects them)
    for i in range(len(node_ids) - 1):
        pair = (node_ids[i], node_ids[i+1])
        if pair not in seen_links:
            lines.append(f"    {node_ids[i]} --> {node_ids[i+1]}")

    lines.extend(offset_lines)

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
    large_data_threshold: int = 64,
    compact_tables: bool = False,
    compact_large_entries: bool = False,
    max_field_bits: Optional[int] = None,
    lang: Literal["auto", "en", "ja"] = "auto",
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
    last_physical_end = base_offset
    is_ja = resolve_language(lang) == "ja"

    diagram_entries = _aggregate_entries_for_diagram(entries, relative_offset=relative_offset)
    for e in diagram_entries:
        if e.offset > last_physical_end:
            gap_bytes = e.offset - last_physical_end
            gap_bits = gap_bytes * 8
            gap_start = current_bit
            gap_end = current_bit + gap_bits - 1
            if large_data_threshold > 0 and gap_bytes >= large_data_threshold:
                lines.append(f'{gap_start}-{gap_end}: "(padding, {gap_bytes}B)"')
            elif gap_start == gap_end:
                lines.append(f'{gap_start}: "(padding)"')
            else:
                lines.append(f'{gap_start}-{gap_end}: "(padding)"')
            current_bit = gap_end + 1

        last_physical_end = e.offset + e.size
        raw_bits = e.size * 8

        is_compact = False
        if compact_tables and getattr(e, "_is_indexed_summary", False):
            target_max = max_field_bits if max_field_bits is not None else bits_per_row
            if raw_bits > target_max:
                is_compact = True
        elif compact_large_entries and max_field_bits is not None and raw_bits > max_field_bits:
            is_compact = True
        elif compact_large_entries and large_data_threshold > 0 and e.size >= large_data_threshold:
            if raw_bits > bits_per_row * 2:
                is_compact = True

        if is_compact:
            cap_bits = max_field_bits if max_field_bits is not None else bits_per_row
            rem = (bits_per_row - (current_bit % bits_per_row)) % bits_per_row
            span_bits = (rem + cap_bits) if rem > 0 else cap_bits
        else:
            span_bits = raw_bits

        if expand_bitfields and e.subfields:
            entry_start_bit = current_bit
            entry_end_bit = current_bit + span_bits
            sorted_subs = sorted(e.subfields, key=lambda s: s.get("bit_start", 0))
            sub_current_bit = entry_start_bit
            for sub in sorted_subs:
                b_start = entry_start_bit + sub.get("bit_start", 0)
                b_end = entry_start_bit + sub.get("bit_end", sub.get("bit_start", 0) + sub.get("width", 1))
                if b_start > sub_current_bit:
                    g_start = sub_current_bit
                    g_end = b_start - 1
                    if g_start == g_end:
                        lines.append(f'{g_start}: "(reserved)"')
                    else:
                        lines.append(f'{g_start}-{g_end}: "(reserved)"')
                    sub_current_bit = b_start

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
                sub_current_bit = b_end

            if sub_current_bit < entry_end_bit:
                g_start = sub_current_bit
                g_end = entry_end_bit - 1
                if g_start == g_end:
                    lines.append(f'{g_start}: "(reserved)"')
                else:
                    lines.append(f'{g_start}-{g_end}: "(reserved)"')
            current_bit = entry_end_bit
        else:
            s_start = current_bit
            s_end = current_bit + span_bits - 1
            name = e.name or e.type_name
            if getattr(e, "_is_rep_summary", False):
                label = f"{name} ({e.size}B)"
            elif getattr(e, "_is_indexed_summary", False):
                label = f"{name} ({e.type_name}, {e.size}B)"
            elif large_data_threshold > 0 and e.size >= large_data_threshold:
                # Large data block auto-summarization
                is_raw_bytes = not e.type_name or e.type_name == "Bytes" or e.type_name.startswith("Bytes[")
                if is_raw_bytes:
                    if name and name != e.type_name:
                        label = f"{name} ({e.size}B)"
                    else:
                        label = f"Bytes ({e.size}B)"
                else:
                    if name and name != e.type_name:
                        label = f"{name} ({e.type_name}, {e.size}B)"
                    else:
                        label = f"{e.type_name} ({e.size}B)"
            else:
                label = f"{name} ({e.type_name})"

            if is_compact:
                compact_tag = " [縮約]" if is_ja else " [compact]"
                label = f"{label}{compact_tag}"

            label = label.replace('"', '\\"')
            if s_start == s_end:
                lines.append(f'{s_start}: "{label}"')
            else:
                lines.append(f'{s_start}-{s_end}: "{label}"')
            current_bit = s_end + 1

    lines.append("```")
    return "\n".join(lines)


