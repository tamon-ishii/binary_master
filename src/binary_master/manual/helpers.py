"""Layout inspection and entry aggregation helpers for manual generator."""

from __future__ import annotations

import re
from typing import Any, List, Optional, cast

from binary_master.layout import LayoutEntry


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
    from typing import Annotated, get_args, get_origin

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
        dummy_kwargs: dict[str, Any] = {fn: 0 for fn in fields}
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

        import enum

        from binary_master.checksum import ChecksumBase
        from binary_master.varint import VarIntTypeMeta

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
                dummy_kwargs[fn] = [create_dummy_instance(cast(type, elem_t))] * cnt
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


