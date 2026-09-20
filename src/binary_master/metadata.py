from __future__ import annotations

import enum
import inspect
import re
import sys
from typing import (
    Annotated,
    Any,
    cast,
    get_args,
    get_origin,
    get_type_hints,
)

from binary_master.binary_types import (
    Array,
    BinaryType,
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
    _normalize_offset_type,
    _parse_offset_spec_args,
)
from binary_master.checksum import ChecksumBase
from binary_master.varint import VarIntTypeMeta, encode_varint, encode_varuint


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
    if _is_named_offset_spec(ftype):
        _, _, offset_t, _ = _extract_named_offset_info(ftype)
        _, size, _ = _normalize_offset_type(offset_t)
        return size
    elif (isinstance(ftype, tuple) and len(ftype) >= 1 and ftype[0] is Offset) or get_origin(ftype) is Offset:
        if isinstance(ftype, tuple):
            offset_t = ftype[2] if len(ftype) >= 3 else UInt32
        else:
            args = get_args(ftype)
            offset_t, _ = _parse_offset_spec_args(args[1:])
        _, size, _ = _normalize_offset_type(offset_t)
        return size
    if (isinstance(ftype, tuple) and len(ftype) >= 1 and ftype[0] is OffsetTable) or get_origin(ftype) is OffsetTable:
        if isinstance(ftype, tuple):
            offset_t = ftype[2] if len(ftype) >= 3 else UInt32
        else:
            args = get_args(ftype)
            offset_t, _ = _parse_offset_spec_args(args[1:])
        _, size, _ = _normalize_offset_type(offset_t)
        return size
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
    if isinstance(ftype, type) and _safe_issubclass(ftype, MagicBase):
        m_size = getattr(ftype, "size", 1)
        m_val = getattr(ftype, "value", None)
        return min(m_size, 8) if isinstance(m_val, int) else 1
    if isinstance(ftype, type) and _safe_issubclass(ftype, ConstantBase):
        return _get_field_alignment(getattr(ftype, "target_type", None))
    if isinstance(ftype, type) and _safe_issubclass(ftype, ChecksumBase):
        return min(getattr(ftype, "size", 1), 8)
    if isinstance(ftype, tuple) and len(ftype) >= 2 and isinstance(ftype[0], type) and _safe_issubclass(ftype[0], enum.Enum):
        return _get_field_alignment(ftype[1])
    if isinstance(ftype, type) and _safe_issubclass(ftype, enum.Enum):
        enum_cls = cast(type[enum.Enum], ftype)
        max_v = max([abs(m.value) for m in enum_cls], default=0)
        return 1 if max_v <= 255 else (2 if max_v <= 65535 else 4)
    if isinstance(ftype, VarIntTypeMeta):
        return 1
    return 1

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

    def __init__(self, cls, endian="little", bits=None, align=None, auto_align=False, total_size=None, pad_byte=b"\x00", doc="", localns=None):
        super().__init__({
            "endian": endian,
            "bits": bits,
            "align": align,
            "auto_align": auto_align,
            "total_size": total_size,
            "pad_byte": pad_byte,
            "doc": doc,
            "descriptions": {},
        })
        self._cls = cls
        self._localns = localns or {}
        self._fields = None
        self._descriptions = None
        try:
            mod = sys.modules.get(cls.__module__)
            globalns = getattr(mod, "__dict__", None)
            self._fields = get_type_hints(cls, globalns=globalns, localns=self._localns)
            self["fields"] = self._fields
            self._descriptions = extract_field_descriptions(cls)
            self["descriptions"] = self._descriptions
        except (NameError, TypeError):
            pass

    def _resolve_fields(self):
        if self._fields is None:
            mod = sys.modules.get(self._cls.__module__)
            globalns = getattr(mod, "__dict__", None)
            try:
                self._fields = get_type_hints(self._cls, globalns=globalns, localns=self._localns)
                self["fields"] = self._fields
            except (NameError, TypeError):
                raw_ann = getattr(self._cls, "__annotations__", {})
                resolved = {}
                import binary_master

                bm_dict = binary_master.__dict__
                combined_ns = {**bm_dict, **(globalns or {})}
                for k, v in raw_ann.items():
                    if isinstance(v, str):
                        try:
                            resolved[k] = eval(v, combined_ns, self._localns)
                        except Exception:
                            resolved[k] = v
                    else:
                        resolved[k] = v
                self._fields = resolved
                self["fields"] = self._fields
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


class _BinarySizeDescriptor:
    def __get__(self, instance, owner=None):
        if instance is not None:
            return sizeof(instance)
        if owner is not None:
            return sizeof(owner)
        return 0


def _safe_issubclass(cls: Any, base: Any) -> bool:
    """Safely check if cls is a subclass of base, handling TypeAliasType, tuples, and non-class types."""
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


def _calculate_field_size(name: str, ftype: Any, val: Any = None, is_cls: bool = True, instance: Any = None) -> int:
    """Calculate size of a single field, either statically or dynamically from an instance."""
    if get_origin(ftype) is Annotated:
        ftype = get_args(ftype)[0]

    # Instance-specific evaluation if val is available
    if not is_cls and val is not None:
        if hasattr(val, "__binary__"):
            return sizeof(val)
        if isinstance(val, (bytes, bytearray, memoryview)):
            return len(val)
        is_variant = (
            (isinstance(ftype, tuple) and len(ftype) >= 3 and ftype[0] is Variant)
            or (get_origin(ftype) is Variant)
        )
        if is_variant:
            target_obj = val.value if isinstance(val, Variant) else val
            if hasattr(target_obj, "__binary__"):
                return sizeof(target_obj)
            if isinstance(target_obj, (bytes, bytearray, memoryview)):
                return len(target_obj)
            return 0
        if isinstance(val, str):
            if ftype is CString or (isinstance(ftype, type) and issubclass(ftype, CString)):
                return len(val.encode(getattr(ftype, "encoding", "utf-8"))) + 1
            if ftype is PrefixedString or (isinstance(ftype, type) and issubclass(ftype, PrefixedString)):
                p_bytes = getattr(ftype, "prefix_bytes", 1)
                return len(val.encode(getattr(ftype, "encoding", "utf-8"))) + p_bytes
            if ftype is FixedString or (isinstance(ftype, type) and issubclass(ftype, FixedString)):
                return ftype._size
            return len(val.encode("utf-8")) + 1
        if isinstance(ftype, type) and issubclass(ftype, Bytes):
            return ftype._size if ftype._size > 0 else (len(val) if val is not None else 0)
        is_arr = (
            (isinstance(ftype, tuple) and len(ftype) >= 2 and ftype[0] is Array)
            or (get_origin(ftype) is Array)
        )
        if is_arr:
            if isinstance(val, list):
                elem_t = ftype[1] if isinstance(ftype, tuple) else get_args(ftype)[0]
                elem_size = sizeof(elem_t) if (hasattr(elem_t, "__binary__") or (isinstance(elem_t, type) and issubclass(elem_t, BinaryType))) else 1
                return len(val) * elem_size
            return 0

    # Static or shared evaluation
    if _is_named_offset_spec(ftype):
        _, _, offset_t, _ = _extract_named_offset_info(ftype)
        _, size, _ = _normalize_offset_type(offset_t)
        return size
    elif (isinstance(ftype, tuple) and len(ftype) >= 1 and ftype[0] is Offset) or get_origin(ftype) is Offset:
        if isinstance(ftype, tuple):
            offset_t = ftype[2] if len(ftype) >= 3 else UInt32
        else:
            args = get_args(ftype)
            offset_t, _ = _parse_offset_spec_args(args[1:])
        _, size, _ = _normalize_offset_type(offset_t)
        return size
    elif (isinstance(ftype, tuple) and len(ftype) >= 1 and ftype[0] is OffsetTable) or get_origin(ftype) is OffsetTable:
        if isinstance(ftype, tuple):
            count = ftype[1] if len(ftype) >= 2 else 0
            offset_t = ftype[2] if len(ftype) >= 3 else UInt32
        else:
            args = get_args(ftype)
            count = args[0] if len(args) >= 1 else 0
            offset_t, _ = _parse_offset_spec_args(args[1:])
        _, size, _ = _normalize_offset_type(offset_t)
        if isinstance(count, str):
            if is_cls:
                raise ValueError(f"Cannot determine static binary size for variable-length OffsetTable with count '{count}'")
            if hasattr(instance, name):
                v = getattr(instance, name)
                if isinstance(v, (list, tuple)):
                    count = len(v)
                elif hasattr(instance, count) and isinstance(getattr(instance, count), int):
                    count = getattr(instance, count)
                else:
                    count = 0
            elif hasattr(instance, count) and isinstance(getattr(instance, count), int):
                count = getattr(instance, count)
            else:
                count = 0
        return count * size
    elif (isinstance(ftype, tuple) and len(ftype) >= 1 and ftype[0] is FixedArray) or get_origin(ftype) is FixedArray:
        elem_t = ftype[1] if isinstance(ftype, tuple) else get_args(ftype)[0]
        count = ftype[2] if isinstance(ftype, tuple) else get_args(ftype)[1]
        elem_size = sizeof(elem_t) if (hasattr(elem_t, "__binary__") or (isinstance(elem_t, type) and issubclass(elem_t, BinaryType))) else 1
        return count * elem_size
    elif hasattr(ftype, "__binary__"):
        return sizeof(ftype)
    elif isinstance(ftype, type) and issubclass(ftype, BinaryType):
        if is_cls and ftype._size == 0:
            raise ValueError(
                f"Cannot determine static binary size for variable-length field '{name}' with type {getattr(ftype, '__name__', str(ftype))}; use sizeof(instance) or offsetof(instance, '{name}') instead"
            )
        return ftype._size
    elif isinstance(ftype, type) and issubclass(ftype, MagicBase):
        return getattr(ftype, "size", 0)
    elif isinstance(ftype, type) and issubclass(ftype, ConstantBase):
        return getattr(ftype, "size", 0)
    elif isinstance(ftype, type) and issubclass(ftype, (RangeBase, LengthOfBase, CountOfBase)):
        return ftype._size
    elif isinstance(ftype, type) and issubclass(ftype, ChecksumBase):
        return getattr(ftype, "size", 0)
    elif isinstance(ftype, VarIntTypeMeta):
        if not is_cls and val is not None:
            return len(encode_varint(val) if ftype.is_signed else encode_varuint(val))
        if is_cls:
            raise ValueError(f"Cannot determine static binary size for variable-length VarInt field '{name}'")
        return 0
    elif isinstance(ftype, tuple) and len(ftype) >= 2 and isinstance(ftype[0], type) and issubclass(ftype[0], enum.Enum):
        return sizeof(ftype[1]) if hasattr(ftype[1], "_size") else 4
    elif isinstance(ftype, type) and issubclass(ftype, enum.Enum):
        max_v = max([abs(m.value) for m in ftype], default=0)
        return 1 if max_v <= 255 else (2 if max_v <= 65535 else 4)
    elif ftype in (int, float):
        return 4
    elif ftype is bool:
        return 1
    else:
        if is_cls:
            raise ValueError(f"Cannot determine static binary size for field '{name}' with type {ftype}; use sizeof(instance) or offsetof(instance, '{name}') instead")
        return 0


def offsetof(target: Any, field_name: str) -> int:
    """Calculate the byte offset of a field within a @binary_struct class or instance.

    Args:
        target: A @binary_struct decorated class or instance.
        field_name: The name of the field. Supports dot notation for nested structs (e.g. "header.magic").

    Returns:
        The byte offset (int) of the field from the beginning of the struct.

    Raises:
        TypeError: If target is not a @binary_struct.
        AttributeError: If field_name does not exist in target.
        ValueError: If the offset cannot be determined statically.
    """
    is_cls = isinstance(target, type)
    cls = target if is_cls else type(target)
    meta = getattr(cls, "__binary__", None)
    if meta is None:
        raise TypeError(f"{getattr(cls, '__name__', str(cls))} is not a @binary_struct")

    if "." in field_name:
        first, rest = field_name.split(".", 1)
        base = offsetof(target, first)
        fields = meta.get("fields", {})
        if first not in fields:
            raise AttributeError(f"Field '{first}' not found in {cls.__name__}")
        ftype = fields[first]
        if get_origin(ftype) is Annotated:
            ftype = get_args(ftype)[0]
        if is_cls:
            if not hasattr(ftype, "__binary__"):
                raise AttributeError(f"Field '{first}' in {cls.__name__} is not a binary_struct, cannot access '{rest}'")
            return base + offsetof(ftype, rest)
        else:
            child = getattr(target, first, None)
            if child is None or not hasattr(child, "__binary__"):
                raise AttributeError(f"Field '{first}' in {cls.__name__} is not a binary_struct, cannot access '{rest}'")
            return base + offsetof(child, rest)

    total_bits = meta.get("bits")
    if isinstance(total_bits, int):
        fields = meta.get("fields", {})
        if field_name not in fields:
            raise AttributeError(f"Field '{field_name}' not found in bitfield {cls.__name__}")
        return 0

    fields = meta.get("fields", {})
    if field_name not in fields:
        raise AttributeError(f"Field '{field_name}' not found in {cls.__name__}")

    align_setting = meta.get("align")
    auto_align = meta.get("auto_align", False)

    current_offset = 0
    for name, ftype in fields.items():
        if get_origin(ftype) is Annotated:
            ftype = get_args(ftype)[0]

        val = getattr(target, name, None) if not is_cls else None

        # Automatic alignment padding before field
        if align_setting is not None or auto_align:
            field_align = _get_field_alignment(ftype, val)
            req_align = min(field_align, align_setting) if align_setting else field_align
            if req_align > 1:
                rem = current_offset % req_align
                if rem != 0:
                    current_offset += (req_align - rem)

        if name == field_name:
            return current_offset

        current_offset += _calculate_field_size(name, ftype, val, is_cls=is_cls, instance=target if not is_cls else None)

    raise AttributeError(f"Field '{field_name}' not found in {cls.__name__}")


def bit_offsetof(target: Any, field_name: str) -> tuple[int, int]:
    """Calculate the (byte_offset, bit_offset) of a field within a @binary_struct class or instance.

    For regular fields, bit_offset is 0.
    For bitfields, returns (byte_offset, bit_start_within_bitfield).
    """
    byte_off = offsetof(target, field_name)
    cls = target if isinstance(target, type) else type(target)
    meta = getattr(cls, "__binary__", None)
    if meta is not None and meta.get("bits") is not None:
        fields = meta.get("fields", {})
        shift = 0
        for name, ftype in fields.items():
            width = ftype[1] if isinstance(ftype, tuple) and len(ftype) >= 2 else (ftype if isinstance(ftype, int) else 1)
            if name == field_name:
                return (byte_off, shift)
            shift += width

    return (byte_off, 0)


class _OffsetofDescriptor:
    def __get__(self, instance, owner=None):
        target = instance if instance is not None else owner
        if target is None:
            return None
        return lambda field_name: offsetof(target, field_name)


class _BitOffsetofDescriptor:
    def __get__(self, instance, owner=None):
        target = instance if instance is not None else owner
        if target is None:
            return None
        return lambda field_name: bit_offsetof(target, field_name)


def sizeof(target: Any) -> int:
    """Calculate the binary size in bytes of a @binary_struct class, instance, or BinaryType."""
    if isinstance(target, type) and issubclass(target, BinaryType):
        return target._size

    # Handle instance
    if not isinstance(target, type):
        if hasattr(target, "__binary__"):
            return len(target.to_bytes())
        raise TypeError(f"Object {target!r} of type {type(target).__name__} is not a binary_struct")

    # Handle class
    meta = getattr(target, "__binary__", None)
    if meta is None:
        target_name = getattr(target, "__name__", None) or type(target).__name__
        raise TypeError(f"Class {target_name} is not a binary_struct")

    total_size_setting = meta.get("total_size")
    if total_size_setting is not None:
        return total_size_setting

    total_bits = meta.get("bits")
    if isinstance(total_bits, int):
        raw_bytes = (total_bits + 7) // 8
        align = meta.get("align")
        if isinstance(align, int) and align > 1:
            raw_bytes = ((raw_bytes + align - 1) // align) * align
        return raw_bytes

    fields = meta.get("fields", {})
    align_setting = meta.get("align")
    auto_align = meta.get("auto_align", False)

    current_offset = 0
    for name, ftype in fields.items():
        if get_origin(ftype) is Annotated:
            ftype = get_args(ftype)[0]

        # Automatic alignment padding before field
        if align_setting is not None or auto_align:
            field_align = _get_field_alignment(ftype, None)
            req_align = min(field_align, align_setting) if align_setting else field_align
            if req_align > 1:
                rem = current_offset % req_align
                if rem != 0:
                    current_offset += (req_align - rem)

        # Field size calculation
        current_offset += _calculate_field_size(name, ftype, val=None, is_cls=True)

    # Struct size alignment padding
    if align_setting is not None or auto_align:
        field_aligns = [_get_field_alignment(ft, None) for fn, ft in fields.items()]
        max_field_align = max(field_aligns, default=1)
        struct_boundary = align_setting if align_setting else max_field_align
        if struct_boundary > 1:
            rem = current_offset % struct_boundary
            if rem != 0:
                current_offset += (struct_boundary - rem)

    return current_offset
