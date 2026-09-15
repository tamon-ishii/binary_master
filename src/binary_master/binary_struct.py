from __future__ import annotations

import base64
import enum
import inspect
import json
import re
import sys
from dataclasses import dataclass
from typing import Annotated, Any, Callable, Generic, Optional, TypeVar, Union, get_args, get_origin, get_type_hints

from binary_master.enums import Endian, EndianType, normalize_endian
from binary_master.exceptions import (
    ChecksumMismatchError,
    InvalidConstantError,
    InvalidEnumError,
    InvalidMagicError,
    RangeValidationError,
    TotalSizeExceededError,
)
from binary_master.checksum import ChecksumBase, compute_checksum, get_checksum_algorithm
from binary_master.varint import VarIntTypeMeta, encode_varint, encode_varuint, decode_varint, decode_varuint

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


class Float16(BinaryType):
    _fmt = "e"
    _size = 2


class Float32(BinaryType):
    _fmt = "f"
    _size = 4


class Float64(BinaryType):
    _fmt = "d"
    _size = 8


# Convenient aliases for floating point types
Float = Float32
Double = Float64
double = Double


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


class BytesMeta(BinaryTypeMeta):
    """Metaclass for Bytes allowing parameterized length like Bytes[16], Bytes[4], etc."""

    _cache: dict[int, type] = {}

    def __getitem__(cls, length: int) -> type:
        if not isinstance(length, int) or length <= 0:
            raise ValueError(f"Bytes length must be a positive integer, got {length}")
        if length in cls._cache:
            return cls._cache[length]

        name = f"Bytes[{length}]"
        base_cls = cls if cls.__name__ == "Bytes" else cls.__bases__[0]
        subcls = BytesMeta(
            name,
            (base_cls,),
            {
                "_size": length,
                "_fmt": f"{length}s",
                "length": length,
                "__module__": cls.__module__,
                "__qualname__": name,
            },
        )
        cls._cache[length] = subcls
        return subcls

    def __call__(cls, *args, **kwargs):
        if args and isinstance(args[0], int) and len(args) == 1 and not kwargs:
            return cls[args[0]]
        if "length" in kwargs and len(kwargs) == 1 and not args:
            return cls[kwargs["length"]]
        if args:
            return bytes(args[0])
        return b""

    def __repr__(cls) -> str:
        if cls._size == 0 and cls.__name__ == "Bytes":
            return "Bytes"
        return f"Bytes[{cls._size}]"


class Bytes(BinaryType, metaclass=BytesMeta):
    """Fixed-length raw byte sequence type: Bytes[N] (e.g. Bytes[16])."""

    _size = 0
    _fmt = "s"


class FixedStringMeta(BinaryTypeMeta):
    """Metaclass for FixedString allowing parameterized length like FixedString[16]."""

    _cache: dict[tuple, type] = {}

    def __getitem__(cls, args: Union[int, tuple]) -> type:
        if isinstance(args, tuple):
            length = args[0]
            encoding = args[1] if len(args) > 1 else "utf-8"
            pad_byte = args[2] if len(args) > 2 else b"\x00"
        else:
            length = args
            encoding = "utf-8"
            pad_byte = b"\x00"

        if not isinstance(length, int) or length <= 0:
            raise ValueError(f"FixedString length must be a positive integer, got {length}")

        cache_key = (length, encoding, pad_byte)
        if cache_key in cls._cache:
            return cls._cache[cache_key]

        name = f"FixedString[{length}]"
        base_cls = cls if cls.__name__ == "FixedString" else cls.__bases__[0]
        subcls = FixedStringMeta(
            name,
            (base_cls,),
            {
                "_size": length,
                "_fmt": f"{length}s",
                "length": length,
                "encoding": encoding,
                "pad_byte": pad_byte,
                "__module__": cls.__module__,
                "__qualname__": name,
            },
        )
        cls._cache[cache_key] = subcls
        return subcls

    def __call__(cls, *args, **kwargs):
        if args and isinstance(args[0], int) and len(args) == 1 and not kwargs:
            return cls[args[0]]
        if args:
            return str(args[0])
        return ""

    def __repr__(cls) -> str:
        if cls._size == 0 and cls.__name__ == "FixedString":
            return "FixedString"
        return f"FixedString[{cls._size}]"


class FixedString(BinaryType, metaclass=FixedStringMeta):
    """Fixed-length string type: FixedString[N] (e.g. FixedString[32])."""

    _size = 0
    _fmt = "s"
    encoding = "utf-8"
    pad_byte = b"\x00"


class CString(BinaryType):
    """Null-terminated (C-style) string type."""

    _size = 0
    _fmt = "s"
    encoding = "utf-8"

    def __repr__(self) -> str:
        return "CString"


class PrefixedStringMeta(BinaryTypeMeta):
    """Metaclass for PrefixedString allowing parameterized prefix bytes like PrefixedString[2]."""

    _cache: dict[tuple, type] = {}

    def __getitem__(cls, args: Union[int, tuple]) -> type:
        if isinstance(args, tuple):
            prefix_bytes = args[0]
            encoding = args[1] if len(args) > 1 else "utf-8"
        else:
            prefix_bytes = args
            encoding = "utf-8"

        if prefix_bytes not in (1, 2, 4, 8):
            raise ValueError(f"PrefixedString prefix_bytes must be 1, 2, 4, or 8, got {prefix_bytes}")

        cache_key = (prefix_bytes, encoding)
        if cache_key in cls._cache:
            return cls._cache[cache_key]

        name = f"PrefixedString[{prefix_bytes}]"
        base_cls = cls if cls.__name__ == "PrefixedString" else cls.__bases__[0]
        subcls = PrefixedStringMeta(
            name,
            (base_cls,),
            {
                "_size": 0,
                "prefix_bytes": prefix_bytes,
                "encoding": encoding,
                "__module__": cls.__module__,
                "__qualname__": name,
            },
        )
        cls._cache[cache_key] = subcls
        return subcls

    def __repr__(cls) -> str:
        p = getattr(cls, "prefix_bytes", 1)
        return f"PrefixedString[{p}]"


class PrefixedString(BinaryType, metaclass=PrefixedStringMeta):
    """Length-prefixed Pascal-style string type: PrefixedString or PrefixedString[prefix_bytes]."""

    _size = 0
    prefix_bytes = 1
    encoding = "utf-8"


class BinaryEnumMeta(enum.EnumType):
    """Metaclass for BinaryEnum allowing member lookup or parameterized type e.g. MyEnum[UInt8]."""

    def __getitem__(cls, item: Any) -> Any:
        if isinstance(item, str) and item in cls._member_map_:
            return cls._member_map_[item]
        return (cls, item)


class BinaryEnum(enum.IntEnum, metaclass=BinaryEnumMeta):
    """Base class for binary integer enums supporting explicit integer sizing (e.g. MyEnum[UInt8])."""
    pass


class MagicMeta(type):
    """Metaclass for Magic[...] types."""

    _value: Any = None
    _raw_val: Any = None
    _size: int = 0
    _fmt: str = ""

    def __getitem__(cls, val: Any) -> type:
        if isinstance(val, (bytes, bytearray)):
            size = len(val)
            fmt = f"{size}s"
            b_val = bytes(val)
        elif isinstance(val, str):
            b_val = val.encode("utf-8")
            size = len(b_val)
            fmt = f"{size}s"
        elif isinstance(val, int):
            if 0 <= val <= 0xFF:
                size = 1
                fmt = "B"
            elif 0 <= val <= 0xFFFF:
                size = 2
                fmt = "H"
            elif 0 <= val <= 0xFFFFFFFF:
                size = 4
                fmt = "I"
            else:
                size = 8
                fmt = "Q"
            b_val = val
        else:
            raise TypeError(f"Magic value must be bytes, str, or int, got {type(val).__name__}")

        name = f"Magic[{val!r}]"
        return MagicMeta(
            name,
            (MagicBase,),
            {
                "_value": b_val,
                "_raw_val": val,
                "_size": size,
                "_fmt": fmt,
                "__module__": cls.__module__,
                "__qualname__": name,
            },
        )

    @property
    def value(cls) -> Any:
        return getattr(cls, "_value", None)

    @property
    def raw_value(cls) -> Any:
        return getattr(cls, "_raw_val", None)

    @property
    def size(cls) -> int:
        return getattr(cls, "_size", 0)

    @property
    def fmt(cls) -> str:
        return getattr(cls, "_fmt", "")

    def __repr__(cls) -> str:
        return f"Magic[{getattr(cls, '_raw_val', None)!r}]"


class MagicBase:
    pass


class Magic(metaclass=MagicMeta):
    """Declarative magic constraint: Magic[b'PNG...'] or Magic[0x504C4159]."""
    pass


class ConstantMeta(type):
    """Metaclass for Constant[Type, Value]."""

    _type: Any = None
    _value: Any = None
    _size: int = 0

    def __getitem__(cls, args: tuple[Any, Any]) -> type:
        if not isinstance(args, tuple) or len(args) != 2:
            raise TypeError("Constant requires (Type, Value), e.g. Constant[UInt16, 1]")
        target_t, val = args
        size = sizeof(target_t) if hasattr(target_t, "_size") or hasattr(target_t, "__binary__") else 4
        name = f"Constant[{getattr(target_t, '__name__', str(target_t))}, {val!r}]"
        return ConstantMeta(
            name,
            (ConstantBase,),
            {
                "_type": target_t,
                "_value": val,
                "_size": size,
                "__module__": cls.__module__,
                "__qualname__": name,
            },
        )

    @property
    def target_type(cls) -> Any:
        return getattr(cls, "_type", None)

    @property
    def value(cls) -> Any:
        return getattr(cls, "_value", None)

    @property
    def size(cls) -> int:
        return getattr(cls, "_size", 0)

    def __repr__(cls) -> str:
        t = getattr(cls, "_type", None)
        v = getattr(cls, "_value", None)
        t_name = getattr(t, "__name__", str(t))
        return f"Constant[{t_name}, {v!r}]"


class ConstantBase:
    pass


class Constant(metaclass=ConstantMeta):
    """Declarative constant constraint: Constant[UInt16, 1]."""
    pass


class RangeBase:
    """Base class for Range[Type, min, max]."""
    _type: Any = None
    _min: Any = None
    _max: Any = None
    _size: int = 4
    _fmt: str = ""


class RangeMeta(BinaryTypeMeta):
    """Metaclass for Range[Type, min, max]."""

    _type: Any = None
    _min: Any = None
    _max: Any = None
    _size: int = 4
    _fmt: str = ""

    def __getitem__(cls, args: tuple[Any, Any, Any]) -> type:
        if not isinstance(args, tuple) or len(args) != 3:
            raise TypeError("Range requires (Type, min, max), e.g. Range[UInt8, 0, 100]")
        target_t, min_val, max_val = args
        sz = sizeof(target_t) if hasattr(target_t, "_size") or hasattr(target_t, "__binary__") else 4
        fmt = getattr(target_t, "_fmt", "")
        name = f"Range[{getattr(target_t, '__name__', str(target_t))}, {min_val!r}, {max_val!r}]"
        base_parent = target_t if isinstance(target_t, type) and issubclass(target_t, BinaryType) else BinaryType
        return RangeMeta(
            name,
            (RangeBase, base_parent),
            {
                "_type": target_t,
                "_min": min_val,
                "_max": max_val,
                "_size": sz,
                "_fmt": fmt,
                "__module__": cls.__module__,
                "__qualname__": name,
            },
        )

    @property
    def target_type(cls) -> Any:
        return getattr(cls, "_type", None)

    @property
    def min_value(cls) -> Any:
        return getattr(cls, "_min", None)

    @property
    def max_value(cls) -> Any:
        return getattr(cls, "_max", None)

    @property
    def size(cls) -> int:
        return getattr(cls, "_size", 0)

    def __repr__(cls) -> str:
        t = getattr(cls, "_type", None)
        min_v = getattr(cls, "_min", None)
        max_v = getattr(cls, "_max", None)
        t_name = getattr(t, "__name__", str(t))
        return f"Range[{t_name}, {min_v!r}, {max_v!r}]"


class Range(metaclass=RangeMeta):
    """Declarative bounded-range field: Range[UInt8, 0, 100]."""
    pass


class LengthOfBase:
    """Base class for LengthOf annotations."""
    _target: str = ""
    _target_field: str = ""
    _type: Any = None
    _target_type: Any = None
    _size: int = 2
    _delta: int = 0
    _fmt: str = "H"


class LengthOfMeta(BinaryTypeMeta):
    """Metaclass for LengthOf[Type, "target_field", delta=0] or LengthOf["target_field", Type, delta=0]."""

    _target: str = ""
    _target_field: str = ""
    _type: Any = None
    _target_type: Any = None
    _size: int = 2
    _delta: int = 0
    _fmt: str = "H"

    def __getitem__(cls, args: Any) -> type:
        delta = 0
        target_t = UInt16
        target = ""
        if isinstance(args, tuple):
            if isinstance(args[0], (str, bytes)):
                target = str(args[0])
                if len(args) >= 2:
                    target_t = args[1]
            else:
                target_t = args[0]
                if len(args) >= 2:
                    target = str(args[1])
            if len(args) >= 3:
                delta = args[2]
        else:
            if isinstance(args, (str, bytes)):
                target = str(args)
            else:
                target_t = args

        sz = sizeof(target_t) if hasattr(target_t, "_size") or hasattr(target_t, "__binary__") else 2
        fmt = getattr(target_t, "_fmt", "H")
        name = f"LengthOf[{getattr(target_t, '__name__', str(target_t))}, {target!r}]"
        base_parent = target_t if isinstance(target_t, type) and issubclass(target_t, BinaryType) else BinaryType
        return LengthOfMeta(
            name,
            (LengthOfBase, base_parent),
            {
                "_target": target,
                "_target_field": target,
                "_type": target_t,
                "_target_type": target_t,
                "_size": sz,
                "_delta": delta,
                "_fmt": fmt,
                "__module__": cls.__module__,
                "__qualname__": name,
            },
        )

    @property
    def target_field(cls) -> str:
        return getattr(cls, "_target", "")

    @property
    def target_type(cls) -> Any:
        return getattr(cls, "_type", None)

    @property
    def delta(cls) -> int:
        return getattr(cls, "_delta", 0)

    @property
    def size(cls) -> int:
        return getattr(cls, "_size", 0)

    def __repr__(cls) -> str:
        target = getattr(cls, "_target", "")
        t = getattr(cls, "_type", None)
        t_name = getattr(t, "__name__", str(t))
        return f"LengthOf[{t_name}, {target!r}]"


class LengthOf(metaclass=LengthOfMeta):
    """Declarative byte length field linking to target field: LengthOf[UInt16, 'payload']."""
    pass


class CountOfBase:
    """Base class for CountOf annotations."""
    _target: str = ""
    _target_field: str = ""
    _type: Any = None
    _target_type: Any = None
    _size: int = 4
    _delta: int = 0
    _fmt: str = "I"


class CountOfMeta(BinaryTypeMeta):
    """Metaclass for CountOf[Type, "target_field", delta=0] or CountOf["target_field", Type, delta=0]."""

    _target: str = ""
    _target_field: str = ""
    _type: Any = None
    _target_type: Any = None
    _size: int = 4
    _delta: int = 0
    _fmt: str = "I"

    def __getitem__(cls, args: Any) -> type:
        delta = 0
        target_t = UInt32
        target = ""
        if isinstance(args, tuple):
            if isinstance(args[0], (str, bytes)):
                target = str(args[0])
                if len(args) >= 2:
                    target_t = args[1]
            else:
                target_t = args[0]
                if len(args) >= 2:
                    target = str(args[1])
            if len(args) >= 3:
                delta = args[2]
        else:
            if isinstance(args, (str, bytes)):
                target = str(args)
            else:
                target_t = args

        sz = sizeof(target_t) if hasattr(target_t, "_size") or hasattr(target_t, "__binary__") else 4
        fmt = getattr(target_t, "_fmt", "I")
        name = f"CountOf[{getattr(target_t, '__name__', str(target_t))}, {target!r}]"
        base_parent = target_t if isinstance(target_t, type) and issubclass(target_t, BinaryType) else BinaryType
        return CountOfMeta(
            name,
            (CountOfBase, base_parent),
            {
                "_target": target,
                "_target_field": target,
                "_type": target_t,
                "_target_type": target_t,
                "_size": sz,
                "_delta": delta,
                "_fmt": fmt,
                "__module__": cls.__module__,
                "__qualname__": name,
            },
        )

    @property
    def target_field(cls) -> str:
        return getattr(cls, "_target", "")

    @property
    def target_type(cls) -> Any:
        return getattr(cls, "_type", None)

    @property
    def delta(cls) -> int:
        return getattr(cls, "_delta", 0)

    @property
    def size(cls) -> int:
        return getattr(cls, "_size", 0)

    def __repr__(cls) -> str:
        target = getattr(cls, "_target", "")
        t = getattr(cls, "_type", None)
        t_name = getattr(t, "__name__", str(t))
        return f"CountOf[{t_name}, {target!r}]"


class CountOf(metaclass=CountOfMeta):
    """Declarative element count field linking to target field: CountOf[UInt32, 'items']."""
    pass




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

    def __init__(self, cls, endian="little", bits=None, align=None, auto_align=False, total_size=None, pad_byte=b"\x00", doc=""):
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
        if is_cls and ftype._size == 0:
            raise ValueError(
                f"Cannot determine static binary size for variable-length field '{name}' with type {getattr(ftype, '__name__', str(ftype))}; use sizeof(instance) or offsetof(instance, '{name}') instead"
            )
        return ftype._size
    elif isinstance(ftype, type) and issubclass(ftype, MagicBase):
        return ftype.size
    elif isinstance(ftype, type) and issubclass(ftype, ConstantBase):
        return ftype.size
    elif isinstance(ftype, type) and issubclass(ftype, (RangeBase, LengthOfBase, CountOfBase)):
        return ftype._size
    elif isinstance(ftype, type) and issubclass(ftype, ChecksumBase):
        return ftype.size
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


class _ToMarkdownDescriptor:
    def __get__(self, instance, owner=None):
        target = instance if instance is not None else owner
        def _to_markdown(**kwargs):
            from binary_master.manual import generate_manual
            return generate_manual(target, **kwargs)
        return _to_markdown


class _WriteMarkdownDescriptor:
    def __get__(self, instance, owner=None):
        target = instance if instance is not None else owner
        def _write_markdown(path, **kwargs):
            from pathlib import Path
            from binary_master.manual import generate_manual
            md = generate_manual(target, **kwargs)
            Path(path).write_text(md, encoding="utf-8")
            return md
        return _write_markdown


class _ToHtmlDescriptor:
    def __get__(self, instance, owner=None):
        target = instance if instance is not None else owner
        def _to_html(**kwargs):
            from binary_master.manual import generate_html
            return generate_html(target, **kwargs)
        return _to_html


class _WriteHtmlDescriptor:
    def __get__(self, instance, owner=None):
        target = instance if instance is not None else owner
        def _write_html(path, **kwargs):
            from pathlib import Path
            from binary_master.manual import generate_html
            content = generate_html(target, **kwargs)
            Path(path).write_text(content, encoding="utf-8")
            return content
        return _write_html


class _ToCodeDescriptor:
    def __get__(self, instance, owner=None):
        target = instance if instance is not None else owner
        def _to_code(lang: str, **kwargs):
            from binary_master.code_gen import generate_code
            return generate_code(target, lang=lang, **kwargs)
        return _to_code


class _WriteCodeDescriptor:
    def __get__(self, instance, owner=None):
        target = instance if instance is not None else owner
        def _write_code(path, lang: Optional[str] = None, **kwargs):
            from binary_master.code_gen import write_code
            return write_code(target, path, lang=lang, **kwargs)
        return _write_code


def _serialize_dict_value(val: Any, bytes_format: str = "hex") -> Any:
    if hasattr(val, "to_dict"):
        return val.to_dict(bytes_format=bytes_format)
    if isinstance(val, (bytes, bytearray, memoryview)):
        b = bytes(val)
        if bytes_format == "hex":
            return "0x" + b.hex()
        elif bytes_format == "base64":
            return base64.b64encode(b).decode("ascii")
        elif bytes_format == "list":
            return list(b)
        return b.hex()
    if isinstance(val, enum.Enum):
        return val.name
    if isinstance(val, list):
        return [_serialize_dict_value(x, bytes_format=bytes_format) for x in val]
    if isinstance(val, tuple):
        return tuple(_serialize_dict_value(x, bytes_format=bytes_format) for x in val)
    if isinstance(val, dict):
        return {k: _serialize_dict_value(v, bytes_format=bytes_format) for k, v in val.items()}
    return val


def to_dict_method(self, bytes_format: str = "hex") -> dict[str, Any]:
    """Convert struct instance to dictionary.
    
    Args:
        bytes_format: 'hex' (default, e.g. '0x...'), 'base64', or 'list' (list of integers).
    """
    from dataclasses import fields as dc_fields, is_dataclass

    result = {}
    field_names = [f.name for f in dc_fields(self)] if is_dataclass(self) else getattr(self, "__binary__", {}).get("fields", {}).keys()
    for fname in field_names:
        val = getattr(self, fname, None)
        result[fname] = _serialize_dict_value(val, bytes_format=bytes_format)
    return result


def _deserialize_dict_value(val: Any, ftype: Any) -> Any:
    if val is None:
        return None
    if get_origin(ftype) is Annotated:
        ftype = get_args(ftype)[0]
    if hasattr(ftype, "from_dict"):
        return ftype.from_dict(val)

    # Check Enum
    if isinstance(ftype, type) and issubclass(ftype, enum.Enum):
        if isinstance(val, str) and hasattr(ftype, val):
            return ftype[val]
        return ftype(val)
    if isinstance(ftype, tuple) and len(ftype) >= 2 and isinstance(ftype[0], type) and issubclass(ftype[0], enum.Enum):
        enum_cls = ftype[0]
        if isinstance(val, str) and hasattr(enum_cls, val):
            return enum_cls[val]
        return enum_cls(val)

    # Check Bytes / byte types
    if (isinstance(ftype, type) and issubclass(ftype, Bytes)) or ftype in (bytes, bytearray):
        if isinstance(val, str):
            if val.startswith("0x") or val.startswith("0X"):
                return bytes.fromhex(val[2:])
            try:
                return bytes.fromhex(val)
            except ValueError:
                return base64.b64decode(val)
        elif isinstance(val, list):
            return bytes(val)
        return val

    # Check FixedArray / Array
    is_arr = (
        (isinstance(ftype, tuple) and len(ftype) >= 2 and ftype[0] in (FixedArray, Array))
        or get_origin(ftype) in (FixedArray, Array)
    )
    if is_arr:
        elem_t = ftype[1] if isinstance(ftype, tuple) else get_args(ftype)[0]
        if elem_t is UInt8:
            if isinstance(val, str):
                if val.startswith("0x") or val.startswith("0X"):
                    return bytes.fromhex(val[2:])
                try:
                    return bytes.fromhex(val)
                except ValueError:
                    return base64.b64decode(val)
            elif isinstance(val, list):
                return val
        if isinstance(val, list):
            return [_deserialize_dict_value(x, elem_t) for x in val]

    return val


def from_dict_method(cls: type[T], data: dict[str, Any]) -> T:
    """Reconstruct a @binary_struct instance from a dictionary."""
    meta = getattr(cls, "__binary__", None)
    if meta is None:
        raise TypeError(f"{cls.__name__} is not a binary_struct")

    fields_meta = meta.get("fields", {})
    resolved = {}
    for name, ftype in fields_meta.items():
        if name in data:
            resolved[name] = _deserialize_dict_value(data[name], ftype)
    return cls(**resolved)


def to_json_method(self, indent: Optional[int] = None, bytes_format: str = "hex") -> str:
    """Convert struct instance to JSON string."""
    return json.dumps(self.to_dict(bytes_format=bytes_format), indent=indent)


def from_json_method(cls: type[T], json_str: str) -> T:
    """Reconstruct a @binary_struct instance from a JSON string."""
    return cls.from_dict(json.loads(json_str))


def binary_struct(cls=None, *, endian="little", bits=None, align=None, auto_align=False, total_size=None, pad_byte=b"\x00"):

    def wrapper(target_cls):
        # Scan annotations and attributes for default values (user defaults, Magic, Constant, Checksum, LengthOf, CountOf)
        magic_const_defaults = {}
        user_defaults = {}
        user_default_factories = {}

        if hasattr(target_cls, "__annotations__"):
            # Extract user defaults (e.g. field: Type = val or field(default=...))
            # We strip them from target_cls before dataclass() so that fields with defaults
            # can appear before fields without defaults without triggering dataclass TypeError!
            for fname in list(target_cls.__annotations__.keys()):
                if hasattr(target_cls, fname):
                    val = getattr(target_cls, fname)
                    if not inspect.isroutine(val) and not isinstance(val, property):
                        import dataclasses
                        if isinstance(val, dataclasses.Field):
                            if val.default is not dataclasses.MISSING:
                                user_defaults[fname] = val.default
                            elif val.default_factory is not dataclasses.MISSING:
                                user_default_factories[fname] = val.default_factory
                        else:
                            user_defaults[fname] = val
                        delattr(target_cls, fname)

            for fname, ftype in target_cls.__annotations__.items():
                if get_origin(ftype) is Annotated:
                    ftype = get_args(ftype)[0]
                if isinstance(ftype, type) and issubclass(ftype, MagicBase):
                    magic_const_defaults[fname] = getattr(ftype, "_raw_val", getattr(ftype, "_value", None))
                elif isinstance(ftype, type) and issubclass(ftype, ConstantBase):
                    magic_const_defaults[fname] = getattr(ftype, "_value", None)
                elif isinstance(ftype, type) and issubclass(ftype, (LengthOfBase, CountOfBase)):
                    magic_const_defaults[fname] = 0
                elif isinstance(ftype, type) and issubclass(ftype, ChecksumBase):
                    magic_const_defaults[fname] = 0

        target_cls = dataclass(slots=True)(target_cls)
        doc = inspect.cleandoc(target_cls.__doc__) if target_cls.__doc__ else ""
        target_cls.__binary__ = BinaryMetadata(
            target_cls,
            endian=endian,
            bits=bits,
            align=align,
            auto_align=auto_align,
            total_size=total_size,
            pad_byte=pad_byte,
            doc=doc,
        )

        all_defaults = {**magic_const_defaults, **user_defaults}
        if all_defaults or user_default_factories:
            orig_init = target_cls.__init__
            from dataclasses import fields as dc_fields
            def wrapped_init(self, *args, **kwargs):
                all_fnames = [f.name for f in dc_fields(self.__class__)]
                if args:
                    non_default_names = [fn for fn in all_fnames if fn not in all_defaults and fn not in user_default_factories]
                    if len(args) == len(non_default_names):
                        for fn, arg_val in zip(non_default_names, args):
                            kwargs[fn] = arg_val
                        args = ()
                    elif len(args) <= len(all_fnames):
                        for fn, arg_val in zip(all_fnames[:len(args)], args):
                            kwargs[fn] = arg_val
                        args = ()
                for k, factory in user_default_factories.items():
                    if k not in kwargs:
                        kwargs[k] = factory()
                for k, v in all_defaults.items():
                    if k not in kwargs:
                        kwargs[k] = v
                for fn in all_fnames:
                    if fn not in kwargs:
                        raise TypeError(f"{self.__class__.__name__}.__init__() missing required argument: {fn!r}")
                orig_init(self, *args, **kwargs)
            target_cls.__init__ = wrapped_init

        target_cls.to_bytes = to_bytes
        target_cls.from_bytes = classmethod(from_bytes)
        target_cls.to_dict = to_dict_method
        target_cls.from_dict = classmethod(from_dict_method)
        target_cls.to_json = to_json_method
        target_cls.from_json = classmethod(from_json_method)
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
        target_cls.to_markdown = _ToMarkdownDescriptor()
        target_cls.write_markdown = _WriteMarkdownDescriptor()
        target_cls.to_html = _ToHtmlDescriptor()
        target_cls.write_html = _WriteHtmlDescriptor()
        target_cls.to_code = _ToCodeDescriptor()
        target_cls.write_code = _WriteCodeDescriptor()
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
    if isinstance(ftype, type) and issubclass(ftype, MagicBase):
        return min(ftype.size, 8) if isinstance(ftype.value, int) else 1
    if isinstance(ftype, type) and issubclass(ftype, ConstantBase):
        return _get_field_alignment(ftype.target_type)
    if isinstance(ftype, type) and issubclass(ftype, ChecksumBase):
        return min(ftype.size, 8)
    if isinstance(ftype, tuple) and len(ftype) >= 2 and isinstance(ftype[0], type) and issubclass(ftype[0], enum.Enum):
        return _get_field_alignment(ftype[1])
    if isinstance(ftype, type) and issubclass(ftype, enum.Enum):
        max_v = max([abs(m.value) for m in ftype], default=0)
        return 1 if max_v <= 255 else (2 if max_v <= 65535 else 4)
    if isinstance(ftype, VarIntTypeMeta):
        return 1
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
                b_val = write_val if isinstance(write_val, (bytes, bytearray)) else (write_val.encode("utf-8") if isinstance(write_val, str) else expected)
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
            int_val = val.value if isinstance(val, enum.Enum) else int(val)
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
        field_aligns = [_get_field_alignment(ft, getattr(instance, fn, None)) for fn, ft in fields.items()]
        max_field_align = max(field_aligns, default=1)
        struct_boundary = align_setting if align_setting else max_field_align
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
    known_counts: dict[str, int] = {}
    known_lengths: dict[str, int] = {}

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
            explicit_count = known_counts.get(name)
            explicit_length = known_lengths.get(name)

            if explicit_count is not None:
                items = []
                for _ in range(explicit_count):
                    if elem_t is Bool or (isinstance(elem_t, type) and issubclass(elem_t, Bool)) or elem_t is bool:
                        b_size = getattr(elem_t, "_size", 1) if elem_t is not bool else 1
                        items.append(reader.read_bool(size=b_size, endian=active_endian))
                    elif elem_t is UInt8:
                        items.append(reader.read_uint8())
                    elif isinstance(elem_t, type) and issubclass(elem_t, BinaryType):
                        items.append(reader._unpack_read(elem_t._fmt, elem_t._size, endian=active_endian))
                    elif hasattr(elem_t, "__binary__"):
                        items.append(read_struct(elem_t, reader=reader, endian=active_endian))
                    else:
                        items.append(reader.read_uint8())
                kwargs[name] = bytes(items) if elem_t is UInt8 else items
            elif explicit_length is not None:
                stop_pos = reader.tell() + explicit_length
                items = []
                while reader.tell() < stop_pos and reader.remaining() > 0:
                    if elem_t is Bool or (isinstance(elem_t, type) and issubclass(elem_t, Bool)) or elem_t is bool:
                        b_size = getattr(elem_t, "_size", 1) if elem_t is not bool else 1
                        items.append(reader.read_bool(size=b_size, endian=active_endian))
                    elif elem_t is UInt8:
                        items.append(reader.read_uint8())
                    elif isinstance(elem_t, type) and issubclass(elem_t, BinaryType):
                        items.append(reader._unpack_read(elem_t._fmt, elem_t._size, endian=active_endian))
                    elif hasattr(elem_t, "__binary__"):
                        items.append(read_struct(elem_t, reader=reader, endian=active_endian))
                    else:
                        items.append(reader.read_uint8())
                kwargs[name] = bytes(items) if elem_t is UInt8 else items
            else:
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

        # Check FixedString type
        if isinstance(ftype, type) and issubclass(ftype, FixedString):
            enc = getattr(ftype, "encoding", "utf-8")
            pad = getattr(ftype, "pad_byte", b"\x00")
            kwargs[name] = reader.read_fixed_string(ftype._size, pad_byte=pad, encoding=enc)
            continue

        # Check Bytes type
        if isinstance(ftype, type) and issubclass(ftype, Bytes):
            explicit_len = known_lengths.get(name, known_counts.get(name))
            if explicit_len is not None:
                kwargs[name] = reader.read_bytes(explicit_len)
            else:
                kwargs[name] = reader.read_bytes(ftype._size if ftype._size > 0 else None)
            continue

        # Check CString type
        if ftype is CString or (isinstance(ftype, type) and issubclass(ftype, CString)):
            enc = getattr(ftype, "encoding", "utf-8")
            kwargs[name] = reader.read_cstring(encoding=enc)
            continue

        # Check PrefixedString type
        if ftype is PrefixedString or (isinstance(ftype, type) and issubclass(ftype, PrefixedString)):
            p_bytes = getattr(ftype, "prefix_bytes", 1)
            enc = getattr(ftype, "encoding", "utf-8")
            kwargs[name] = reader.read_prefixed_string(prefix_bytes=p_bytes, endian=active_endian, encoding=enc)
            continue

        # Check Magic type
        if isinstance(ftype, type) and issubclass(ftype, MagicBase):
            expected = getattr(ftype, "_value", None)
            raw_val = getattr(ftype, "_raw_val", expected)
            if isinstance(expected, bytes):
                read_b = reader.read_bytes(len(expected))
                if read_b != expected:
                    raise InvalidMagicError(
                        f"Magic mismatch for field '{name}': expected {expected!r}, got {read_b!r}"
                    )
                kwargs[name] = read_b
            else:
                fmt_char = getattr(ftype, "_fmt", "I")
                size = getattr(ftype, "_size", 4)
                val = reader._unpack_read(fmt_char, size, endian=active_endian)
                if val != raw_val:
                    raise InvalidMagicError(
                        f"Magic mismatch for field '{name}': expected {raw_val!r}, got {val!r}"
                    )
                kwargs[name] = val
            continue

        # Check Constant type
        if isinstance(ftype, type) and issubclass(ftype, ConstantBase):
            target_t = getattr(ftype, "_type", UInt32)
            expected = getattr(ftype, "_value", None)
            fmt_char = getattr(target_t, "_fmt", "I")
            size = getattr(target_t, "_size", 4)
            val = reader._unpack_read(fmt_char, size, endian=active_endian)
            if val != expected:
                raise InvalidConstantError(
                    f"Constant mismatch for field '{name}': expected {expected!r}, got {val!r}"
                )
            kwargs[name] = val
            continue

        # Check Range constraint
        if isinstance(ftype, type) and issubclass(ftype, RangeBase):
            fmt = getattr(ftype, "_fmt", "")
            sz = getattr(ftype, "_size", 4)
            val = reader._unpack_read(fmt, sz, endian=active_endian)
            min_v = ftype._min
            max_v = ftype._max
            if not (min_v <= val <= max_v):
                raise RangeValidationError(name, val, min_v, max_v)
            kwargs[name] = val
            continue

        # Check LengthOf / CountOf
        if isinstance(ftype, type) and issubclass(ftype, (LengthOfBase, CountOfBase)):
            fmt_char = getattr(ftype, "_fmt", "H")
            sz = getattr(ftype, "_size", 2)
            val = reader._unpack_read(fmt_char, sz, endian=active_endian)
            kwargs[name] = val
            target_name = getattr(ftype, "_target", "")
            delta = getattr(ftype, "_delta", 0)
            if target_name:
                if issubclass(ftype, CountOfBase):
                    known_counts[target_name] = val - delta
                else:
                    known_lengths[target_name] = val - delta
            continue

        # Check ChecksumBase type
        if isinstance(ftype, type) and issubclass(ftype, ChecksumBase):
            cur_pos = reader.tell()
            brange = getattr(ftype, "_range", None)
            start_idx = struct_start_pos if (brange is None or brange.start is None) else brange.start
            end_idx = cur_pos if (brange is None or brange.stop is None) else brange.stop
            with reader.preserve_position():
                reader.seek(start_idx)
                covered_bytes = reader.read_bytes(end_idx - start_idx)
            calculated = compute_checksum(ftype._algorithm, covered_bytes)
            size = ftype._size
            fmt_char = {1: "B", 2: "H", 4: "I", 8: "Q"}.get(size, "I")
            val = reader._unpack_read(fmt_char, size, endian=active_endian)
            if val != calculated:
                raise ChecksumMismatchError(
                    f"Checksum mismatch for field '{name}': computed {hex(calculated)}, got {hex(val)} in stream"
                )
            kwargs[name] = val
            continue

        # Check VarInt / VarUInt types
        if isinstance(ftype, VarIntTypeMeta):
            if ftype.is_signed:
                kwargs[name] = reader.read_varint()
            else:
                kwargs[name] = reader.read_varuint()
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
            fmt_char = {1: "B", 2: "H", 4: "I", 8: "Q"}.get(enum_size, "I")
            raw_val = reader._unpack_read(fmt_char, enum_size, endian=active_endian)
            try:
                kwargs[name] = enum_cls(raw_val)
            except ValueError as exc:
                raise InvalidEnumError(
                    f"Invalid enum value {raw_val} for {enum_cls.__name__} in field '{name}'"
                ) from exc
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
        field_aligns = [_get_field_alignment(ft, None) for fn, ft in fields.items()]
        max_field_align = max(field_aligns, default=1)
        struct_boundary = align_setting if align_setting else max_field_align
        if struct_boundary > 1:
            reader.align(struct_boundary)

    # Struct total_size padding
    total_size_setting = meta.get("total_size")
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
