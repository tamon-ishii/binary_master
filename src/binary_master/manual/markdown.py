"""Markdown specification manual generator with embedded Mermaid diagrams."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Literal, Optional

from binary_master.layout import LayoutEntry
from binary_master.manual.diagrams import (
    generate_bitfield_packet_diagram,
    generate_mermaid_diagram,
    generate_packet_diagram,
)
from binary_master.manual.helpers import (
    _compress_consecutive_indexed_entries,
    _detect_repetition,
    _format_repeat_label,
    _is_offset_table_entries,
    format_value_preview,
    inspect_struct_layout,
)
from binary_master.manual.i18n import resolve_language


def generate_manual(
    entries: Any,
    default_endian: str = "little",
    title: str = "Binary Specification Manual",
    diagram_direction: Literal["TD", "LR"] = "TD",
    diagram_type: Literal["both", "flowchart", "packet", "none"] = "both",
    bits_per_row: int = 32,
    include_bitfield_diagram: bool = True,
    expand_bitfields: bool = False,
    font_size: Optional[str] = None,
    bit_width: Optional[int] = None,
    section_packet_diagrams: bool = False,
    include_values: bool = False,
    lang: Literal["auto", "en", "ja"] = "auto",
    include_section_offsets: bool = False,
    large_data_threshold: int = 64,
    full_packet_diagram: bool = False,
    compact_tables: bool = True,
    compact_large_entries: bool = False,
    max_packet_field_bits: Optional[int] = None,
    **kwargs: Any,
) -> str:
    """Generate a comprehensive Markdown specification manual with Mermaid diagrams.

    Args:
        entries: A @binary_struct class/instance, BinaryWriter, Builder, or list of LayoutEntry.
        default_endian: Default endianness ("little" or "big").
        title: Document title.
        diagram_direction: Mermaid flowchart direction ("TD" or "LR").
        diagram_type: Mermaid diagram type: "both", "flowchart", "packet", or "none".
        bits_per_row: Packet diagram width in bits.
        include_bitfield_diagram: Whether to render bitfield diagrams.
        expand_bitfields: Whether to expand bitfields in packet diagrams.
        font_size: Optional font size for diagrams.
        bit_width: Optional bit width for packet diagrams.
        section_packet_diagrams: Whether to include packet diagrams per struct.
        include_values: Whether to include runtime values in tables.
        lang: Output language ("auto", "en", or "ja"). Default is "auto" (detected from system locale).
        include_section_offsets: Whether to append (0xXXXX - 0xYYYY, ZZB) offset ranges to section titles. Default is False.
        large_data_threshold: Threshold in bytes to summarize large data blocks in packet diagrams (default 64).
        full_packet_diagram: Whether to include the full packet diagram at the top when diagram_type is 'both' even if sections/structs exist. Default is False.

    Returns:
        Complete Markdown document string.
    """
    if hasattr(entries, "__binary__"):
        if isinstance(entries, type):
            entries = inspect_struct_layout(entries)
        else:
            from binary_master.writer import BinaryWriter
            w = BinaryWriter()
            w.write_struct(entries)
            entries = w.entries
    elif hasattr(entries, "entries"):
        entries = getattr(entries, "entries")
    total_bytes = 0
    if entries:
        total_bytes = max(e.offset + e.size for e in entries)

    is_ja = resolve_language(lang) == "ja"
    if is_ja and title == "Binary Specification Manual":
        resolved_title = "バイナリ仕様書"
    else:
        resolved_title = title


    sections: List[str] = []
    sections.append(f"# {resolved_title}\n")

    distinct_struct_names: List[str] = []
    for e in entries:
        if e.struct_name and (not distinct_struct_names or distinct_struct_names[-1] != e.struct_name):
            distinct_struct_names.append(e.struct_name)

    # Unique defined field keys
    unique_field_keys = set()
    for e in entries:
        clean_name = re.sub(r"\[\d+\]$", "", e.name or "")
        unique_field_keys.add((e.struct_name or e.caption or "", clean_name))
    defined_field_count = len(unique_field_keys)

    # Build offset to target label lookup for pointers
    offset_to_target_label: Dict[int, str] = {}
    caption_groups_for_lookup: List[tuple[Optional[str], List[LayoutEntry]]] = []
    _curr_cap: Optional[str] = None
    _curr_entries: List[LayoutEntry] = []
    for e in entries:
        c = e.caption or e.struct_name
        if c != _curr_cap:
            if _curr_entries:
                caption_groups_for_lookup.append((_curr_cap, _curr_entries))
            _curr_cap = c
            _curr_entries = [e]
        else:
            _curr_entries.append(e)
    if _curr_entries:
        caption_groups_for_lookup.append((_curr_cap, _curr_entries))

    for cap, c_entries in caption_groups_for_lookup:
        display_name = cap or (c_entries[0].struct_name if c_entries else "") or "Section"
        is_rep_lookup, rep_spec_lookup, u_entries_lookup, s_cnt_lookup = _detect_repetition(c_entries)
        if is_rep_lookup and u_entries_lookup:
            u_len = len(u_entries_lookup)
            for k in range(0, len(c_entries), u_len):
                elem_idx = k // u_len
                first_off = c_entries[k].offset
                offset_to_target_label[first_off] = f"{display_name}[{elem_idx}]"
        else:
            if c_entries:
                first_off = c_entries[0].offset
                offset_to_target_label[first_off] = display_name

    has_captions = any(e.caption for e in entries)
    has_multiple_structs = len(distinct_struct_names) > 1
    has_sections = has_captions or has_multiple_structs
    want_section_packets = section_packet_diagrams or (has_sections and diagram_type in ("packet", "both"))

    # 1. Summary
    root_doc = ""
    for e in entries:
        if e.struct_doc:
            root_doc = e.struct_doc
            break

    if is_ja:
        sections.append("## 概要\n")
        if root_doc:
            sections.append(f"{root_doc}\n")
        endian_disp = "リトルエンディアン (Little)" if default_endian.lower() == "little" else "ビッグエンディアン (Big)"
        sections.append(f"- **合計サイズ**: {total_bytes} バイト (`0x{total_bytes:04X}`)")
        sections.append(f"- **デフォルトエンディアン**: {endian_disp}")
        if len(entries) != defined_field_count and defined_field_count > 0:
            sections.append(f"- **合計フィールド数**: {len(entries)} (定義数: {defined_field_count})")
        else:
            sections.append(f"- **合計フィールド数**: {len(entries)}")
        if len(distinct_struct_names) > 1:
            sections.append(f"- **構造体数**: {len(distinct_struct_names)}")
        sections.append("")
    else:
        sections.append("## Overview\n")
        if root_doc:
            sections.append(f"{root_doc}\n")
        sections.append(f"- **Total Size**: {total_bytes} bytes (`0x{total_bytes:04X}`)")
        sections.append(f"- **Default Endianness**: {default_endian.capitalize()}")
        if len(entries) != defined_field_count and defined_field_count > 0:
            sections.append(f"- **Total Fields**: {len(entries)} (Defined: {defined_field_count})")
        else:
            sections.append(f"- **Total Fields**: {len(entries)}")
        if len(distinct_struct_names) > 1:
            sections.append(f"- **Structure Count**: {len(distinct_struct_names)}")
        sections.append("")

    # 2. Structure Diagram
    if entries:
        diag_title = f"{resolved_title} レイアウト" if is_ja else f"{resolved_title} Layout"
        if diagram_type == "flowchart":
            sections.append("## 構造図\n" if is_ja else "## Structure Diagram\n")
            sections.append(generate_mermaid_diagram(entries, direction=diagram_direction, include_section_offsets=include_section_offsets, lang=lang))
            sections.append("")
        elif diagram_type == "packet":
            sections.append("## 構造図 (パケット図)\n" if is_ja else "## Structure Diagram (Packet)\n")
            sections.append(
                generate_packet_diagram(
                    entries,
                    title=diag_title,
                    bits_per_row=bits_per_row,
                    expand_bitfields=expand_bitfields,
                    font_size=font_size,
                    bit_width=bit_width,
                    include_values=include_values,
                    large_data_threshold=large_data_threshold,
                    compact_tables=compact_tables,
                    compact_large_entries=compact_large_entries,
                    max_field_bits=max_packet_field_bits,
                    lang=lang,
                )
            )
            sections.append("")
        elif diagram_type == "both":
            if has_sections and not full_packet_diagram:
                sections.append("## 構造図\n" if is_ja else "## Structure Diagram\n")
                sections.append(generate_mermaid_diagram(entries, direction=diagram_direction, include_section_offsets=include_section_offsets, lang=lang))
                sections.append("")
            else:
                sections.append("## 構造図 (フローチャート)\n" if is_ja else "## Structure Diagram (Flowchart)\n")
                sections.append(generate_mermaid_diagram(entries, direction=diagram_direction, include_section_offsets=include_section_offsets, lang=lang))
                sections.append("")
                sections.append("## 構造図 (パケット図)\n" if is_ja else "## Structure Diagram (Packet)\n")
                sections.append(
                    generate_packet_diagram(
                        entries,
                        title=diag_title,
                        bits_per_row=bits_per_row,
                        expand_bitfields=expand_bitfields,
                        font_size=font_size,
                        bit_width=bit_width,
                        include_values=include_values,
                        large_data_threshold=large_data_threshold,
                        compact_tables=compact_tables,
                        compact_large_entries=compact_large_entries,
                        max_field_bits=max_packet_field_bits,
                        lang=lang,
                    )
                )
                sections.append("")

    # 3. Layout Table
    sections.append("## メモリレイアウト表\n" if is_ja else "## Memory Layout Table\n")

    def _inspect_struct_layout(struct_cls: type) -> List[LayoutEntry]:
        return inspect_struct_layout(struct_cls)


    def _render_variant_table_rows(v_entries: List[LayoutEntry], sec_list: List[str], inc_values: bool) -> None:
        if is_ja:
            if inc_values:
                sec_list.append(
                    "| 相対オフセット | サイズ (B) | フィールド名 | 型 | エンディアン | 値 / プレビュー | 説明 |"
                )
                sec_list.append("|---|---|---|---|---|---|---|")
            else:
                sec_list.append(
                    "| 相対オフセット | サイズ (B) | フィールド名 | 型 | エンディアン | 説明 |"
                )
                sec_list.append("|---|---|---|---|---|---|")
        else:
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

        compressed = _compress_consecutive_indexed_entries(v_entries)
        for is_omitted, item in compressed:
            if is_omitted:
                if inc_values:
                    sec_list.append("| ... | ... | ... | ... | ... | ... | ... |")
                else:
                    sec_list.append("| ... | ... | ... | ... | ... | ... |")
                continue
            entry = item
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
        if is_ja:
            if include_values:
                sections.append(
                    "| オフセット (16進) | オフセット (10進) | サイズ (B) | フィールド名 | 型 | エンディアン | 値 / プレビュー | 説明 |"
                )
                sections.append("|---|---|---|---|---|---|---|---|")
            else:
                sections.append(
                    "| オフセット (16進) | オフセット (10進) | サイズ (B) | フィールド名 | 型 | エンディアン | 説明 |"
                )
                sections.append("|---|---|---|---|---|---|---|")
        else:
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

        compressed = _compress_consecutive_indexed_entries(entry_list)
        for is_omitted, item in compressed:
            if is_omitted:
                if include_values:
                    sections.append("| ... | ... | ... | ... | ... | ... | ... | ... |")
                else:
                    sections.append("| ... | ... | ... | ... | ... | ... | ... |")
                continue
            entry = item
            off_hex = f"`0x{entry.offset:04X}`"
            off_dec = str(entry.offset)
            size_str = str(entry.size)
            name_str = f"`{entry.name}`" if entry.name else "-"
            type_str = f"`{entry.type_name}`"
            endian_str = entry.endian or "-"
            desc_str = entry.description or "-"
            if entry.target_offset is not None:
                ref_label = offset_to_target_label.get(entry.target_offset)
                if ref_label:
                    target_marker = f"`-> 0x{entry.target_offset:04X}` ({ref_label})"
                else:
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
        if is_ja:
            if include_values:
                sections.append(
                    "| 相対オフセット | サイズ (B) | フィールド名 | 型 | エンディアン | 値 / プレビュー | 説明 |"
                )
                sections.append("|---|---|---|---|---|---|---|")
            else:
                sections.append(
                    "| 相対オフセット | サイズ (B) | フィールド名 | 型 | エンディアン | 説明 |"
                )
                sections.append("|---|---|---|---|---|---|")
        else:
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

        compressed = _compress_consecutive_indexed_entries(entry_list)
        for is_omitted, item in compressed:
            if is_omitted:
                if include_values:
                    sections.append("| ... | ... | ... | ... | ... | ... | ... |")
                else:
                    sections.append("| ... | ... | ... | ... | ... | ... |")
                continue
            entry = item
            rel_bytes = entry.offset - base_offset
            off_hex = f"`+0x{rel_bytes:02X}`" if rel_bytes < 256 else f"`+0x{rel_bytes:04X}`"
            size_str = str(entry.size)
            name_str = f"`{entry.name}`" if entry.name else "-"
            type_str = f"`{entry.type_name}`"
            endian_str = entry.endian or "-"
            desc_str = entry.description or "-"
            if entry.target_offset is not None:
                ref_label = offset_to_target_label.get(entry.target_offset)
                if ref_label:
                    target_marker = f"`-> 0x{entry.target_offset:04X}` ({ref_label})"
                else:
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

    if not has_sections:
        is_rep, rep_spec, unit_entries, sample_count = _detect_repetition(entries)
        if is_rep:
            unit_size = sum(e.size for e in unit_entries)
            repeat_label = _format_repeat_label(rep_spec)
            if is_ja:
                meta_lines = [
                    f"- 🔁 **繰り返し**: {repeat_label}",
                    f"- **1要素サイズ**: `{unit_size}` バイト (0x{unit_size:X})",
                ]
                if sample_count > 1:
                    meta_lines.append(f"- **サンプルデータ**: {sample_count} 件 (合計 `{total_bytes}` バイト)")
            else:
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
                    title=f"{resolved_title} (1要素の構造)" if is_ja else f"{title} (1要素の構造)",
                    bits_per_row=bits_per_row,
                    expand_bitfields=expand_bitfields,
                    font_size=font_size,
                    bit_width=bit_width,
                    relative_offset=True,
                    include_values=False,
                    large_data_threshold=large_data_threshold,
                    compact_tables=compact_tables,
                    compact_large_entries=compact_large_entries,
                    max_field_bits=max_packet_field_bits,
                    lang=lang,
                )
                if sec_diag:
                    sections.append(sec_diag)
                    sections.append("")
            _render_relative_table_rows(unit_entries, base_offset=unit_entries[0].offset)
        else:
            if section_packet_diagrams and diagram_type not in ("packet", "both"):
                diag = generate_packet_diagram(
                    entries,
                    title=f"{resolved_title} レイアウト" if is_ja else f"{title} Layout",
                    bits_per_row=bits_per_row,
                    expand_bitfields=expand_bitfields,
                    font_size=font_size,
                    bit_width=bit_width,
                    relative_offset=True,
                    include_values=include_values,
                    large_data_threshold=large_data_threshold,
                    compact_tables=compact_tables,
                    compact_large_entries=compact_large_entries,
                    max_field_bits=max_packet_field_bits,
                    lang=lang,
                )
                if diag:
                    sections.append(diag)
                    sections.append("")

            _render_table_rows(entries)
    else:
        # Group by consecutive caption or struct_name
        caption_groups: List[tuple[Optional[str], List[LayoutEntry]]] = []
        current_cap: Optional[str] = None
        current_cap_entries: List[LayoutEntry] = []

        for entry in entries:
            cap = entry.caption or entry.struct_name
            if not cap:
                if entry.type_name and entry.type_name.startswith("Offset["):
                    m = re.match(r"^(.+)\[\d+\]$", entry.name) if entry.name else None
                    base_name = m.group(1) if m else ""
                    if not base_name or base_name in ("offsets", "offset_table"):
                        cap = "オフセットテーブル" if is_ja else "Offset Table"
                    else:
                        cap = base_name

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
            cap_desc = c_entries[0].caption_desc
            if not cap_desc:
                for e in c_entries:
                    if e.struct_doc:
                        cap_desc = e.struct_doc
                        break
            is_rep, rep_spec, unit_entries, sample_count = _detect_repetition(c_entries)

            if not cap:
                if _is_offset_table_entries(c_entries):
                    display_cap = "オフセットテーブル" if is_ja else "Offset Table"
                else:
                    display_cap = "データ領域" if is_ja else "Data Section"
            else:
                display_cap = cap

            if is_rep:
                unit_size = sum(e.size for e in unit_entries)
                if include_section_offsets:
                    sections.append(f"### {display_cap} (0x{min_off:04X} - 0x{max_off:04X}, {total_size}B)\n")
                else:
                    sections.append(f"### {display_cap}\n")

                if cap_desc:
                    sections.append(f"{cap_desc}\n")

                repeat_label = _format_repeat_label(rep_spec)
                if is_ja:
                    meta_lines = [
                        f"- 🔁 **繰り返し**: {repeat_label}",
                        f"- **1要素サイズ**: `{unit_size}` バイト (0x{unit_size:X})",
                        f"- **配置範囲**: `0x{min_off:04X}` 〜 `0x{max_off:04X}` (`{total_size}` バイト)",
                    ]
                    if sample_count > 1:
                        meta_lines.append(f"- **サンプルデータ**: {sample_count} 件 (合計 `{total_size}` バイト)")
                    else:
                        meta_lines.append(f"- **サンプルデータ**: 1 件 (`{total_size}` バイト)")
                else:
                    meta_lines = [
                        f"- 🔁 **繰り返し**: {repeat_label}",
                        f"- **1要素サイズ**: `{unit_size}` bytes (0x{unit_size:X})",
                        f"- **Offset Range**: `0x{min_off:04X}` - `0x{max_off:04X}` (`{total_size}` bytes)",
                    ]
                    if sample_count > 1:
                        meta_lines.append(f"- **サンプルデータ**: {sample_count} 件 (合計 `{total_size}` bytes)")
                    else:
                        meta_lines.append(f"- **サンプルデータ**: 1 件 (`{total_size}` bytes)")
                sections.append("\n".join(meta_lines) + "\n")

                if want_section_packets:
                    sec_diag = generate_packet_diagram(
                        unit_entries,
                        title=f"{display_cap} (1要素の構造)" if is_ja else f"{display_cap} (Unit Structure)",
                        bits_per_row=bits_per_row,
                        expand_bitfields=expand_bitfields,
                        font_size=font_size,
                        bit_width=bit_width,
                        relative_offset=True,
                        include_values=False,
                        large_data_threshold=large_data_threshold,
                        compact_tables=compact_tables,
                        compact_large_entries=compact_large_entries,
                        max_field_bits=max_packet_field_bits,
                        lang=lang,
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
                            if include_section_offsets:
                                sections.append(f"#### {sub_title} ({s_size}B)\n")
                            else:
                                sections.append(f"#### {sub_title}\n")
                            if s_desc:
                                sections.append(f"{s_desc}\n")
                        _render_relative_table_rows(s_entries, base_offset=unit_entries[0].offset)
                else:
                    _render_relative_table_rows(unit_entries, base_offset=unit_entries[0].offset)

            else:
                if include_section_offsets:
                    sections.append(f"### {display_cap} (0x{min_off:04X} - 0x{max_off:04X}, {total_size}B)\n")
                else:
                    sections.append(f"### {display_cap}\n")

                if cap_desc:
                    sections.append(f"{cap_desc}\n")

                if want_section_packets:
                    sec_diag = generate_packet_diagram(
                        c_entries,
                        title=f"{display_cap} レイアウト" if is_ja else f"{display_cap} Layout",
                        bits_per_row=bits_per_row,
                        expand_bitfields=expand_bitfields,
                        font_size=font_size,
                        bit_width=bit_width,
                        relative_offset=True,
                        include_values=include_values,
                        large_data_threshold=large_data_threshold,
                        compact_tables=compact_tables,
                        compact_large_entries=compact_large_entries,
                        max_field_bits=max_packet_field_bits,
                        lang=lang,
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
                            if include_section_offsets:
                                sections.append(f"#### {sub_title} (0x{s_min:04X} - 0x{s_max:04X}, {s_size}B)\n")
                            else:
                                sections.append(f"#### {sub_title}\n")
                            if s_desc:
                                sections.append(f"{s_desc}\n")
                            if want_section_packets:
                                s_diag = generate_packet_diagram(
                                    s_entries,
                                    title=f"{sub_title} レイアウト" if is_ja else f"{sub_title} Layout",
                                    bits_per_row=bits_per_row,
                                    expand_bitfields=expand_bitfields,
                                    font_size=font_size,
                                    bit_width=bit_width,
                                    relative_offset=True,
                                    include_values=include_values,
                                    large_data_threshold=large_data_threshold,
                                    compact_tables=compact_tables,
                                    compact_large_entries=compact_large_entries,
                                    max_field_bits=max_packet_field_bits,
                                    lang=lang,
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
                    var_prefix = "#### [バリアント]" if is_ja else "#### [Variant]"
                    header_str = f"{var_prefix} {tag_str + ': ' if tag_str else ''}`{cls_name}`\n"
                    sections.append(header_str)
                    doc_text = v_desc or getattr(v_cls, "__doc__", "") or ""
                    if doc_text:
                        import inspect
                        sections.append(f"{inspect.cleandoc(doc_text)}\n")

                    v_entries = _inspect_struct_layout(v_cls)
                    if v_entries:
                        if want_section_packets:
                            v_diag = generate_packet_diagram(
                                v_entries,
                                title=f"{cls_name} Layout",
                                bits_per_row=bits_per_row,
                                expand_bitfields=expand_bitfields,
                                font_size=font_size,
                                bit_width=bit_width,
                                relative_offset=True,
                                include_values=False,
                                large_data_threshold=large_data_threshold,
                                compact_tables=compact_tables,
                                compact_large_entries=compact_large_entries,
                                max_field_bits=max_packet_field_bits,
                                lang=lang,
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
        sections.append("## ビットフィールド詳細\n" if is_ja else "## Bitfield Details\n")
        for bf in bitfields:
            bf_name = bf.name or bf.type_name
            if is_ja:
                sections.append(
                    f"### `{bf_name}` (オフセット: `0x{bf.offset:04X}`, サイズ: {bf.size}B)\n"
                )
            else:
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
            if is_ja:
                if include_values:
                    sections.append(
                        "| ビット範囲 | フィールド名 | ビット幅 | 値 | 説明 |"
                    )
                    sections.append("|---|---|---|---|---|")
                else:
                    sections.append(
                        "| ビット範囲 | フィールド名 | ビット幅 | 説明 |"
                    )
                    sections.append("|---|---|---|---|")
            else:
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
                width_str = f"{sub.get('width', 1)} bit" if is_ja else f"{sub.get('width', 1)} bit(s)"
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


