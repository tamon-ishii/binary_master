from __future__ import annotations

import enum
from typing import (
    Annotated,
    Any,
    Generic,
    Literal,
    Optional,
    TypeVar,
    Union,
    get_args,
    get_origin,
)


def _unwrap_literal_int(val: Any) -> Any:
    """Extracts int value if val is a Literal[int], else returns val."""
    if get_origin(val) is Literal:
        args = get_args(val)
        if args and isinstance(args[0], int):
            return args[0]
    return val


def _get_type_size(target_t: Any, default: int = 4) -> int:
    """Helper to determine type size without circular import of sizeof."""
    if hasattr(target_t, '_size') and isinstance(target_t._size, int) and target_t._size > 0:
        return target_t._size
    if hasattr(target_t, '__binary__'):
        from binary_master.metadata import sizeof
        return sizeof(target_t)
    return default


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


# Modern compact primitive type aliases (Pattern Language / Rust / ImHex style)
u8 = UInt8
u16 = UInt16
u32 = UInt32
u64 = UInt64

i8 = Int8
i16 = Int16
i32 = Int32
i64 = Int64

s8 = Int8
s16 = Int16
s32 = Int32
s64 = Int64

f16 = Float16
f32 = Float32
f64 = Float64


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

    def __getitem__(cls, name: Any) -> Any:
        if isinstance(name, str) and name in cls._member_map_:
            return cls._member_map_[name]
        return (cls, name)


class BinaryEnum(enum.IntEnum, metaclass=BinaryEnumMeta):
    """Base class for binary integer enums supporting explicit integer sizing (e.g. MyEnum[UInt8])."""
    pass


class BinaryFlag(enum.IntFlag, metaclass=BinaryEnumMeta):
    """Base class for binary bitmask flags supporting bitwise operations and explicit integer sizing (e.g. MyFlags[UInt16])."""
    pass


class MagicMeta(type):
    """Metaclass for Magic[...] types."""

    _value: Any = None
    _raw_val: Any = None
    _size: int = 0
    _fmt: str = ""

    def __getitem__(cls, val: Any) -> type:
        b_val: Any
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
        size = _get_type_size(target_t, 4)
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
        sz = _get_type_size(target_t, 4)
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

        sz = _get_type_size(target_t, 2)
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

        sz = _get_type_size(target_t, 4)
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


T1 = TypeVar("T1")
T2 = TypeVar("T2", default=Any)
T3 = TypeVar("T3", default=Any)
T4 = TypeVar("T4", default=Any)


def _parse_named_offset_args(args: Any) -> tuple[Any, Any, Any, Any]:
    """Parses arguments for key-based Offset: (key, target_type, offset_type, base_offset)."""
    if not isinstance(args, tuple):
        return args, None, UInt32, 0

    key = args[0]
    rest = args[1:]
    target_type = None
    offset_type = UInt32
    base_offset = 0

    for a in rest:
        if _is_base_offset_arg(a):
            base_offset = a
        elif _is_offset_type_arg(a):
            offset_type = a
        elif isinstance(a, int) and a not in (1, 2, 4, 8) and base_offset == 0:
            base_offset = a
        else:
            target_type = a

    return key, target_type, offset_type, base_offset


def _is_named_offset_spec(ftype: Any) -> bool:
    """Check if ftype is a named offset specification (e.g. Offset['key', ...])."""
    if isinstance(ftype, tuple) and len(ftype) == 5 and ftype[0] is Offset:
        return True
    if get_origin(ftype) is Offset:
        args = get_args(ftype)
        if args and isinstance(args[0], enum.Enum):
            return True
        if args and isinstance(args[0], str):
            first = args[0]
            if "/" in first or not (first.isidentifier() and first[0].isupper()):
                return True
            if len(args) >= 2 and (isinstance(args[1], type) or hasattr(args[1], "__binary__")):
                return True
    return False


def _extract_named_offset_info(ftype: Any) -> tuple[Any, Optional[Any], Any, Any]:
    """Extract (key, target_type, offset_type, base_offset) from an Offset field type."""
    if isinstance(ftype, tuple):
        if len(ftype) >= 5 and ftype[0] is Offset:
            return ftype[1], ftype[2], ftype[3], ftype[4]
        return _parse_named_offset_args(ftype[1:])
    elif get_args(ftype):
        return _parse_named_offset_args(get_args(ftype))
    return None, None, UInt32, 0


class Offset(Generic[T1, T2, T3, T4]):
    """シリアライズ時に自動計算されるオフセット:
    直接指定: Offset[Target, OffsetType=UInt32, BaseOffset=0]
    名前指定: Offset["key", Target=None, OffsetType=UInt32, BaseOffset=0]
    """

    def __init__(self, target: Any = None, offset: Optional[int] = None):
        self.target = target
        self.offset = offset

    def __getattr__(self, name: str) -> Any:
        if self.target is not None and hasattr(self.target, name):
            return getattr(self.target, name)
        raise AttributeError(f"'Offset' object has no attribute '{name}'")

    def __class_getitem__(cls, args):
        if isinstance(args, tuple):
            first = args[0]
            if isinstance(first, enum.Enum):
                key, target_t, offset_t, base_offset = _parse_named_offset_args(args)
                return cls, key, target_t, offset_t, base_offset
            if isinstance(first, str):
                is_named = True
                if len(args) == 1 and first.isidentifier() and first[0].isupper():
                    is_named = False
                elif (
                    len(args) >= 2
                    and first.isidentifier()
                    and first[0].isupper()
                    and (_is_offset_type_arg(args[1]) or _is_base_offset_arg(args[1]))
                ):
                    is_named = False
                if is_named:
                    key, target_t, offset_t, base_offset = _parse_named_offset_args(args)
                    return cls, key, target_t, offset_t, base_offset
                else:
                    target_t = first
                    offset_t, base_offset = _parse_offset_spec_args(args[1:])
                    return cls, target_t, offset_t, base_offset
            if len(args) >= 1 and args[0] is OffsetTable:
                target_t = args
                offset_t = UInt32
                base_offset = 0
                return cls, target_t, offset_t, base_offset
            target_t = args[0]
            offset_t, base_offset = _parse_offset_spec_args(args[1:])
        elif isinstance(args, enum.Enum):
            key, target_t, offset_t, base_offset = _parse_named_offset_args((args,))
            return cls, key, target_t, offset_t, base_offset
        elif isinstance(args, str):
            if "/" in args or (args and not (args.isidentifier() and args[0].isupper())):
                key, target_t, offset_t, base_offset = _parse_named_offset_args((args,))
                return cls, key, target_t, offset_t, base_offset
            target_t = args
            offset_t = UInt32
            base_offset = 0
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


class FixedArray(Generic[T1, T2]):
    """固定長配列"""

    def __class_getitem__(cls, args):
        if isinstance(args, tuple) and len(args) == 2:
            element_type, count = args
            return cls, element_type, _unwrap_literal_int(count)
        return cls, args


class Bits(Generic[T1]):

    def __class_getitem__(cls, width):
        return cls, _unwrap_literal_int(width)


class OffsetTable(Generic[T1, T2, T3]):
    """オフセットテーブル型: OffsetTable[Count, OffsetType, BaseOffset] または OffsetTable[Count, OffsetType] または OffsetTable[Count]"""

    def __class_getitem__(cls, args):
        if isinstance(args, tuple):
            count = _unwrap_literal_int(args[0])
            offset_t, base_offset = _parse_offset_spec_args(args[1:])
        else:
            count = _unwrap_literal_int(args)
            offset_t = UInt32
            base_offset = 0
        return cls, count, offset_t, base_offset



class Variant(Generic[T1, T2, T3]):
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


def _is_offset_table_spec(t: Any) -> bool:
    """Check if type specification represents an OffsetTable."""
    if t is OffsetTable:
        return True
    if isinstance(t, tuple) and len(t) >= 1 and t[0] is OffsetTable:
        return True
    if get_origin(t) is OffsetTable:
        return True
    return False


def _get_field_default_zero(ftype: Any) -> tuple[Any, bool]:
    """Returns (default_value_or_factory, is_factory) for zero-initialization."""
    if get_origin(ftype) is Annotated:
        ftype = get_args(ftype)[0]

    # Offset[OffsetTable[...]]
    if (isinstance(ftype, tuple) and len(ftype) >= 1 and ftype[0] is Offset) or get_origin(ftype) is Offset:
        target_t = ftype[1] if isinstance(ftype, tuple) and len(ftype) >= 2 else (get_args(ftype)[0] if get_args(ftype) else None)
        if _is_offset_table_spec(target_t):
            return (list, True)
        return (0, False)

    # OffsetTable
    if _is_offset_table_spec(ftype):
        return (list, True)

    # Key-based Offset (Offset["key", ...])
    if _is_named_offset_spec(ftype):
        return (0, False)

    # FixedArray
    if (isinstance(ftype, tuple) and len(ftype) >= 3 and ftype[0] is FixedArray) or get_origin(ftype) is FixedArray:
        if isinstance(ftype, tuple):
            elem_t, count = ftype[1], ftype[2]
        else:
            args = get_args(ftype)
            elem_t, count = args[0], args[1]

        elem_name = getattr(elem_t, "__name__", str(elem_t))
        if elem_t in (UInt8, Int8, bytes) or elem_name in ("UInt8", "Int8"):
            return (b"\x00" * count, False)
        return ((lambda c=count: [0] * c), True)

    # Array
    if (isinstance(ftype, tuple) and len(ftype) >= 2 and ftype[0] is Array) or get_origin(ftype) is Array:
        return (list, True)

    # Floating point types
    if ftype in (Float16, Float32, Float64, float):
        return (0.0, False)

    # Bool types
    if ftype is Bool or (isinstance(ftype, type) and issubclass(ftype, Bool)) or ftype is bool:
        return (False, False)

    # Nested binary_struct
    if isinstance(ftype, type) and hasattr(ftype, "__binary__"):
        return ((lambda cls=ftype: cls()), True)

    # Enum types
    if isinstance(ftype, type) and issubclass(ftype, enum.Enum):
        members = list(ftype)
        if members:
            return (members[0], False)
        return (0, False)

    # String types
    if ftype is str or (isinstance(ftype, type) and issubclass(ftype, (FixedString, CString, PrefixedString))):
        return ("", False)

    # Bytes types
    if ftype is bytes or (isinstance(ftype, type) and issubclass(ftype, Bytes)):
        sz = getattr(ftype, "_size", 0)
        return (b"\x00" * sz if sz > 0 else b"", False)

    # Default for integers, Bits, VarInt, Magic, Constant, etc.
    return (0, False)


