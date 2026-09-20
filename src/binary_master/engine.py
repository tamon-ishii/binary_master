from __future__ import annotations

import enum
import struct
import sys
from typing import (
    Annotated,
    Any,
    Literal,
    Optional,
    TypeVar,
    Union,
    cast,
    get_args,
    get_origin,
)

T = TypeVar("T")

from binary_master.binary_types import (
    Array,
    BinaryType,
    Bool,
    Bytes,
    ConstantBase,
    CountOfBase,
    CString,
    FixedArray,
    FixedString,
    LengthOfBase,
    MagicBase,
    Offset,
    OffsetTable,
    PrefixedString,
    RangeBase,
    UInt32,
    Variant,
    _extract_named_offset_info,
    _is_named_offset_spec,
    _is_offset_table_spec,
    _normalize_offset_type,
    _parse_offset_spec_args,
    _resolve_base_offset,
)
from binary_master.checksum import ChecksumBase, compute_checksum
from binary_master.compressed import CompressedBase, compress_data, decompress_data
from binary_master.enums import Endian, EndianType, normalize_endian, normalize_offset_key
from binary_master.exceptions import (
    ChecksumMismatchError,
    InvalidConstantError,
    InvalidEnumError,
    InvalidMagicError,
    RangeValidationError,
    TotalSizeExceededError,
)
from binary_master.metadata import _get_field_alignment, _safe_issubclass, sizeof
from binary_master.plan import FieldKind, get_struct_plan
from binary_master.varint import (
    VarIntTypeMeta,
)


def _write_bitfield(
    instance: Any,
    writer: Any,
    endian: Endian,
    total_bits: int,
    field_name: str = "",
    parent_struct: Optional[str] = None,
    desc: str = "",
    struct_doc: str = "",
) -> None:
    import struct
    fields = instance.__binary__["fields"]
    descriptions = instance.__binary__.get("descriptions", {})
    bf_doc = struct_doc or instance.__binary__.get("doc", "")
    packed_value = 0
    shift = 0
    subfields = []
    for name, ftype in fields.items():
        val = getattr(instance, name, 0)
        width = ftype[1] if isinstance(ftype, tuple) and len(ftype) >= 2 else 1
        mask = (1 << width) - 1
        packed_value |= (int(val) & mask) << shift
        subfields.append({
            "name": name,
            "width": width,
            "bit_start": shift,
            "bit_end": shift + width,
            "value": val,
            "description": descriptions.get(name, ""),
        })
        shift += width

    offset = writer.tell()
    if total_bits <= 8:
        writer._stream.write(struct.pack("B", packed_value))
        size = 1
    elif total_bits <= 16:
        writer._stream.write(struct.pack(f"{endian.value}H", packed_value))
        size = 2
    elif total_bits <= 32:
        writer._stream.write(struct.pack(f"{endian.value}I", packed_value))
        size = 4
    elif total_bits <= 64:
        writer._stream.write(struct.pack(f"{endian.value}Q", packed_value))
        size = 8
    else:
        num_bytes = (total_bits + 7) // 8
        byteorder: Literal["little", "big"] = "little" if endian == Endian.LITTLE else "big"
        raw = packed_value.to_bytes(num_bytes, byteorder=byteorder)
        writer._stream.write(raw)
        size = num_bytes

    if hasattr(writer, "_record_entry"):
        writer._record_entry(
            offset=offset,
            size=size,
            type_name=instance.__class__.__name__,
            value=packed_value,
            name=field_name or instance.__class__.__name__,
            endian=endian.name.capitalize(),
            description=desc,
            struct_name=parent_struct or instance.__class__.__name__,
            subfields=subfields,
            struct_doc=bf_doc,
        )


def _write_fixed_array(name: str, elem_type: Any, count: int, val: Any, writer: Any, endian: Endian) -> None:
    if val is None:
        val = b"\x00" * count
    if isinstance(val, (bytes, bytearray, memoryview)):
        raw = bytes(val)
        if len(raw) < count:
            raw = raw.ljust(count, b"\x00")
        elif len(raw) > count:
            raise ValueError(f"Data for FixedArray {name} exceeds {count} bytes (got {len(raw)})")
        writer._stream.write(raw)
    elif isinstance(val, (list, tuple)):
        if len(val) > count:
            raise ValueError(f"Sequence for FixedArray {name} exceeds {count} elements (got {len(val)})")
        for item in val:
            _write_element(elem_type, item, writer, endian)
        for _ in range(count - len(val)):
            _write_element(elem_type, 0, writer, endian)
    else:
        raise TypeError(f"FixedArray field {name} expected bytes or sequence, got {type(val).__name__}")


def _write_array(name: str, elem_type: Any, val: Any, writer: Any, endian: Endian) -> None:
    if val is None:
        return
    if isinstance(val, (bytes, bytearray, memoryview)):
        writer._stream.write(bytes(val))
    elif isinstance(val, (list, tuple)):
        for item in val:
            _write_element(elem_type, item, writer, endian)
    else:
        raise TypeError(f"Array field {name} expected bytes or sequence, got {type(val).__name__}")


def _write_element(elem_type: Any, val: Any, writer: Any, endian: Endian) -> None:
    import struct
    if elem_type is Bool or (isinstance(elem_type, type) and issubclass(elem_type, Bool)) or elem_type is bool:
        size = getattr(elem_type, "_size", 1) if elem_type is not bool else 1
        writer.write_bool(bool(val), size=size, endian=endian)
    elif isinstance(elem_type, type) and issubclass(elem_type, BinaryType):
        data = struct.pack(f"{endian.value}{elem_type._fmt}", val)
        writer._stream.write(data)
    elif hasattr(val, "__binary__"):
        write_struct(val, writer=writer, endian=endian)
    elif isinstance(val, int):
        writer._stream.write(struct.pack("B", val))
    else:
        raise TypeError(f"Cannot serialize element of type {type(val).__name__}")

def write_struct(
    instance: Any,
    writer: Optional[Any] = None,
    endian: Optional[EndianType] = None,
    parent_field_name: str = "",
    parent_struct_name: Optional[str] = None,
    desc: str = "",
    section: str = "",
    spec_count: Optional[Union[int, str, bool]] = None,
    repeat: Optional[Union[int, str, bool]] = None,
    record_entries: bool = True,
) -> Any:
    """Serialize a @binary_struct instance to a BinaryWriter stream."""
    from binary_master.writer import BinaryWriter

    meta = getattr(instance, "__binary__", None)
    if meta is None:
        raise TypeError(f"Object of type {type(instance).__name__} is not a binary_struct")

    eff_spec = spec_count if spec_count is not None else repeat
    struct_endian = meta.get("endian", "little")
    active_endian = normalize_endian(endian or struct_endian)

    if writer is None:
        writer = BinaryWriter(default_endian=active_endian, record_entries=record_entries)
        if section:
            writer.set_caption(title=section, desc=desc, spec_count=eff_spec)
        elif eff_spec is not None:
            writer.set_caption(title=instance.__class__.__name__, desc=desc, spec_count=eff_spec)
    else:
        if section:
            if (
                getattr(writer, "_current_caption", None) != section
                or getattr(writer, "_current_caption_spec_count", None) != eff_spec
            ):
                if hasattr(writer, "set_caption"):
                    writer.set_caption(title=section, desc=desc, spec_count=eff_spec)
        elif eff_spec is not None:
            if getattr(writer, "_current_caption", None) is None:
                if hasattr(writer, "set_caption"):
                    writer.set_caption(title=instance.__class__.__name__, desc=desc, spec_count=eff_spec)
            elif hasattr(writer, "_current_caption_spec_count"):
                writer._current_caption_spec_count = eff_spec

    if hasattr(writer, "_struct_classes") and instance.__class__ not in writer._struct_classes:
        writer._struct_classes.append(instance.__class__)
    if hasattr(writer, "_elements_log"):
        writer._elements_log.append(("struct", instance.__class__))

    struct_start_pos = writer.tell()
    current_struct_name = parent_struct_name or instance.__class__.__name__
    struct_doc = meta.get("doc", "")
    align_setting = meta.get("align")
    auto_align = meta.get("auto_align", False)

    plan = get_struct_plan(instance.__class__)
    if not getattr(writer, "_record_entries", True) and plan.can_fast_pack and not section and eff_spec is None:
        st = plan.fast_struct_little if active_endian == Endian.LITTLE else plan.fast_struct_big
        if st is not None:
            vals = tuple(getattr(instance, fn) for fn in plan.fast_field_names)
            writer._stream.write(st.pack(*vals))
            return writer

    total_bits = meta.get("bits")
    if isinstance(total_bits, int):
        _write_bitfield(
            instance,
            writer,
            active_endian,
            total_bits,
            field_name=parent_field_name or instance.__class__.__name__,
            parent_struct=current_struct_name,
            desc=desc,
            struct_doc=struct_doc,
        )
        return writer

    fields = meta.get("fields", {})
    descriptions = meta.get("descriptions", {})
    deferred_offsets: list[Any] = []

    # Pre-resolve dynamic counts for OffsetTable fields if omitted (0 or None)
    for f_name, f_type in fields.items():
        f_val = getattr(instance, f_name, None)
        is_dir_tbl = (isinstance(f_type, tuple) and len(f_type) >= 2 and f_type[0] is OffsetTable) or get_origin(f_type) is OffsetTable
        if is_dir_tbl:
            cnt = f_type[1] if isinstance(f_type, tuple) else get_args(f_type)[0]
            if isinstance(cnt, str) and hasattr(instance, cnt):
                if (getattr(instance, cnt) == 0 or getattr(instance, cnt) is None) and isinstance(f_val, (list, tuple)) and len(f_val) > 0:
                    try:
                        setattr(instance, cnt, len(f_val))
                    except Exception:
                        pass
        is_off_tbl = (isinstance(f_type, tuple) and len(f_type) >= 2 and f_type[0] is Offset) or get_origin(f_type) is Offset
        if is_off_tbl:
            t_type = f_type[1] if isinstance(f_type, tuple) else (get_args(f_type)[0] if get_args(f_type) else None)
            if _is_offset_table_spec(t_type):
                cnt = t_type[1] if isinstance(t_type, tuple) and len(t_type) >= 2 else (get_args(t_type)[0] if get_args(t_type) else None)
                if isinstance(cnt, str) and hasattr(instance, cnt):
                    if (getattr(instance, cnt) == 0 or getattr(instance, cnt) is None) and isinstance(f_val, (list, tuple)) and len(f_val) > 0:
                        try:
                            setattr(instance, cnt, len(f_val))
                        except Exception:
                            pass

    for name, ftype in fields.items():
        val = getattr(instance, name, None)
        f_desc = descriptions.get(name, "")

        # Unwrap Annotated[T, description] if used
        if get_origin(ftype) is Annotated:
            args = get_args(ftype)
            if not f_desc:
                for arg in args[1:]:
                    if isinstance(arg, str):
                        f_desc = arg
                        break
            ftype = args[0]

        # Automatic alignment padding before field
        if align_setting is not None or auto_align:
            field_align = _get_field_alignment(ftype, val)
            req_align = min(field_align, align_setting) if align_setting else field_align
            if req_align > 1:
                cur_pos = writer.tell()
                rem = cur_pos % req_align
                if rem != 0:
                    pad_len = req_align - rem
                    writer.pad(pad_len, name="padding", desc="Alignment padding")

        # Check Offset[T, OffsetType, BaseOffset]
        is_offset = (
            (isinstance(ftype, tuple) and len(ftype) >= 1 and ftype[0] is Offset and not _is_named_offset_spec(ftype))
            or (get_origin(ftype) is Offset and not _is_named_offset_spec(ftype))
        )
        if is_offset:
            target = val.target if isinstance(val, Offset) else val
            target_name = ""
            offset_t = UInt32
            base_offset = 0
            if isinstance(ftype, tuple):
                if len(ftype) >= 2:
                    t_arg = ftype[1]
                    target_name = t_arg.__name__ if hasattr(t_arg, "__name__") else str(t_arg)
                offset_t, base_offset = _parse_offset_spec_args(ftype[2:])
            elif get_args(ftype):
                args = get_args(ftype)
                t_arg = args[0]
                target_name = t_arg.__name__ if hasattr(t_arg, "__name__") else str(t_arg)
                offset_t, base_offset = _parse_offset_spec_args(args[1:])

            fmt_char, offset_size, offset_label = _normalize_offset_type(offset_t)
            if offset_label != "UInt32":
                type_label = f"Offset[{target_name}, {offset_label}]" if target_name else f"Offset[{offset_label}]"
            else:
                type_label = f"Offset[{target_name}]" if target_name else "Offset"

            offset_placeholder_idx = len(writer._entries) if hasattr(writer, "_entries") else -1
            placeholder_pos = writer.tell()
            actual_base = _resolve_base_offset(base_offset, struct_start_pos, placeholder_pos)

            if _is_offset_table_spec(t_arg):
                if isinstance(t_arg, tuple):
                    tbl_count = t_arg[1] if len(t_arg) >= 2 else 0
                    tbl_offset_t, tbl_base_offset = _parse_offset_spec_args(t_arg[2:])
                else:
                    tbl_args = get_args(t_arg)
                    tbl_count = tbl_args[0] if len(tbl_args) >= 1 else 0
                    tbl_offset_t, tbl_base_offset = _parse_offset_spec_args(tbl_args[1:])

                type_label = f"Offset[OffsetTable[{tbl_count}]]"
                target_list = target if isinstance(target, (list, tuple)) else ([] if target is None else [target])

                if isinstance(tbl_count, str) and hasattr(instance, tbl_count):
                    cur_v = getattr(instance, tbl_count)
                    if (cur_v == 0 or cur_v is None) and len(target_list) > 0:
                        try:
                            setattr(instance, tbl_count, len(target_list))
                        except Exception:
                            pass

                writer._pack_write(fmt_char, 0, endian=active_endian, name=name, desc=f_desc, struct_name=current_struct_name, struct_doc=struct_doc)
                if offset_placeholder_idx >= 0 and offset_placeholder_idx < len(writer._entries):
                    writer._entries[offset_placeholder_idx].type_name = type_label
                deferred_offsets.append((
                    "offset_to_table",
                    offset_placeholder_idx,
                    placeholder_pos,
                    t_arg,
                    target_list,
                    active_endian,
                    fmt_char,
                    actual_base,
                    name,
                    f_desc,
                ))
                continue

            if target is None:
                writer._pack_write(fmt_char, 0, endian=active_endian, name=name, desc=f_desc, struct_name=current_struct_name, struct_doc=struct_doc)
            elif isinstance(target, int):
                stored_val = target - actual_base
                if stored_val < 0 and fmt_char in ("B", "H", "I", "Q"):
                    raise ValueError(f"Offset value {stored_val} is negative (target={target}, base={actual_base})")
                writer._pack_write(fmt_char, stored_val, endian=active_endian, name=name, desc=f_desc, struct_name=current_struct_name, struct_doc=struct_doc)
                if offset_placeholder_idx >= 0 and offset_placeholder_idx < len(writer._entries):
                    writer._entries[offset_placeholder_idx].type_name = type_label
                    writer._entries[offset_placeholder_idx].target_offset = target
            elif hasattr(target, "__binary__"):
                writer._pack_write(fmt_char, 0, endian=active_endian, name=name, desc=f_desc, struct_name=current_struct_name, struct_doc=struct_doc)
                if offset_placeholder_idx >= 0 and offset_placeholder_idx < len(writer._entries):
                    writer._entries[offset_placeholder_idx].type_name = type_label
                deferred_offsets.append((offset_placeholder_idx, placeholder_pos, target, active_endian, fmt_char, actual_base))
            else:
                raise TypeError(f"Offset field {name} expected binary_struct, OffsetTable, or int, got {type(target).__name__}")
            continue

        # Check key-based Offset[Key, TargetType, OffsetType, BaseOffset]
        is_named_offset = _is_named_offset_spec(ftype)
        if is_named_offset:
            key_arg, target_type, offset_t, base_offset = _extract_named_offset_info(ftype)
            key_name = normalize_offset_key(key_arg)

            fmt_char, offset_size, offset_label = _normalize_offset_type(offset_t)
            qualified_key = writer._qualify_name(key_name) if hasattr(writer, "_qualify_name") else key_name
            target_str = ""
            if target_type is not None:
                t_name = getattr(target_type, "__name__", str(target_type))
                target_str = f", {t_name}"
            if offset_label != "UInt32":
                type_label = f"Offset[{qualified_key!r}{target_str}, {offset_label}]"
            elif target_str:
                type_label = f"Offset[{qualified_key!r}{target_str}]"
            else:
                type_label = f"Offset[{qualified_key!r}]"

            offset_placeholder_idx = len(writer._entries) if hasattr(writer, "_entries") else -1
            placeholder_pos = writer.tell()
            actual_base = _resolve_base_offset(base_offset, struct_start_pos, placeholder_pos)

            writer._pack_write(fmt_char, 0, endian=active_endian, name=name, desc=f_desc, struct_name=current_struct_name, struct_doc=struct_doc)
            if offset_placeholder_idx >= 0 and offset_placeholder_idx < len(writer._entries):
                writer._entries[offset_placeholder_idx].type_name = type_label

            target_val = val if (val is not None and hasattr(val, "__binary__")) else None
            if hasattr(writer, "_register_named_offset_slot"):
                writer._register_named_offset_slot(
                    key_name,
                    placeholder_pos=placeholder_pos,
                    fmt_char=fmt_char,
                    endian=active_endian,
                    actual_base=actual_base,
                    entry_idx=offset_placeholder_idx,
                    target_obj=target_val,
                )
            continue

        # Check OffsetTable[Count, OffsetType]
        is_offset_table = (
            (isinstance(ftype, tuple) and len(ftype) >= 2 and ftype[0] is OffsetTable)
            or (get_origin(ftype) is OffsetTable)
        )
        if is_offset_table:
            if isinstance(ftype, tuple):
                count = ftype[1]
                offset_t, base_offset = _parse_offset_spec_args(ftype[2:])
            else:
                args = get_args(ftype)
                count = args[0]
                offset_t, base_offset = _parse_offset_spec_args(args[1:])

            repeat_spec = count if isinstance(count, str) else None
            actual_count = count
            if isinstance(count, str):
                if isinstance(val, (list, tuple)) and len(val) > 0:
                    actual_count = len(val)
                elif val is not None and hasattr(val, "_targets") and isinstance(val._targets, (list, tuple)) and len(val._targets) > 0:
                    actual_count = len(val._targets)
                elif hasattr(instance, count) and isinstance(getattr(instance, count), int) and getattr(instance, count) > 0:
                    actual_count = getattr(instance, count)
                else:
                    actual_count = 1

            offset_size = offset_t._size if hasattr(offset_t, "_size") else 4
            placeholder_pos = writer.tell()
            actual_base = _resolve_base_offset(base_offset, struct_start_pos, placeholder_pos)
            table_handle = writer.write_offset_table(
                count=actual_count,
                offset_size=offset_size,
                endian=active_endian,
                name=name,
                desc=f_desc,
                base_offset=actual_base,
                spec_count=repeat_spec,
                struct_name=current_struct_name,
            )
            tbl_target_list: Any = val if isinstance(val, (list, tuple)) else (getattr(val, "_targets", None) if val is not None else None)
            if tbl_target_list is not None:
                for i, target_item in enumerate(tbl_target_list):
                    if i < actual_count:
                        if hasattr(target_item, "__binary__"):
                            deferred_offsets.append(("table_entry", table_handle, i, target_item, active_endian))
                        elif isinstance(target_item, int):
                            table_handle.set_offset(i, target_item)
                table_handle._targets = list(tbl_target_list)
            try:
                setattr(instance, name, table_handle)
            except Exception:
                pass
            continue

        # Check Variant[tag_field, mapping]
        is_variant = (
            (isinstance(ftype, tuple) and len(ftype) >= 3 and ftype[0] is Variant)
            or (get_origin(ftype) is Variant)
        )
        if is_variant:
            _tag_field = ftype[1] if isinstance(ftype, tuple) else get_args(ftype)[0]
            mapping = ftype[2] if isinstance(ftype, tuple) else get_args(ftype)[1]
            var_list = [(k, v, getattr(v, "__doc__", "") or "") for k, v in mapping.items()]
            if hasattr(writer, "_current_caption_variants") and writer._current_caption_variants is None:
                writer._current_caption_variants = var_list
            if hasattr(writer, "_variants"):
                v_entry = {
                    "name": name,
                    "tag_field": _tag_field,
                    "variants": var_list,
                    "desc": f_desc,
                }
                if v_entry not in writer._variants:
                    writer._variants.append(v_entry)
                if hasattr(writer, "_elements_log"):
                    writer._elements_log.append(("choice", v_entry))
            for v in mapping.values():
                if hasattr(writer, "_struct_classes") and v not in writer._struct_classes:
                    writer._struct_classes.append(v)
            target_obj = val.value if isinstance(val, Variant) else val
            if hasattr(target_obj, "__binary__"):
                write_struct(
                    target_obj,
                    writer=writer,
                    endian=active_endian,
                    parent_field_name=name,
                    parent_struct_name=current_struct_name,
                    desc=f_desc,
                )
            elif isinstance(target_obj, (bytes, bytearray, memoryview)):
                writer.write_bytes(bytes(target_obj), name=name, desc=f_desc)
            continue

        # Check FixedArray[T, N]
        is_fixed = (
            (isinstance(ftype, tuple) and len(ftype) >= 3 and ftype[0] is FixedArray)
            or (get_origin(ftype) is FixedArray)
        )
        if is_fixed:
            if isinstance(ftype, tuple):
                elem_t, count = ftype[1], ftype[2]
            else:
                args = get_args(ftype)
                elem_t, count = args[0], args[1]
            elem_name = elem_t.__name__ if hasattr(elem_t, "__name__") else str(elem_t)
            start_p = writer.tell()
            _write_fixed_array(name, elem_t, count, val, writer, active_endian)
            if hasattr(writer, "_record_entry"):
                writer._record_entry(
                    offset=start_p,
                    size=writer.tell() - start_p,
                    type_name=f"FixedArray[{elem_name}, {count}]",
                    value=val,
                    name=name,
                    endian=active_endian.name.capitalize(),
                    description=f_desc,
                    struct_name=current_struct_name,
                    struct_doc=struct_doc,
                )
            continue

        # Check Array[T]
        is_arr = (
            (isinstance(ftype, tuple) and len(ftype) >= 2 and ftype[0] is Array)
            or (get_origin(ftype) is Array)
        )
        if is_arr:
            elem_t = ftype[1] if isinstance(ftype, tuple) else get_args(ftype)[0]
            elem_name = elem_t.__name__ if hasattr(elem_t, "__name__") else str(elem_t)
            start_p = writer.tell()
            _write_array(name, elem_t, val, writer, active_endian)
            if hasattr(writer, "_record_entry"):
                writer._record_entry(
                    offset=start_p,
                    size=writer.tell() - start_p,
                    type_name=f"Array[{elem_name}]",
                    value=val,
                    name=name,
                    endian=active_endian.name.capitalize(),
                    description=f_desc,
                    struct_name=current_struct_name,
                    struct_doc=struct_doc,
                )
            continue

        # Check Compressed
        if isinstance(ftype, type) and issubclass(ftype, CompressedBase):
            algo = getattr(ftype, "_algo", "zlib")
            if val is not None and hasattr(val, "to_bytes"):
                raw_bytes = val.to_bytes()
            elif isinstance(val, (bytes, bytearray, memoryview)):
                raw_bytes = bytes(val)
            elif val is None:
                raw_bytes = b""
            else:
                raw_bytes = bytes(val)
            comp_bytes = compress_data(raw_bytes, algo=algo)
            writer._pack_write("I", len(comp_bytes), endian=active_endian, name=f"{name}_len", desc=f"Compressed length ({algo})")
            writer.write_bytes(comp_bytes, name=name, desc=f_desc or f"Compressed[{algo}]")
            if hasattr(writer, "_entries") and writer._entries:
                writer._entries[-1].type_name = repr(ftype)
            continue

        # Check nested binary_struct
        if hasattr(val, "__binary__"):
            write_struct(
                val,
                writer=writer,
                endian=active_endian,
                parent_field_name=name,
                parent_struct_name=current_struct_name,
                desc=f_desc,
            )
            continue

        # Check Bool type
        if ftype is Bool or (isinstance(ftype, type) and issubclass(ftype, Bool)):
            writer.write_bool(
                bool(val) if val is not None else False,
                size=ftype._size,
                endian=active_endian,
                name=name,
                desc=f_desc,
                struct_name=current_struct_name,
                struct_doc=struct_doc,
            )
            continue

        # Check FixedString type
        if isinstance(ftype, type) and issubclass(ftype, FixedString):
            s_val = str(val) if val is not None else ""
            enc = getattr(ftype, "encoding", "utf-8")
            pad = getattr(ftype, "pad_byte", b"\x00")
            writer.write_fixed_string(s_val, length=ftype._size, pad_byte=pad, encoding=enc, name=name, desc=f_desc)
            continue

        # Check Bytes type
        if isinstance(ftype, type) and issubclass(ftype, Bytes):
            b_val = bytes(val) if val is not None else b""
            if ftype._size > 0:
                if len(b_val) < ftype._size:
                    b_val = b_val.ljust(ftype._size, b"\x00")
                elif len(b_val) > ftype._size:
                    b_val = b_val[:ftype._size]
            writer.write_bytes(b_val, name=name, desc=f_desc)
            if hasattr(writer, "_entries") and writer._entries and ftype._size > 0:
                writer._entries[-1].type_name = f"Bytes[{ftype._size}]"
            continue

        # Check CString type
        if ftype is CString or (isinstance(ftype, type) and issubclass(ftype, CString)):
            s_val = str(val) if val is not None else ""
            enc = getattr(ftype, "encoding", "utf-8")
            writer.write_cstring(s_val, encoding=enc, name=name, desc=f_desc)
            continue

        # Check PrefixedString type
        if ftype is PrefixedString or (isinstance(ftype, type) and issubclass(ftype, PrefixedString)):
            s_val = str(val) if val is not None else ""
            p_bytes = getattr(ftype, "prefix_bytes", 1)
            enc = getattr(ftype, "encoding", "utf-8")
            writer.write_prefixed_string(s_val, prefix_bytes=p_bytes, endian=active_endian, encoding=enc, name=name, desc=f_desc)
        # Check Magic type
        if isinstance(ftype, type) and issubclass(ftype, MagicBase):
            expected = getattr(ftype, "_value", None)
            write_val = val if val is not None else getattr(ftype, "_raw_val", expected)
            if isinstance(expected, bytes):
                b_val = bytes(write_val) if isinstance(write_val, (bytes, bytearray)) else (write_val.encode("utf-8") if isinstance(write_val, str) else bytes(expected or b""))
                writer.write_bytes(b_val, name=name, desc=f_desc)
                if hasattr(writer, "_entries") and writer._entries:
                    writer._entries[-1].type_name = f"Magic[{getattr(ftype, '_raw_val', '')!r}]"
            else:
                fmt_char = getattr(ftype, "_fmt", "I")
                writer._pack_write(fmt_char, write_val, endian=active_endian, name=name, desc=f_desc, struct_name=current_struct_name, struct_doc=struct_doc)
                if hasattr(writer, "_entries") and writer._entries:
                    writer._entries[-1].type_name = f"Magic[{getattr(ftype, '_raw_val', '')!r}]"
            continue

        # Check Constant type
        if isinstance(ftype, type) and issubclass(ftype, ConstantBase):
            target_t = getattr(ftype, "_type", UInt32)
            c_val = val if val is not None else getattr(ftype, "_value", None)
            fmt_char = getattr(target_t, "_fmt", "I")
            writer._pack_write(fmt_char, c_val, endian=active_endian, name=name, desc=f_desc, struct_name=current_struct_name, struct_doc=struct_doc)
            if hasattr(writer, "_entries") and writer._entries:
                writer._entries[-1].type_name = f"Constant[{getattr(target_t, '__name__', str(target_t))}, {getattr(ftype, '_value', '')!r}]"
            continue

        # Check Range constraint
        if isinstance(ftype, type) and issubclass(ftype, RangeBase):
            min_v = ftype._min
            max_v = ftype._max
            val_to_check = val if val is not None else 0
            if not (min_v <= val_to_check <= max_v):
                raise RangeValidationError(name, val_to_check, min_v, max_v)
            fmt = getattr(ftype, "_fmt", "")
            if fmt:
                writer._pack_write(fmt, val_to_check, endian=active_endian, name=name, desc=f_desc or f"Range: [{min_v}, {max_v}]", struct_name=current_struct_name, struct_doc=struct_doc)
                if hasattr(writer, "_entries") and writer._entries:
                    writer._entries[-1].type_name = repr(ftype)
            continue

        # Check LengthOf / CountOf
        if isinstance(ftype, type) and issubclass(ftype, (LengthOfBase, CountOfBase)):
            target_name = getattr(ftype, "_target", "")
            delta = getattr(ftype, "_delta", 0)
            target_obj = getattr(instance, target_name, None) if instance is not None else None
            calculated_val = 0
            if target_obj is not None:
                if issubclass(ftype, CountOfBase):
                    try:
                        calculated_val = len(target_obj) + delta
                    except Exception:
                        calculated_val = delta
                else:
                    if hasattr(target_obj, "__binary__"):
                        calculated_val = sizeof(target_obj) + delta
                    elif isinstance(target_obj, (bytes, bytearray, memoryview)):
                        calculated_val = len(target_obj) + delta
                    elif isinstance(target_obj, str):
                        calculated_val = len(target_obj.encode("utf-8")) + delta
                    elif isinstance(target_obj, list):
                        calculated_val = sum(sizeof(x) if hasattr(x, "__binary__") else (len(x) if isinstance(x, (bytes, bytearray, str)) else getattr(x, "_size", 1)) for x in target_obj) + delta
                    else:
                        calculated_val = delta

            write_val = calculated_val if (val is None or val == 0) else val
            try:
                setattr(instance, name, write_val)
            except Exception:
                pass
            fmt_char = getattr(ftype, "_fmt", "H")
            kind_str = "Count" if issubclass(ftype, CountOfBase) else "Length"
            writer._pack_write(fmt_char, write_val, endian=active_endian, name=name, desc=f_desc or f"{kind_str} of '{target_name}'", struct_name=current_struct_name, struct_doc=struct_doc)
            if hasattr(writer, "_entries") and writer._entries:
                writer._entries[-1].type_name = repr(ftype)
            continue

        # Check ChecksumBase type
        if isinstance(ftype, type) and issubclass(ftype, ChecksumBase):
            current_all = writer.to_bytes()
            cur_pos = writer.tell()
            brange = getattr(ftype, "_range", None)
            start_idx = struct_start_pos if (brange is None or brange.start is None) else brange.start
            end_idx = cur_pos if (brange is None or brange.stop is None) else brange.stop
            covered_bytes = current_all[start_idx:end_idx]
            calculated_val = compute_checksum(ftype._algorithm, covered_bytes)
            size = ftype._size
            fmt_char = {1: "B", 2: "H", 4: "I", 8: "Q"}.get(size, "I")
            writer._pack_write(fmt_char, calculated_val, endian=active_endian, name=name, desc=f_desc or f"{ftype._algorithm.upper()} Checksum", struct_name=current_struct_name, struct_doc=struct_doc)
            if hasattr(writer, "_entries") and writer._entries:
                writer._entries[-1].type_name = ftype.__name__
            try:
                setattr(instance, name, calculated_val)
            except Exception:
                pass
            continue


        # Check VarInt / VarUInt types
        if isinstance(ftype, VarIntTypeMeta):
            num_val = val if val is not None else 0
            if ftype.is_signed:
                writer.write_varint(num_val, name=name, desc=f_desc)
            else:
                writer.write_varuint(num_val, name=name, desc=f_desc)
            continue

        # Check Enum / BinaryEnum types
        is_enum = False
        enum_cls = None
        enum_size = 4
        if isinstance(ftype, tuple) and len(ftype) >= 2 and isinstance(ftype[0], type) and issubclass(ftype[0], enum.Enum):
            is_enum = True
            enum_cls = ftype[0]
            enum_size = getattr(ftype[1], "_size", 4)
        elif isinstance(ftype, type) and issubclass(ftype, enum.Enum):
            is_enum = True
            enum_cls = ftype
            max_v = max([abs(m.value) for m in enum_cls], default=0)
            enum_size = 1 if max_v <= 255 else (2 if max_v <= 65535 else 4)

        if is_enum and enum_cls is not None:
            int_val = val.value if isinstance(val, enum.Enum) else (int(val) if val is not None else 0)
            fmt_char = {1: "B", 2: "H", 4: "I", 8: "Q"}.get(enum_size, "I")
            writer._pack_write(fmt_char, int_val, endian=active_endian, name=name, desc=f_desc or f"Enum {enum_cls.__name__}", struct_name=current_struct_name, struct_doc=struct_doc)
            if hasattr(writer, "_entries") and writer._entries:
                writer._entries[-1].type_name = f"Enum[{enum_cls.__name__}]"
            continue

        # Check primitive BinaryType
        if isinstance(ftype, type) and issubclass(ftype, BinaryType):
            fmt = ftype._fmt
            if fmt:
                writer._pack_write(fmt, val, endian=active_endian, name=name, desc=f_desc, struct_name=current_struct_name, struct_doc=struct_doc)
            continue

        # Standard Python types fallback
        if ftype is int or (isinstance(val, int) and not isinstance(val, bool)):
            writer._pack_write("I", val, endian=active_endian, name=name, desc=f_desc, struct_name=current_struct_name, struct_doc=struct_doc)
        elif ftype is float or isinstance(val, float):
            writer._pack_write("f", val, endian=active_endian, name=name, desc=f_desc, struct_name=current_struct_name, struct_doc=struct_doc)
        elif ftype is bool or isinstance(val, bool):
            writer.write_bool(bool(val) if val is not None else False, name=name, desc=f_desc)
        elif ftype is bytes or isinstance(val, (bytes, bytearray)):
            writer.write_bytes(bytes(val) if val is not None else b"", name=name, desc=f_desc)
        elif ftype is str or isinstance(val, str):
            writer.write_cstring(str(val) if val is not None else "", name=name, desc=f_desc)
        else:
            raise TypeError(f"Unsupported field type for {name}: {ftype}")

    # Struct size alignment padding
    if align_setting is not None or auto_align:
        struct_boundary = align_setting if align_setting else plan.max_field_align
        if struct_boundary > 1:
            cur_pos = writer.tell()
            rem = cur_pos % struct_boundary
            if rem != 0:
                pad_len = struct_boundary - rem
                writer.pad(pad_len, name="alignment_pad", desc="Struct size alignment")

    # Struct total_size padding
    total_size_setting = meta.get("total_size")
    if total_size_setting is not None:
        cur_written = writer.tell() - struct_start_pos
        if cur_written > total_size_setting:
            raise TotalSizeExceededError(
                f"Struct {current_struct_name} serialized size ({cur_written}B) exceeds declared total_size ({total_size_setting}B)"
            )
        elif cur_written < total_size_setting:
            pad_b = meta.get("pad_byte", b"\x00")
            if isinstance(pad_b, int):
                pad_b = bytes([pad_b])
            pad_len = total_size_setting - cur_written
            writer.write_bytes(
                pad_b * pad_len,
                name="_padding",
                desc=f"Padding to total_size={total_size_setting}B",
            )
            if hasattr(writer, "_entries") and writer._entries:
                writer._entries[-1].struct_name = current_struct_name
                writer._entries[-1].struct_doc = struct_doc

    # Process deferred offset target objects
    for item in deferred_offsets:
        if isinstance(item, tuple) and len(item) == 5 and item[0] == "table_entry":
            _, table_handle, idx, target_obj, off_endian = item
            target_pos = writer.tell()
            write_struct(target_obj, writer=writer, endian=off_endian)
            table_handle.set_offset(idx, target_pos)
        elif isinstance(item, tuple) and len(item) == 6:
            offset_placeholder_idx, placeholder_pos, target_obj, off_endian, fmt_char, actual_base = item
            target_pos = writer.tell()
            write_struct(target_obj, writer=writer, endian=off_endian)
            return_pos = writer.tell()
            stored_val = target_pos - actual_base
            if stored_val < 0 and fmt_char in ("B", "H", "I", "Q"):
                raise ValueError(f"Offset value {stored_val} is negative (target={target_pos}, base={actual_base})")
            writer.seek(placeholder_pos)
            order = normalize_endian(off_endian)
            writer._stream.write(struct.pack(f"{order.value}{fmt_char}", stored_val))
            writer.seek(return_pos)
            if hasattr(writer, "_entries") and 0 <= offset_placeholder_idx < len(writer._entries):
                writer._entries[offset_placeholder_idx].value = stored_val
                writer._entries[offset_placeholder_idx].target_offset = target_pos
        elif isinstance(item, tuple) and len(item) >= 8 and item[0] == "offset_to_table":
            (
                _,
                offset_placeholder_idx,
                placeholder_pos,
                t_arg,
                target_list,
                off_endian,
                fmt_char,
                actual_base,
                field_name,
                f_desc,
            ) = item[:10]

            if isinstance(t_arg, tuple):
                tbl_count = t_arg[1] if len(t_arg) >= 2 else len(target_list)
                tbl_offset_t, tbl_base_offset = _parse_offset_spec_args(t_arg[2:])
            else:
                tbl_args = get_args(t_arg)
                tbl_count = tbl_args[0] if len(tbl_args) >= 1 else len(target_list)
                tbl_offset_t, tbl_base_offset = _parse_offset_spec_args(tbl_args[1:])

            actual_count = len(target_list)
            if isinstance(tbl_count, int):
                actual_count = tbl_count
            elif isinstance(tbl_count, str) and hasattr(instance, tbl_count):
                cnt_val = getattr(instance, tbl_count)
                if isinstance(cnt_val, int) and cnt_val > 0:
                    actual_count = cnt_val

            # 1. Backpatch the offset pointing to the table
            table_pos = writer.tell()
            stored_val = table_pos - actual_base
            if stored_val < 0 and fmt_char in ("B", "H", "I", "Q"):
                raise ValueError(f"Offset value {stored_val} is negative (table_pos={table_pos}, base={actual_base})")

            return_pos = writer.tell()
            writer.seek(placeholder_pos)
            order = normalize_endian(off_endian)
            writer._stream.write(struct.pack(f"{order.value}{fmt_char}", stored_val))
            writer.seek(return_pos)
            if hasattr(writer, "_entries") and 0 <= offset_placeholder_idx < len(writer._entries):
                writer._entries[offset_placeholder_idx].value = stored_val
                writer._entries[offset_placeholder_idx].target_offset = table_pos

            # 2. Write the offset table at current position (table_pos)
            tbl_fmt_char, tbl_offset_size, _ = _normalize_offset_type(tbl_offset_t)
            actual_table_base = _resolve_base_offset(tbl_base_offset, table_pos, table_pos)

            table_handle = writer.write_offset_table(
                count=actual_count,
                offset_size=tbl_offset_size,
                endian=off_endian,
                name=f"{field_name}_table",
                desc=f_desc,
                base_offset=actual_table_base,
                spec_count=tbl_count if isinstance(tbl_count, str) else None,
                struct_name=current_struct_name,
            )

            # 3. Write child targets and record their offsets in table_handle
            for idx in range(actual_count):
                if idx < len(target_list):
                    t_item = target_list[idx]
                    if hasattr(t_item, "__binary__"):
                        item_pos = writer.tell()
                        write_struct(t_item, writer=writer, endian=off_endian)
                        table_handle.set_offset(idx, item_pos)
                    elif isinstance(t_item, int):
                        table_handle.set_offset(idx, t_item)

    return writer


def read_struct(
    cls: type[T],
    reader: Optional[Any] = None,
    endian: Optional[EndianType] = None,
) -> T:
    """Deserialize a @binary_struct class from a BinaryReader, bytes, or stream.

    Args:
        cls: The @binary_struct class to instantiate.
        reader: A BinaryReader instance, bytes/bytearray, file path, or stream.
        endian: Optional endianness override.

    Returns:
        Deserialized instance of `cls`.
    """
    from binary_master.reader import BinaryReader

    meta = getattr(cls, "__binary__", None)
    if meta is None:
        raise TypeError(f"Class {getattr(cls, '__name__', str(cls))} is not a binary_struct")

    if reader is None:
        raise ValueError("A reader or bytes data must be provided to read_struct")

    plan = get_struct_plan(cls)
    active_endian = normalize_endian(endian or plan.endian)

    # 1. Fast path for plain primitive structs
    if plan.can_fast_unpack and plan.fast_struct_little is not None and plan.fast_struct_big is not None:
        st = plan.fast_struct_little if active_endian == Endian.LITTLE else plan.fast_struct_big
        if isinstance(reader, (bytes, bytearray, memoryview)):
            raw_b = bytes(reader) if not isinstance(reader, bytes) else reader
            if len(raw_b) >= plan.total_fixed_size:
                vals = st.unpack_from(raw_b, 0)
                return cls(*vals)
        elif isinstance(reader, BinaryReader) and (not hasattr(reader, "_bit_reader") or reader._bit_reader is None):
            if reader.remaining() >= plan.total_fixed_size:
                raw = reader._read_exact(plan.total_fixed_size)
                vals = st.unpack(raw)
                return cls(*vals)

    if not isinstance(reader, BinaryReader):
        reader = BinaryReader(reader)

    struct_start_pos = reader.tell()

    # BitField handling
    if plan.is_bitfield:
        total_bits = plan.total_bits
        if total_bits is not None:
            if total_bits <= 8:
                packed_value = reader.read_uint8()
            elif total_bits <= 16:
                packed_value = reader.read_uint16(endian=active_endian)
            elif total_bits <= 32:
                packed_value = reader.read_uint32(endian=active_endian)
            elif total_bits <= 64:
                packed_value = reader.read_uint64(endian=active_endian)
            else:
                num_bytes = (total_bits + 7) // 8
                raw = reader.read_bytes(num_bytes)
                byteorder: Literal["little", "big"] = "little" if active_endian == Endian.LITTLE else "big"
                packed_value = int.from_bytes(raw, byteorder=byteorder)

            fields = meta.get("fields", {})
            shift = 0
            bf_kwargs: dict[str, Any] = {}
            for name, ftype in fields.items():
                base_t = ftype[0] if isinstance(ftype, tuple) and len(ftype) >= 2 else ftype
                width = ftype[1] if isinstance(ftype, tuple) and len(ftype) >= 2 else 1
                mask = (1 << width) - 1
                val = (packed_value >> shift) & mask
                if base_t is Bool or (isinstance(base_t, type) and _safe_issubclass(base_t, Bool)) or base_t is bool:
                    bf_kwargs[name] = bool(val)
                else:
                    bf_kwargs[name] = val
                shift += width
            return cls(**bf_kwargs)

    kwargs: dict[str, Any] = {}
    known_counts: dict[str, int] = {}
    known_lengths: dict[str, int] = {}
    align_setting = plan.align_setting
    auto_align = plan.auto_align

    for fp in plan.field_plans:
        name = fp.name

        # Alignment
        if (align_setting is not None or auto_align) and fp.align > 1:
            req_align = min(fp.align, align_setting) if align_setting else fp.align
            if req_align > 1:
                reader.align(req_align)

        kind = fp.kind
        if kind == FieldKind.PRIMITIVE:
            kwargs[name] = reader._unpack_read(fp.fmt, fp.size, endian=active_endian)
        elif kind == FieldKind.BOOL:
            kwargs[name] = reader.read_bool(size=fp.size, endian=active_endian)
        elif kind == FieldKind.MAGIC:
            if fp.is_bytes_magic:
                read_b = reader.read_bytes(fp.size)
                if read_b != fp.expected:
                    raise InvalidMagicError(f"Magic mismatch for field '{name}': expected {fp.expected!r}, got {read_b!r}")
                kwargs[name] = read_b
            else:
                val = reader._unpack_read(fp.fmt, fp.size, endian=active_endian)
                if val != fp.raw_val:
                    raise InvalidMagicError(f"Magic mismatch for field '{name}': expected {fp.raw_val!r}, got {val!r}")
                kwargs[name] = val
        elif kind == FieldKind.CONSTANT:
            val = reader._unpack_read(fp.fmt, fp.size, endian=active_endian)
            if val != fp.expected:
                raise InvalidConstantError(f"Constant mismatch for field '{name}': expected {fp.expected!r}, got {val!r}")
            kwargs[name] = val
        elif kind == FieldKind.RANGE:
            val = reader._unpack_read(fp.fmt, fp.size, endian=active_endian)
            if not (fp.min_val <= val <= fp.max_val):
                raise RangeValidationError(name, val, fp.min_val, fp.max_val)
            kwargs[name] = val
        elif kind == FieldKind.LENGTH_OF or kind == FieldKind.COUNT_OF:
            val = reader._unpack_read(fp.fmt, fp.size, endian=active_endian)
            kwargs[name] = val
            if fp.target_name:
                if kind == FieldKind.COUNT_OF:
                    known_counts[fp.target_name] = val - fp.delta
                else:
                    known_lengths[fp.target_name] = val - fp.delta
        elif kind == FieldKind.CHECKSUM:
            cur_pos = reader.tell()
            brange = fp.checksum_range
            start_idx = struct_start_pos if (brange is None or brange.start is None) else brange.start
            end_idx = cur_pos if (brange is None or brange.stop is None) else brange.stop
            with reader.preserve_position():
                reader.seek(start_idx)
                covered_bytes = reader.read_bytes(end_idx - start_idx)
            algo = fp.checksum_algo
            calculated = compute_checksum(algo, covered_bytes)
            val = reader._unpack_read(fp.fmt, fp.size, endian=active_endian)
            if val != calculated:
                raise ChecksumMismatchError(f"Checksum mismatch for field '{name}': computed {hex(calculated)}, got {hex(val)} in stream")
            kwargs[name] = val
        elif kind == FieldKind.COMPRESSED:
            comp_len = reader._unpack_read("I", 4, endian=active_endian)
            comp_bytes = reader.read_bytes(comp_len)
            algo = fp.checksum_algo or "zlib"
            decomp_bytes = decompress_data(comp_bytes, algo=algo)
            target_t = fp.target_type
            if hasattr(target_t, "__binary__"):
                kwargs[name] = read_struct(target_t, reader=decomp_bytes, endian=active_endian)
            else:
                kwargs[name] = decomp_bytes
        elif kind == FieldKind.VARINT:
            if fp.varint_signed:
                kwargs[name] = reader.read_varint()
            else:
                kwargs[name] = reader.read_varuint()
        elif kind == FieldKind.ENUM:
            raw_val = reader._unpack_read(fp.fmt, fp.size, endian=active_endian)
            enum_type = fp.enum_cls
            try:
                kwargs[name] = enum_type(raw_val)
            except ValueError as exc:
                cls_n = getattr(enum_type, "__name__", str(enum_type))
                raise InvalidEnumError(f"Invalid enum value {raw_val} for {cls_n} in field '{name}'") from exc
        elif kind == FieldKind.NESTED_STRUCT:
            nested_type = cast(type, fp.nested_cls)
            kwargs[name] = read_struct(nested_type, reader=reader, endian=active_endian)
        elif kind == FieldKind.FIXED_STRING:
            kwargs[name] = reader.read_fixed_string(fp.size, pad_byte=fp.pad_byte, encoding=fp.encoding)
        elif kind == FieldKind.BYTES:
            explicit_len = known_lengths.get(name, known_counts.get(name))
            kwargs[name] = reader.read_bytes(explicit_len if explicit_len is not None else (fp.size if fp.size > 0 else None))
        elif kind == FieldKind.C_STRING:
            kwargs[name] = reader.read_cstring(encoding=fp.encoding)
        elif kind == FieldKind.PREFIXED_STRING:
            kwargs[name] = reader.read_prefixed_string(prefix_bytes=fp.prefix_bytes, endian=active_endian, encoding=fp.encoding)
        elif kind == FieldKind.FIXED_ARRAY:
            count = fp.count
            elem_t = cast(type, fp.elem_type)
            if fp.elem_is_bool:
                kwargs[name] = [reader.read_bool(size=fp.elem_bool_size, endian=active_endian) for _ in range(count)]
            elif fp.elem_is_uint8:
                kwargs[name] = reader.read_bytes(count)
            elif fp.elem_is_int8:
                kwargs[name] = [reader.read_int8() for _ in range(count)]
            elif fp.elem_is_primitive:
                kwargs[name] = [reader._unpack_read(fp.elem_fmt, fp.elem_size, endian=active_endian) for _ in range(count)]
            elif fp.elem_is_struct:
                kwargs[name] = [read_struct(elem_t, reader=reader, endian=active_endian) for _ in range(count)]
            else:
                kwargs[name] = reader.read_bytes(count)
        elif kind == FieldKind.ARRAY:
            elem_t = cast(type, fp.elem_type)
            explicit_count = known_counts.get(name)
            explicit_length = known_lengths.get(name)
            if explicit_count is not None:
                items: list[Any] = []
                for _ in range(explicit_count):
                    if fp.elem_is_bool:
                        items.append(reader.read_bool(size=fp.elem_bool_size, endian=active_endian))
                    elif fp.elem_is_uint8:
                        items.append(reader.read_uint8())
                    elif fp.elem_is_primitive:
                        items.append(reader._unpack_read(fp.elem_fmt, fp.elem_size, endian=active_endian))
                    elif fp.elem_is_struct:
                        items.append(read_struct(elem_t, reader=reader, endian=active_endian))
                    else:
                        items.append(reader.read_uint8())
                kwargs[name] = bytes(items) if fp.elem_is_uint8 else items
            elif explicit_length is not None:
                stop_pos = reader.tell() + explicit_length
                items_len: list[Any] = []
                while reader.tell() < stop_pos and reader.remaining() > 0:
                    if fp.elem_is_bool:
                        items_len.append(reader.read_bool(size=fp.elem_bool_size, endian=active_endian))
                    elif fp.elem_is_uint8:
                        items_len.append(reader.read_uint8())
                    elif fp.elem_is_primitive:
                        items_len.append(reader._unpack_read(fp.elem_fmt, fp.elem_size, endian=active_endian))
                    elif fp.elem_is_struct:
                        items_len.append(read_struct(elem_t, reader=reader, endian=active_endian))
                    else:
                        items_len.append(reader.read_uint8())
                kwargs[name] = bytes(items_len) if fp.elem_is_uint8 else items_len
            else:
                if fp.elem_is_bool:
                    b_size = fp.elem_bool_size
                    items_rem: list[Any] = []
                    while reader.remaining() >= b_size:
                        items_rem.append(reader.read_bool(size=b_size, endian=active_endian))
                    kwargs[name] = items_rem
                elif fp.elem_is_uint8:
                    kwargs[name] = reader.read_bytes()
                elif fp.elem_is_primitive:
                    items_rem_p: list[Any] = []
                    while reader.remaining() >= fp.elem_size:
                        items_rem_p.append(reader._unpack_read(fp.elem_fmt, fp.elem_size, endian=active_endian))
                    kwargs[name] = items_rem_p
                elif fp.elem_is_struct:
                    items_rem_s: list[Any] = []
                    while reader.remaining() > 0:
                        items_rem_s.append(read_struct(elem_t, reader=reader, endian=active_endian))
                    kwargs[name] = items_rem_s
                else:
                    kwargs[name] = reader.read_bytes()
        elif kind == FieldKind.OFFSET:
            target_type = fp.target_type
            off_info = cast(tuple, fp.offset_info)
            offset_t, base_offset, _, is_tbl = off_info
            field_pos = reader.tell()
            actual_base = _resolve_base_offset(base_offset, struct_start_pos, field_pos)
            stored_offset = reader._unpack_read(fp.fmt, fp.size, endian=active_endian)
            target_offset = stored_offset + actual_base

            if is_tbl:
                tbl_count = target_type[1] if isinstance(target_type, tuple) and len(target_type) >= 2 else (get_args(target_type)[0] if get_args(target_type) else 0)
                tbl_rest = target_type[2:] if isinstance(target_type, tuple) else get_args(target_type)[1:]
                tbl_offset_t, _ = _parse_offset_spec_args(tbl_rest)
                actual_count = kwargs.get(tbl_count) if isinstance(tbl_count, str) else tbl_count
                int_count = int(actual_count) if isinstance(actual_count, (int, float, str)) else (len(actual_count) if isinstance(actual_count, (list, tuple)) else 0)
                tbl_fmt_char, tbl_offset_size, _ = _normalize_offset_type(tbl_offset_t)
                if target_offset > 0 and int_count > 0:
                    saved_pos = reader.tell()
                    reader.seek(target_offset)
                    kwargs[name] = [reader._unpack_read(tbl_fmt_char, tbl_offset_size, endian=active_endian) for _ in range(int_count)]
                    reader.seek(saved_pos)
                else:
                    kwargs[name] = []
                continue

            if isinstance(target_type, str):
                mod = sys.modules.get(cls.__module__)
                if mod and hasattr(mod, target_type):
                    target_type = getattr(mod, target_type)

            if target_type and hasattr(target_type, "__binary__") and target_offset > 0:
                saved_pos = reader.tell()
                reader.seek(target_offset)
                target_obj = read_struct(target_type, reader=reader, endian=active_endian)
                reader.seek(saved_pos)
                kwargs[name] = target_obj
            else:
                kwargs[name] = target_offset
        elif kind == FieldKind.NAMED_OFFSET:
            off_info = cast(tuple, fp.offset_info)
            _, _, offset_t, base_offset, _ = off_info
            target_type = fp.target_type
            field_pos = reader.tell()
            actual_base = _resolve_base_offset(base_offset, struct_start_pos, field_pos)
            stored_offset = reader._unpack_read(fp.fmt, fp.size, endian=active_endian)
            target_offset = stored_offset + actual_base

            if isinstance(target_type, str):
                mod = sys.modules.get(cls.__module__)
                if mod and hasattr(mod, target_type):
                    target_type = getattr(mod, target_type)

            if target_type and hasattr(target_type, "__binary__") and target_offset > 0:
                saved_pos = reader.tell()
                reader.seek(target_offset)
                target_obj = read_struct(target_type, reader=reader, endian=active_endian)
                reader.seek(saved_pos)
                kwargs[name] = target_obj
            else:
                kwargs[name] = target_offset
        elif kind == FieldKind.OFFSET_TABLE:
            off_info = cast(tuple, fp.offset_info)
            offset_t, base_offset, _ = off_info
            count = fp.count
            actual_count = kwargs.get(count) if isinstance(count, str) else count
            if actual_count is None:
                raise ValueError(f"Count field '{count}' must precede OffsetTable field '{name}' in struct definition")
            int_count = int(actual_count) if isinstance(actual_count, (int, float, str)) else (len(actual_count) if isinstance(actual_count, (list, tuple)) else 0)
            kwargs[name] = [reader._unpack_read(fp.fmt, fp.size, endian=active_endian) for _ in range(int_count)]
        elif kind == FieldKind.VARIANT:
            var_info = cast(tuple, fp.variant_info)
            tag_field, mapping = var_info
            tag_val = kwargs.get(tag_field)
            if tag_val is None:
                raise ValueError(f"Tag field '{tag_field}' must precede Variant field '{name}' in struct definition")
            target_cls = mapping.get(tag_val)
            if target_cls is None:
                raise ValueError(f"Unknown variant tag {tag_val!r} for field '{name}' (known tags: {list(mapping.keys())})")
            if hasattr(target_cls, "__binary__"):
                kwargs[name] = read_struct(target_cls, reader=reader, endian=active_endian)
            elif target_cls is bytes:
                kwargs[name] = reader.read_bytes()
            else:
                kwargs[name] = reader.read_bytes()
        elif kind == FieldKind.PYTHON_PRIMITIVE:
            ftype = fp.py_type
            if ftype is int:
                kwargs[name] = reader.read_uint32(endian=active_endian)
            elif ftype is float:
                kwargs[name] = reader.read_float32(endian=active_endian)
            elif ftype is bool:
                kwargs[name] = reader.read_bool()
            elif ftype is bytes:
                explicit_len = known_lengths.get(name, known_counts.get(name))
                kwargs[name] = reader.read_bytes(explicit_len)
            elif ftype is str:
                explicit_len = known_lengths.get(name)
                if explicit_len is not None:
                    kwargs[name] = reader.read_bytes(explicit_len).decode("utf-8", errors="replace")
                else:
                    kwargs[name] = reader.read_cstring()
            else:
                raise TypeError(f"Unsupported field type for {name}: {ftype}")

    # Struct size alignment padding
    if align_setting is not None or auto_align:
        struct_boundary = align_setting if align_setting else plan.max_field_align
        if struct_boundary > 1:
            reader.align(struct_boundary)

    # Struct total_size padding
    total_size_setting = plan.total_size
    if total_size_setting is not None:
        cur_read = reader.tell() - struct_start_pos
        if cur_read < total_size_setting:
            reader.skip(total_size_setting - cur_read)

    return cls(**kwargs)


def write_variant(
    data: Any,
    candidates: Union[list, dict, tuple],
    writer: Optional[Any] = None,
    tag_field: Optional[str] = None,
    name: str = "",
    desc: str = "",
    condition: Optional[str] = None,
    endian: EndianType = None,
    section: str = "",
    spec_count: Optional[Union[int, str, bool]] = None,
    repeat: Optional[Union[int, str, bool]] = None,
) -> Any:
    """Serialize a polymorphic variant struct with candidate validation into a BinaryWriter."""
    from binary_master.writer import BinaryWriter
    if writer is None:
        writer = BinaryWriter(default_endian=endian or Endian.LITTLE)
    eff_spec = spec_count if spec_count is not None else repeat
    writer.write_variant(
        data,
        candidates=candidates,
        tag_field=tag_field,
        name=name,
        desc=desc,
        condition=condition,
        endian=endian,
        section=section,
        spec_count=eff_spec,
    )
    return writer


#
