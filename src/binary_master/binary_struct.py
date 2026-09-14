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
    _fmt: str = ""
    _size: int = 0

    @property
    def fmt(cls) -> str:
        return getattr(cls, "_fmt", "")

    @property
    def size(cls) -> int:
        return getattr(cls, "_size", 0)


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


class BoolMeta(BinaryTypeMeta):
    """Metaclass for Bool allowing parameterized sizes like Bool[2], Bool[4], etc."""

    _cache: dict[int, type] = {}

    def __getitem__(cls, size: int) -> type:
        if not isinstance(size, int) or size <= 0:
            raise ValueError(f"Bool size must be a positive integer, got {size}")
        if size == 1 and cls.__name__ == "Bool":
            return cls
        if size in cls._cache:
            return cls._cache[size]

        fmt_map = {1: "?", 2: "H", 4: "I", 8: "Q"}
        fmt = fmt_map.get(size, f"{size}s")
        name = f"Bool[{size}]"

        base_cls = cls if cls.__name__ == "Bool" else cls.__bases__[0]
        subcls = BoolMeta(
            name,
            (base_cls,),
            {
                "_size": size,
                "_fmt": fmt,
                "__module__": cls.__module__,
                "__qualname__": name,
            },
        )
        cls._cache[size] = subcls
        return subcls

    def __call__(cls, *args, **kwargs):
        if args and isinstance(args[0], int) and not isinstance(args[0], bool) and len(args) == 1 and not kwargs:
            return cls[args[0]]
        if "size" in kwargs and len(kwargs) == 1 and not args:
            return cls[kwargs["size"]]
        if args:
            return bool(args[0])
        return False

    def __repr__(cls) -> str:
        if cls._size == 1 and cls.__name__ == "Bool":
            return "Bool"
        return f"Bool[{cls._size}]"


class Bool(BinaryType, metaclass=BoolMeta):
    """Boolean binary type. Default size is 1 byte, configurable via Bool[size] or Bool(size)."""

    _fmt = "?"
    _size = 1


# ==========================================================
# Generic Types
# ==========================================================

T = TypeVar("T")


def _normalize_offset_type(offset_t: Any) -> tuple[str, int, str]:
    """Returns (fmt_char, size_in_bytes, type_label) for an offset type or byte size."""
    size_map = {1: ("B", 1, "UInt8"), 2: ("H", 2, "UInt16"), 4: ("I", 4, "UInt32"), 8: ("Q", 8, "UInt64")}
    if isinstance(offset_t, int):
        if offset_t not in size_map:
            raise ValueError(f"Offset byte size must be 1, 2, 4, or 8, got {offset_t}")
        return size_map[offset_t]
    if hasattr(offset_t, "_size") and hasattr(offset_t, "_fmt"):
        return offset_t._fmt, offset_t._size, getattr(offset_t, "__name__", str(offset_t))
    return ("I", 4, "UInt32")


class RelativeBase:
    """Represents a relative origin base for offsets."""

    def __init__(self, target: str = "self", delta: int = 0):
        self.target = target  # "self", "struct", "field"
        self.delta = delta

    def __add__(self, other: int) -> "RelativeBase":
        if not isinstance(other, int):
            return NotImplemented
        return RelativeBase(self.target, self.delta + other)

    def __sub__(self, other: int) -> "RelativeBase":
        if not isinstance(other, int):
            return NotImplemented
        return RelativeBase(self.target, self.delta - other)

    def resolve(self, struct_start: int, field_pos: int = 0) -> int:
        origin = struct_start if self.target in ("self", "struct") else field_pos
        return origin + self.delta

    def __repr__(self) -> str:
        name = f"Base.{self.target.upper()}"
        if self.delta > 0:
            return f"{name}+{hex(self.delta)}" if self.delta > 9 else f"{name}+{self.delta}"
        elif self.delta < 0:
            return f"{name}-{hex(-self.delta)}" if -self.delta > 9 else f"{name}-{(-self.delta)}"
        return name

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, RelativeBase):
            return self.target == other.target and self.delta == other.delta
        return False


class Base:
    """Predefined base origin symbols for relative offset calculations."""

    SELF = RelativeBase("self", 0)
    STRUCT = SELF
    FIELD = RelativeBase("field", 0)


def _resolve_base_offset(base: Any, struct_start: int, field_pos: int = 0) -> int:
    """Resolves a base offset (int, RelativeBase, or str) into an absolute byte origin."""
    if isinstance(base, RelativeBase):
        return base.resolve(struct_start, field_pos)
    if isinstance(base, int):
        return base
    if isinstance(base, str):
        val_clean = base.strip().lower()
        if val_clean in ("self", "struct"):
            return struct_start
        if val_clean == "field":
            return field_pos
        import re
        m = re.match(r"^(self|struct|field)\s*([+-])\s*(0x[0-9a-fA-F]+|\d+)$", val_clean)
        if m:
            target, sign, num_str = m.group(1), m.group(2), m.group(3)
            num = int(num_str, 16) if num_str.startswith("0x") else int(num_str)
            delta = num if sign == "+" else -num
            origin = struct_start if target in ("self", "struct") else field_pos
            return origin + delta
    return 0


def _is_base_offset_arg(arg: Any) -> bool:
    """Returns True if arg represents a relative base offset origin."""
    if isinstance(arg, RelativeBase):
        return True
    if isinstance(arg, str) and any(arg.lower().strip().startswith(p) for p in ("self", "struct", "field")):
        return True
    return False


def _is_offset_type_arg(arg: Any) -> bool:
    """Returns True if arg represents an offset data type."""
    if isinstance(arg, type) and issubclass(arg, BinaryType):
        return True
    if hasattr(arg, "_fmt") and hasattr(arg, "_size"):
        return True
    return False


def _parse_offset_spec_args(args: tuple[Any, ...]) -> tuple[Any, Any]:
    """Parses optional (offset_type, base_offset) in any order from generic arguments.

    Returns:
        tuple (offset_type, base_offset), defaulting to (UInt32, 0).
    """
    if not args:
        return UInt32, 0
    if len(args) == 1:
        arg = args[0]
        if _is_base_offset_arg(arg):
            return UInt32, arg
        if _is_offset_type_arg(arg):
            return arg, 0
        if isinstance(arg, int) and arg not in (1, 2, 4, 8):
            return UInt32, arg
        return arg, 0

    first, second = args[0], args[1]
    if _is_base_offset_arg(first) or (_is_offset_type_arg(second) and not _is_offset_type_arg(first)):
        return second, first
    return first, second


class Offset(Generic[T]):
    """シリアライズ時に自動計算されるオフセット: Offset[Target, OffsetType=UInt32, BaseOffset=0]"""

    def __init__(self, target: Any = None, offset: Optional[int] = None):
        self.target = target
        self.offset = offset

    def __class_getitem__(cls, args):
        if isinstance(args, tuple):
            target_t = args[0]
            offset_t, base_offset = _parse_offset_spec_args(args[1:])
        else:
            target_t = args
            offset_t = UInt32
            base_offset = 0
        return cls, target_t, offset_t, base_offset

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
            offset_t, base_offset = _parse_offset_spec_args(args[1:])
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


class _BinarySizeDescriptor:
    def __get__(self, instance, owner=None):
        if instance is not None:
            return sizeof(instance)
        if owner is not None:
            return sizeof(owner)
        return 0


def _calculate_field_size(name: str, ftype: Any, val: Any = None, is_cls: bool = True) -> int:
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
    if (isinstance(ftype, tuple) and len(ftype) >= 1 and ftype[0] is Offset) or get_origin(ftype) is Offset:
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
        return ftype._size
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

        current_offset += _calculate_field_size(name, ftype, val, is_cls=is_cls)

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


binary_size = sizeof


def to_bytes(self, endian: Optional[EndianType] = None) -> bytes:
    """Serialize this binary_struct instance to bytes."""
    writer = write_struct(self, endian=endian)
    return writer.to_bytes()


def from_bytes(cls, data: Union[bytes, bytearray], endian: Optional[EndianType] = None) -> Any:
    """Deserialize a @binary_struct instance from bytes."""
    return read_struct(cls, reader=data, endian=endian)


def to_c_struct_method(cls, name: Optional[str] = None, desc: str = "") -> str:
    """Generate a C typedef struct definition for this @binary_struct class."""
    from binary_master.c_header import to_c_struct

    return to_c_struct(cls, name=name, desc=desc)


def to_rust_struct_method(cls, name: Optional[str] = None, desc: str = "") -> str:
    """Generate a Rust struct definition for this @binary_struct class."""
    from binary_master.code_gen.rust import generate_rust_struct

    return generate_rust_struct(cls, name=name, desc=desc)


def to_cpp_struct_method(cls, name: Optional[str] = None, desc: str = "") -> str:
    """Generate a modern C++ struct definition for this @binary_struct class."""
    from binary_master.code_gen.cpp import generate_cpp_struct

    return generate_cpp_struct(cls, name=name, desc=desc)


def to_csharp_struct_method(cls, name: Optional[str] = None, desc: str = "") -> str:
    """Generate a C# struct definition for this @binary_struct class."""
    from binary_master.code_gen.csharp import generate_csharp_struct

    return generate_csharp_struct(cls, name=name, desc=desc)


def to_go_struct_method(cls, name: Optional[str] = None, desc: str = "") -> str:
    """Generate a Go struct definition for this @binary_struct class."""
    from binary_master.code_gen.go import generate_go_struct

    return generate_go_struct(cls, name=name, desc=desc)


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
        target_cls.to_c_struct = classmethod(to_c_struct_method)
        target_cls.to_c = classmethod(to_c_struct_method)
        target_cls.to_rust_struct = classmethod(to_rust_struct_method)
        target_cls.to_rust = classmethod(to_rust_struct_method)
        target_cls.to_cpp_struct = classmethod(to_cpp_struct_method)
        target_cls.to_cpp = classmethod(to_cpp_struct_method)
        target_cls.to_csharp_struct = classmethod(to_csharp_struct_method)
        target_cls.to_csharp = classmethod(to_csharp_struct_method)
        target_cls.to_go_struct = classmethod(to_go_struct_method)
        target_cls.to_go = classmethod(to_go_struct_method)
        target_cls.binary_size = _BinarySizeDescriptor()
        target_cls.offsetof = _OffsetofDescriptor()
        target_cls.bit_offsetof = _BitOffsetofDescriptor()
        target_cls.__len__ = lambda self: sizeof(self)
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
    return 1


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
) -> Any:
    """Serialize a @binary_struct instance to a BinaryWriter stream."""
    import struct
    from binary_master.writer import BinaryWriter

    meta = getattr(instance, "__binary__", None)
    if meta is None:
        raise TypeError(f"Object of type {type(instance).__name__} is not a binary_struct")

    eff_spec = spec_count if spec_count is not None else repeat
    struct_endian = meta.get("endian", "little")
    active_endian = normalize_endian(endian or struct_endian)

    if writer is None:
        writer = BinaryWriter(default_endian=active_endian)
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

        # Check Offset[T, OffsetType, BaseOffset]
        is_offset = (
            (isinstance(ftype, tuple) and len(ftype) >= 1 and ftype[0] is Offset)
            or (get_origin(ftype) is Offset)
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
                elif hasattr(val, "_targets") and isinstance(val._targets, (list, tuple)) and len(val._targets) > 0:
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
            )
            target_list = val if isinstance(val, (list, tuple)) else getattr(val, "_targets", None)
            if target_list is not None:
                for i, target_item in enumerate(target_list):
                    if i < actual_count:
                        if hasattr(target_item, "__binary__"):
                            deferred_offsets.append(("table_entry", table_handle, i, target_item, active_endian))
                        elif isinstance(target_item, int):
                            table_handle.set_offset(i, target_item)
                table_handle._targets = list(target_list)
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

    struct_start_pos = reader.tell()
    struct_endian = meta.get("endian", "little")
    active_endian = normalize_endian(endian or struct_endian)

    total_bits = meta.get("bits")
    if isinstance(total_bits, int):
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
            base_t = ftype[0] if isinstance(ftype, tuple) and len(ftype) >= 2 else ftype
            width = ftype[1] if isinstance(ftype, tuple) and len(ftype) >= 2 else 1
            mask = (1 << width) - 1
            val = (packed_value >> shift) & mask
            if base_t is Bool or (isinstance(base_t, type) and issubclass(base_t, Bool)) or base_t is bool:
                kwargs[name] = bool(val)
            else:
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

        # Check Offset[T, OffsetType, BaseOffset]
        is_offset = (
            (isinstance(ftype, tuple) and len(ftype) >= 1 and ftype[0] is Offset)
            or (get_origin(ftype) is Offset)
        )
        if is_offset:
            target_type = None
            offset_t = UInt32
            base_offset = 0
            if isinstance(ftype, tuple):
                if len(ftype) >= 2:
                    target_type = ftype[1]
                offset_t, base_offset = _parse_offset_spec_args(ftype[2:])
            elif get_args(ftype):
                args = get_args(ftype)
                target_type = args[0]
                offset_t, base_offset = _parse_offset_spec_args(args[1:])

            field_pos = reader.tell()
            actual_base = _resolve_base_offset(base_offset, struct_start_pos, field_pos)

            fmt_char, offset_size, _ = _normalize_offset_type(offset_t)
            stored_offset = reader._unpack_read(fmt_char, offset_size, endian=active_endian)
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
            continue

        # Check OffsetTable[Count, OffsetType, BaseOffset]
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

            fmt_char, offset_size, _ = _normalize_offset_type(offset_t)
            actual_count = kwargs.get(count) if isinstance(count, str) else count
            if actual_count is None:
                raise ValueError(
                    f"Count field '{count}' must precede OffsetTable field '{name}' in struct definition"
                )
            offs = [
                reader._unpack_read(fmt_char, offset_size, endian=active_endian)
                for _ in range(actual_count)
            ]
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

            if elem_t is Bool or (isinstance(elem_t, type) and issubclass(elem_t, Bool)) or elem_t is bool:
                b_size = getattr(elem_t, "_size", 1) if elem_t is not bool else 1
                kwargs[name] = [reader.read_bool(size=b_size, endian=active_endian) for _ in range(count)]
            elif elem_t is UInt8:
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
            if elem_t is Bool or (isinstance(elem_t, type) and issubclass(elem_t, Bool)) or elem_t is bool:
                b_size = getattr(elem_t, "_size", 1) if elem_t is not bool else 1
                items = []
                while reader.remaining() >= b_size:
                    items.append(reader.read_bool(size=b_size, endian=active_endian))
                kwargs[name] = items
            elif elem_t is UInt8:
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

        # Check Bool type
        if ftype is Bool or (isinstance(ftype, type) and issubclass(ftype, Bool)):
            kwargs[name] = reader.read_bool(size=ftype._size, endian=active_endian)
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
