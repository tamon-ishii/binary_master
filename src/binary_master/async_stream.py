"""Asynchronous binary stream I/O support for asyncio.StreamReader and asyncio.StreamWriter."""

from __future__ import annotations

import asyncio
import struct
from typing import Any, Callable, Optional, TypeVar, Union, cast

from binary_master.checksum import compute_checksum
from binary_master.compressed import decompress_data
from binary_master.enums import Endian, EndianType, normalize_endian
from binary_master.exceptions import (
    ChecksumMismatchError,
    InvalidConstantError,
    InvalidEnumError,
    InvalidMagicError,
    RangeValidationError,
)

T = TypeVar("T")


class AsyncBinaryReader:
    """Asynchronous binary reader wrapping an asyncio.StreamReader."""

    def __init__(
        self,
        reader: Union[asyncio.StreamReader, bytes, bytearray, memoryview],
        default_endian: EndianType = Endian.BIG,
    ) -> None:
        """Initialize an AsyncBinaryReader.

        Args:
            reader: The underlying asyncio.StreamReader or raw bytes/buffer.
            default_endian: Default byte order (Endian.BIG or Endian.LITTLE).
        """
        if isinstance(reader, (bytes, bytearray, memoryview)):
            stream_reader = asyncio.StreamReader()
            stream_reader.feed_data(bytes(reader))
            stream_reader.feed_eof()
            reader = stream_reader

        self._reader = reader
        self._default_endian = normalize_endian(default_endian)
        self._pos = 0
        self._read_hooks: list[Callable[[bytes], None]] = []

    @property
    def reader(self) -> asyncio.StreamReader:
        """The underlying asyncio.StreamReader."""
        return self._reader

    @property
    def endian(self) -> Endian:
        """Default endianness."""
        return self._default_endian

    def tell(self) -> int:
        """Return the current byte offset read through this reader."""
        return self._pos

    async def read_bytes(self, size: int) -> bytes:
        """Read exactly `size` bytes from the stream."""
        if size == 0:
            return b""
        data = await self._reader.readexactly(size)
        self._pos += len(data)
        for hook in self._read_hooks:
            hook(data)
        return data

    async def read(self, n: int = -1) -> bytes:
        """Read up to `n` bytes from the stream."""
        data = await self._reader.read(n)
        self._pos += len(data)
        for hook in self._read_hooks:
            hook(data)
        return data

    async def align(self, n: int) -> int:
        """Consume padding bytes up to the next n-byte alignment boundary."""
        pad = (n - (self._pos % n)) % n
        if pad > 0:
            await self.read_bytes(pad)
        return pad

    async def _unpack_read(self, fmt: str, size: int, endian: Optional[EndianType] = None) -> Any:
        active_endian = normalize_endian(endian or self._default_endian)
        prefix = "<" if active_endian == Endian.LITTLE else ">"
        data = await self.read_bytes(size)
        return struct.unpack(f"{prefix}{fmt}", data)[0]

    async def read_uint8(self) -> int:
        """Read an unsigned 8-bit integer."""
        b = await self.read_bytes(1)
        return b[0]

    async def read_int8(self) -> int:
        """Read a signed 8-bit integer."""
        b = await self.read_bytes(1)
        return struct.unpack("b", b)[0]

    async def read_uint16(self, endian: Optional[EndianType] = None) -> int:
        """Read an unsigned 16-bit integer."""
        return await self._unpack_read("H", 2, endian)

    async def read_int16(self, endian: Optional[EndianType] = None) -> int:
        """Read a signed 16-bit integer."""
        return await self._unpack_read("h", 2, endian)

    async def read_uint32(self, endian: Optional[EndianType] = None) -> int:
        """Read an unsigned 32-bit integer."""
        return await self._unpack_read("I", 4, endian)

    async def read_int32(self, endian: Optional[EndianType] = None) -> int:
        """Read a signed 32-bit integer."""
        return await self._unpack_read("i", 4, endian)

    async def read_uint64(self, endian: Optional[EndianType] = None) -> int:
        """Read an unsigned 64-bit integer."""
        return await self._unpack_read("Q", 8, endian)

    async def read_int64(self, endian: Optional[EndianType] = None) -> int:
        """Read a signed 64-bit integer."""
        return await self._unpack_read("q", 8, endian)

    async def read_float(self, endian: Optional[EndianType] = None) -> float:
        """Read a 32-bit IEEE-754 float."""
        return await self._unpack_read("f", 4, endian)

    async def read_double(self, endian: Optional[EndianType] = None) -> float:
        """Read a 64-bit IEEE-754 double."""
        return await self._unpack_read("d", 8, endian)

    async def read_float16(self, endian: Optional[EndianType] = None) -> float:
        """Read a 16-bit IEEE-754 half-precision float."""
        return await self._unpack_read("e", 2, endian)

    read_u8 = read_uint8
    read_i8 = read_int8
    read_s8 = read_int8
    read_u16 = read_uint16
    read_i16 = read_int16
    read_s16 = read_int16
    read_u32 = read_uint32
    read_i32 = read_int32
    read_s32 = read_int32
    read_u64 = read_uint64
    read_i64 = read_int64
    read_s64 = read_int64
    read_f16 = read_float16
    read_f32 = read_float
    read_f64 = read_double

    async def read_bool(self, size: int = 1, endian: Optional[EndianType] = None) -> bool:
        """Read a boolean value with the given byte size."""
        if size == 1:
            return (await self.read_uint8()) != 0
        elif size == 2:
            return (await self.read_uint16(endian)) != 0
        elif size == 4:
            return (await self.read_uint32(endian)) != 0
        elif size == 8:
            return (await self.read_uint64(endian)) != 0
        raw = await self.read_bytes(size)
        return any(b != 0 for b in raw)

    async def read_cstring(self, encoding: str = "utf-8") -> str:
        """Read a null-terminated C-string."""
        raw = await self._reader.readuntil(b"\x00")
        self._pos += len(raw)
        for hook in self._read_hooks:
            hook(raw)
        return raw[:-1].decode(encoding)

    async def read_fixed_string(self, size: int, pad_byte: bytes = b"\x00", encoding: str = "utf-8") -> str:
        """Read a fixed-length string stripped of trailing pad_byte."""
        data = await self.read_bytes(size)
        return data.rstrip(pad_byte).decode(encoding)

    async def read_prefixed_string(
        self, prefix_bytes: int = 1, endian: Optional[EndianType] = None, encoding: str = "utf-8"
    ) -> str:
        """Read a length-prefixed string."""
        if prefix_bytes == 1:
            length = await self.read_uint8()
        elif prefix_bytes == 2:
            length = await self.read_uint16(endian)
        elif prefix_bytes == 4:
            length = await self.read_uint32(endian)
        else:
            raise ValueError(f"Unsupported prefix_bytes: {prefix_bytes}")
        data = await self.read_bytes(length)
        return data.decode(encoding)

    async def read_varuint(self) -> int:
        """Decode an unsigned integer using LEB128."""
        result = 0
        shift = 0
        count = 0
        while True:
            raw = await self.read_bytes(1)
            byte = raw[0]
            count += 1
            result |= (byte & 0x7F) << shift
            shift += 7
            if not (byte & 0x80):
                break
            if count > 10:
                raise ValueError("VarUInt exceeds maximum 64-bit representation (10 bytes)")
        return result

    async def read_varint(self) -> int:
        """Decode a signed integer using signed LEB128."""
        result = 0
        shift = 0
        count = 0
        while True:
            raw = await self.read_bytes(1)
            byte = raw[0]
            count += 1
            result |= (byte & 0x7F) << shift
            shift += 7
            if not (byte & 0x80):
                if (byte & 0x40) and shift < 64:
                    result |= -(1 << shift)
                break
            if count > 10:
                raise ValueError("VarInt exceeds maximum 64-bit representation (10 bytes)")
        return result

    async def read_struct(self, struct_cls: type[T], endian: Optional[EndianType] = None) -> T:
        """Read a @binary_struct instance asynchronously from the stream.

        Args:
            struct_cls: The @binary_struct class to instantiate.
            endian: Optional endianness override.

        Returns:
            Deserialized instance of `struct_cls`.
        """
        from binary_master.binary_struct import FieldKind, get_struct_plan, read_struct, sizeof

        meta = getattr(struct_cls, "__binary__", None)
        if meta is None:
            raise TypeError(f"Class {getattr(struct_cls, '__name__', str(struct_cls))} is not a binary_struct")

        plan = get_struct_plan(struct_cls)
        active_endian = normalize_endian(endian or plan.endian)

        # 1. Fast path for statically-sized structs
        try:
            static_sz = sizeof(struct_cls)
            data = await self.read_bytes(static_sz)
            return read_struct(struct_cls, reader=data, endian=active_endian)
        except (ValueError, TypeError):
            pass

        # 2. Variable-length structs: read field by field
        if plan.is_bitfield:
            total_bits = plan.total_bits or 8
            byte_count = (total_bits + 7) // 8
            raw_data = await self.read_bytes(byte_count)
            return read_struct(struct_cls, reader=raw_data, endian=active_endian)

        kwargs: dict[str, Any] = {}
        known_counts: dict[str, int] = {}
        known_lengths: dict[str, int] = {}
        align_setting = plan.align_setting
        auto_align = plan.auto_align

        struct_history = bytearray()
        self._read_hooks.append(struct_history.extend)

        try:
            for fp in plan.field_plans:
                name = fp.name

                if (align_setting is not None or auto_align) and fp.align > 1:
                    req_align = min(fp.align, align_setting) if align_setting else fp.align
                    if req_align > 1:
                        await self.align(req_align)

                kind = fp.kind
                if kind == FieldKind.PRIMITIVE:
                    kwargs[name] = await self._unpack_read(fp.fmt, fp.size, endian=active_endian)
                elif kind == FieldKind.BOOL:
                    kwargs[name] = await self.read_bool(size=fp.size, endian=active_endian)
                elif kind == FieldKind.MAGIC:
                    if fp.is_bytes_magic:
                        read_b = await self.read_bytes(fp.size)
                        if read_b != fp.expected:
                            raise InvalidMagicError(
                                f"Magic mismatch for field '{name}': expected {fp.expected!r}, got {read_b!r}"
                            )
                        kwargs[name] = read_b
                    else:
                        val = await self._unpack_read(fp.fmt, fp.size, endian=active_endian)
                        if val != fp.raw_val:
                            raise InvalidMagicError(
                                f"Magic mismatch for field '{name}': expected {fp.raw_val!r}, got {val!r}"
                            )
                        kwargs[name] = val
                elif kind == FieldKind.CONSTANT:
                    val = await self._unpack_read(fp.fmt, fp.size, endian=active_endian)
                    if val != fp.expected:
                        raise InvalidConstantError(
                            f"Constant mismatch for field '{name}': expected {fp.expected!r}, got {val!r}"
                        )
                    kwargs[name] = val
                elif kind == FieldKind.RANGE:
                    val = await self._unpack_read(fp.fmt, fp.size, endian=active_endian)
                    if not (fp.min_val <= val <= fp.max_val):
                        raise RangeValidationError(name, val, fp.min_val, fp.max_val)
                    kwargs[name] = val
                elif kind == FieldKind.LENGTH_OF or kind == FieldKind.COUNT_OF:
                    val = await self._unpack_read(fp.fmt, fp.size, endian=active_endian)
                    kwargs[name] = val
                    if fp.target_name:
                        if kind == FieldKind.COUNT_OF:
                            known_counts[fp.target_name] = val - fp.delta
                        else:
                            known_lengths[fp.target_name] = val - fp.delta
                elif kind == FieldKind.CHECKSUM:
                    start_idx = 0 if (fp.checksum_range is None or fp.checksum_range.start is None) else fp.checksum_range.start
                    end_idx = (
                        len(struct_history)
                        if (fp.checksum_range is None or fp.checksum_range.stop is None)
                        else fp.checksum_range.stop
                    )
                    covered_bytes = bytes(struct_history[start_idx:end_idx])
                    calculated = compute_checksum(fp.checksum_algo, covered_bytes)
                    val = await self._unpack_read(fp.fmt, fp.size, endian=active_endian)
                    if val != calculated:
                        raise ChecksumMismatchError(
                            f"Checksum mismatch for field '{name}': computed {hex(calculated)}, got {hex(val)} in stream"
                        )
                    kwargs[name] = val
                elif kind == FieldKind.COMPRESSED:
                    comp_len = await self.read_uint32(endian=active_endian)
                    comp_bytes = await self.read_bytes(comp_len)
                    algo = fp.checksum_algo or "zlib"
                    decomp_bytes = decompress_data(comp_bytes, algo=algo)
                    target_t = fp.target_type
                    if hasattr(target_t, "__binary__"):
                        kwargs[name] = read_struct(target_t, reader=decomp_bytes, endian=active_endian)
                    else:
                        kwargs[name] = decomp_bytes
                elif kind == FieldKind.VARINT:
                    if fp.varint_signed:
                        kwargs[name] = await self.read_varint()
                    else:
                        kwargs[name] = await self.read_varuint()
                elif kind == FieldKind.ENUM:
                    raw_val = await self._unpack_read(fp.fmt, fp.size, endian=active_endian)
                    enum_type = fp.enum_cls
                    try:
                        kwargs[name] = enum_type(raw_val)
                    except ValueError as exc:
                        cls_n = getattr(enum_type, "__name__", str(enum_type))
                        raise InvalidEnumError(f"Invalid enum value {raw_val} for {cls_n} in field '{name}'") from exc
                elif kind == FieldKind.NESTED_STRUCT:
                    nested_type = cast(type, fp.nested_cls)
                    kwargs[name] = await self.read_struct(nested_type, endian=active_endian)
                elif kind == FieldKind.FIXED_STRING:
                    kwargs[name] = await self.read_fixed_string(fp.size, pad_byte=fp.pad_byte, encoding=fp.encoding)
                elif kind == FieldKind.BYTES:
                    explicit_len = known_lengths.get(name, known_counts.get(name))
                    target_len = explicit_len if explicit_len is not None else (fp.size if fp.size > 0 else None)
                    if target_len is None:
                        kwargs[name] = await self._reader.read()
                    else:
                        kwargs[name] = await self.read_bytes(target_len)
                elif kind == FieldKind.C_STRING:
                    kwargs[name] = await self.read_cstring(encoding=fp.encoding)
                elif kind == FieldKind.PREFIXED_STRING:
                    kwargs[name] = await self.read_prefixed_string(
                        prefix_bytes=fp.prefix_bytes, endian=active_endian, encoding=fp.encoding
                    )
                elif kind == FieldKind.FIXED_ARRAY:
                    count = fp.count
                    elem_t = cast(type, fp.elem_type)
                    if fp.elem_is_bool:
                        kwargs[name] = [await self.read_bool(size=fp.elem_bool_size, endian=active_endian) for _ in range(count)]
                    elif fp.elem_is_uint8:
                        kwargs[name] = await self.read_bytes(count)
                    elif fp.elem_is_int8:
                        kwargs[name] = [await self.read_int8() for _ in range(count)]
                    elif fp.elem_is_primitive:
                        kwargs[name] = [
                            await self._unpack_read(fp.elem_fmt, fp.elem_size, endian=active_endian) for _ in range(count)
                        ]
                    elif fp.elem_is_struct:
                        kwargs[name] = [await self.read_struct(elem_t, endian=active_endian) for _ in range(count)]
                    else:
                        kwargs[name] = await self.read_bytes(count)
                elif kind == FieldKind.ARRAY:
                    elem_t = cast(type, fp.elem_type)
                    explicit_count = known_counts.get(name)
                    explicit_length = known_lengths.get(name)
                    if explicit_count is not None:
                        items: list[Any] = []
                        for _ in range(explicit_count):
                            if fp.elem_is_bool:
                                items.append(await self.read_bool(size=fp.elem_bool_size, endian=active_endian))
                            elif fp.elem_is_uint8:
                                items.append(await self.read_uint8())
                            elif fp.elem_is_primitive:
                                items.append(await self._unpack_read(fp.elem_fmt, fp.elem_size, endian=active_endian))
                            elif fp.elem_is_struct:
                                items.append(await self.read_struct(elem_t, endian=active_endian))
                            else:
                                items.append(await self.read_uint8())
                        kwargs[name] = bytes(items) if fp.elem_is_uint8 else items
                    elif explicit_length is not None:
                        raw = await self.read_bytes(explicit_length)
                        from binary_master.reader import BinaryReader

                        sub_r = BinaryReader(raw, default_endian=active_endian)
                        items_len: list[Any] = []
                        while sub_r.remaining() > 0:
                            if fp.elem_is_primitive:
                                items_len.append(sub_r._unpack_read(fp.elem_fmt, fp.elem_size, endian=active_endian))
                            elif fp.elem_is_struct:
                                items_len.append(read_struct(elem_t, reader=sub_r, endian=active_endian))
                            else:
                                items_len.append(sub_r.read_uint8())
                        kwargs[name] = bytes(items_len) if fp.elem_is_uint8 else items_len
                    else:
                        raise ValueError(f"Array field '{name}' requires known length or count prefix")
                else:
                    raise NotImplementedError(f"Unsupported FieldKind {kind} in AsyncBinaryReader")

            return struct_cls(**kwargs)
        finally:
            self._read_hooks.pop()


class _AsyncBufferWriter:
    def __init__(self) -> None:
        self._buf = bytearray()

    def write(self, data: Union[bytes, bytearray, memoryview]) -> None:
        self._buf.extend(data)

    async def drain(self) -> None:
        pass

    def close(self) -> None:
        pass

    async def wait_closed(self) -> None:
        pass

    def to_bytes(self) -> bytes:
        return bytes(self._buf)


class AsyncBinaryWriter:
    """Asynchronous binary writer wrapping an asyncio.StreamWriter or in-memory buffer."""

    def __init__(
        self,
        writer: Optional[Any] = None,
        default_endian: EndianType = Endian.BIG,
    ) -> None:
        """Initialize an AsyncBinaryWriter.

        Args:
            writer: The underlying asyncio.StreamWriter or None for in-memory buffer.
            default_endian: Default byte order (Endian.BIG or Endian.LITTLE).
        """
        self._writer = writer if writer is not None else _AsyncBufferWriter()
        self._default_endian = normalize_endian(default_endian)

    def to_bytes(self) -> bytes:
        """Return buffered bytes if writing to an in-memory buffer."""
        if hasattr(self._writer, "to_bytes"):
            return self._writer.to_bytes()
        raise TypeError("to_bytes() is only available when writing to an in-memory AsyncBinaryWriter")

    @property
    def writer(self) -> Any:
        """The underlying asyncio.StreamWriter or in-memory buffer."""
        return self._writer

    @property
    def endian(self) -> Endian:
        """Default endianness."""
        return self._default_endian

    def write_bytes(self, data: Union[bytes, bytearray, memoryview]) -> None:
        """Write raw bytes to the stream buffer."""
        self._writer.write(data)

    def write_uint8(self, val: int) -> None:
        """Write an unsigned 8-bit integer."""
        self._writer.write(bytes([val & 0xFF]))

    def write_int8(self, val: int) -> None:
        """Write a signed 8-bit integer."""
        self._writer.write(struct.pack("b", val))

    def _pack_write(self, fmt: str, val: Any, endian: Optional[EndianType] = None) -> None:
        active_endian = normalize_endian(endian or self._default_endian)
        prefix = "<" if active_endian == Endian.LITTLE else ">"
        self._writer.write(struct.pack(f"{prefix}{fmt}", val))

    def write_uint16(self, val: int, endian: Optional[EndianType] = None) -> None:
        """Write an unsigned 16-bit integer."""
        self._pack_write("H", val, endian)

    def write_int16(self, val: int, endian: Optional[EndianType] = None) -> None:
        """Write a signed 16-bit integer."""
        self._pack_write("h", val, endian)

    def write_uint32(self, val: int, endian: Optional[EndianType] = None) -> None:
        """Write an unsigned 32-bit integer."""
        self._pack_write("I", val, endian)

    def write_int32(self, val: int, endian: Optional[EndianType] = None) -> None:
        """Write a signed 32-bit integer."""
        self._pack_write("i", val, endian)

    def write_uint64(self, val: int, endian: Optional[EndianType] = None) -> None:
        """Write an unsigned 64-bit integer."""
        self._pack_write("Q", val, endian)

    def write_int64(self, val: int, endian: Optional[EndianType] = None) -> None:
        """Write a signed 64-bit integer."""
        self._pack_write("q", val, endian)

    def write_float(self, val: float, endian: Optional[EndianType] = None) -> None:
        """Write a 32-bit IEEE-754 float."""
        self._pack_write("f", val, endian)

    def write_double(self, val: float, endian: Optional[EndianType] = None) -> None:
        """Write a 64-bit IEEE-754 double."""
        self._pack_write("d", val, endian)

    def write_float16(self, val: float, endian: Optional[EndianType] = None) -> None:
        """Write a 16-bit IEEE-754 half-precision float."""
        self._pack_write("e", val, endian)

    write_u8 = write_uint8
    write_i8 = write_int8
    write_s8 = write_int8
    write_u16 = write_uint16
    write_i16 = write_int16
    write_s16 = write_int16
    write_u32 = write_uint32
    write_i32 = write_int32
    write_s32 = write_int32
    write_u64 = write_uint64
    write_i64 = write_int64
    write_s64 = write_int64
    write_f16 = write_float16
    write_f32 = write_float
    write_f64 = write_double

    def write_cstring(self, s: str, encoding: str = "utf-8") -> None:
        """Write a null-terminated C-string."""
        self._writer.write(s.encode(encoding) + b"\x00")

    def write_struct(self, instance: Any, endian: Optional[EndianType] = None) -> None:
        """Serialize a @binary_struct instance and write it to the stream buffer."""
        from binary_master.binary_struct import write_struct

        active_endian = normalize_endian(endian or self._default_endian)
        writer = write_struct(instance, endian=active_endian)
        self._writer.write(writer.to_bytes())

    async def send_struct(self, instance: Any, endian: Optional[EndianType] = None) -> None:
        """Serialize a @binary_struct instance, write it, and drain immediately."""
        self.write_struct(instance, endian=endian)
        await self.drain()

    async def drain(self) -> None:
        """Flush stream writer buffer to the underlying transport."""
        await self._writer.drain()

    async def close(self) -> None:
        """Close the underlying stream writer."""
        self._writer.close()
        if hasattr(self._writer, "wait_closed"):
            await self._writer.wait_closed()

    async def __aenter__(self) -> AsyncBinaryWriter:
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        await self.drain()


async def async_read_struct(
    reader: asyncio.StreamReader,
    cls: type[T],
    endian: Optional[EndianType] = None,
) -> T:
    """Read a @binary_struct instance asynchronously from an asyncio.StreamReader.

    Args:
        reader: The asyncio.StreamReader to read from.
        cls: The @binary_struct class.
        endian: Optional endianness override.

    Returns:
        Deserialized instance.
    """
    async_reader = AsyncBinaryReader(reader, default_endian=endian or Endian.BIG)
    return await async_reader.read_struct(cls, endian=endian)


async def async_write_struct(
    writer: asyncio.StreamWriter,
    instance: Any,
    endian: Optional[EndianType] = None,
    drain: bool = True,
) -> None:
    """Write a @binary_struct instance asynchronously to an asyncio.StreamWriter.

    Args:
        writer: The asyncio.StreamWriter to write to.
        instance: The @binary_struct instance to serialize.
        endian: Optional endianness override.
        drain: Whether to await writer.drain() after writing.
    """
    async_writer = AsyncBinaryWriter(writer, default_endian=endian or Endian.BIG)
    async_writer.write_struct(instance, endian=endian)
    if drain:
        await async_writer.drain()
