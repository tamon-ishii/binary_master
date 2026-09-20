from __future__ import annotations

import enum
import struct
import sys
from typing import (
    Annotated,
    Any,
    Optional,
    get_args,
    get_origin,
)

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
    Int8,
    LengthOfBase,
    MagicBase,
    Offset,
    OffsetTable,
    PrefixedString,
    RangeBase,
    UInt8,
    UInt32,
    Variant,
    _extract_named_offset_info,
    _is_named_offset_spec,
    _is_offset_table_spec,
    _normalize_offset_type,
    _parse_offset_spec_args,
)
from binary_master.checksum import ChecksumBase
from binary_master.compressed import CompressedBase
from binary_master.enums import Endian, normalize_endian, normalize_offset_key
from binary_master.metadata import _get_field_alignment, _safe_issubclass
from binary_master.varint import VarIntTypeMeta


class FieldKind:
    PRIMITIVE = 1          # UInt8, UInt16, UInt32, Int8, Float32, etc.
    BOOL = 2               # Bool / Bool[N]
    FIXED_STRING = 3       # FixedString[N]
    BYTES = 4              # Bytes[N]
    C_STRING = 5           # CString
    PREFIXED_STRING = 6    # PrefixedString[N]
    MAGIC = 7              # Magic[...]
    CONSTANT = 8           # Constant[Type, Val]
    RANGE = 9              # Range[Type, min, max]
    LENGTH_OF = 10         # LengthOf[Type, target, delta]
    COUNT_OF = 11          # CountOf[Type, target, delta]
    CHECKSUM = 12          # Checksum[Algo, ...]
    VARINT = 13            # VarInt / VarUInt
    ENUM = 14              # Enum / BinaryEnum
    NESTED_STRUCT = 15     # @binary_struct
    FIXED_ARRAY = 16       # FixedArray[elem_t, count]
    ARRAY = 17             # Array[elem_t]
    OFFSET = 18            # Offset[...]
    NAMED_OFFSET = 19      # Offset[key, ...]
    OFFSET_TABLE = 20      # OffsetTable[...]
    VARIANT = 21           # Variant[...]
    PYTHON_PRIMITIVE = 22  # int, float, bool, bytes, str
    COMPRESSED = 23        # Compressed[T, algo]


class FieldPlan:
    __slots__ = (
        "name",
        "kind",
        "align",
        "fmt",
        "size",
        "f_desc",
        "target_type",
        "expected",
        "raw_val",
        "min_val",
        "max_val",
        "target_name",
        "delta",
        "elem_type",
        "count",
        "elem_is_bool",
        "elem_is_uint8",
        "elem_is_int8",
        "elem_is_primitive",
        "elem_is_struct",
        "elem_bool_size",
        "elem_fmt",
        "elem_size",
        "enum_cls",
        "checksum_algo",
        "checksum_range",
        "varint_signed",
        "encoding",
        "pad_byte",
        "prefix_bytes",
        "offset_info",
        "variant_info",
        "raw_ftype",
        "nested_cls",
        "is_bytes_magic",
        "py_type",
    )

    name: str
    kind: int
    align: int
    fmt: str
    size: int
    f_desc: str
    target_type: Any
    expected: Any
    raw_val: Any
    min_val: Any
    max_val: Any
    target_name: str
    delta: int
    elem_type: Any
    count: Any
    elem_is_bool: bool
    elem_is_uint8: bool
    elem_is_int8: bool
    elem_is_primitive: bool
    elem_is_struct: bool
    elem_bool_size: int
    elem_fmt: str
    elem_size: int
    enum_cls: Any
    checksum_algo: Any
    checksum_range: Any
    varint_signed: bool
    encoding: str
    pad_byte: bytes
    prefix_bytes: int
    offset_info: Any
    variant_info: Any
    raw_ftype: Any
    nested_cls: Any
    is_bytes_magic: bool
    py_type: Any

    def __init__(self, name: str) -> None:
        self.name = name
        self.kind = FieldKind.PRIMITIVE
        self.align = 1
        self.fmt = ""
        self.size = 0
        self.f_desc = ""
        self.target_type = None
        self.expected = None
        self.raw_val = None
        self.min_val = None
        self.max_val = None
        self.target_name = ""
        self.delta = 0
        self.elem_type = None
        self.count = 0
        self.elem_is_bool = False
        self.elem_is_uint8 = False
        self.elem_is_int8 = False
        self.elem_is_primitive = False
        self.elem_is_struct = False
        self.elem_bool_size = 1
        self.elem_fmt = ""
        self.elem_size = 0
        self.enum_cls = None
        self.checksum_algo = None
        self.checksum_range = None
        self.varint_signed = False
        self.encoding = "utf-8"
        self.pad_byte = b"\x00"
        self.prefix_bytes = 1
        self.offset_info = None
        self.variant_info = None
        self.raw_ftype = None
        self.nested_cls = None
        self.is_bytes_magic = False
        self.py_type = None


class StructPlan:
    __slots__ = (
        "cls",
        "endian",
        "is_bitfield",
        "total_bits",
        "align_setting",
        "auto_align",
        "max_field_align",
        "total_size",
        "pad_byte",
        "field_plans",
        "can_fast_unpack",
        "can_fast_pack",
        "total_fixed_size",
        "fast_struct_little",
        "fast_struct_big",
        "fast_field_names",
    )

    cls: type
    endian: Endian
    is_bitfield: bool
    total_bits: Optional[int]
    align_setting: Optional[int]
    auto_align: bool
    max_field_align: int
    total_size: Optional[int]
    pad_byte: bytes
    field_plans: list[FieldPlan]
    can_fast_unpack: bool
    can_fast_pack: bool
    total_fixed_size: int
    fast_struct_little: Optional[struct.Struct]
    fast_struct_big: Optional[struct.Struct]
    fast_field_names: tuple[str, ...]

    def __init__(self, cls: type) -> None:
        self.cls = cls
        self.endian = Endian.LITTLE
        self.is_bitfield = False
        self.total_bits = None
        self.align_setting = None
        self.auto_align = False
        self.max_field_align = 1
        self.total_size = None
        self.pad_byte = b"\x00"
        self.field_plans: list[FieldPlan] = []
        self.can_fast_unpack = False
        self.can_fast_pack = False
        self.total_fixed_size = 0
        self.fast_struct_little = None
        self.fast_struct_big = None
        self.fast_field_names: tuple[str, ...] = ()


def compile_struct_plan(cls: type) -> StructPlan:
    meta = getattr(cls, "__binary__", None)
    if meta is None:
        meta = {}
    plan = StructPlan(cls)
    plan.endian = normalize_endian(meta.get("endian", "little"))
    total_bits = meta.get("bits")
    plan.is_bitfield = isinstance(total_bits, int)
    plan.total_bits = total_bits
    plan.align_setting = meta.get("align")
    plan.auto_align = meta.get("auto_align", False)
    plan.total_size = meta.get("total_size")
    pad_b = meta.get("pad_byte", b"\x00")
    if isinstance(pad_b, int):
        pad_b = bytes([pad_b])
    plan.pad_byte = pad_b

    fields = meta.get("fields", {})
    descriptions = meta.get("descriptions", {})

    field_aligns: list[int] = []
    field_plans: list[FieldPlan] = []
    all_primitive = True
    fast_fmts: list[str] = []
    fast_names: list[str] = []

    for name, ftype in fields.items():
        fp = FieldPlan(name)
        fp.raw_ftype = ftype
        f_desc = descriptions.get(name, "")

        # Unwrap Annotated
        if get_origin(ftype) is Annotated:
            args = get_args(ftype)
            if not f_desc:
                for arg in args[1:]:
                    if isinstance(arg, str):
                        f_desc = arg
                        break
            ftype = args[0]
        if isinstance(ftype, str):
            import binary_master

            mod = sys.modules.get(cls.__module__)
            lookup_ns = {**binary_master.__dict__, **(getattr(mod, "__dict__", {}) if mod else {})}
            if ftype in lookup_ns:
                ftype = lookup_ns[ftype]
            else:
                try:
                    ftype = eval(ftype, lookup_ns)
                except Exception:
                    pass

        fp.align = _get_field_alignment(ftype, None)
        field_aligns.append(fp.align)

        # Check Named Offset (Offset["key", ...])
        is_named_offset = _is_named_offset_spec(ftype)
        if is_named_offset:
            fp.kind = FieldKind.NAMED_OFFSET
            all_primitive = False
            key_arg, target_type, offset_t, base_offset = _extract_named_offset_info(ftype)
            key_name = normalize_offset_key(key_arg)
            fmt_char, offset_size, offset_label = _normalize_offset_type(offset_t)
            fp.fmt = fmt_char
            fp.size = offset_size
            fp.target_type = target_type
            fp.offset_info = (key_arg, key_name, offset_t, base_offset, offset_label)
            field_plans.append(fp)
            continue

        # Check Direct Offset (Offset[Target, ...])
        is_offset = (
            (isinstance(ftype, tuple) and len(ftype) >= 1 and ftype[0] is Offset)
            or (get_origin(ftype) is Offset)
        )
        if is_offset:
            fp.kind = FieldKind.OFFSET
            all_primitive = False
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
            fmt_char, offset_size, offset_label = _normalize_offset_type(offset_t)
            fp.fmt = fmt_char
            fp.size = offset_size
            fp.target_type = target_type
            fp.offset_info = (offset_t, base_offset, offset_label, _is_offset_table_spec(target_type))
            field_plans.append(fp)
            continue

        # Check OffsetTable
        is_offset_table = (
            (isinstance(ftype, tuple) and len(ftype) >= 2 and ftype[0] is OffsetTable)
            or (get_origin(ftype) is OffsetTable)
        )
        if is_offset_table:
            fp.kind = FieldKind.OFFSET_TABLE
            all_primitive = False
            if isinstance(ftype, tuple):
                count = ftype[1]
                offset_t, base_offset = _parse_offset_spec_args(ftype[2:])
            else:
                args = get_args(ftype)
                count = args[0]
                offset_t, base_offset = _parse_offset_spec_args(args[1:])
            fmt_char, offset_size, offset_label = _normalize_offset_type(offset_t)
            fp.fmt = fmt_char
            fp.size = offset_size
            fp.count = count
            fp.offset_info = (offset_t, base_offset, offset_label)
            field_plans.append(fp)
            continue

        # Check Variant
        is_variant = (
            (isinstance(ftype, tuple) and len(ftype) >= 3 and ftype[0] is Variant)
            or (get_origin(ftype) is Variant)
        )
        if is_variant:
            fp.kind = FieldKind.VARIANT
            all_primitive = False
            tag_field = ftype[1] if isinstance(ftype, tuple) else get_args(ftype)[0]
            mapping = ftype[2] if isinstance(ftype, tuple) else get_args(ftype)[1]
            fp.variant_info = (tag_field, mapping)
            field_plans.append(fp)
            continue

        # Check FixedArray
        is_fixed = (
            (isinstance(ftype, tuple) and len(ftype) >= 3 and ftype[0] is FixedArray)
            or (get_origin(ftype) is FixedArray)
        )
        if is_fixed:
            fp.kind = FieldKind.FIXED_ARRAY
            all_primitive = False
            elem_t, count = (ftype[1], ftype[2]) if isinstance(ftype, tuple) else (get_args(ftype)[0], get_args(ftype)[1])
            fp.elem_type = elem_t
            fp.count = count
            fp.elem_is_bool = elem_t is Bool or _safe_issubclass(elem_t, Bool) or elem_t is bool
            fp.elem_bool_size = getattr(elem_t, "_size", 1) if elem_t is not bool else 1
            fp.elem_is_uint8 = elem_t is UInt8
            fp.elem_is_int8 = elem_t is Int8
            fp.elem_is_primitive = isinstance(elem_t, type) and _safe_issubclass(elem_t, BinaryType)
            fp.elem_is_struct = hasattr(elem_t, "__binary__")
            if fp.elem_is_primitive:
                fp.elem_fmt = elem_t._fmt
                fp.elem_size = elem_t._size
            field_plans.append(fp)
            continue

        # Check Array
        is_arr = (
            (isinstance(ftype, tuple) and len(ftype) >= 2 and ftype[0] is Array)
            or (get_origin(ftype) is Array)
        )
        if is_arr:
            fp.kind = FieldKind.ARRAY
            all_primitive = False
            elem_t = ftype[1] if isinstance(ftype, tuple) else get_args(ftype)[0]
            fp.elem_type = elem_t
            fp.elem_is_bool = elem_t is Bool or _safe_issubclass(elem_t, Bool) or elem_t is bool
            fp.elem_bool_size = getattr(elem_t, "_size", 1) if elem_t is not bool else 1
            fp.elem_is_uint8 = elem_t is UInt8
            fp.elem_is_int8 = elem_t is Int8
            fp.elem_is_primitive = isinstance(elem_t, type) and _safe_issubclass(elem_t, BinaryType)
            fp.elem_is_struct = hasattr(elem_t, "__binary__")
            if fp.elem_is_primitive:
                fp.elem_fmt = elem_t._fmt
                fp.elem_size = elem_t._size
            field_plans.append(fp)
            continue

        # Check nested binary_struct
        if hasattr(ftype, "__binary__"):
            fp.kind = FieldKind.NESTED_STRUCT
            all_primitive = False
            fp.nested_cls = ftype
            field_plans.append(fp)
            continue

        # Check Bool
        if ftype is Bool or _safe_issubclass(ftype, Bool):
            fp.kind = FieldKind.BOOL
            fp.size = getattr(ftype, "_size", 1)
            fp.fmt = {1: "?", 2: "H", 4: "I", 8: "Q"}.get(fp.size, "?")
            if fp.size == 1:
                fast_fmts.append("?")
                fast_names.append(name)
            else:
                all_primitive = False
            field_plans.append(fp)
            continue

        # Check FixedString
        if _safe_issubclass(ftype, FixedString):
            fp.kind = FieldKind.FIXED_STRING
            all_primitive = False
            fp.size = getattr(ftype, "_size", 0)
            fp.encoding = getattr(ftype, "encoding", "utf-8")
            fp.pad_byte = getattr(ftype, "pad_byte", b"\x00")
            field_plans.append(fp)
            continue

        # Check Bytes
        if _safe_issubclass(ftype, Bytes):
            fp.kind = FieldKind.BYTES
            fp.size = getattr(ftype, "_size", 0)
            if fp.size > 0:
                fp.fmt = f"{fp.size}s"
                fast_fmts.append(fp.fmt)
                fast_names.append(name)
            else:
                all_primitive = False
            field_plans.append(fp)
            continue

        # Check CString
        if ftype is CString or _safe_issubclass(ftype, CString):
            fp.kind = FieldKind.C_STRING
            all_primitive = False
            fp.encoding = getattr(ftype, "encoding", "utf-8")
            field_plans.append(fp)
            continue

        # Check PrefixedString
        if ftype is PrefixedString or _safe_issubclass(ftype, PrefixedString):
            fp.kind = FieldKind.PREFIXED_STRING
            all_primitive = False
            fp.prefix_bytes = getattr(ftype, "prefix_bytes", 1)
            fp.encoding = getattr(ftype, "encoding", "utf-8")
            field_plans.append(fp)
            continue

        # Check Magic
        if _safe_issubclass(ftype, MagicBase):
            fp.kind = FieldKind.MAGIC
            all_primitive = False
            expected = getattr(ftype, "_value", None)
            fp.expected = expected
            fp.raw_val = getattr(ftype, "_raw_val", expected)
            fp.is_bytes_magic = isinstance(expected, bytes)
            fp.size = getattr(ftype, "_size", len(expected) if isinstance(expected, bytes) else 4)
            fp.fmt = getattr(ftype, "_fmt", "I")
            field_plans.append(fp)
            continue

        # Check Constant
        if _safe_issubclass(ftype, ConstantBase):
            fp.kind = FieldKind.CONSTANT
            all_primitive = False
            target_t = getattr(ftype, "_type", UInt32)
            fp.target_type = target_t
            fp.expected = getattr(ftype, "_value", None)
            fp.fmt = getattr(target_t, "_fmt", "I")
            fp.size = getattr(target_t, "_size", 4)
            field_plans.append(fp)
            continue

        # Check Range
        if _safe_issubclass(ftype, RangeBase):
            fp.kind = FieldKind.RANGE
            all_primitive = False
            fp.fmt = getattr(ftype, "_fmt", "")
            fp.size = getattr(ftype, "_size", 4)
            fp.min_val = getattr(ftype, "_min", 0)
            fp.max_val = getattr(ftype, "_max", 0)
            field_plans.append(fp)
            continue

        # Check LengthOf
        if _safe_issubclass(ftype, LengthOfBase):
            fp.kind = FieldKind.LENGTH_OF
            all_primitive = False
            fp.fmt = getattr(ftype, "_fmt", "H")
            fp.size = getattr(ftype, "_size", 2)
            fp.target_name = getattr(ftype, "_target", "")
            fp.delta = getattr(ftype, "_delta", 0)
            field_plans.append(fp)
            continue

        # Check CountOf
        if _safe_issubclass(ftype, CountOfBase):
            fp.kind = FieldKind.COUNT_OF
            all_primitive = False
            fp.fmt = getattr(ftype, "_fmt", "I")
            fp.size = getattr(ftype, "_size", 4)
            fp.target_name = getattr(ftype, "_target", "")
            fp.delta = getattr(ftype, "_delta", 0)
            field_plans.append(fp)
            continue

        # Check ChecksumBase
        if _safe_issubclass(ftype, ChecksumBase):
            fp.kind = FieldKind.CHECKSUM
            all_primitive = False
            fp.checksum_algo = getattr(ftype, "_algorithm", "crc32")
            fp.checksum_range = getattr(ftype, "_range", None)
            fp.size = getattr(ftype, "_size", 4)
            fp.fmt = {1: "B", 2: "H", 4: "I", 8: "Q"}.get(fp.size, "I")
            field_plans.append(fp)
            continue

        # Check Compressed
        if _safe_issubclass(ftype, CompressedBase):
            fp.kind = FieldKind.COMPRESSED
            all_primitive = False
            fp.target_type = getattr(ftype, "_target_type", bytes)
            fp.checksum_algo = getattr(ftype, "_algo", "zlib")
            field_plans.append(fp)
            continue

        # Check VarInt / VarUInt
        if isinstance(ftype, VarIntTypeMeta):
            fp.kind = FieldKind.VARINT
            all_primitive = False
            fp.varint_signed = ftype.is_signed
            field_plans.append(fp)
            continue

        # Check Enum
        is_enum = False
        enum_cls = None
        enum_size = 4
        if isinstance(ftype, tuple) and len(ftype) >= 2 and _safe_issubclass(ftype[0], enum.Enum):
            is_enum = True
            enum_cls = ftype[0]
            enum_size = getattr(ftype[1], "_size", 4)
        elif _safe_issubclass(ftype, enum.Enum):
            is_enum = True
            enum_cls = ftype
            max_v = max([abs(m.value) for m in enum_cls], default=0)
            enum_size = 1 if max_v <= 255 else (2 if max_v <= 65535 else 4)

        if is_enum and enum_cls is not None:
            fp.kind = FieldKind.ENUM
            all_primitive = False
            fp.enum_cls = enum_cls
            fp.size = enum_size
            fp.fmt = {1: "B", 2: "H", 4: "I", 8: "Q"}.get(enum_size, "I")
            field_plans.append(fp)
            continue

        # Check primitive BinaryType
        if _safe_issubclass(ftype, BinaryType):
            fp.kind = FieldKind.PRIMITIVE
            fp.fmt = getattr(ftype, "_fmt", "")
            fp.size = getattr(ftype, "_size", 0)
            if fp.fmt:
                fast_fmts.append(fp.fmt)
                fast_names.append(name)
            else:
                all_primitive = False
            field_plans.append(fp)
            continue

        # Standard Python types
        fp.kind = FieldKind.PYTHON_PRIMITIVE
        fp.py_type = ftype
        all_primitive = False
        field_plans.append(fp)

    plan.max_field_align = max(field_aligns, default=1)
    plan.field_plans = field_plans

    # Determine if fast-path is applicable
    if (
        all_primitive
        and not plan.is_bitfield
        and plan.align_setting is None
        and not plan.auto_align
        and plan.total_size is None
        and len(fast_fmts) == len(field_plans)
        and len(fast_fmts) > 0
    ):
        comb = "".join(fast_fmts)
        plan.fast_struct_little = struct.Struct(f"<{comb}")
        plan.fast_struct_big = struct.Struct(f">{comb}")
        plan.total_fixed_size = plan.fast_struct_little.size
        plan.fast_field_names = tuple(fast_names)
        plan.can_fast_unpack = True
        plan.can_fast_pack = True

    return plan


_STRUCT_PLAN_CACHE: dict[type, StructPlan] = {}


def get_struct_plan(cls: type) -> StructPlan:
    """Retrieve or compile the cached execution plan for a @binary_struct class."""
    plan = _STRUCT_PLAN_CACHE.get(cls)
    if plan is None:
        plan = compile_struct_plan(cls)
        _STRUCT_PLAN_CACHE[cls] = plan
    return plan
