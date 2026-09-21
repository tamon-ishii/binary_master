"""Interactive single-page HTML specification manual generator."""

from __future__ import annotations

import re
from pathlib import Path
from typing import IO, Any, Dict, List, Literal, Optional, Union

from binary_master.layout import LayoutEntry
from binary_master.manual.diagrams import (
    generate_mermaid_diagram,
    generate_packet_diagram,
)
from binary_master.manual.helpers import (
    _compress_consecutive_indexed_entries,
    _detect_repetition,
    create_dummy_instance,
    format_value_preview,
)
from binary_master.manual.i18n import resolve_language


def generate_html(
    entries: Any,
    default_endian: str = "little",
    title: str = "Binary Specification Manual",
    sample_data: Optional[bytes] = None,
    diagram_type: Literal["both", "flowchart", "packet", "none"] = "both",
    diagram_direction: Literal["TD", "LR"] = "TD",
    bits_per_row: int = 32,
    include_values: bool = True,
    theme: Literal["auto", "light", "dark"] = "auto",
    lang: Literal["auto", "en", "ja"] = "auto",
    include_section_offsets: bool = False,
    large_data_threshold: int = 64,
    full_packet_diagram: bool = False,
    compact_tables: bool = True,
    compact_large_entries: bool = False,
    max_packet_field_bits: Optional[int] = None,
    **kwargs: Any,
) -> str:
    """Generate a standalone, interactive HTML specification manual with an embedded hex inspector.

    Features:
        - Responsive modern CSS styling with light/dark theme support.
        - Interactive Hex Inspector linking hex dump bytes to specification table rows.
        - Embedded Mermaid diagram visualization.
        - Bitfield layout breakdown tables.

    Args:
        entries: A @binary_struct class/instance, BinaryWriter, Builder, or list of LayoutEntry.
        default_endian: Default endianness ("little" or "big").
        title: Document title.
        sample_data: Optional raw binary data to display in the hex dump inspector.
        diagram_type: Mermaid diagram type: "flowchart", "packet", "both", or "none".
        diagram_direction: Mermaid flowchart direction ("TD", "LR").
        bits_per_row: Number of bits per row for packet diagrams (default: 32).
        include_values: Whether to include sample values in tables.
        theme: Color theme ("auto", "light", or "dark").
        lang: Output language ("auto", "en", or "ja"). Default is "auto" (detected from system locale).
        include_section_offsets: Whether to append offset ranges to section titles and diagrams. Default is False.
        large_data_threshold: Threshold in bytes to summarize large data blocks in packet diagrams (default 64).
        full_packet_diagram: Whether to include the full packet diagram when diagram_type is 'both' even if sections/structs exist. Default is False.

    Returns:
        Complete standalone HTML document as a string.
    """
    import html as html_lib

    is_ja = resolve_language(lang) == "ja"
    if is_ja and title == "Binary Specification Manual":
        resolved_title = "バイナリ仕様書"
    else:
        resolved_title = title


    _raw_entries = entries
    extracted_sample_data = sample_data

    if hasattr(entries, "__binary__"):
        from binary_master.writer import BinaryWriter
        w = BinaryWriter()
        if isinstance(entries, type):
            dummy = create_dummy_instance(entries)
            if dummy is not None:
                w.write_struct(dummy)
        else:
            w.write_struct(entries)
        entries_list = w.entries
        if extracted_sample_data is None:
            extracted_sample_data = w.to_bytes()
    elif hasattr(entries, "to_bytes") and hasattr(entries, "entries"):
        entries_list = getattr(entries, "entries", [])
        if extracted_sample_data is None:
            try:
                extracted_sample_data = entries.to_bytes()
            except Exception:
                extracted_sample_data = None
    elif hasattr(entries, "entries"):
        entries_list = getattr(entries, "entries", [])
    elif isinstance(entries, (list, tuple)):
        entries_list = list(entries)
    else:
        entries_list = []

    total_bytes = 0
    if entries_list:
        total_bytes = max(e.offset + e.size for e in entries_list)
    if extracted_sample_data is not None and len(extracted_sample_data) > total_bytes:
        total_bytes = len(extracted_sample_data)

    root_doc = ""
    for e in entries_list:
        if e.struct_doc:
            root_doc = e.struct_doc
            break

    distinct_struct_names: List[str] = []
    for e in entries_list:
        if e.struct_name and (not distinct_struct_names or distinct_struct_names[-1] != e.struct_name):
            distinct_struct_names.append(e.struct_name)

    offset_to_target_label: Dict[int, str] = {}
    caption_groups_lookup: List[tuple[Optional[str], List[LayoutEntry]]] = []
    _c_cap: Optional[str] = None
    _c_entries: List[LayoutEntry] = []
    for e in entries_list:
        c = e.caption or e.struct_name
        if c != _c_cap:
            if _c_entries:
                caption_groups_lookup.append((_c_cap, _c_entries))
            _c_cap = c
            _c_entries = [e]
        else:
            _c_entries.append(e)
    if _c_entries:
        caption_groups_lookup.append((_c_cap, _c_entries))

    for cap, c_entries in caption_groups_lookup:
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

    has_captions = any(e.caption for e in entries_list)
    has_multiple_structs = len(distinct_struct_names) > 1
    has_sections = has_captions or has_multiple_structs

    # Prepare Mermaid Diagram content
    mermaid_blocks: List[str] = []
    if diagram_type in ("flowchart", "both") and entries_list:
        f_diag = generate_mermaid_diagram(entries_list, direction=diagram_direction, include_section_offsets=include_section_offsets, lang=lang)
        # Strip code fences
        clean_f = re.sub(r"^```mermaid\s*", "", f_diag).rstrip("`\n")
        mermaid_blocks.append(clean_f)
    should_include_packet = (diagram_type == "packet") or (
        diagram_type == "both" and (not has_sections or full_packet_diagram)
    )
    if should_include_packet and entries_list:
        p_diag = generate_packet_diagram(
            entries_list,
            title=f"{resolved_title} レイアウト" if is_ja else f"{resolved_title} Layout",
            bits_per_row=bits_per_row,
            include_values=include_values,
            large_data_threshold=large_data_threshold,
            compact_tables=compact_tables,
            compact_large_entries=compact_large_entries,
            max_field_bits=max_packet_field_bits,
            lang=lang,
        )
        clean_p = re.sub(r"^```mermaid\s*", "", p_diag).rstrip("`\n")
        mermaid_blocks.append(clean_p)

    # Build Hex Dump HTML
    hex_dump_html = ""
    if extracted_sample_data:
        hex_lines = []
        b_data = extracted_sample_data
        for line_start in range(0, len(b_data), 16):
            chunk = b_data[line_start : line_start + 16]
            off_str = f"{line_start:08X}"

            # Format 16 bytes
            byte_spans = []
            for i in range(16):
                if i < len(chunk):
                    curr_off = line_start + i
                    b_val = chunk[i]
                    byte_spans.append(
                        f'<span class="hex-byte" data-offset="{curr_off}" title="Offset: 0x{curr_off:04X} ({curr_off})">{b_val:02X}</span>'
                    )
                else:
                    byte_spans.append('<span class="hex-byte empty">&nbsp;&nbsp;</span>')
                if i == 7:
                    byte_spans.append('<span class="hex-gap"> </span>')

            # Format ASCII
            ascii_spans = []
            for i, b in enumerate(chunk):
                curr_off = line_start + i
                ch = chr(b) if 32 <= b <= 126 else "."
                ch_escaped = html_lib.escape(ch)
                ascii_spans.append(f'<span class="ascii-byte" data-offset="{curr_off}">{ch_escaped}</span>')

            hex_lines.append(
                f'<div class="hex-line"><span class="hex-offset">{off_str}:</span> '
                f'<span class="hex-bytes">{" ".join(byte_spans)}</span>  '
                f'<span class="hex-ascii">{"".join(ascii_spans)}</span></div>'
            )
        hex_dump_html = "\n".join(hex_lines)

    # Table rows HTML
    compressed = _compress_consecutive_indexed_entries(entries_list)
    table_rows: List[str] = []
    for idx, (is_omitted, item) in enumerate(compressed):
        if is_omitted:
            tr = (
                '<tr class="table-row table-row-omitted">\n'
                '  <td class="cell-mono cell-offset">...</td>\n'
                '  <td class="cell-mono">...</td>\n'
                '  <td class="cell-name"><code>...</code></td>\n'
                '  <td><span class="type-badge">...</span></td>\n'
                '  <td class="cell-dim">-</td>\n'
            )
            if include_values:
                tr += '  <td class="cell-mono cell-val">...</td>\n'
            tr += '  <td class="cell-desc">...</td>\n</tr>'
            table_rows.append(tr)
            continue

        e = item
        off_start = e.offset
        off_end = e.offset + e.size
        off_hex = f"0x{e.offset:04X}"
        off_dec = str(e.offset)
        size_str = f"{e.size}B"
        name_str = html_lib.escape(e.name or "-")
        type_str = html_lib.escape(e.type_name)
        endian_str = html_lib.escape(e.endian or default_endian)
        val_str = html_lib.escape(format_value_preview(e.value)) if include_values else "-"
        desc_str = html_lib.escape(e.description or "-")
        if e.target_offset is not None:
            ref_label = offset_to_target_label.get(e.target_offset)
            if ref_label:
                desc_str += f" &rarr; <code>0x{e.target_offset:04X} ({html_lib.escape(ref_label)})</code>"
            else:
                desc_str += f" &rarr; <code>0x{e.target_offset:04X}</code>"

        tr = (
            f'<tr class="table-row" id="field-row-{idx}" '
            f'data-field-index="{idx}" '
            f'data-offset-start="{off_start}" '
            f'data-offset-end="{off_end}" '
            f'data-name="{name_str}" '
            f'data-type="{type_str}" '
            f'data-size="{e.size}" '
            f'data-value="{val_str}">\n'
            f'  <td class="cell-mono cell-offset">{off_hex} <span class="text-dim">({off_dec})</span></td>\n'
            f'  <td class="cell-mono">{size_str}</td>\n'
            f'  <td class="cell-name"><code>{name_str}</code></td>\n'
            f'  <td><span class="type-badge">{type_str}</span></td>\n'
            f'  <td class="cell-dim">{endian_str}</td>\n'
        )
        if include_values:
            tr += f'  <td class="cell-mono cell-val">{val_str}</td>\n'
        tr += f'  <td class="cell-desc">{desc_str}</td>\n</tr>'
        table_rows.append(tr)

    # Bitfields HTML
    bitfields_html = ""
    bitfields = []
    seen_bf = set()
    for e in entries_list:
        if e.subfields:
            key = (e.struct_name, e.name, e.type_name)
            if key not in seen_bf:
                seen_bf.add(key)
                bitfields.append(e)
    if bitfields:
        bf_sections = []
        for bf in bitfields:
            bf_name = html_lib.escape(bf.name or bf.type_name)
            sub_trs = []
            for sub in (bf.subfields or []):
                b_range = f"[{sub.get('bit_start', 0)}:{sub.get('bit_end', 0)}]"
                s_name = html_lib.escape(sub.get("name", "-"))
                s_width = f"{sub.get('width', 1)} bit" if is_ja else f"{sub.get('width', 1)} bit(s)"
                s_val = html_lib.escape(format_value_preview(sub.get("value"))) if include_values else "-"
                s_desc = html_lib.escape(sub.get("description") or "-")
                sub_trs.append(
                    f"<tr><td><code>{b_range}</code></td><td><code>{s_name}</code></td><td>{s_width}</td>"
                    + (f"<td><code>{s_val}</code></td>" if include_values else "")
                    + f"<td>{s_desc}</td></tr>"
                )
            th_bit_range = "ビット範囲" if is_ja else "Bit Range"
            th_field_name = "フィールド名" if is_ja else "Field Name"
            th_bit_width = "ビット幅" if is_ja else "Width"
            th_bit_val = "値" if is_ja else "Value"
            th_bit_desc = "説明" if is_ja else "Description"
            off_lbl = "オフセット:" if is_ja else "Offset:"
            size_lbl = "サイズ:" if is_ja else "Size:"
            bf_sections.append(
                f'<div class="card mb-4">\n'
                f'  <h3><code>{bf_name}</code> ({off_lbl} 0x{bf.offset:04X}, {size_lbl} {bf.size}B)</h3>\n'
                f'  <table class="layout-table">\n'
                f'    <thead><tr><th>{th_bit_range}</th><th>{th_field_name}</th><th>{th_bit_width}</th>'
                f'{"<th>" + th_bit_val + "</th>" if include_values else ""}<th>{th_bit_desc}</th></tr></thead>\n'
                f'    <tbody>{"".join(sub_trs)}</tbody>\n'
                f'  </table>\n'
                f'</div>'
            )
        bf_main_title = "ビットフィールド詳細" if is_ja else "Bitfield Details"
        bitfields_html = (
            '<section class="section">\n'
            f'  <h2>{bf_main_title}</h2>\n'
            + "\n".join(bf_sections)
            + '\n</section>'
        )

    # Build final HTML
    escaped_title = html_lib.escape(resolved_title)
    doc_html = f'<p class="overview-doc">{html_lib.escape(root_doc)}</p>' if root_doc else ""

    mermaid_section = ""
    if mermaid_blocks:
        mermaid_html_blocks = "\n".join(
            f'<div class="mermaid-card"><pre class="mermaid">\n{blk}\n</pre></div>'
            for blk in mermaid_blocks
        )
        diag_heading = "構造図" if is_ja else "Structure Diagram"
        mermaid_section = (
            '<section class="section">\n'
            f'  <h2>{diag_heading}</h2>\n'
            f'{mermaid_html_blocks}\n'
            '</section>'
        )

    hex_section = ""
    if hex_dump_html:
        hex_main_title = "ヘックスインスペクター" if is_ja else "Interactive Hex Inspector"
        hover_badge = "バイトまたは表の行にホバーして検査" if is_ja else "Hover bytes or table rows to inspect"
        inspect_bar_label = "検査情報:" if is_ja else "Inspection:"
        inspect_placeholder = "バイトまたは表の行にホバーして詳細を表示" if is_ja else "Hover over a byte or table row to inspect"
        hex_section = f"""
<section class="section">
  <div class="section-header">
    <h2>{hex_main_title}</h2>
    <span class="badge badge-info">{hover_badge}</span>
  </div>
  <div class="inspector-bar" id="inspector-bar">
    <span class="inspector-label">{inspect_bar_label}</span>
    <span id="inspector-info">{inspect_placeholder}</span>
  </div>
  <div class="hex-viewer-container">
    <div class="hex-viewer" id="hex-viewer">
{hex_dump_html}
    </div>
  </div>
</section>
"""

    html_lang = "ja" if is_ja else "en"
    size_badge_lbl = "合計サイズ:" if is_ja else "Total Size:"
    size_unit_lbl = "バイト" if is_ja else "bytes"
    endian_badge_lbl = "エンディアン:" if is_ja else "Endianness:"
    endian_disp_val = ("リトルエンディアン (Little)" if default_endian.lower() == "little" else "ビッグエンディアン (Big)") if is_ja else default_endian.capitalize()
    fields_badge_lbl = "フィールド数:" if is_ja else "Fields:"

    th_off_col = "オフセット" if is_ja else "Offset"
    th_sz_col = "サイズ" if is_ja else "Size"
    th_fn_col = "フィールド名" if is_ja else "Field Name"
    th_tp_col = "型" if is_ja else "Type"
    th_en_col = "エンディアン" if is_ja else "Endian"
    th_val_col = "値 / プレビュー" if is_ja else "Value / Preview"
    th_desc_col = "説明" if is_ja else "Description"
    mem_table_heading = "メモリレイアウト表" if is_ja else "Memory Layout Table"
    filter_placeholder = "フィールド名・型・説明で検索..." if is_ja else "Filter by field name, type, description..."

    js_field_lbl = "フィールド:" if is_ja else "Field:"
    js_type_lbl = "型:" if is_ja else "Type:"
    js_offset_lbl = "オフセット:" if is_ja else "Offset:"
    js_size_lbl = "サイズ:" if is_ja else "Size:"
    js_val_lbl = "値:" if is_ja else "Value:"
    js_unmapped = "(未マッピング / パディング)" if is_ja else "(unmapped / padding)"
    js_hover_prompt = "バイトまたは表の行にホバーして詳細を表示" if is_ja else "Hover over a byte or table row to inspect"

    return f"""<!DOCTYPE html>
<html lang="{html_lang}" data-theme="{theme}">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{escaped_title}</title>
  <style>
    :root {{
      --bg: #f8fafc;
      --card-bg: #ffffff;
      --text: #0f172a;
      --text-dim: #64748b;
      --border: #e2e8f0;
      --accent: #2563eb;
      --accent-hover: #1d4ed8;
      --highlight: #fef08a;
      --highlight-text: #854d0e;
      --highlight-border: #facc15;
      --badge-bg: #eff6ff;
      --table-header: #f1f5f9;
      --mono-font: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
      --sans-font: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    }}
    [data-theme="dark"] {{
      --bg: #0f172a;
      --card-bg: #1e293b;
      --text: #f8fafc;
      --text-dim: #94a3b8;
      --border: #334155;
      --accent: #3b82f6;
      --accent-hover: #60a5fa;
      --highlight: #854d0e;
      --highlight-text: #fef08a;
      --highlight-border: #ca8a04;
      --badge-bg: #1e3a8a;
      --table-header: #1e293b;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: var(--sans-font);
      background-color: var(--bg);
      color: var(--text);
      line-height: 1.6;
      padding: 2rem 1rem;
    }}
    .container {{
      max-width: 1200px;
      margin: 0 auto;
    }}
    header {{
      margin-bottom: 2rem;
      border-bottom: 2px solid var(--border);
      padding-bottom: 1.5rem;
    }}
    h1 {{
      font-size: 2.25rem;
      font-weight: 700;
      color: var(--text);
      margin-bottom: 0.5rem;
    }}
    .overview-doc {{
      font-size: 1.1rem;
      color: var(--text-dim);
      margin-bottom: 1rem;
      white-space: pre-line;
    }}
    .meta-badges {{
      display: flex;
      flex-wrap: wrap;
      gap: 0.75rem;
      margin-top: 1rem;
    }}
    .badge {{
      display: inline-flex;
      align-items: center;
      padding: 0.35rem 0.75rem;
      border-radius: 9999px;
      font-size: 0.85rem;
      font-weight: 500;
      background: var(--card-bg);
      border: 1px solid var(--border);
      color: var(--text);
    }}
    .badge-info {{
      background: var(--badge-bg);
      color: var(--accent);
      border-color: var(--accent);
    }}
    .section {{
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 1.5rem;
      margin-bottom: 2rem;
      box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }}
    .section-header {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 1rem;
    }}
    .mermaid-card {{
      overflow-x: auto;
      display: flex;
      justify-content: center;
      padding: 1rem 0;
    }}
    .table-container {{
      overflow-x: auto;
    }}
    .layout-table {{
      width: 100%;
      border-collapse: collapse;
      text-align: left;
      font-size: 0.9rem;
    }}
    .layout-table th, .layout-table td {{
      padding: 0.75rem 1rem;
      border-bottom: 1px solid var(--border);
    }}
    .layout-table th {{
      background-color: var(--table-header);
      font-weight: 600;
      color: var(--text-dim);
      text-transform: uppercase;
      font-size: 0.75rem;
      letter-spacing: 0.05em;
    }}
    .table-row {{
      cursor: pointer;
      transition: background-color 0.15s, border-left 0.15s;
    }}
    .table-row:hover, .table-row.active {{
      background-color: var(--highlight) !important;
      color: var(--highlight-text) !important;
    }}
    .table-row.active td {{
      font-weight: 600;
    }}
    .table-row-omitted {{
      cursor: default;
      opacity: 0.6;
    }}
    .table-row-omitted:hover {{
      background-color: transparent !important;
    }}
    .cell-mono {{ font-family: var(--mono-font); font-size: 0.85rem; }}
    .cell-offset {{ font-weight: 600; color: var(--accent); }}
    .cell-dim {{ color: var(--text-dim); }}
    .text-dim {{ color: var(--text-dim); font-size: 0.8em; }}
    .type-badge {{
      display: inline-block;
      padding: 0.15rem 0.5rem;
      border-radius: 4px;
      font-size: 0.8rem;
      font-family: var(--mono-font);
      background: var(--badge-bg);
      color: var(--accent);
    }}
    /* Hex Inspector Styles */
    .inspector-bar {{
      position: sticky;
      top: 10px;
      z-index: 100;
      background: var(--card-bg);
      border: 1px solid var(--accent);
      padding: 0.75rem 1.25rem;
      border-radius: 8px;
      font-family: var(--mono-font);
      font-size: 0.9rem;
      margin-bottom: 1rem;
      display: flex;
      align-items: center;
      gap: 0.75rem;
      box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1);
    }}
    .inspector-label {{
      font-weight: 700;
      color: var(--accent);
    }}
    .hex-viewer-container {{
      background: var(--bg);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 1rem;
      overflow-x: auto;
      font-family: var(--mono-font);
      font-size: 0.88rem;
    }}
    .hex-line {{
      display: flex;
      white-space: pre;
      line-height: 1.5;
    }}
    .hex-offset {{
      color: var(--text-dim);
      user-select: none;
      margin-right: 1.25rem;
    }}
    .hex-bytes {{
      margin-right: 1.5rem;
    }}
    .hex-byte {{
      display: inline-block;
      width: 2.2ch;
      text-align: center;
      cursor: pointer;
      border-radius: 2px;
      transition: background-color 0.1s;
    }}
    .hex-byte.empty {{ cursor: default; }}
    .hex-byte:hover, .hex-byte.active {{
      background-color: var(--highlight-border);
      color: var(--highlight-text);
      font-weight: 700;
    }}
    .ascii-byte {{
      display: inline-block;
      width: 1.1ch;
      text-align: center;
    }}
    .ascii-byte.active {{
      background-color: var(--highlight-border);
      color: var(--highlight-text);
      font-weight: 700;
    }}
    .hex-gap {{ display: inline-block; width: 1ch; }}
    code {{
      font-family: var(--mono-font);
      background: var(--badge-bg);
      padding: 0.15rem 0.35rem;
      border-radius: 4px;
      font-size: 0.88em;
    }}
    .table-toolbar {{
      margin-bottom: 0.75rem;
      display: flex;
      justify-content: flex-end;
    }}
    .search-input {{
      width: 100%;
      max-width: 320px;
      padding: 0.5rem 0.85rem;
      border: 1px solid var(--border);
      border-radius: 6px;
      background: var(--bg);
      color: var(--text);
      font-family: var(--sans-font);
      font-size: 0.88rem;
      outline: none;
      transition: border-color 0.2s, box-shadow 0.2s;
    }}
    .search-input:focus {{
      border-color: var(--accent);
      box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.2);
    }}
    @keyframes flashRow {{
      0% {{ background-color: var(--highlight-border); }}
      100% {{ background-color: transparent; }}
    }}
    .table-row.flash {{
      animation: flashRow 1.5s ease-out;
    }}
    g.node {{
      cursor: pointer;
    }}
  </style>
  <script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
  <script>
    mermaid.initialize({{
      startOnLoad: true,
      theme: 'default'
    }});
  </script>
</head>
<body>
  <div class="container">
    <header>
      <h1>{escaped_title}</h1>
      {doc_html}
      <div class="meta-badges">
        <span class="badge"><strong>{size_badge_lbl}</strong>&nbsp;{total_bytes} {size_unit_lbl} (0x{total_bytes:04X})</span>
        <span class="badge"><strong>{endian_badge_lbl}</strong>&nbsp;{endian_disp_val}</span>
        <span class="badge"><strong>{fields_badge_lbl}</strong>&nbsp;{len(entries_list)}</span>
      </div>
    </header>

    {mermaid_section}

    {hex_section}

    <section class="section">
      <div class="section-header">
        <h2>{mem_table_heading}</h2>
      </div>
      <div class="table-toolbar">
        <input type="text" id="table-search" placeholder="{filter_placeholder}" class="search-input" />
      </div>
      <div class="table-container">
        <table class="layout-table" id="layout-table">
          <thead>
            <tr>
              <th>{th_off_col}</th>
              <th>{th_sz_col}</th>
              <th>{th_fn_col}</th>
              <th>{th_tp_col}</th>
              <th>{th_en_col}</th>
              {"<th>" + th_val_col + "</th>" if include_values else ""}
              <th>{th_desc_col}</th>
            </tr>
          </thead>
          <tbody>
            {"".join(table_rows)}
          </tbody>
        </table>
      </div>
    </section>

    {bitfields_html}
  </div>

  <script>
    (function() {{
      const inspectorBar = document.getElementById('inspector-info');
      const tableRows = document.querySelectorAll('.table-row');
      const hexBytes = document.querySelectorAll('.hex-byte:not(.empty)');
      const asciiBytes = document.querySelectorAll('.ascii-byte');

      function clearHighlights() {{
        document.querySelectorAll('.active').forEach(el => el.classList.remove('active'));
      }}

      function highlightRange(start, end, infoText) {{
        clearHighlights();
        if (infoText && inspectorBar) {{
          inspectorBar.innerHTML = infoText;
        }}
        // Highlight hex bytes
        for (let off = start; off < end; off++) {{
          const hb = document.querySelector(`.hex-byte[data-offset="${{off}}"]`);
          if (hb) hb.classList.add('active');
          const ab = document.querySelector(`.ascii-byte[data-offset="${{off}}"]`);
          if (ab) ab.classList.add('active');
        }}
      }}

      // Table search filter
      const searchInput = document.getElementById('table-search');
      if (searchInput) {{
        searchInput.addEventListener('input', (e) => {{
          const term = e.target.value.toLowerCase().trim();
          tableRows.forEach(row => {{
            if (row.classList.contains('table-row-omitted')) return;
            const text = row.textContent.toLowerCase();
            if (!term || text.includes(term)) {{
              row.style.display = '';
            }} else {{
              row.style.display = 'none';
            }}
          }});
        }});
      }}

      // Mermaid node click interaction
      document.addEventListener('click', (e) => {{
        const node = e.target.closest('.node');
        if (!node) return;
        const textEl = node.querySelector('.nodeLabel') || node;
        const nodeText = textEl.textContent || '';
        const mOff = nodeText.match(/0x([0-9A-Fa-f]{{4}})/);
        let targetRow = null;
        if (mOff) {{
          const targetOffset = parseInt(mOff[1], 16);
          targetRow = document.querySelector(`.table-row[data-offset-start="${{targetOffset}}"]`);
        }}
        if (!targetRow && node.id) {{
          const nidMatch = node.id.match(/-(N\\d+)-/);
          if (nidMatch) {{
            const idx = parseInt(nidMatch[1].replace('N', ''), 10);
            targetRow = document.getElementById(`field-row-${{idx}}`);
          }}
        }}
        if (targetRow) {{
          targetRow.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
          targetRow.classList.add('flash');
          setTimeout(() => targetRow.classList.remove('flash'), 1500);
        }}
      }});

      // Row hover
      tableRows.forEach(row => {{
        const start = parseInt(row.getAttribute('data-offset-start'), 10);
        const end = parseInt(row.getAttribute('data-offset-end'), 10);
        const name = row.getAttribute('data-name');
        const type = row.getAttribute('data-type');
        const size = row.getAttribute('data-size');
        const val = row.getAttribute('data-value');

        const info = `<strong>{js_field_lbl}</strong> <code>${{name}}</code> | <strong>{js_type_lbl}</strong> ${{type}} | <strong>{js_offset_lbl}</strong> 0x${{start.toString(16).padStart(4, '0')}} (${{start}}) | <strong>{js_size_lbl}</strong> ${{size}}B` + (val !== '-' ? ` | <strong>{js_val_lbl}</strong> <code>${{val}}</code>` : '');

        row.addEventListener('mouseenter', () => {{
          row.classList.add('active');
          highlightRange(start, end, info);
        }});
        row.addEventListener('mouseleave', () => {{
          clearHighlights();
          if (inspectorBar) inspectorBar.textContent = '{js_hover_prompt}';
        }});
      }});

      // Hex byte hover
      hexBytes.forEach(byteEl => {{
        const offset = parseInt(byteEl.getAttribute('data-offset'), 10);
        byteEl.addEventListener('mouseenter', () => {{
          // Find matching table row
          let matchedRow = null;
          tableRows.forEach(row => {{
            const start = parseInt(row.getAttribute('data-offset-start'), 10);
            const end = parseInt(row.getAttribute('data-offset-end'), 10);
            if (offset >= start && offset < end) {{
              matchedRow = row;
            }}
          }});

          if (matchedRow) {{
            const start = parseInt(matchedRow.getAttribute('data-offset-start'), 10);
            const end = parseInt(matchedRow.getAttribute('data-offset-end'), 10);
            const name = matchedRow.getAttribute('data-name');
            const type = matchedRow.getAttribute('data-type');
            const size = matchedRow.getAttribute('data-size');
            const val = matchedRow.getAttribute('data-value');

            matchedRow.classList.add('active');
            const info = `<strong>{js_offset_lbl}</strong> 0x${{offset.toString(16).padStart(4, '0')}} (${{offset}}) &rarr; <strong>{js_field_lbl}</strong> <code>${{name}}</code> | <strong>{js_type_lbl}</strong> ${{type}} | <strong>{js_size_lbl}</strong> ${{size}}B` + (val !== '-' ? ` | <strong>{js_val_lbl}</strong> <code>${{val}}</code>` : '');
            highlightRange(start, end, info);
          }} else {{
            clearHighlights();
            byteEl.classList.add('active');
            if (inspectorBar) {{
              inspectorBar.innerHTML = `<strong>{js_offset_lbl}</strong> 0x${{offset.toString(16).padStart(4, '0')}} (${{offset}}) {js_unmapped}`;
            }}
          }}
        }});

        byteEl.addEventListener('mouseleave', () => {{
          clearHighlights();
          if (inspectorBar) inspectorBar.textContent = '{js_hover_prompt}';
        }});
      }});
    }})();
  </script>
</body>
</html>
"""


def write_html(
    entries: Any,
    path_or_file: Union[str, Path, IO[str]],
    lang: Literal["auto", "en", "ja"] = "auto",
    **kwargs: Any,
) -> str:
    """Generate interactive specification HTML and write it to a file or stream.

    Args:
        entries: A @binary_struct class/instance, BinaryWriter, Builder, or list of LayoutEntry.
        path_or_file: File path string, Path object, or writable text stream.
        lang: Output language ("auto", "en", or "ja"). Default is "auto" (detected from system locale).
        **kwargs: Options forwarded to generate_html().

    Returns:
        The generated HTML content as a string.
    """
    kwargs["lang"] = lang
    content = generate_html(entries, **kwargs)
    if isinstance(path_or_file, (str, Path)):
        p = Path(path_or_file)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
    elif hasattr(path_or_file, "write"):
        path_or_file.write(content)
    else:
        raise TypeError(f"Invalid path_or_file: {type(path_or_file).__name__}")
    return content


