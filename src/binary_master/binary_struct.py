from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Any, Generic, Optional, TypeVar, get_args, get_origin, get_type_hints

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


# ==========================================================
# binary_struct
# ==========================================================

class BinaryMetadata(dict):
    """Metadata container for binary_struct with lazy type hint resolution."""

    def __init__(self, cls, endian="little", bits=None):
        super().__init__({
            "endian": endian,
            "bits": bits,
        })
        self._cls = cls
        self._fields = None
        try:
            self._fields = get_type_hints(cls)
            self["fields"] = self._fields
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

    def __getitem__(self, item):
        if item == "fields" and self._fields is None:
            return self._resolve_fields()
        return super().__getitem__(item)

    def get(self, item, default=None):
        if item == "fields" and self._fields is None:
            return self._resolve_fields()
        return super().get(item, default)

    def items(self):
        self._resolve_fields()
        return super().items()

    def values(self):
        self._resolve_fields()
        return super().values()


def to_bytes(self, endian: Optional[EndianType] = None) -> bytes:
    """Serialize this binary_struct instance to bytes."""
    writer = write_struct(self, endian=endian)
    return writer.to_bytes()


def binary_struct(cls=None, *, endian="little", bits=None):

    def wrapper(target_cls):
        target_cls = dataclass(slots=True)(target_cls)
        target_cls.__binary__ = BinaryMetadata(target_cls, endian=endian, bits=bits)
        target_cls.to_bytes = to_bytes
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
) -> None:
    import struct
    fields = instance.__binary__["fields"]
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
            struct_name=parent_struct or instance.__class__.__name__,
            subfields=subfields,
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


def write_struct(
    instance: Any,
    writer: Optional[Any] = None,
    endian: Optional[EndianType] = None,
    parent_field_name: str = "",
    parent_struct_name: Optional[str] = None,
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

    total_bits = meta.get("bits")
    if total_bits is not None:
        _write_bitfield(
            instance,
            writer,
            active_endian,
            total_bits,
            field_name=parent_field_name or instance.__class__.__name__,
            parent_struct=current_struct_name,
        )
        return writer

    fields = meta.get("fields", {})
    deferred_offsets = []

    for name, ftype in fields.items():
        val = getattr(instance, name, None)

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
                writer._pack_write("I", 0, endian=active_endian, name=name, struct_name=current_struct_name)
            elif isinstance(target, int):
                writer._pack_write("I", target, endian=active_endian, name=name, struct_name=current_struct_name)
                if offset_placeholder_idx >= 0 and offset_placeholder_idx < len(writer._entries):
                    writer._entries[offset_placeholder_idx].type_name = type_label
                    writer._entries[offset_placeholder_idx].target_offset = target
            elif hasattr(target, "__binary__"):
                writer._pack_write("I", 0, endian=active_endian, name=name, struct_name=current_struct_name)
                if offset_placeholder_idx >= 0 and offset_placeholder_idx < len(writer._entries):
                    writer._entries[offset_placeholder_idx].type_name = type_label
                deferred_offsets.append((offset_placeholder_idx, placeholder_pos, target, active_endian))
            else:
                raise TypeError(f"Offset field {name} expected binary_struct or int, got {type(target).__name__}")
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
                    struct_name=current_struct_name,
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
                    struct_name=current_struct_name,
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
            )
            continue

        # Check primitive BinaryType
        if isinstance(ftype, type) and issubclass(ftype, BinaryType):
            fmt = ftype._fmt
            if fmt:
                writer._pack_write(fmt, val, endian=active_endian, name=name, struct_name=current_struct_name)
            continue

        # Standard Python types fallback
        if ftype is int or (isinstance(val, int) and not isinstance(val, bool)):
            writer._pack_write("I", val, endian=active_endian, name=name, struct_name=current_struct_name)
        elif ftype is float or isinstance(val, float):
            writer._pack_write("f", val, endian=active_endian, name=name, struct_name=current_struct_name)
        elif ftype is bool or isinstance(val, bool):
            writer.write_bool(val, name=name)
        elif ftype is bytes or isinstance(val, (bytes, bytearray)):
            writer.write_bytes(val, name=name)
        elif ftype is str or isinstance(val, str):
            writer.write_cstring(val, name=name)
        else:
            raise TypeError(f"Unsupported field type for {name}: {ftype}")

    # Process deferred offset target objects
    for offset_placeholder_idx, placeholder_pos, target_obj, off_endian in deferred_offsets:
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
