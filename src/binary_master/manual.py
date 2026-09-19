"""Manual and documentation generator with Mermaid diagrams for BinaryWriter."""

from __future__ import annotations

import locale
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, IO, List, Literal, Optional, Union


def resolve_language(lang: Optional[str] = "auto") -> Literal["en", "ja"]:
    """Resolve language choice ('auto', 'en', 'ja') to 'en' or 'ja' based on system locale.

    If lang is 'auto' (or None/empty), it checks environment variables (LC_ALL, LC_MESSAGES, LANG)
    and Python's locale.getlocale(). If the locale indicates Japanese ('ja' or 'japanese'),
    it returns 'ja', otherwise 'en'.
    """
    if not lang or lang == "auto":
        env_lang = (
            os.environ.get("LC_ALL")
            or os.environ.get("LC_MESSAGES")
            or os.environ.get("LANG")
            or ""
        )
        if not env_lang:
            try:
                loc = locale.getlocale()[0] or ""
                env_lang = loc
            except Exception:
                pass
        if env_lang.lower().startswith("ja") or "japanese" in env_lang.lower():
            return "ja"
        return "en"

    clean = lang.lower().strip()
    if clean.startswith("ja") or clean.startswith("jp"):
        return "ja"
    return "en"


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
    caption_spec_count: Optional[Union[int, str, bool]] = None
    caption_repeat: Optional[Union[int, str, bool]] = None

    def __post_init__(self):
        if self.caption_spec_count is None and self.caption_repeat is not None:
            self.caption_spec_count = self.caption_repeat
        elif self.caption_repeat is None and self.caption_spec_count is not None:
            self.caption_repeat = self.caption_spec_count


def _safe_issubclass(cls: Any, base: Any) -> bool:
    """Safely check if cls is a subclass of base, handling TypeAliasType and missing types."""
    if not isinstance(cls, type) or base is None:
        return False
    if isinstance(base, tuple):
        valid_bases = tuple(b for b in base if isinstance(b, type))
        if not valid_bases:
            return False
        return issubclass(cls, valid_bases)
    if not isinstance(base, type):
        return False
    return issubclass(cls, base)


def create_dummy_instance(struct_cls: type) -> Any:
    """Create a dummy instance of a @binary_struct class for layout inspection."""
    if not hasattr(struct_cls, "__binary__"):
        return None
    from typing import get_origin, get_args, Annotated
    import binary_master as bm

    _BinaryType = getattr(bm, "BinaryType", None)
    _FixedArray = getattr(bm, "FixedArray", None)
    _Array = getattr(bm, "Array", None)
    _Offset = getattr(bm, "Offset", None)
    _OffsetTable = getattr(bm, "OffsetTable", None)
    _UInt8 = getattr(bm, "UInt8", None)
    _Bool = getattr(bm, "Bool", None)
    _Bytes = getattr(bm, "Bytes", None)
    _FixedString = getattr(bm, "FixedString", None)
    _CString = getattr(bm, "CString", None)
    _PrefixedString = getattr(bm, "PrefixedString", None)
    _MagicBase = getattr(bm, "MagicBase", None)
    _ConstantBase = getattr(bm, "ConstantBase", None)
    _RangeBase = getattr(bm, "RangeBase", None)
    _LengthOfBase = getattr(bm, "LengthOfBase", None)
    _CountOfBase = getattr(bm, "CountOfBase", None)

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

        is_fixed = (_FixedArray is not None) and (
            (isinstance(ft, tuple) and len(ft) >= 3 and ft[0] is _FixedArray)
            or (get_origin(ft) is _FixedArray)
        )
        is_arr = (_Array is not None) and (
            (isinstance(ft, tuple) and len(ft) >= 2 and ft[0] is _Array)
            or (get_origin(ft) is _Array)
        )
        is_offset = (_Offset is not None) and (
            (isinstance(ft, tuple) and len(ft) >= 1 and ft[0] is _Offset)
            or (get_origin(ft) is _Offset)
        )
        is_offset_tbl = (_OffsetTable is not None) and (
            (isinstance(ft, tuple) and len(ft) >= 1 and ft[0] is _OffsetTable)
            or (get_origin(ft) is _OffsetTable)
        )

        from binary_master.checksum import ChecksumBase
        from binary_master.varint import VarIntTypeMeta
        import enum

        if _safe_issubclass(ft, _MagicBase):
            expected = getattr(ft, "_value", None)
            dummy_kwargs[fn] = expected if expected is not None else getattr(ft, "_raw_val", 0)
        elif _safe_issubclass(ft, _ConstantBase):
            dummy_kwargs[fn] = getattr(ft, "_value", 0)
        elif _safe_issubclass(ft, _RangeBase):
            dummy_kwargs[fn] = getattr(ft, "_min", 0)
        elif _safe_issubclass(ft, (_LengthOfBase, _CountOfBase)):
            dummy_kwargs[fn] = 0
        elif _safe_issubclass(ft, ChecksumBase):
            dummy_kwargs[fn] = 0
        elif isinstance(ft, VarIntTypeMeta):
            dummy_kwargs[fn] = 0
        elif _safe_issubclass(ft, enum.Enum):
            dummy_kwargs[fn] = next(iter(ft)) if len(ft) > 0 else 0
        elif isinstance(ft, tuple) and len(ft) >= 2 and _safe_issubclass(ft[0], enum.Enum):
            dummy_kwargs[fn] = next(iter(ft[0])) if len(ft[0]) > 0 else 0
        elif ft is bool or _safe_issubclass(ft, _Bool) or ft is _Bool:
            dummy_kwargs[fn] = False
        elif _safe_issubclass(ft, (_FixedString, _CString, _PrefixedString)):
            dummy_kwargs[fn] = ""
        elif _safe_issubclass(ft, _Bytes):
            dummy_kwargs[fn] = b"\x00" * getattr(ft, "_size", 0)
        elif _safe_issubclass(ft, _BinaryType):
            dummy_kwargs[fn] = 0
        elif is_fixed:
            args = get_args(ft)
            cnt = ft[2] if isinstance(ft, tuple) and len(ft) >= 3 else (args[1] if len(args) >= 2 else 1)
            elem_t = ft[1] if isinstance(ft, tuple) and len(ft) >= 2 else (args[0] if len(args) >= 1 else _UInt8)
            if hasattr(cnt, "__value__"):
                cnt = cnt.__value__
            if not isinstance(cnt, int):
                cnt = 1
            if elem_t is _UInt8:
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
            if isinstance(ft, tuple):
                count_arg = ft[1] if len(ft) >= 2 else 1
            else:
                args = get_args(ft)
                count_arg = args[0] if len(args) >= 1 else 1
            if isinstance(count_arg, int):
                dummy_kwargs[fn] = [0] * count_arg
            else:
                dummy_kwargs[fn] = [0]
                if isinstance(count_arg, str) and count_arg in dummy_kwargs:
                    dummy_kwargs[count_arg] = 1
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
                curr_name = re.sub(r"\[\d+\]$", "", e_curr.name) if (explicit_repeat is not None and e_curr.name) else e_curr.name
                base_name = re.sub(r"\[\d+\]$", "", e_base.name) if (explicit_repeat is not None and e_base.name) else e_base.name
                if (
                    curr_name != base_name
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

        fixed_units = []
        for u in unit_entries:
            if u.name and re.search(r"\[\d+\]$", u.name):
                u_copy = LayoutEntry(
                    name=re.sub(r"\[\d+\]$", "[i]", u.name),
                    offset=u.offset,
                    size=u.size,
                    type_name=u.type_name,
                    endian=u.endian,
                    value=u.value,
                    description=re.sub(r"\[#\d+\]", "[#i]", u.description) if u.description else u.description,
                    struct_name=u.struct_name,
                    struct_doc=u.struct_doc,
                    subfields=u.subfields,
                    caption=u.caption,
                    caption_desc=u.caption_desc,
                    caption_repeat=u.caption_repeat,
                    subcaption=u.subcaption,
                    subcaption_desc=u.subcaption_desc,
                    target_offset=u.target_offset,
                )
                fixed_units.append(u_copy)
            else:
                fixed_units.append(u)
        return True, explicit_repeat, fixed_units, sample_count

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


def _compress_consecutive_indexed_entries(
    entry_list: List[LayoutEntry],
) -> List[tuple[bool, Any]]:
    """Compress consecutive indexed entries (e.g. offsets[0]..offsets[N-1]) where N >= 3.

    Keeps the first (0) and last (N-1) entries, omitting intermediate items with a marker.
    Returns:
        List of tuples: (is_omitted, item)
        If is_omitted is False, item is LayoutEntry.
        If is_omitted is True, item is a tuple: (omitted_count, first_entry, last_entry).
    """
    if len(entry_list) < 3:
        return [(False, e) for e in entry_list]

    result: List[tuple[bool, Any]] = []
    i = 0
    n = len(entry_list)
    while i < n:
        curr = entry_list[i]
        m = re.match(r"^(.+)\[(\d+)\]$", curr.name) if curr.name else None
        if not m:
            result.append((False, curr))
            i += 1
            continue

        base_name = m.group(1)
        idx_val = int(m.group(2))

        # Look for consecutive sequence starting from idx_val
        j = i + 1
        expected_idx = idx_val + 1
        while j < n:
            nxt = entry_list[j]
            m_nxt = re.match(r"^(.+)\[(\d+)\]$", nxt.name) if nxt.name else None
            if not m_nxt:
                break
            if m_nxt.group(1) != base_name:
                break
            if int(m_nxt.group(2)) != expected_idx:
                break
            if nxt.type_name != curr.type_name or nxt.size != curr.size:
                break
            expected_idx += 1
            j += 1

        count = j - i
        if count >= 3:
            result.append((False, entry_list[i]))
            result.append((True, (count - 2, entry_list[i], entry_list[j - 1])))
            result.append((False, entry_list[j - 1]))
            i = j
        else:
            for k in range(i, j):
                result.append((False, entry_list[k]))
            i = j

    return result


def _format_indexed_type_name(base_type: Optional[str], count: int) -> str:
    """Format an aggregated type name for indexed entries (e.g. Offset[UInt16] -> OffsetTable[10, UInt16])."""
    if not base_type:
        return f"[{count}]"
    m = re.match(r"^Offset\[(.+)\]$", base_type)
    if m:
        target_t = m.group(1)
        return f"OffsetTable[{count}, {target_t}]"
    if base_type == "Offset":
        return f"OffsetTable[{count}]"
    return f"{base_type}[{count}]"


def _aggregate_indexed_entries_in_list(entries: List[LayoutEntry]) -> List[LayoutEntry]:
    """Aggregate consecutive indexed entries (e.g. offsets[0..9]) into a single LayoutEntry."""
    result: List[LayoutEntry] = []
    i = 0
    n = len(entries)
    while i < n:
        curr = entries[i]
        m = re.match(r"^(.+)\[(\d+)\]$", curr.name) if curr.name else None
        if not m:
            result.append(curr)
            i += 1
            continue

        base_name = m.group(1)
        idx_val = int(m.group(2))
        j = i + 1
        expected_idx = idx_val + 1
        while j < n:
            nxt = entries[j]
            m_nxt = re.match(r"^(.+)\[(\d+)\]$", nxt.name) if nxt.name else None
            if not m_nxt or m_nxt.group(1) != base_name or int(m_nxt.group(2)) != expected_idx:
                break
            if nxt.type_name != curr.type_name or nxt.size != curr.size:
                break
            expected_idx += 1
            j += 1

        count = j - i
        if count >= 3:
            total_size = sum(entries[k].size for k in range(i, j))
            agg_type = _format_indexed_type_name(curr.type_name, count)
            summary_entry = LayoutEntry(
                offset=curr.offset,
                size=total_size,
                name=base_name,
                type_name=agg_type,
                endian=curr.endian,
                description=curr.description,
                struct_name=curr.struct_name,
                caption=curr.caption,
                target_offset=curr.target_offset,
            )
            setattr(summary_entry, "_is_indexed_summary", True)
            result.append(summary_entry)
            i = j
        else:
            for k in range(i, j):
                result.append(entries[k])
            i = j

    return result


def _aggregate_entries_for_diagram(
    entries: List[LayoutEntry],
    relative_offset: bool = False,
) -> List[LayoutEntry]:
    """Aggregate repeated sections and indexed entries into single coherent blocks for packet diagrams.

    This eliminates unhelpful intermediate '...' ellipses in diagrams.
    """
    if not entries:
        return []

    # If rendering a relative section (e.g. unit of a repeated struct), only aggregate indexed entries
    if relative_offset:
        return _aggregate_indexed_entries_in_list(entries)

    # Group entries by section (caption or struct_name)
    groups: List[List[LayoutEntry]] = []
    current_key = None
    current_group: List[LayoutEntry] = []

    for entry in entries:
        key = entry.caption or entry.struct_name
        if key != current_key:
            if current_group:
                groups.append(current_group)
            current_key = key
            current_group = [entry]
        else:
            current_group.append(entry)
    if current_group:
        groups.append(current_group)

    aggregated: List[LayoutEntry] = []
    for grp in groups:
        is_rep, rep_spec, u_entries, sample_count = _detect_repetition(grp)
        if is_rep and sample_count >= 2:
            first_e = grp[0]
            sec_name = first_e.struct_name or first_e.caption or "Payload"
            total_size = sum(e.size for e in grp)
            rep_tag = _format_repeat_tag(rep_spec)
            summary_entry = LayoutEntry(
                offset=first_e.offset,
                size=total_size,
                name=f"{sec_name}{rep_tag}",
                type_name=f"{sec_name}{rep_tag}",
                endian=first_e.endian,
                description=first_e.description or first_e.caption_desc or "",
                struct_name=first_e.struct_name,
                caption=first_e.caption,
            )
            setattr(summary_entry, "_is_rep_summary", True)
            aggregated.append(summary_entry)
        else:
            aggregated.extend(_aggregate_indexed_entries_in_list(grp))

    return aggregated


def _is_offset_table_entries(entries: List[LayoutEntry]) -> bool:
    """Check if the given layout entries represent an offset table."""
    if not entries:
        return False
    return any(e.type_name and e.type_name.startswith("Offset[") for e in entries) and all(
        (e.type_name and e.type_name.startswith("Offset["))
        or (e.name and bool(re.search(r"\[\d+\]$", e.name)))
        for e in entries
    )


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

    diagram_entries = _aggregate_entries_for_diagram(entries, relative_offset=relative_offset)
    for e in diagram_entries:
        entry_start_bit = (e.offset - base_offset) * 8
        entry_end_bit = entry_start_bit + (e.size * 8)

        if entry_start_bit > current_bit:
            gap_start = current_bit
            gap_end = entry_start_bit - 1
            gap_bytes = (gap_end - gap_start + 1) // 8
            if large_data_threshold > 0 and gap_bytes >= large_data_threshold:
                lines.append(f'{gap_start}-{gap_end}: "(padding, {gap_bytes}B)"')
            elif gap_start == gap_end:
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
            label = label.replace('"', '\\"')
            if s_start == s_end:
                lines.append(f'{s_start}: "{label}"')
            else:
                lines.append(f'{s_start}-{s_end}: "{label}"')
            current_bit = entry_end_bit

    lines.append("```")
    return "\n".join(lines)


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


    raw_entries = entries
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
                f'<tr class="table-row table-row-omitted">\n'
                f'  <td class="cell-mono cell-offset">...</td>\n'
                f'  <td class="cell-mono">...</td>\n'
                f'  <td class="cell-name"><code>...</code></td>\n'
                f'  <td><span class="type-badge">...</span></td>\n'
                f'  <td class="cell-dim">-</td>\n'
            )
            if include_values:
                tr += f'  <td class="cell-mono cell-val">...</td>\n'
            tr += f'  <td class="cell-desc">...</td>\n</tr>'
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

