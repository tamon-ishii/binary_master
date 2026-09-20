from __future__ import annotations

import dataclasses
import inspect
from dataclasses import dataclass
from pathlib import Path
from typing import (
    IO,
    Annotated,
    Any,
    Optional,
    TypeVar,
    Union,
    dataclass_transform,
    get_args,
    get_origin,
)

from binary_master.binary_types import (
    Array,
    Base,
    BinaryEnum,
    BinaryEnumMeta,
    BinaryFlag,
    BinaryType,
    BinaryTypeMeta,
    Bits,
    Bool,
    BoolMeta,
    Bytes,
    BytesMeta,
    Constant,
    ConstantBase,
    ConstantMeta,
    CountOf,
    CountOfBase,
    CountOfMeta,
    CString,
    FixedArray,
    FixedString,
    FixedStringMeta,
    Float16,
    Float32,
    Float64,
    Int8,
    Int16,
    Int32,
    Int64,
    LengthOf,
    LengthOfBase,
    LengthOfMeta,
    Magic,
    MagicBase,
    MagicMeta,
    Offset,
    OffsetTable,
    PrefixedString,
    PrefixedStringMeta,
    Range,
    RangeBase,
    RangeMeta,
    RelativeBase,
    UInt8,
    UInt16,
    UInt32,
    UInt64,
    Variant,
    _extract_named_offset_info,
    _get_field_default_zero,
    _is_base_offset_arg,
    _is_named_offset_spec,
    _is_offset_table_spec,
    _is_offset_type_arg,
    _normalize_offset_type,
    _parse_named_offset_args,
    _parse_offset_spec_args,
    _resolve_base_offset,
    _unwrap_literal_int,
    f16,
    f32,
    f64,
    i8,
    i16,
    i32,
    i64,
    s8,
    s16,
    s32,
    s64,
    u8,
    u16,
    u32,
    u64,
)
from binary_master.bridge import (
    _deserialize_dict_value,
    _serialize_dict_value,
    _ToCodeDescriptor,
    _ToHtmlDescriptor,
    _ToMarkdownDescriptor,
    _WriteCodeDescriptor,
    _WriteHtmlDescriptor,
    _WriteMarkdownDescriptor,
    async_iter_packets_method,
    attach_struct_methods,
    dummy_method,
    from_async_stream,
    from_bytes,
    from_dict_method,
    from_file,
    from_json_method,
    from_stream,
    iter_packets_method,
    iter_views_method,
    struct_hexdump_method,
    to_async_stream,
    to_bytes,
    to_c_struct_method,
    to_cpp_struct_method,
    to_csharp_struct_method,
    to_dict_method,
    to_file,
    to_go_struct_method,
    to_hexpat_method,
    to_json_method,
    to_rust_struct_method,
    to_wireshark_method,
    view_from_file_method,
    view_method,
    write_hexpat_method,
    write_wireshark_method,
)
from binary_master.checksum import ChecksumBase
from binary_master.engine import (
    _write_array,
    _write_bitfield,
    _write_element,
    _write_fixed_array,
    read_struct,
    write_struct,
    write_variant,
)
from binary_master.enums import Endian, EndianType
from binary_master.metadata import (
    BinaryMetadata,
    _BinarySizeDescriptor,
    _BitOffsetofDescriptor,
    _calculate_field_size,
    _get_field_alignment,
    _OffsetofDescriptor,
    _safe_issubclass,
    bit_offsetof,
    extract_field_descriptions,
    offsetof,
    sizeof,
)
from binary_master.plan import (
    FieldKind,
    FieldPlan,
    StructPlan,
    compile_struct_plan,
    get_struct_plan,
)

T = TypeVar("T")


@dataclass_transform()
def binary_struct(
    cls: Any = None,
    *,
    endian: str = "little",
    bits: Optional[int] = None,
    align: Optional[int] = None,
    auto_align: bool = False,
    total_size: Optional[int] = None,
    pad_byte: bytes = b"\x00",
) -> Any:
    """Decorator to define a binary struct with memory layout, endianness, and validation."""

    def wrapper(target_cls: type) -> type:
        if hasattr(target_cls, "__binary__"):
            if endian != "little" or bits is not None or align is not None or auto_align or total_size is not None:
                bm = target_cls.__binary__
                if isinstance(bm, dict):
                    bm["endian"] = endian
                    bm["bits"] = bits
                    bm["align"] = align
                    bm["auto_align"] = auto_align
                    bm["total_size"] = total_size
                    bm["pad_byte"] = pad_byte
            return target_cls

        # Scan annotations and attributes for default values
        magic_const_defaults: dict[str, Any] = {}
        user_defaults: dict[str, Any] = {}
        user_default_factories: dict[str, Any] = {}

        if hasattr(target_cls, "__annotations__"):
            # Strip explicit field defaults before dataclass() so order doesn't cause TypeError
            for fname in list(target_cls.__annotations__.keys()):
                if hasattr(target_cls, fname):
                    val = getattr(target_cls, fname)
                    if not inspect.isroutine(val) and not isinstance(val, property):
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

        # Collect implicit zero defaults for fields not explicitly defaulted
        implicit_defaults: dict[str, Any] = {}
        implicit_factories: dict[str, Any] = {}
        if hasattr(target_cls, "__annotations__"):
            for fname, ftype in target_cls.__annotations__.items():
                if fname not in user_defaults and fname not in user_default_factories and fname not in magic_const_defaults:
                    def_val, is_fac = _get_field_default_zero(ftype)
                    if is_fac:
                        implicit_factories[fname] = def_val
                    else:
                        implicit_defaults[fname] = def_val

        target_cls = dataclass(slots=True)(target_cls)
        doc = inspect.cleandoc(target_cls.__doc__) if target_cls.__doc__ else ""
        cur_frame = inspect.currentframe()
        caller_locals: dict[str, Any] = {}
        f = cur_frame.f_back if cur_frame else None
        while f is not None:
            if f.f_code.co_filename != __file__:
                caller_locals = dict(f.f_locals)
                break
            f = f.f_back

        target_cls.__binary__ = BinaryMetadata(
            target_cls,
            endian=endian,
            bits=bits,
            align=align,
            auto_align=auto_align,
            total_size=total_size,
            pad_byte=pad_byte,
            doc=doc,
            localns=caller_locals,
        )

        explicit_defaults = {**magic_const_defaults, **user_defaults}
        orig_init = target_cls.__init__
        from dataclasses import fields as dc_fields

        def wrapped_init(self: Any, *args: Any, **kwargs: Any) -> None:
            all_fnames = [fld.name for fld in dc_fields(self.__class__)]
            if args:
                non_default_names = [fn for fn in all_fnames if fn not in explicit_defaults and fn not in user_default_factories]
                if len(args) == len(non_default_names) and len(non_default_names) > 0 and (explicit_defaults or user_default_factories):
                    for fn, arg_val in zip(non_default_names, args):
                        kwargs[fn] = arg_val
                    args = ()
                elif len(args) <= len(all_fnames):
                    for fn, arg_val in zip(all_fnames[:len(args)], args):
                        kwargs[fn] = arg_val
                    args = ()

            # 1. Explicit factories & defaults
            for k, factory in user_default_factories.items():
                if k not in kwargs:
                    kwargs[k] = factory()
            for k, v in explicit_defaults.items():
                if k not in kwargs:
                    kwargs[k] = v

            # 2. Implicit zero factories & defaults
            for k, factory in implicit_factories.items():
                if k not in kwargs:
                    kwargs[k] = factory()
            for k, v in implicit_defaults.items():
                if k not in kwargs:
                    kwargs[k] = v

            # 3. Fallback for any remaining uninitialized field
            for fn in all_fnames:
                if fn not in kwargs:
                    kwargs[fn] = 0

            orig_init(self, *args, **kwargs)

        target_cls.__init__ = wrapped_init
        attach_struct_methods(target_cls)
        return target_cls

    if cls is not None:
        return wrapper(cls)
    return wrapper


class BinaryStruct:
    """Base class for binary structures supporting static type checking and IDE autocompletion.

    Inheriting from BinaryStruct allows static type checkers (such as ty, Pyright, mypy)
    to recognize methods like to_bytes(), from_bytes(), to_dict(), etc. statically,
    eliminating unresolved-attribute warnings.

    Usage:
        @binary_struct
        class Data(BinaryStruct):
            data: UInt16

        packet = Data(data=42)
        raw = packet.to_bytes()
    """

    __slots__ = ()

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        pass

    def to_bytes(self, endian: Optional[EndianType] = None) -> bytes:
        """Serialize struct to bytes."""
        return to_bytes(self, endian=endian)

    @classmethod
    def from_bytes(cls: type[T], data: Union[bytes, bytearray, memoryview], endian: Optional[EndianType] = None) -> T:
        """Deserialize struct from bytes."""
        return from_bytes(cls, data, endian=endian)

    def to_file(self, path_or_file: Union[str, Path, IO[bytes]], endian: Optional[EndianType] = None) -> int:
        """Serialize struct and write to a file or stream."""
        return to_file(self, path_or_file, endian=endian)

    @classmethod
    def from_file(cls: type[T], path_or_file: Union[str, Path, IO[bytes]], endian: Optional[EndianType] = None) -> T:
        """Deserialize struct from a file path or stream."""
        return from_file(cls, path_or_file, endian=endian)

    @classmethod
    def from_stream(cls: type[T], stream: IO[bytes], endian: Optional[EndianType] = None) -> T:
        """Deserialize struct from a readable binary stream."""
        return from_stream(cls, stream, endian=endian)

    async def to_async_stream(self, writer: Any, endian: Optional[EndianType] = None, drain: bool = True) -> None:
        """Serialize struct and write to an asyncio.StreamWriter."""
        await to_async_stream(self, writer, endian=endian, drain=drain)

    @classmethod
    async def from_async_stream(cls: type[T], reader: Any, endian: Optional[EndianType] = None) -> T:
        """Deserialize struct from an asyncio.StreamReader."""
        return await from_async_stream(cls, reader, endian=endian)

    def to_dict(self, bytes_format: str = "hex") -> dict[str, Any]:
        """Convert struct to a dictionary."""
        return to_dict_method(self, bytes_format=bytes_format)

    @classmethod
    def from_dict(cls: type[T], data: dict[str, Any]) -> T:
        """Reconstruct struct from a dictionary."""
        return from_dict_method(cls, data)

    def to_json(self, indent: Optional[int] = None, bytes_format: str = "hex") -> str:
        """Serialize struct to JSON string."""
        return to_json_method(self, indent=indent, bytes_format=bytes_format)

    @classmethod
    def from_json(cls: type[T], json_str: str) -> T:
        """Deserialize struct from JSON string."""
        return from_json_method(cls, json_str)

    @classmethod
    def to_c_struct(cls, name: Optional[str] = None, desc: str = "") -> str:
        """Generate C struct definition."""
        return to_c_struct_method(cls, name=name, desc=desc)

    @classmethod
    def to_rust_struct(cls, name: Optional[str] = None, desc: str = "") -> str:
        """Generate Rust struct definition."""
        return to_rust_struct_method(cls, name=name, desc=desc)

    @classmethod
    def to_cpp_struct(cls, name: Optional[str] = None, desc: str = "") -> str:
        """Generate C++ struct definition."""
        return to_cpp_struct_method(cls, name=name, desc=desc)

    @classmethod
    def to_csharp_struct(cls, name: Optional[str] = None, desc: str = "") -> str:
        """Generate C# struct definition."""
        return to_csharp_struct_method(cls, name=name, desc=desc)

    @classmethod
    def to_go_struct(cls, name: Optional[str] = None, desc: str = "") -> str:
        """Generate Go struct definition."""
        return to_go_struct_method(cls, name=name, desc=desc)

    @classmethod
    def to_wireshark(
        cls,
        protocol_name: Optional[str] = None,
        description: Optional[str] = None,
        port: Optional[int] = None,
    ) -> str:
        """Generate Wireshark Lua Dissector."""
        return to_wireshark_method(cls, protocol_name=protocol_name, description=description, port=port)

    @classmethod
    def write_wireshark(
        cls,
        path_or_file: Optional[Union[str, Path, IO[str]]] = None,
        protocol_name: Optional[str] = None,
        description: Optional[str] = None,
        port: Optional[int] = None,
    ) -> str:
        """Generate Wireshark Lua Dissector and optionally save to file or stream."""
        return write_wireshark_method(cls, path_or_file=path_or_file, protocol_name=protocol_name, description=description, port=port)

    @classmethod
    def to_hexpat(
        cls,
        root_name: Optional[str] = None,
        endian: Optional[EndianType] = None,
    ) -> str:
        """Generate ImHex Pattern Language (.hexpat) script."""
        return to_hexpat_method(cls, root_name=root_name, endian=endian)

    @classmethod
    def write_hexpat(
        cls,
        path_or_file: Union[str, Path, IO[str]],
        root_name: Optional[str] = None,
        endian: Optional[EndianType] = None,
    ) -> str:
        """Generate ImHex Pattern Language (.hexpat) file."""
        return write_hexpat_method(cls, path_or_file=path_or_file, root_name=root_name, endian=endian)

    @classmethod
    def view(
        cls: type[T],
        buffer: Union[bytes, bytearray, memoryview],
        offset: int = 0,
        endian: Optional[Union[str, Endian]] = None,
    ) -> Any:
        """Create a ZeroCopyView over the given buffer."""
        return view_method(cls, buffer=buffer, offset=offset, endian=endian)

    @classmethod
    def view_from_bytes(
        cls: type[T],
        buffer: Union[bytes, bytearray, memoryview],
        offset: int = 0,
        endian: Optional[Union[str, Endian]] = None,
    ) -> Any:
        """Create a ZeroCopyView over bytes."""
        return view_method(cls, buffer=buffer, offset=offset, endian=endian)

    @classmethod
    def view_from_file(
        cls: type[T],
        path: Union[str, Path],
        offset: int = 0,
        endian: Optional[Union[str, Endian]] = None,
        writable: bool = False,
    ) -> Any:
        """Create a ZeroCopyView backed by a memory-mapped file."""
        return view_from_file_method(cls, path=path, offset=offset, endian=endian, writable=writable)

    @classmethod
    def iter_packets(
        cls: type[T],
        source: Union[bytes, bytearray, memoryview, Any],
        max_count: Optional[int] = None,
        ignore_errors: bool = False,
        endian: Optional[str] = None,
    ) -> Any:
        """Continuously yield packets from a binary stream or buffer."""
        return iter_packets_method(cls, source, max_count=max_count, ignore_errors=ignore_errors, endian=endian)

    @classmethod
    def iter_views(
        cls: type[T],
        source: Union[bytes, bytearray, memoryview, str, Path],
        max_count: Optional[int] = None,
        endian: Optional[str] = None,
    ) -> Any:
        """Continuously yield zero-copy views from a buffer."""
        return iter_views_method(cls, source, max_count=max_count, endian=endian)

    @classmethod
    def async_iter_packets(
        cls: type[T],
        source: Any,
        max_count: Optional[int] = None,
        ignore_errors: bool = False,
        endian: Optional[str] = None,
    ) -> Any:
        """Asynchronously yield packets from an async reader."""
        return async_iter_packets_method(cls, source, max_count=max_count, ignore_errors=ignore_errors, endian=endian)

    @classmethod
    def dummy(
        cls: type[T],
        seed: Optional[int] = None,
        **overrides: Any,
    ) -> T:
        """Generate a dummy/mock instance populated with valid random data."""
        return dummy_method(cls, seed=seed, **overrides)

    def hexdump(
        self,
        width: int = 16,
        color: bool = False,
        annotate: bool = True,
        show_ascii: bool = True,
        show_header: bool = True,
        cursor: Optional[int] = None,
        max_bytes: Optional[int] = None,
    ) -> str:
        """Generate annotated hexdump of this struct's serialized binary bytes."""
        return struct_hexdump_method(
            self,
            width=width,
            color=color,
            annotate=annotate,
            show_ascii=show_ascii,
            show_header=show_header,
            cursor=cursor,
            max_bytes=max_bytes,
        )

    def __len__(self) -> int:
        return sizeof(self)


__all__ = [
    "binary_struct",
    "BinaryStruct",
    "BinaryType",
    "BinaryTypeMeta",
    "UInt8",
    "UInt16",
    "UInt32",
    "UInt64",
    "Int8",
    "Int16",
    "Int32",
    "Int64",
    "Float16",
    "Float32",
    "Float64",
    "u8",
    "u16",
    "u32",
    "u64",
    "i8",
    "i16",
    "i32",
    "i64",
    "s8",
    "s16",
    "s32",
    "s64",
    "f16",
    "f32",
    "f64",
    "Bool",
    "BoolMeta",
    "Bytes",
    "BytesMeta",
    "FixedString",
    "FixedStringMeta",
    "CString",
    "PrefixedString",
    "PrefixedStringMeta",
    "BinaryEnum",
    "BinaryEnumMeta",
    "BinaryFlag",
    "Magic",
    "MagicBase",
    "MagicMeta",
    "Constant",
    "ConstantBase",
    "ConstantMeta",
    "Range",
    "RangeBase",
    "RangeMeta",
    "LengthOf",
    "LengthOfBase",
    "LengthOfMeta",
    "CountOf",
    "CountOfBase",
    "CountOfMeta",
    "Offset",
    "OffsetTable",
    "Array",
    "FixedArray",
    "Bits",
    "Variant",
    "RelativeBase",
    "Base",
    "extract_field_descriptions",
    "BinaryMetadata",
    "sizeof",
    "offsetof",
    "bit_offsetof",
    "FieldKind",
    "FieldPlan",
    "StructPlan",
    "compile_struct_plan",
    "get_struct_plan",
    "write_struct",
    "read_struct",
    "write_variant",
    "to_bytes",
    "from_bytes",
    "to_file",
    "from_file",
    "from_stream",
    "to_async_stream",
    "from_async_stream",
    "_calculate_field_size",
    "_get_field_alignment",
    "_safe_issubclass",
    "_write_bitfield",
    "_write_fixed_array",
    "_write_array",
    "_write_element",
    "_unwrap_literal_int",
    "_normalize_offset_type",
    "_resolve_base_offset",
    "_is_base_offset_arg",
    "_is_offset_type_arg",
    "_parse_offset_spec_args",
    "_parse_named_offset_args",
    "_is_named_offset_spec",
    "_extract_named_offset_info",
    "_is_offset_table_spec",
    "_get_field_default_zero",
    "_BinarySizeDescriptor",
    "_BitOffsetofDescriptor",
    "_OffsetofDescriptor",
    "_ToCodeDescriptor",
    "_ToHtmlDescriptor",
    "_ToMarkdownDescriptor",
    "_WriteCodeDescriptor",
    "_WriteHtmlDescriptor",
    "_WriteMarkdownDescriptor",
    "_deserialize_dict_value",
    "_serialize_dict_value",
    "attach_struct_methods",
]
