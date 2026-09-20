from __future__ import annotations

import base64
import enum
import json
from pathlib import Path
from typing import (
    IO,
    Annotated,
    Any,
    Optional,
    TypeVar,
    Union,
    cast,
    get_args,
    get_origin,
)

from binary_master.binary_types import (
    Array,
    Bytes,
    ConstantBase,
    FixedArray,
    MagicBase,
    UInt8,
)
from binary_master.engine import read_struct, write_struct
from binary_master.enums import Endian, EndianType, normalize_endian
from binary_master.metadata import (
    _BinarySizeDescriptor,
    _BitOffsetofDescriptor,
    _OffsetofDescriptor,
    sizeof,
)
from binary_master.plan import get_struct_plan

T = TypeVar("T")


def to_bytes(self, endian: Optional[EndianType] = None) -> bytes:
    """Serialize this binary_struct instance to bytes."""
    cls = self.__class__
    if hasattr(cls, "__binary__"):
        plan = get_struct_plan(cls)
        active_endian = normalize_endian(endian or plan.endian)
        if plan.can_fast_pack and plan.fast_struct_little is not None and plan.fast_struct_big is not None:
            st = plan.fast_struct_little if active_endian == Endian.LITTLE else plan.fast_struct_big
            vals = tuple(getattr(self, fn) for fn in plan.fast_field_names)
            return st.pack(*vals)
    writer = write_struct(self, endian=endian, record_entries=False)
    return writer.to_bytes()


def from_bytes(cls, data: Union[bytes, bytearray, memoryview], endian: Optional[EndianType] = None) -> Any:
    """Deserialize a @binary_struct instance from bytes."""
    if hasattr(cls, "__binary__"):
        plan = get_struct_plan(cls)
        active_endian = normalize_endian(endian or plan.endian)
        if plan.can_fast_unpack and plan.fast_struct_little is not None and plan.fast_struct_big is not None:
            if len(data) >= plan.total_fixed_size:
                st = plan.fast_struct_little if active_endian == Endian.LITTLE else plan.fast_struct_big
                vals = st.unpack_from(data, 0)
                return cls(*vals)
    return read_struct(cls, reader=data, endian=endian)


def to_file(self, path_or_file: Union[str, Path, IO[bytes]], endian: Optional[EndianType] = None) -> int:
    """Serialize this binary_struct instance and write it to a file path or binary stream.

    Args:
        path_or_file: A filesystem path (str or Path) or a writable binary stream.
        endian: Optional endianness override.

    Returns:
        Number of bytes written.
    """
    data = self.to_bytes(endian=endian)
    if isinstance(path_or_file, (str, Path)):
        p = Path(path_or_file)
        if p.parent and not p.parent.exists():
            p.parent.mkdir(parents=True, exist_ok=True)
        return p.write_bytes(data)
    return path_or_file.write(data)


def from_file(cls, path_or_file: Union[str, Path, IO[bytes]], endian: Optional[EndianType] = None) -> Any:
    """Deserialize a @binary_struct instance from a file path or binary stream.

    Args:
        path_or_file: A filesystem path (str or Path) or a readable binary stream.
        endian: Optional endianness override.

    Returns:
        Deserialized instance of `cls`.
    """
    if isinstance(path_or_file, (str, Path)):
        data = Path(path_or_file).read_bytes()
        return cls.from_bytes(data, endian=endian)
    return read_struct(cls, reader=path_or_file, endian=endian)


def from_stream(cls, stream: IO[bytes], endian: Optional[EndianType] = None) -> Any:
    """Deserialize a @binary_struct instance from a readable binary stream.

    Args:
        stream: A readable binary stream (e.g. io.BytesIO or file).
        endian: Optional endianness override.

    Returns:
        Deserialized instance of `cls`.
    """
    return read_struct(cls, reader=stream, endian=endian)


async def to_async_stream(self, writer: Any, endian: Optional[EndianType] = None, drain: bool = True) -> None:
    """Serialize a @binary_struct instance and send asynchronously to an asyncio.StreamWriter."""
    from binary_master.async_stream import async_write_struct

    await async_write_struct(writer, self, endian=endian, drain=drain)


async def from_async_stream(cls, reader: Any, endian: Optional[EndianType] = None) -> Any:
    """Deserialize a @binary_struct instance asynchronously from an asyncio.StreamReader."""
    from binary_master.async_stream import async_read_struct

    return await async_read_struct(reader, cls, endian=endian)



def to_c_struct_method(cls, name: Optional[str] = None, desc: str = "") -> str:
    """Generate a C typedef struct definition for this @binary_struct class."""
    from binary_master.code_gen.c import to_c_struct

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


def to_wireshark_method(
    cls,
    protocol_name: Optional[str] = None,
    description: Optional[str] = None,
    port: Optional[int] = None,
) -> str:
    """Generate a Wireshark Lua Dissector for this @binary_struct class."""
    from binary_master.code_gen.wireshark import generate_wireshark_dissector

    return generate_wireshark_dissector(
        cls, protocol_name=protocol_name, description=description, port=port
    )


def write_wireshark_method(
    cls,
    path_or_file: Optional[Union[str, Path, IO[str]]] = None,
    protocol_name: Optional[str] = None,
    description: Optional[str] = None,
    port: Optional[int] = None,
) -> str:
    """Generate a Wireshark Lua Dissector and optionally save to file or stream."""
    from binary_master.code_gen.wireshark import write_wireshark

    return write_wireshark(
        cls,
        path_or_file=path_or_file,
        protocol_name=protocol_name,
        description=description,
        port=port,
    )


def to_hexpat_method(
    cls,
    root_name: Optional[str] = None,
    endian: Optional[EndianType] = None,
) -> str:
    """Generate an ImHex Pattern Language (.hexpat) script for this @binary_struct class."""
    from binary_master.code_gen.imhex import generate_imhex_pattern

    return generate_imhex_pattern(cls, root_name=root_name, endian=endian)


def write_hexpat_method(
    cls,
    path_or_file: Union[str, Path, IO[str]],
    root_name: Optional[str] = None,
    endian: Optional[EndianType] = None,
) -> str:
    """Generate and write an ImHex Pattern Language (.hexpat) file for this @binary_struct class."""
    from binary_master.code_gen.imhex import write_imhex_pattern

    return write_imhex_pattern(cls, path_or_file=path_or_file, root_name=root_name, endian=endian)


def view_method(
    cls: type[T],
    buffer: Union[bytes, bytearray, memoryview],
    offset: int = 0,
    endian: Optional[Union[str, Endian]] = None,
) -> Any:
    """Create a ZeroCopyView over the buffer without allocating full struct instances."""
    from binary_master.zero_copy import ZeroCopyView

    return ZeroCopyView(cls, buffer=buffer, offset=offset, endian=endian)


def view_from_file_method(
    cls: type[T],
    path: Union[str, Path],
    offset: int = 0,
    endian: Optional[Union[str, Endian]] = None,
    writable: bool = False,
) -> Any:
    """Create a ZeroCopyView backed by a memory-mapped file."""
    from binary_master.zero_copy import ZeroCopyView

    return ZeroCopyView.from_file(cls, path=path, offset=offset, endian=endian, writable=writable)


def iter_packets_method(
    cls: type[T],
    source: Union[bytes, bytearray, memoryview, Any],
    max_count: Optional[int] = None,
    ignore_errors: bool = False,
    endian: Optional[str] = None,
) -> Any:
    """Continuously yield packets from a binary stream or buffer."""
    from binary_master.streaming import iter_packets

    return iter_packets(source, cls, max_count=max_count, ignore_errors=ignore_errors, endian=endian)


def iter_views_method(
    cls: type[T],
    source: Union[bytes, bytearray, memoryview, str, Path],
    max_count: Optional[int] = None,
    endian: Optional[str] = None,
) -> Any:
    """Continuously yield zero-copy views of packets from a buffer."""
    from binary_master.streaming import iter_views

    return iter_views(source, cls, max_count=max_count, endian=endian)


def async_iter_packets_method(
    cls: type[T],
    source: Any,
    max_count: Optional[int] = None,
    ignore_errors: bool = False,
    endian: Optional[str] = None,
) -> Any:
    """Asynchronously yield packets from an async reader."""
    from binary_master.streaming import async_iter_packets

    return async_iter_packets(source, cls, max_count=max_count, ignore_errors=ignore_errors, endian=endian)


def dummy_method(
    cls: type[T],
    seed: Optional[int] = None,
    **overrides: Any,
) -> T:
    """Generate a dummy/mock instance populated with valid random data."""
    from binary_master.dummy import generate_dummy

    return generate_dummy(cls, seed=seed, **overrides)


def struct_hexdump_method(
    self: Any,
    width: int = 16,
    color: bool = False,
    annotate: bool = True,
    show_ascii: bool = True,
    show_header: bool = True,
    cursor: Optional[int] = None,
    max_bytes: Optional[int] = None,
) -> str:
    """Generate annotated hexdump of this struct's serialized binary bytes."""
    from binary_master.debug import hexdump as _hexdump

    return _hexdump(
        self.to_bytes(),
        width=width,
        color=color,
        annotate=annotate,
        show_ascii=show_ascii,
        show_header=show_header,
        cursor=cursor,
        max_bytes=max_bytes,
    )


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
    from dataclasses import fields as dc_fields
    from dataclasses import is_dataclass

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

    # Check Magic / Constant
    if isinstance(ftype, type):
        if issubclass(ftype, MagicBase):
            return getattr(ftype, "_value", val)
        if issubclass(ftype, ConstantBase):
            return getattr(ftype, "_value", val)

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
    data = json.loads(json_str)
    from_dict_fn = getattr(cls, "from_dict", None)
    if callable(from_dict_fn):
        return cast(T, from_dict_fn(data))
    return cls(**data)


def attach_struct_methods(target_cls: Any) -> None:
    """Attach all standard bridge methods and descriptors to a @binary_struct class."""
    target_cls.to_bytes = to_bytes
    target_cls.from_bytes = classmethod(from_bytes)
    target_cls.to_file = to_file
    target_cls.from_file = classmethod(from_file)
    target_cls.from_stream = classmethod(from_stream)
    target_cls.to_async_stream = to_async_stream
    target_cls.from_async_stream = classmethod(from_async_stream)
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
    target_cls.to_wireshark = classmethod(to_wireshark_method)
    target_cls.write_wireshark = classmethod(write_wireshark_method)
    target_cls.to_lua = classmethod(to_wireshark_method)
    target_cls.write_lua = classmethod(write_wireshark_method)
    target_cls.to_hexpat = classmethod(to_hexpat_method)
    target_cls.write_hexpat = classmethod(write_hexpat_method)
    target_cls.to_imhex = classmethod(to_hexpat_method)
    target_cls.write_imhex = classmethod(write_hexpat_method)
    target_cls.view = classmethod(view_method)
    target_cls.view_from_bytes = classmethod(view_method)
    target_cls.view_from_file = classmethod(view_from_file_method)
    target_cls.iter_packets = classmethod(iter_packets_method)
    target_cls.iter_views = classmethod(iter_views_method)
    target_cls.async_iter_packets = classmethod(async_iter_packets_method)
    target_cls.dummy = classmethod(dummy_method)
    target_cls.to_markdown = _ToMarkdownDescriptor()
    target_cls.write_markdown = _WriteMarkdownDescriptor()
    target_cls.to_html = _ToHtmlDescriptor()
    target_cls.write_html = _WriteHtmlDescriptor()
    target_cls.to_code = _ToCodeDescriptor()
    target_cls.write_code = _WriteCodeDescriptor()
    target_cls.binary_size = _BinarySizeDescriptor()
    target_cls.offsetof = _OffsetofDescriptor()
    target_cls.bit_offsetof = _BitOffsetofDescriptor()
    target_cls.hexdump = struct_hexdump_method
    target_cls.__len__ = lambda self: sizeof(self)

