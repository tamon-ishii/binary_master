"""BinaryWriter: Core sequential binary writer implementation."""

from __future__ import annotations

import io
from pathlib import Path
import struct
from typing import IO, Optional, Union

from binary_master.enums import Endian, EndianType, normalize_endian

# Integer boundary constants
INT8_MIN, INT8_MAX = -128, 127
UINT8_MIN, UINT8_MAX = 0, 255
INT16_MIN, INT16_MAX = -32768, 32767
UINT16_MIN, UINT16_MAX = 0, 65535
INT32_MIN, INT32_MAX = -2147483648, 2147483647
UINT32_MIN, UINT32_MAX = 0, 4294967295
INT64_MIN, INT64_MAX = -9223372036854775808, 9223372036854775807
UINT64_MIN, UINT64_MAX = 0, 18446744073709551615

_FMT_TO_TYPE_NAME = {
    "B": "UInt8",
    "b": "Int8",
    "H": "UInt16",
    "h": "Int16",
    "I": "UInt32",
    "i": "Int32",
    "Q": "UInt64",
    "q": "Int64",
    "f": "Float32",
    "d": "Float64",
}


def _check_int_bounds(name: str, value: int, min_val: int, max_val: int) -> None:
    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError(f"{name} requires an integer, got {type(value).__name__}")
    if not (min_val <= value <= max_val):
        raise ValueError(
            f"Value {value} out of range for {name} (expected {min_val} to {max_val})"
        )


class BinaryWriter:
    """A sequential binary writer supporting in-memory buffers and stream/file targets."""

    def __init__(
        self,
        stream: Optional[IO[bytes]] = None,
        default_endian: EndianType = Endian.LITTLE,
        auto_close: Optional[bool] = None,
    ) -> None:
        """Initialize a BinaryWriter.

        Args:
            stream: A writable binary stream (e.g. io.BytesIO or open binary file).
                    If None, an in-memory io.BytesIO is created.
            default_endian: The default byte order (Endian.LITTLE, Endian.BIG, or string alias).
            auto_close: Whether closing this writer should close the underlying stream.
                        Defaults to True if a file path was opened, False if stream was provided.
        """
        self._default_endian = normalize_endian(default_endian)
        self._entries: list[Any] = []
        self._current_caption: Optional[str] = None
        self._current_caption_desc: str = ""
        self._current_caption_variants: Optional[list] = None
        self._current_subcaption: Optional[str] = None
        self._current_subcaption_desc: str = ""
        if stream is None:
            self._stream = io.BytesIO()
            self._close_stream = auto_close if auto_close is not None else False
            self._is_memory = True
        else:
            self._stream = stream
            self._close_stream = auto_close if auto_close is not None else False
            self._is_memory = isinstance(stream, io.BytesIO)

    def caption(
        self,
        title: Optional[str] = None,
        desc: str = "",
        variants: Optional[list] = None,
    ) -> BinaryWriter:
        """Set the active section caption/title for subsequent binary writes.

        Fields and structures written after this call will be grouped under
        this caption in generated manuals and diagrams until a new caption is set.

        Args:
            title: The caption or title string. Pass None or an empty string to clear.
            desc: Optional description for this section/caption.
            variants: Optional list of candidate variant structures for this section,
                      e.g. [(tag, StructCls, desc), ...] or [StructCls, ...].

        Returns:
            self for method chaining.
        """
        self._current_caption = title if title else None
        self._current_caption_desc = desc
        self._current_caption_variants = variants
        self._current_subcaption = None
        self._current_subcaption_desc = ""
        return self

    def subcaption(self, title: Optional[str] = None, desc: str = "") -> BinaryWriter:
        """Set an active subcaption under the current section caption.

        Args:
            title: The subcaption title string.
            desc: Optional description for this subcaption.

        Returns:
            self for method chaining.
        """
        self._current_subcaption = title if title else None
        self._current_subcaption_desc = desc
        return self

    @property
    def current_caption(self) -> Optional[str]:
        """Get the currently active section caption."""
        return self._current_caption

    @property
    def current_caption_desc(self) -> str:
        """Get the description of the currently active section caption."""
        return self._current_caption_desc

    @property
    def current_caption_variants(self) -> Optional[list]:
        """Get the candidate variants of the currently active section caption."""
        return self._current_caption_variants

    @property
    def current_subcaption(self) -> Optional[str]:
        """Get the currently active subcaption."""
        return self._current_subcaption

    @property
    def current_subcaption_desc(self) -> str:
        """Get the description of the currently active subcaption."""
        return self._current_subcaption_desc

    @classmethod
    def to_memory(cls, default_endian: EndianType = Endian.LITTLE) -> BinaryWriter:
        """Create a BinaryWriter writing to an in-memory buffer."""
        return cls(stream=None, default_endian=default_endian, auto_close=False)

    @classmethod
    def to_file(
        cls,
        path_or_file: Union[str, Path, IO[bytes]],
        default_endian: EndianType = Endian.LITTLE,
        mode: str = "wb",
    ) -> BinaryWriter:
        """Create a BinaryWriter targeting a file path or file stream.

        Args:
            path_or_file: A file path string, pathlib.Path, or open binary file-like object.
            default_endian: Default byte order.
            mode: File open mode when a path is supplied (default 'wb').
        """
        if isinstance(path_or_file, (str, Path)):
            file_stream = open(path_or_file, mode)
            return cls(stream=file_stream, default_endian=default_endian, auto_close=True)
        return cls(stream=path_or_file, default_endian=default_endian, auto_close=False)

    @property
    def default_endian(self) -> Endian:
        """Get the default endianness."""
        return self._default_endian

    @default_endian.setter
    def default_endian(self, endian: EndianType) -> None:
        """Set the default endianness."""
        self._default_endian = normalize_endian(endian)

    @property
    def stream(self) -> IO[bytes]:
        """Get the underlying binary stream."""
        return self._stream

    @property
    def closed(self) -> bool:
        """Check if the underlying stream is closed."""
        return self._stream.closed

    def flush(self) -> None:
        """Flush the underlying stream."""
        self._stream.flush()

    def close(self) -> None:
        """Close the writer and the underlying stream if auto_close is enabled."""
        self.flush()
        if self._close_stream and not self._stream.closed:
            self._stream.close()

    def to_bytes(self) -> bytes:
        """Return the accumulated binary data as immutable bytes (in-memory writers only).

        Raises:
            TypeError: If the writer is not writing to an in-memory BytesIO buffer.
        """
        if isinstance(self._stream, io.BytesIO):
            return self._stream.getvalue()
        raise TypeError("to_bytes() is only available for in-memory buffer writers")

    def to_bytearray(self) -> bytearray:
        """Return the accumulated binary data as a mutable bytearray (in-memory writers only)."""
        return bytearray(self.to_bytes())

    def __enter__(self) -> BinaryWriter:
        return self

    def __exit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        self.close()

    @property
    def entries(self) -> list[Any]:
        """Get the recorded layout entries."""
        return self._entries

    def _record_entry(
        self,
        offset: int,
        size: int,
        type_name: str,
        value: Any = None,
        name: str = "",
        endian: Optional[str] = None,
        description: str = "",
        struct_name: Optional[str] = None,
        target_offset: Optional[int] = None,
        subfields: Optional[list] = None,
        caption: Optional[str] = None,
        struct_doc: Optional[str] = None,
        caption_desc: Optional[str] = None,
        subcaption: Optional[str] = None,
        subcaption_desc: Optional[str] = None,
        caption_variants: Optional[list] = None,
    ) -> None:
        from binary_master.manual import LayoutEntry

        active_caption = caption if caption is not None else self._current_caption
        active_caption_desc = caption_desc if caption_desc is not None else self._current_caption_desc
        active_subcaption = subcaption if subcaption is not None else self._current_subcaption
        active_subcaption_desc = subcaption_desc if subcaption_desc is not None else self._current_subcaption_desc
        active_variants = caption_variants if caption_variants is not None else self._current_caption_variants
        self._entries.append(
            LayoutEntry(
                offset=offset,
                size=size,
                type_name=type_name,
                value=value,
                name=name,
                endian=endian,
                description=description,
                struct_name=struct_name,
                target_offset=target_offset,
                subfields=subfields,
                caption=active_caption,
                struct_doc=struct_doc,
                caption_desc=active_caption_desc,
                subcaption=active_subcaption,
                subcaption_desc=active_subcaption_desc,
                caption_variants=active_variants,
            )
        )

    # --- Internal Packing Helper ---

    def _pack_write(
        self,
        fmt_char: str,
        value: object,
        endian: EndianType = None,
        name: str = "",
        desc: str = "",
        struct_name: Optional[str] = None,
        struct_doc: Optional[str] = None,
    ) -> BinaryWriter:
        order = normalize_endian(endian, self._default_endian)
        data = struct.pack(f"{order.value}{fmt_char}", value)
        offset = self.tell()
        self._stream.write(data)
        self._record_entry(
            offset=offset,
            size=len(data),
            type_name=_FMT_TO_TYPE_NAME.get(fmt_char, fmt_char),
            value=value,
            name=name,
            endian=order.name.capitalize(),
            description=desc,
            struct_name=struct_name,
            struct_doc=struct_doc,
        )
        return self

    # --- Integer Methods ---

    def write_uint8(self, value: int, name: str = "", desc: str = "") -> BinaryWriter:
        """Write an unsigned 8-bit integer (0 to 255)."""
        _check_int_bounds("uint8", value, UINT8_MIN, UINT8_MAX)
        return self._pack_write("B", value, Endian.NATIVE, name=name, desc=desc)

    def write_int8(self, value: int, name: str = "", desc: str = "") -> BinaryWriter:
        """Write a signed 8-bit integer (-128 to 127)."""
        _check_int_bounds("int8", value, INT8_MIN, INT8_MAX)
        return self._pack_write("b", value, Endian.NATIVE, name=name, desc=desc)

    def write_uint16(self, value: int, endian: EndianType = None, name: str = "", desc: str = "") -> BinaryWriter:
        """Write an unsigned 16-bit integer (0 to 65535)."""
        _check_int_bounds("uint16", value, UINT16_MIN, UINT16_MAX)
        return self._pack_write("H", value, endian, name=name, desc=desc)

    def write_int16(self, value: int, endian: EndianType = None, name: str = "", desc: str = "") -> BinaryWriter:
        """Write a signed 16-bit integer (-32768 to 32767)."""
        _check_int_bounds("int16", value, INT16_MIN, INT16_MAX)
        return self._pack_write("h", value, endian, name=name, desc=desc)

    def write_uint32(self, value: int, endian: EndianType = None, name: str = "", desc: str = "") -> BinaryWriter:
        """Write an unsigned 32-bit integer (0 to 4294967295)."""
        _check_int_bounds("uint32", value, UINT32_MIN, UINT32_MAX)
        return self._pack_write("I", value, endian, name=name, desc=desc)

    def write_int32(self, value: int, endian: EndianType = None, name: str = "", desc: str = "") -> BinaryWriter:
        """Write a signed 32-bit integer (-2147483648 to 2147483647)."""
        _check_int_bounds("int32", value, INT32_MIN, INT32_MAX)
        return self._pack_write("i", value, endian, name=name, desc=desc)

    def write_uint64(self, value: int, endian: EndianType = None, name: str = "", desc: str = "") -> BinaryWriter:
        """Write an unsigned 64-bit integer (0 to 18446744073709551615)."""
        _check_int_bounds("uint64", value, UINT64_MIN, UINT64_MAX)
        return self._pack_write("Q", value, endian, name=name, desc=desc)

    def write_int64(self, value: int, endian: EndianType = None, name: str = "", desc: str = "") -> BinaryWriter:
        """Write a signed 64-bit integer (-9223372036854775808 to 9223372036854775807)."""
        _check_int_bounds("int64", value, INT64_MIN, INT64_MAX)
        return self._pack_write("q", value, endian, name=name, desc=desc)

    # --- Floating Point, Boolean, and Raw Bytes Methods ---

    def write_float32(self, value: float, endian: EndianType = None, name: str = "", desc: str = "") -> BinaryWriter:
        """Write a 32-bit single-precision IEEE 754 floating point number."""
        if not isinstance(value, (float, int)):
            raise TypeError(f"write_float32 requires a float or int, got {type(value).__name__}")
        return self._pack_write("f", float(value), endian, name=name, desc=desc)

    def write_float64(self, value: float, endian: EndianType = None, name: str = "", desc: str = "") -> BinaryWriter:
        """Write a 64-bit double-precision IEEE 754 floating point number."""
        if not isinstance(value, (float, int)):
            raise TypeError(f"write_float64 requires a float or int, got {type(value).__name__}")
        return self._pack_write("d", float(value), endian, name=name, desc=desc)

    def write_bool(self, value: bool, name: str = "", desc: str = "") -> BinaryWriter:
        """Write a boolean value as a single byte (0x01 for True, 0x00 for False)."""
        offset = self.tell()
        self._stream.write(b"\x01" if value else b"\x00")
        self._record_entry(
            offset=offset,
            size=1,
            type_name="Bool",
            value=value,
            name=name,
            endian="-",
            description=desc,
        )
        return self

    def write_bytes(self, data: Union[bytes, bytearray, memoryview], name: str = "", desc: str = "") -> BinaryWriter:
        """Write a sequence of raw bytes directly to the stream."""
        if not isinstance(data, (bytes, bytearray, memoryview)):
            raise TypeError(f"write_bytes requires bytes-like object, got {type(data).__name__}")
        raw = bytes(data)
        offset = self.tell()
        self._stream.write(raw)
        self._record_entry(
            offset=offset,
            size=len(raw),
            type_name=f"Bytes[{len(raw)}]",
            value=raw,
            name=name,
            endian="-",
            description=desc,
        )
        return self

    # --- String Serialization Methods ---

    def write_cstring(self, text: str, encoding: str = "utf-8", name: str = "", desc: str = "") -> BinaryWriter:
        """Write a null-terminated string (C-string).
        Args:
            text: The string to write.
            encoding: Character encoding (default 'utf-8').
            name: Optional field label for manual generation.
            desc: Optional description for manual generation.
        """
        if not isinstance(text, str):
            raise TypeError(f"write_cstring requires str, got {type(text).__name__}")
        encoded = text.encode(encoding) + b"\x00"
        offset = self.tell()
        self._stream.write(encoded)
        self._record_entry(
            offset=offset,
            size=len(encoded),
            type_name="CString",
            value=text,
            name=name,
            endian="-",
            description=desc,
        )
        return self

    def write_prefixed_string(
        self,
        text: str,
        prefix_bytes: int = 2,
        encoding: str = "utf-8",
        endian: EndianType = None,
        name: str = "",
        desc: str = "",
    ) -> BinaryWriter:
        """Write a length-prefixed string (Pascal-style).

        Args:
            text: The string to write.
            prefix_bytes: Number of bytes for length prefix (1, 2, 4, or 8).
            encoding: Character encoding (default 'utf-8').
            endian: Endianness for multi-byte length prefix.
            name: Optional field label for manual.
            desc: Optional description for manual.
        """
        if not isinstance(text, str):
            raise TypeError(f"write_prefixed_string requires str, got {type(text).__name__}")
        encoded = text.encode(encoding)
        length = len(encoded)
        offset = self.tell()

        if prefix_bytes == 1:
            self._stream.write(struct.pack("B", length))
        elif prefix_bytes == 2:
            order = normalize_endian(endian, self._default_endian)
            self._stream.write(struct.pack(f"{order.value}H", length))
        elif prefix_bytes == 4:
            order = normalize_endian(endian, self._default_endian)
            self._stream.write(struct.pack(f"{order.value}I", length))
        elif prefix_bytes == 8:
            order = normalize_endian(endian, self._default_endian)
            self._stream.write(struct.pack(f"{order.value}Q", length))
        else:
            raise ValueError(f"Unsupported prefix_bytes: {prefix_bytes}. Expected 1, 2, 4, or 8")

        self._stream.write(encoded)
        order = normalize_endian(endian, self._default_endian)
        self._record_entry(
            offset=offset,
            size=prefix_bytes + length,
            type_name=f"PrefixedString[{prefix_bytes}]",
            value=text,
            name=name,
            endian=order.name.capitalize(),
            description=desc,
        )
        return self

    def write_fixed_string(
        self,
        text: str,
        length: int,
        encoding: str = "utf-8",
        pad_byte: bytes = b"\x00",
        truncate: bool = False,
        name: str = "",
        desc: str = "",
    ) -> BinaryWriter:
        """Write a string into a fixed-length byte buffer, padding or truncating as needed."""
        if not isinstance(text, str):
            raise TypeError(f"write_fixed_string requires str, got {type(text).__name__}")
        if not isinstance(pad_byte, (bytes, bytearray)) or len(pad_byte) != 1:
            raise ValueError("pad_byte must be a single byte (e.g. b'\\x00' or b' ')")
        if length < 0:
            raise ValueError(f"length must be non-negative, got {length}")

        encoded = text.encode(encoding)
        if len(encoded) > length:
            if truncate:
                encoded = encoded[:length]
            else:
                raise ValueError(
                    f"Encoded string length ({len(encoded)} bytes) exceeds fixed length ({length} bytes)"
                )

        padding = bytes(pad_byte) * (length - len(encoded))
        offset = self.tell()
        self._stream.write(encoded + padding)
        self._record_entry(
            offset=offset,
            size=length,
            type_name=f"FixedString[{length}]",
            value=text,
            name=name,
            endian="-",
            description=desc,
        )
        return self

    def write_string(
        self,
        text: str,
        encoding: str = "utf-8",
        strategy: str = "null_terminated",
        prefix_bytes: int = 2,
        length: Optional[int] = None,
        pad_byte: bytes = b"\x00",
        endian: EndianType = None,
        name: str = "",
        desc: str = "",
    ) -> BinaryWriter:
        """Convenience method to write strings with various strategies."""
        norm_strategy = strategy.lower().replace("-", "_")
        if norm_strategy in ("null_terminated", "cstring", "c_string"):
            return self.write_cstring(text, encoding=encoding, name=name, desc=desc)
        if norm_strategy in ("prefixed", "pascal", "length_prefixed"):
            return self.write_prefixed_string(
                text, prefix_bytes=prefix_bytes, encoding=encoding, endian=endian, name=name, desc=desc
            )
        if norm_strategy in ("fixed", "fixed_length"):
            if length is None:
                raise ValueError("length is required when strategy is 'fixed'")
            return self.write_fixed_string(
                text, length=length, encoding=encoding, pad_byte=pad_byte, name=name, desc=desc
            )
        raise ValueError(f"Unknown string strategy: {strategy!r}")

    # --- Cursor Positioning, Seeking, and Alignment ---

    def tell(self) -> int:
        """Get the current cursor position in bytes.

        Raises:
            io.UnsupportedOperation: If the underlying stream does not support tell.
        """
        return self._stream.tell()

    def seek(self, offset: int, whence: int = io.SEEK_SET) -> int:
        """Seek to a byte offset in the stream.

        Args:
            offset: The byte offset to seek to.
            whence: io.SEEK_SET (0), io.SEEK_CUR (1), or io.SEEK_END (2).

        Returns:
            The new absolute cursor position.

        Raises:
            io.UnsupportedOperation: If the underlying stream is not seekable.
        """
        if hasattr(self._stream, "seekable") and not self._stream.seekable():
            raise io.UnsupportedOperation("Underlying stream is not seekable")
        return self._stream.seek(offset, whence)

    def pad(self, count: int, pad_byte: bytes = b"\x00", name: str = "padding", desc: str = "") -> BinaryWriter:
        """Write a number of padding bytes."""
        if not isinstance(count, int) or count < 0:
            raise ValueError(f"pad count must be a non-negative integer, got {count}")
        if not isinstance(pad_byte, (bytes, bytearray)) or len(pad_byte) != 1:
            raise ValueError("pad_byte must be a single byte (e.g. b'\\x00')")
        if count > 0:
            offset = self.tell()
            self._stream.write(bytes(pad_byte) * count)
            self._record_entry(
                offset=offset,
                size=count,
                type_name=f"Padding[{count}]",
                value=bytes(pad_byte) * count,
                name=name,
                endian="-",
                description=desc,
            )
        return self

    def align(self, boundary: int, pad_byte: bytes = b"\x00", name: str = "align", desc: str = "") -> BinaryWriter:
        """Align cursor position to a byte boundary by writing padding bytes if needed."""
        if not isinstance(boundary, int) or boundary <= 0:
            raise ValueError(f"boundary must be a positive integer, got {boundary}")

        pos = self.tell()
        rem = pos % boundary
        if rem != 0:
            padding_needed = boundary - rem
            self.pad(padding_needed, pad_byte=pad_byte, name=name, desc=desc or f"Align to {boundary}B boundary")
        return self

    def write_offset_table(
        self,
        count: int,
        offset_size: int = 4,
        endian: EndianType = None,
        name: str = "offsets",
        desc: str = "Offset Table",
        base_offset: int = 0,
    ) -> OffsetTableHandle:
        """Reserve an offset table for `count` entries of `offset_size` bytes each.

        Returns an OffsetTableHandle whose methods (write_offset, set_offset, write_target)
        can be used to fill in target offsets later.

        Args:
            count: Number of offset entries in the table.
            offset_size: Byte size of each offset (1, 2, 4, or 8 bytes, default: 4).
            endian: Endianness for offset values (default: writer's default endian).
            name: Base name for the table entries (e.g. 'file_offsets').
            desc: Description of the offset table.
            base_offset: The base origin (in bytes) subtracted from recorded target offsets
                         (default: 0, file/stream beginning).

        Returns:
            OffsetTableHandle for recording/writing target offsets.
        """
        if count < 0:
            raise ValueError(f"count must be non-negative, got {count}")
        if offset_size not in (1, 2, 4, 8):
            raise ValueError(f"offset_size must be 1, 2, 4, or 8, got {offset_size}")
        if hasattr(base_offset, "resolve"):
            base_offset = base_offset.resolve(self.tell(), self.tell())
        if base_offset < 0:
            raise ValueError(f"base_offset must be non-negative, got {base_offset}")

        order = normalize_endian(endian, self._default_endian)
        start_pos = self.tell()
        fmt_map = {1: "UInt8", 2: "UInt16", 4: "UInt32", 8: "UInt64"}
        type_name = f"Offset[{fmt_map.get(offset_size, f'UInt{offset_size*8}')}]"

        entry_indices: list[int] = []
        for i in range(count):
            slot_pos = self.tell()
            self._stream.write(b"\x00" * offset_size)
            idx = len(self._entries)
            self._record_entry(
                offset=slot_pos,
                size=offset_size,
                type_name=type_name,
                value=0,
                name=f"{name}[{i}]",
                endian=order.name.capitalize(),
                description=f"{desc} [#{i}]" if desc else f"Offset entry {i}",
            )
            entry_indices.append(idx)

        return OffsetTableHandle(
            writer=self,
            start_offset=start_pos,
            count=count,
            offset_size=offset_size,
            endian=order,
            entry_indices=entry_indices,
            name=name,
            base_offset=base_offset,
        )

    def write_struct(self, instance: object, endian: EndianType = None) -> BinaryWriter:
        """Write a @binary_struct instance to this writer's stream.

        Args:
            instance: An instance of a class decorated with @binary_struct.
            endian: Optional endianness override for this struct write.
        """
        from binary_master.binary_struct import write_struct
        write_struct(instance, writer=self, endian=endian)
        return self


class OffsetTableHandle:
    """Handle returned by BinaryWriter.write_offset_table.

    Allows setting or writing target offsets into the reserved offset table slots.
    """

    def __init__(
        self,
        writer: BinaryWriter,
        start_offset: int,
        count: int,
        offset_size: int,
        endian: Endian,
        entry_indices: list[int],
        name: str = "offsets",
        base_offset: int = 0,
    ):
        self._writer = writer
        self._start_offset = start_offset
        self._count = count
        self._offset_size = offset_size
        self._endian = endian
        self._entry_indices = entry_indices
        self._name = name
        self._base_offset = base_offset
        self._offsets: list[Optional[int]] = [None] * count

    @property
    def count(self) -> int:
        return self._count

    @property
    def offset_size(self) -> int:
        return self._offset_size

    @property
    def base_offset(self) -> int:
        """The base offset (origin) from which target offsets are calculated."""
        return self._base_offset

    def get_target_offset(self, index: int) -> Optional[int]:
        """Get the absolute target offset recorded for slot `index`."""
        if index < 0 or index >= self._count:
            raise IndexError(f"OffsetTable index {index} out of range (count={self._count})")
        return self._offsets[index]

    def get_stored_offset(self, index: int) -> Optional[int]:
        """Get the stored relative offset value (target - base) for slot `index`."""
        target = self.get_target_offset(index)
        if target is None:
            return None
        return target - self._base_offset

    def __len__(self) -> int:
        return self._count

    def __getitem__(self, index: int) -> Optional[int]:
        if index < 0 or index >= self._count:
            raise IndexError(f"OffsetTable index {index} out of range (count={self._count})")
        return self._offsets[index]

    def __setitem__(self, index: int, target_offset: int) -> None:
        self.set_offset(index, target_offset)

    def set_offset(self, index: int, target_offset: Optional[int] = None) -> int:
        """Set the target offset at slot `index`.

        If target_offset is None, automatically sets it to the current stream position (writer.tell()).
        Writes the value (target_offset - base_offset) into the binary stream placeholder and updates
        the manual layout entry.

        Returns:
            The stored relative offset value (target_offset - base_offset).
        """
        if index < 0 or index >= self._count:
            raise IndexError(f"OffsetTable index {index} out of range (count={self._count})")

        if target_offset is None:
            target_offset = self._writer.tell()

        stored_value = target_offset - self._base_offset
        if stored_value < 0:
            raise ValueError(
                f"Calculated offset {stored_value} is negative (target={target_offset}, base={self._base_offset})"
            )

        self._offsets[index] = target_offset
        slot_pos = self._start_offset + index * self._offset_size

        fmt_map = {1: "B", 2: "H", 4: "I", 8: "Q"}
        fmt_char = fmt_map.get(self._offset_size)
        if not fmt_char:
            raise ValueError(f"Unsupported offset_size: {self._offset_size}. Must be 1, 2, 4, or 8.")

        packed = struct.pack(f"{self._endian.value}{fmt_char}", stored_value)
        cur_pos = self._writer.tell()
        self._writer.seek(slot_pos)
        self._writer._stream.write(packed)
        self._writer.seek(cur_pos)

        if hasattr(self._writer, "_entries") and index < len(self._entry_indices):
            entry_idx = self._entry_indices[index]
            if 0 <= entry_idx < len(self._writer._entries):
                entry = self._writer._entries[entry_idx]
                entry.value = stored_value
                entry.target_offset = target_offset

        return stored_value

    def write_offset(self, index: int, target_offset: Optional[int] = None) -> int:
        """Write the offset into slot `index` (synonym for set_offset)."""
        return self.set_offset(index, target_offset)

    def write_target(self, index: int, target: Any) -> Any:
        """Record current offset into slot `index`, then serialize and write `target`."""
        pos = self._writer.tell()
        self.set_offset(index, pos)
        if hasattr(target, "__binary__"):
            self._writer.write_struct(target)
        elif isinstance(target, (bytes, bytearray)):
            self._writer.write_bytes(target)
        elif callable(target):
            target(self._writer)
        else:
            raise TypeError(f"Cannot write target of type {type(target).__name__}")
        return pos


Writer = BinaryWriter

