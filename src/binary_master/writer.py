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
        if stream is None:
            self._stream = io.BytesIO()
            self._close_stream = auto_close if auto_close is not None else False
            self._is_memory = True
        else:
            self._stream = stream
            self._close_stream = auto_close if auto_close is not None else False
            self._is_memory = isinstance(stream, io.BytesIO)

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
    ) -> None:
        from binary_master.manual import LayoutEntry

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


    def write_struct(self, instance: object, endian: EndianType = None) -> BinaryWriter:
        """Write a @binary_struct instance to this writer's stream.

        Args:
            instance: An instance of a class decorated with @binary_struct.
            endian: Optional endianness override for this struct write.
        """
        from binary_master.binary_struct import write_struct
        write_struct(instance, writer=self, endian=endian)
        return self

    def write_manual(
        self,
        path_or_file: Optional[Union[str, Path, IO[str]]] = None,
        title: str = "Binary Specification Manual",
        diagram_direction: str = "TD",
        diagram_type: str = "flowchart",
        bits_per_row: int = 32,
        include_bitfield_diagram: bool = True,
    ) -> str:
        """Generate a Mermaid-powered Markdown manual documenting the written binary layout.

        Args:
            path_or_file: Optional file path or stream to write the manual to.
            title: Title of the manual document.
            diagram_direction: Direction for Mermaid flowchart ('TD', 'LR', etc.).
            diagram_type: Type of structure diagram ('flowchart', 'packet', or 'both').
            bits_per_row: Number of bits per row in packet diagrams (default: 32).
            include_bitfield_diagram: Whether to include packet diagrams in bitfield breakdown.

        Returns:
            The generated Markdown manual as a string.
        """
        from binary_master.manual import generate_manual

        content = generate_manual(
            self._entries,
            default_endian=self._default_endian.name,
            title=title,
            diagram_direction=diagram_direction,
            diagram_type=diagram_type,
            bits_per_row=bits_per_row,
            include_bitfield_diagram=include_bitfield_diagram,
        )
        if path_or_file is not None:
            if isinstance(path_or_file, (str, Path)):
                Path(path_or_file).write_text(content, encoding="utf-8")
            else:
                path_or_file.write(content)
        return content


