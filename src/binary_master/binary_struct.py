from __future__ import annotations

import inspect
import re
import sys
from dataclasses import dataclass
from typing import Annotated, Any, Generic, Optional, TypeVar, Union, get_args, get_origin, get_type_hints

from binary_master.enums import Endian, EndianType, normalize_endian

# ==========================================================
# Binary Primitive Types
# ==========================================================

class BinaryTypeMeta(type):
    @property
    def fmt(cls):
        return cls._fmt

    @property
    def size(cls):
        return cls._size


class BinaryType(metaclass=BinaryTypeMeta):
    _fmt = ""
    _size = 0


class UInt8(BinaryType):
    _fmt = "B"
    _size = 1


class UInt16(BinaryType):
    _fmt = "H"
    _size = 2


class UInt32(BinaryType):
    _fmt = "I"
    _size = 4


class UInt64(BinaryType):
    _fmt = "Q"
    _size = 8


class Int8(BinaryType):
    _fmt = "b"
    _size = 1


class Int16(BinaryType):
    _fmt = "h"
    _size = 2


class Int32(BinaryType):
    _fmt = "i"
    _size = 4


class Int64(BinaryType):
    _fmt = "q"
    _size = 8


class Float32(BinaryType):
    _fmt = "f"
    _size = 4


class Float64(BinaryType):
    _fmt = "d"
    _size = 8


# ==========================================================
# Generic Types
# ==========================================================

T = TypeVar("T")


class Offset(Generic[T]):
    """シリアライズ時に自動計算されるオフセット"""

    def __init__(self, target: Any = None, offset: Optional[int] = None):
        self.target = target
        self.offset = offset

    def __repr__(self) -> str:
        return f"Offset(target={self.target!r}, offset={self.offset!r})"


class Array(Generic[T]):
    """可変長配列"""

    def __class_getitem__(cls, item):
        return cls, item


class FixedArray(Generic[T]):
    """固定長配列"""

    def __class_getitem__(cls, args):
        element_type, count = args
        return cls, element_type, count


class Bits:

    def __class_getitem__(cls, width):
        return cls, width


class OffsetTable(Generic[T]):
    """オフセットテーブル型: OffsetTable[Count, OffsetType, BaseOffset] または OffsetTable[Count, OffsetType] または OffsetTable[Count]"""

    def __class_getitem__(cls, args):
        if isinstance(args, tuple):
            count = args[0]
            offset_t = args[1] if len(args) > 1 else UInt32
            base_offset = args[2] if len(args) > 2 else 0
        else:
            count = args
            offset_t = UInt32
            base_offset = 0
        return cls, count, offset_t, base_offset


class Variant(Generic[T]):
    """タグフィールドの値に応じて型が切り替わるバリアント型 (Tagged Union / Chunk Variants)"""

    def __init__(
        self,
        value: Any = None,
        *,
        tag_field: Optional[str] = None,
        mapping: Optional[dict[Any, type]] = None,
    ):
        self.value = value
        self.tag_field = tag_field
        self.mapping = mapping or {}

    def __class_getitem__(cls, args):
        if not isinstance(args, tuple) or len(args) < 2:
            raise TypeError("Variant requires [tag_field_name, {tag_value: StructClass, ...}]")
        tag_field, mapping = args[0], args[1]
        return cls, tag_field, mapping

    def __repr__(self) -> str:
        return f"Variant({self.value!r})"


# ==========================================================
# Description Extractor & binary_struct
# ==========================================================

def extract_field_descriptions(cls: type) -> dict[str, str]:
    """Extract field descriptions from Annotated type hints or source comments."""
    descriptions: dict[str, str] = {}

    # 1. Extract from typing.Annotated if present
    annotations = getattr(cls, "__annotations__", {})
    for name, ann in annotations.items():
        if get_origin(ann) is Annotated:
            args = get_args(ann)
            for arg in args[1:]:
                if isinstance(arg, str):
                    descriptions[name] = arg
                    break

    # 2. Extract from source code comments
    try:
        source = inspect.getsource(cls)
        lines = source.splitlines()
        prev_comment = ""
        for line in lines:
            stripped = line.strip()
            # Standalone comment above field
            if stripped.startswith("#") and not stripped.startswith("#:"):
                prev_comment = stripped.lstrip("#").strip()
                continue
            if stripped.startswith("#:"):
                prev_comment = stripped.lstrip("#:").strip()
                continue

            # Inline comment: field: Type ... # comment
            m = re.match(r"^\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*:[^#]*#(.*)$", line)
            if m:
                fname = m.group(1).strip()
                comment = m.group(2).strip()
                if fname not in descriptions and comment:
                    descriptions[fname] = comment
                prev_comment = ""
                continue

            # Field without inline comment but preceded by comment
            m2 = re.match(r"^\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*:", line)
            if m2:
                fname = m2.group(1).strip()
                if fname not in descriptions and prev_comment:
                    descriptions[fname] = prev_comment
                prev_comment = ""
            else:
                prev_comment = ""
    except Exception:
        pass

    return descriptions


class BinaryMetadata(dict):
    """Metadata container for binary_struct with lazy type hint and description resolution."""

    def __init__(self, cls, endian="little", bits=None, align=None, auto_align=False, doc=""):
        super().__init__({
            "endian": endian,
            "bits": bits,
            "align": align,
            "auto_align": auto_align,
            "doc": doc,
            "descriptions": {},
        })
        self._cls = cls
        self._fields = None
        self._descriptions = None
        try:
            self._fields = get_type_hints(cls)
            self["fields"] = self._fields
            self._descriptions = extract_field_descriptions(cls)
            self["descriptions"] = self._descriptions
        except NameError:
            pass

    def _resolve_fields(self):
        if self._fields is None:
            mod = sys.modules.get(self._cls.__module__)
            globalns = getattr(mod, "__dict__", None)
            try:
                self._fields = get_type_hints(self._cls, globalns=globalns)
                self["fields"] = self._fields
            except NameError:
                return getattr(self._cls, "__annotations__", {})
        return self._fields

    def _resolve_descriptions(self):
        if self._descriptions is None:
            self._descriptions = extract_field_descriptions(self._cls)
            self["descriptions"] = self._descriptions
        return self._descriptions

    def __getitem__(self, item):
        if item == "fields" and self._fields is None:
            return self._resolve_fields()
        if item == "descriptions" and self._descriptions is None:
            return self._resolve_descriptions()
        return super().__getitem__(item)

    def get(self, item, default=None):
        if item == "fields" and self._fields is None:
            return self._resolve_fields()
        if item == "descriptions" and self._descriptions is None:
            return self._resolve_descriptions()
        return super().get(item, default)

    def items(self):
        self._resolve_fields()
        self._resolve_descriptions()
        return super().items()

    def values(self):
        self._resolve_fields()
        self._resolve_descriptions()
        return super().values()


def to_bytes(self, endian: Optional[EndianType] = None) -> bytes:
    """Serialize this binary_struct instance to bytes."""
    writer = write_struct(self, endian=endian)
    return writer.to_bytes()


def from_bytes(cls, data: Union[bytes, bytearray], endian: Optional[EndianType] = None) -> Any:
    """Deserialize a @binary_struct instance from bytes."""
    return read_struct(cls, reader=data, endian=endian)


def binary_struct(cls=None, *, endian="little", bits=None, align=None, auto_align=False):

    def wrapper(target_cls):
        target_cls = dataclass(slots=True)(target_cls)
        doc = inspect.cleandoc(target_cls.__doc__) if target_cls.__doc__ else ""
        target_cls.__binary__ = BinaryMetadata(
            target_cls,
            endian=endian,
            bits=bits,
            align=align,
            auto_align=auto_align,
            doc=doc,
        )
        target_cls.to_bytes = to_bytes
        target_cls.from_bytes = classmethod(from_bytes)
        return target_cls

    if cls is not None:
        return wrapper(cls)
    return wrapper


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
        byteorder = "little" if endian == Endian.LITTLE else "big"
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
    if isinstance(elem_type, type) and issubclass(elem_type, BinaryType):
        data = struct.pack(f"{endian.value}{elem_type._fmt}", val)
        writer._stream.write(data)
    elif hasattr(val, "__binary__"):
        write_struct(val, writer=writer, endian=endian)
    elif isinstance(val, int):
        writer._stream.write(struct.pack("B", val))
    else:
        raise TypeError(f"Cannot serialize element of type {type(val).__name__}")


def _get_field_alignment(ftype: Any, val: Any = None) -> int:
    """Determine alignment requirement in bytes for a struct field."""
    if get_origin(ftype) is Annotated:
        ftype = get_args(ftype)[0]

    if isinstance(ftype, type) and issubclass(ftype, BinaryType):
        return min(ftype._size, 8)

    target = ftype if hasattr(ftype, "__binary__") else val
    if hasattr(target, "__binary__"):
        sub_align = target.__binary__.get("align")
        if sub_align:
            return sub_align
        total_bits = target.__binary__.get("bits")
        if total_bits is not None:
            if total_bits <= 8:
                return 1
            elif total_bits <= 16:
                return 2
            elif total_bits <= 32:
                return 4
            elif total_bits <= 64:
                return 8
            return 4
        sub_fields = target.__binary__.get("fields", {})
        sub_aligns = [_get_field_alignment(s_ft) for s_ft in sub_fields.values()]
        return max(sub_aligns, default=4)

    if ftype in (int, float) or isinstance(val, (int, float)):
        return 4
    if (isinstance(ftype, tuple) and len(ftype) >= 1 and ftype[0] is Offset) or get_origin(ftype) is Offset:
        return 4
    if (isinstance(ftype, tuple) and len(ftype) >= 1 and ftype[0] is OffsetTable) or get_origin(ftype) is OffsetTable:
        offset_t = ftype[2] if isinstance(ftype, tuple) and len(ftype) >= 3 else UInt32
        return offset_t._size if hasattr(offset_t, "_size") else 4
    is_variant = (
        (isinstance(ftype, tuple) and len(ftype) >= 1 and ftype[0] is Variant)
        or (get_origin(ftype) is Variant)
    )
    if is_variant:
        mapping = (
            ftype[2]
            if isinstance(ftype, tuple) and len(ftype) >= 3
            else (get_args(ftype)[1] if len(get_args(ftype)) > 1 else {})
        )
        if mapping:
            return max([_get_field_alignment(c) for c in mapping.values()], default=4)
        return 4
    return 1


def write_struct(
    instance: Any,
    writer: Optional[Any] = None,
    endian: Optional[EndianType] = None,
    parent_field_name: str = "",
    parent_struct_name: Optional[str] = None,
    desc: str = "",
) -> Any:
    """Serialize a @binary_struct instance to a BinaryWriter stream."""
    import struct
    from binary_master.writer import BinaryWriter

    meta = getattr(instance, "__binary__", None)
    if meta is None:
        raise TypeError(f"Object of type {type(instance).__name__} is not a binary_struct")

    struct_endian = meta.get("endian", "little")
    active_endian = normalize_endian(endian or struct_endian)

    if writer is None:
        writer = BinaryWriter(default_endian=active_endian)

    current_struct_name = parent_struct_name or instance.__class__.__name__
    struct_doc = meta.get("doc", "")
    align_setting = meta.get("align")
    auto_align = meta.get("auto_align", False)

    total_bits = meta.get("bits")
    if total_bits is not None:
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
    deferred_offsets = []

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

        # Check Offset[T]
        is_offset = (
            (isinstance(ftype, tuple) and len(ftype) >= 1 and ftype[0] is Offset)
            or (get_origin(ftype) is Offset)
        )
        if is_offset:
            target = val.target if isinstance(val, Offset) else val
            target_name = ""
            if isinstance(ftype, tuple) and len(ftype) >= 2:
                t_arg = ftype[1]
                target_name = t_arg.__name__ if hasattr(t_arg, "__name__") else str(t_arg)
            elif get_args(ftype):
                t_arg = get_args(ftype)[0]
                target_name = t_arg.__name__ if hasattr(t_arg, "__name__") else str(t_arg)
            type_label = f"Offset[{target_name}]" if target_name else "Offset"

            offset_placeholder_idx = len(writer._entries) if hasattr(writer, "_entries") else -1
            placeholder_pos = writer.tell()
            if target is None:
                writer._pack_write("I", 0, endian=active_endian, name=name, desc=f_desc, struct_name=current_struct_name, struct_doc=struct_doc)
            elif isinstance(target, int):
                writer._pack_write("I", target, endian=active_endian, name=name, desc=f_desc, struct_name=current_struct_name, struct_doc=struct_doc)
                if offset_placeholder_idx >= 0 and offset_placeholder_idx < len(writer._entries):
                    writer._entries[offset_placeholder_idx].type_name = type_label
                    writer._entries[offset_placeholder_idx].target_offset = target
            elif hasattr(target, "__binary__"):
                writer._pack_write("I", 0, endian=active_endian, name=name, desc=f_desc, struct_name=current_struct_name, struct_doc=struct_doc)
                if offset_placeholder_idx >= 0 and offset_placeholder_idx < len(writer._entries):
                    writer._entries[offset_placeholder_idx].type_name = type_label
                deferred_offsets.append((offset_placeholder_idx, placeholder_pos, target, active_endian))
            else:
                raise TypeError(f"Offset field {name} expected binary_struct or int, got {type(target).__name__}")
            continue

        # Check OffsetTable[Count, OffsetType]
        is_offset_table = (
            (isinstance(ftype, tuple) and len(ftype) >= 2 and ftype[0] is OffsetTable)
            or (get_origin(ftype) is OffsetTable)
        )
        if is_offset_table:
            if isinstance(ftype, tuple):
                count = ftype[1]
                offset_t = ftype[2] if len(ftype) >= 3 else UInt32
                base_offset = ftype[3] if len(ftype) >= 4 else 0
            else:
                args = get_args(ftype)
                count = args[0]
                offset_t = args[1] if len(args) > 1 else UInt32
                base_offset = args[2] if len(args) > 2 else 0

            offset_size = offset_t._size if hasattr(offset_t, "_size") else 4
            table_handle = writer.write_offset_table(
                count=count,
                offset_size=offset_size,
                endian=active_endian,
                name=name,
                desc=f_desc,
                base_offset=base_offset,
            )
            if isinstance(val, (list, tuple)):
                for i, target_item in enumerate(val):
                    if i < count:
                        if hasattr(target_item, "__binary__"):
                            deferred_offsets.append(("table_entry", table_handle, i, target_item, active_endian))
                        elif isinstance(target_item, int):
                            table_handle.set_offset(i, target_item)
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
            tag_field = ftype[1] if isinstance(ftype, tuple) else get_args(ftype)[0]
            mapping = ftype[2] if isinstance(ftype, tuple) else get_args(ftype)[1]
            if hasattr(writer, "_current_caption_variants") and writer._current_caption_variants is None:
                writer._current_caption_variants = [(k, v, getattr(v, "__doc__", "") or "") for k, v in mapping.items()]
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
            writer.write_bool(val, name=name, desc=f_desc)
        elif ftype is bytes or isinstance(val, (bytes, bytearray)):
            writer.write_bytes(val, name=name, desc=f_desc)
        elif ftype is str or isinstance(val, str):
            writer.write_cstring(val, name=name, desc=f_desc)
        else:
            raise TypeError(f"Unsupported field type for {name}: {ftype}")

    # Struct size alignment padding
    if align_setting is not None or auto_align:
        field_aligns = [_get_field_alignment(ft, getattr(instance, fn, None)) for fn, ft in fields.items()]
        max_field_align = max(field_aligns, default=1)
        struct_boundary = align_setting if align_setting else max_field_align
        if struct_boundary > 1:
            cur_pos = writer.tell()
            rem = cur_pos % struct_boundary
            if rem != 0:
                pad_len = struct_boundary - rem
                writer.pad(pad_len, name="alignment_pad", desc="Struct size alignment")

    # Process deferred offset target objects
    for item in deferred_offsets:
        if isinstance(item, tuple) and len(item) == 5 and item[0] == "table_entry":
            _, table_handle, idx, target_obj, off_endian = item
            target_pos = writer.tell()
            write_struct(target_obj, writer=writer, endian=off_endian)
            table_handle.set_offset(idx, target_pos)
        else:
            offset_placeholder_idx, placeholder_pos, target_obj, off_endian = item
            target_pos = writer.tell()
            write_struct(target_obj, writer=writer, endian=off_endian)
            return_pos = writer.tell()
            writer.seek(placeholder_pos)
            order = normalize_endian(off_endian)
            writer._stream.write(struct.pack(f"{order.value}I", target_pos))
            writer.seek(return_pos)
            if hasattr(writer, "_entries") and 0 <= offset_placeholder_idx < len(writer._entries):
                writer._entries[offset_placeholder_idx].value = target_pos
                writer._entries[offset_placeholder_idx].target_offset = target_pos

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

    if not isinstance(reader, BinaryReader):
        reader = BinaryReader(reader)

    struct_endian = meta.get("endian", "little")
    active_endian = normalize_endian(endian or struct_endian)

    total_bits = meta.get("bits")
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
            byteorder = "little" if active_endian == Endian.LITTLE else "big"
            packed_value = int.from_bytes(raw, byteorder=byteorder)

        fields = meta.get("fields", {})
        shift = 0
        kwargs = {}
        for name, ftype in fields.items():
            width = ftype[1] if isinstance(ftype, tuple) and len(ftype) >= 2 else 1
            mask = (1 << width) - 1
            val = (packed_value >> shift) & mask
            kwargs[name] = val
            shift += width
        return cls(**kwargs)

    fields = meta.get("fields", {})
    align_setting = meta.get("align")
    auto_align = meta.get("auto_align", False)
    kwargs = {}

    for name, ftype in fields.items():
        # Unwrap Annotated
        if get_origin(ftype) is Annotated:
            ftype = get_args(ftype)[0]

        # Automatic alignment padding before field
        if align_setting is not None or auto_align:
            field_align = _get_field_alignment(ftype, None)
            req_align = min(field_align, align_setting) if align_setting else field_align
            if req_align > 1:
                reader.align(req_align)

        # Check Offset[T]
        is_offset = (
            (isinstance(ftype, tuple) and len(ftype) >= 1 and ftype[0] is Offset)
            or (get_origin(ftype) is Offset)
        )
        if is_offset:
            target_offset = reader.read_uint32(endian=active_endian)
            target_type = None
            if isinstance(ftype, tuple) and len(ftype) >= 2:
                target_type = ftype[1]
            elif get_args(ftype):
                target_type = get_args(ftype)[0]

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
            continue

        # Check OffsetTable[Count, OffsetType]
        is_offset_table = (
            (isinstance(ftype, tuple) and len(ftype) >= 2 and ftype[0] is OffsetTable)
            or (get_origin(ftype) is OffsetTable)
        )
        if is_offset_table:
            if isinstance(ftype, tuple):
                count = ftype[1]
                offset_t = ftype[2] if len(ftype) >= 3 else UInt32
            else:
                args = get_args(ftype)
                count = args[0]
                offset_t = args[1] if len(args) > 1 else UInt32

            offs = []
            for _ in range(count):
                if offset_t is UInt8:
                    off = reader.read_uint8()
                elif offset_t is UInt16:
                    off = reader.read_uint16(endian=active_endian)
                elif offset_t is UInt64:
                    off = reader.read_uint64(endian=active_endian)
                else:
                    off = reader.read_uint32(endian=active_endian)
                offs.append(off)
            kwargs[name] = offs
            continue

        # Check Variant[tag_field, mapping]
        is_variant = (
            (isinstance(ftype, tuple) and len(ftype) >= 3 and ftype[0] is Variant)
            or (get_origin(ftype) is Variant)
        )
        if is_variant:
            tag_field = ftype[1] if isinstance(ftype, tuple) else get_args(ftype)[0]
            mapping = ftype[2] if isinstance(ftype, tuple) else get_args(ftype)[1]
            tag_val = kwargs.get(tag_field)
            if tag_val is None:
                raise ValueError(
                    f"Tag field '{tag_field}' must precede Variant field '{name}' in struct definition"
                )
            target_cls = mapping.get(tag_val)
            if target_cls is None:
                raise ValueError(
                    f"Unknown variant tag {tag_val!r} for field '{name}' (known tags: {list(mapping.keys())})"
                )
            if hasattr(target_cls, "__binary__"):
                kwargs[name] = read_struct(target_cls, reader=reader, endian=active_endian)
            elif target_cls is bytes:
                kwargs[name] = reader.read_bytes()
            else:
                kwargs[name] = reader.read_bytes()
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

            if elem_t is UInt8:
                kwargs[name] = reader.read_bytes(count)
            elif elem_t is Int8:
                kwargs[name] = [reader.read_int8() for _ in range(count)]
            elif isinstance(elem_t, type) and issubclass(elem_t, BinaryType):
                kwargs[name] = [
                    reader._unpack_read(elem_t._fmt, elem_t._size, endian=active_endian)
                    for _ in range(count)
                ]
            elif hasattr(elem_t, "__binary__"):
                kwargs[name] = [
                    read_struct(elem_t, reader=reader, endian=active_endian)
                    for _ in range(count)
                ]
            else:
                kwargs[name] = reader.read_bytes(count)
            continue

        # Check Array[T]
        is_arr = (
            (isinstance(ftype, tuple) and len(ftype) >= 2 and ftype[0] is Array)
            or (get_origin(ftype) is Array)
        )
        if is_arr:
            elem_t = ftype[1] if isinstance(ftype, tuple) else get_args(ftype)[0]
            if elem_t is UInt8:
                kwargs[name] = reader.read_bytes()
            elif isinstance(elem_t, type) and issubclass(elem_t, BinaryType):
                items = []
                while reader.remaining() >= elem_t._size:
                    items.append(reader._unpack_read(elem_t._fmt, elem_t._size, endian=active_endian))
                kwargs[name] = items
            elif hasattr(elem_t, "__binary__"):
                items = []
                while reader.remaining() > 0:
                    items.append(read_struct(elem_t, reader=reader, endian=active_endian))
                kwargs[name] = items
            else:
                kwargs[name] = reader.read_bytes()
            continue

        # Check nested binary_struct
        if hasattr(ftype, "__binary__"):
            kwargs[name] = read_struct(ftype, reader=reader, endian=active_endian)
            continue

        # Check primitive BinaryType
        if isinstance(ftype, type) and issubclass(ftype, BinaryType):
            fmt = ftype._fmt
            if fmt:
                kwargs[name] = reader._unpack_read(fmt, ftype._size, endian=active_endian)
            continue

        # Standard Python types fallback
        if ftype is int:
            kwargs[name] = reader.read_uint32(endian=active_endian)
        elif ftype is float:
            kwargs[name] = reader.read_float32(endian=active_endian)
        elif ftype is bool:
            kwargs[name] = reader.read_bool()
        elif ftype is bytes:
            kwargs[name] = reader.read_bytes()
        elif ftype is str:
            kwargs[name] = reader.read_cstring()
        else:
            raise TypeError(f"Unsupported field type for {name}: {ftype}")

    # Struct size alignment padding
    if align_setting is not None or auto_align:
        field_aligns = [_get_field_alignment(ft, None) for fn, ft in fields.items()]
        max_field_align = max(field_aligns, default=1)
        struct_boundary = align_setting if align_setting else max_field_align
        if struct_boundary > 1:
            reader.align(struct_boundary)

    return cls(**kwargs)


#
# # ==========================================================
# # BitField
# # ==========================================================
#
# @binary_struct(bits=16)
# class Flags:
#
#     enable: Bits[1]
#     mode: Bits[3]
#     priority: Bits[4]
#     reserved: Bits[8]
#
#
# # ==========================================================
# # Struct
# # ==========================================================
#
# @binary_struct(endian="little")
# class Header:
#
#     magic: UInt32
#     version: UInt16
#     flags: Flags
#     image_offset: Offset["Image"]
#
#
# @binary_struct(endian="little")
# class Image:
#
#     width: UInt16
#     height: UInt16
#     pixels: Array[UInt8]
#
#
# @binary_struct(endian="big")
# class Packet:
#
#     id: UInt16
#     count: UInt8
#     payload: FixedArray[UInt8, 64]
