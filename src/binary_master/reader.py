"""BinaryReader: Core sequential binary reader implementation."""

from __future__ import annotations

import io
from pathlib import Path
import struct
from typing import IO, Any, Optional, TypeVar, Union

from binary_master.enums import Endian, EndianType, normalize_endian

T = TypeVar("T")


class _ReaderPositionContext:
    """Context manager for preserving reader cursor position."""

    def __init__(self, reader: BinaryReader) -> None:
        self._reader = reader
        self._pos = reader.tell()

    def __enter__(self) -> BinaryReader:
        return self._reader

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self._reader.seek(self._pos, io.SEEK_SET)


class BinaryReader:
    """A sequential binary reader supporting in-memory buffers and stream/file targets."""

    def __init__(
        self,
        source: Union[bytes, bytearray, IO[bytes], str, Path],
        default_endian: EndianType = Endian.LITTLE,
        auto_close: Optional[bool] = None,
    ) -> None:
        """Initialize a BinaryReader.

        Args:
            source: Binary data source (bytes, bytearray, readable binary stream, or file path).
            default_endian: The default byte order (Endian.LITTLE, Endian.BIG, or string alias).
            auto_close: Whether closing this reader should close the underlying stream.
        """
        self._default_endian = normalize_endian(default_endian)

        if isinstance(source, (bytes, bytearray)):
            self._stream: IO[bytes] = io.BytesIO(source)
            self._auto_close = True if auto_close is None else auto_close
        elif isinstance(source, (str, Path)):
            self._stream = open(source, "rb")
            self._auto_close = True if auto_close is None else auto_close
        elif hasattr(source, "read"):
            self._stream = source
            self._auto_close = False if auto_close is None else auto_close
        else:
            raise TypeError(
                f"source must be bytes, bytearray, readable stream, or file path, got {type(source).__name__}"
            )

    @classmethod
    def from_bytes(
        cls,
        data: Union[bytes, bytearray],
        default_endian: EndianType = Endian.LITTLE,
    ) -> BinaryReader:
        """Create a BinaryReader from in-memory bytes or bytearray."""
        return cls(data, default_endian=default_endian)

    @classmethod
    def from_file(
        cls,
        path: Union[str, Path],
        default_endian: EndianType = Endian.LITTLE,
    ) -> BinaryReader:
        """Create a BinaryReader from a file path."""
        return cls(path, default_endian=default_endian, auto_close=True)

    @classmethod
    def from_mmap(
        cls,
        path: Union[str, Path],
        default_endian: EndianType = Endian.LITTLE,
    ) -> BinaryReader:
        """Create a BinaryReader with memory-mapped zero-copy access."""
        import mmap
        f = open(path, "rb")
        fileno = f.fileno()
        mm = mmap.mmap(fileno, 0, access=mmap.ACCESS_READ)
        reader = cls(mm, default_endian=default_endian, auto_close=True)
        reader._mmap_file = f
        reader._mmap = mm
        return reader

    @property
    def default_endian(self) -> Endian:
        """Get the default endianness of this reader."""
        return self._default_endian

    @property
    def stream(self) -> IO[bytes]:
        """Get the underlying binary stream."""
        return self._stream

    def tell(self) -> int:
        """Get current read position (byte offset)."""
        return self._stream.tell()

    def seek(self, offset: int, whence: int = io.SEEK_SET) -> int:
        """Move the read position to offset."""
        return self._stream.seek(offset, whence)

    def skip(self, count: int) -> int:
        """Skip forward by `count` bytes."""
        if count < 0:
            raise ValueError(f"skip count must be non-negative, got {count}")
        return self.seek(count, io.SEEK_CUR)

    def remaining(self) -> int:
        """Return the number of remaining unread bytes in the stream (if seekable)."""
        cur = self.tell()
        self._stream.seek(0, io.SEEK_END)
        end = self.tell()
        self._stream.seek(cur, io.SEEK_SET)
        return end - cur

    def align(self, boundary: int) -> int:
        """Align read position to next `boundary` byte boundary by skipping padding bytes."""
        if boundary <= 0 or (boundary & (boundary - 1)) != 0:
            raise ValueError(f"Alignment boundary must be a positive power of 2, got {boundary}")
        cur = self.tell()
        rem = cur % boundary
        if rem != 0:
            padding_needed = boundary - rem
            self.skip(padding_needed)
        return self.tell()

    @property
    def is_eof(self) -> bool:
        """Return True if cursor has reached or passed the end of the stream."""
        return self.remaining() == 0

    @property
    def eof(self) -> bool:
        """Alias for is_eof."""
        return self.is_eof

    def preserve_position(self) -> _ReaderPositionContext:
        """Context manager that preserves and restores the stream cursor upon exit."""
        return _ReaderPositionContext(self)

    def peek(self, count: int) -> bytes:
        """Read up to `count` bytes without advancing the stream position."""
        if count < 0:
            raise ValueError(f"peek count must be non-negative, got {count}")
        if count == 0:
            return b""
        cur = self.tell()
        try:
            return self._stream.read(count)
        finally:
            self._stream.seek(cur, io.SEEK_SET)

    def peek_bytes(self, count: int) -> bytes:
        """Alias for peek(count)."""
        return self.peek(count)

    def peek_uint8(self) -> int:
        """Peek an unsigned 8-bit integer without advancing the cursor."""
        with self.preserve_position():
            return self.read_uint8()

    def peek_int8(self) -> int:
        """Peek a signed 8-bit integer without advancing the cursor."""
        with self.preserve_position():
            return self.read_int8()

    def peek_uint16(self, endian: EndianType = None) -> int:
        """Peek an unsigned 16-bit integer without advancing the cursor."""
        with self.preserve_position():
            return self.read_uint16(endian=endian)

    def peek_int16(self, endian: EndianType = None) -> int:
        """Peek a signed 16-bit integer without advancing the cursor."""
        with self.preserve_position():
            return self.read_int16(endian=endian)

    def peek_uint32(self, endian: EndianType = None) -> int:
        """Peek an unsigned 32-bit integer without advancing the cursor."""
        with self.preserve_position():
            return self.read_uint32(endian=endian)

    def peek_int32(self, endian: EndianType = None) -> int:
        """Peek a signed 32-bit integer without advancing the cursor."""
        with self.preserve_position():
            return self.read_int32(endian=endian)

    def peek_uint64(self, endian: EndianType = None) -> int:
        """Peek an unsigned 64-bit integer without advancing the cursor."""
        with self.preserve_position():
            return self.read_uint64(endian=endian)

    def peek_int64(self, endian: EndianType = None) -> int:
        """Peek a signed 64-bit integer without advancing the cursor."""
        with self.preserve_position():
            return self.read_int64(endian=endian)

    def close(self) -> None:
        """Close the reader and underlying stream if auto_close is True."""
        if hasattr(self, "_mmap") and self._mmap is not None:
            self._mmap.close()
            self._mmap = None
        if hasattr(self, "_mmap_file") and self._mmap_file is not None:
            self._mmap_file.close()
            self._mmap_file = None
        if self._auto_close and hasattr(self._stream, "close") and not getattr(self._stream, "closed", False):
            self._stream.close()

    def __enter__(self) -> BinaryReader:
        return self

    def __exit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        self.close()

    def iter_struct(self, struct_cls: type[T]) -> Any:
        """Iteratively read struct instances until EOF."""
        while not self.is_eof:
            yield self.read_struct(struct_cls)

    def read_varuint(self) -> int:
        """Read an unsigned variable-length integer (LEB128)."""
        from binary_master.varint import decode_varuint

        val, _ = decode_varuint(self._stream)
        return val

    def read_varint(self) -> int:
        """Read a signed variable-length integer (LEB128)."""
        from binary_master.varint import decode_varint

        val, _ = decode_varint(self._stream)
        return val

    def read_bits(self, bit_count: int) -> int:
        """Read an arbitrary number of bits across byte boundaries."""
        if not hasattr(self, "_bit_reader") or self._bit_reader is None:
            from binary_master.bitstream import BitReader

            self._bit_reader = BitReader(self._stream, msb_first=True)
        return self._bit_reader.read_bits(bit_count)

    def align_to_byte(self) -> None:
        """Align bitstream reader to next byte boundary."""
        if hasattr(self, "_bit_reader") and self._bit_reader is not None:
            self._bit_reader.align_to_byte()
            self._bit_reader = None

    def verify_checksum(
        self,
        algorithm: Union[str, Any] = "crc32",
        expected: Optional[int] = None,
        length: Optional[int] = None,
    ) -> bool:
        """Verify checksum of preceding or specified length of bytes against expected (or next read)."""
        from binary_master.checksum import compute_checksum, get_checksum_algorithm
        from binary_master.exceptions import ChecksumMismatchError

        func, size = get_checksum_algorithm(algorithm)
        if expected is None:
            fmt = {1: "B", 2: "H", 4: "I", 8: "Q"}.get(size, "I")
            expected = self._unpack_read(fmt, size, endian=self._default_endian)

        cur = self.tell()
        check_len = cur - size if length is None else length
        start = max(0, cur - size - check_len) if length is None else cur - size - length
        with self.preserve_position():
            self.seek(start)
            data = self.read_bytes(check_len)
        computed = compute_checksum(algorithm, data)
        if expected != computed:
            raise ChecksumMismatchError(expected=computed, actual=expected)
        return True


    # --- Internal Read Helpers ---

    def _read_exact(self, count: int) -> bytes:
        """Read exactly `count` bytes or raise EOFError."""
        if count < 0:
            raise ValueError(f"Cannot read negative count of bytes: {count}")
        if count == 0:
            return b""
        data = self._stream.read(count)
        if len(data) < count:
            raise EOFError(
                f"Unexpected EOF: requested {count} bytes at offset {self.tell() - len(data)}, got {len(data)}"
            )
        return data

    def _unpack_read(self, fmt_char: str, size: int, endian: EndianType = None) -> Any:
        order = normalize_endian(endian, self._default_endian)
        raw = self._read_exact(size)
        return struct.unpack(f"{order.value}{fmt_char}", raw)[0]

    # --- Primitive Integer Readers ---

    def read_uint8(self) -> int:
        """Read an unsigned 8-bit integer (0 to 255)."""
        return self._unpack_read("B", 1)

    def read_int8(self) -> int:
        """Read a signed 8-bit integer (-128 to 127)."""
        return self._unpack_read("b", 1)

    def read_uint16(self, endian: EndianType = None) -> int:
        """Read an unsigned 16-bit integer (0 to 65535)."""
        return self._unpack_read("H", 2, endian)

    def read_int16(self, endian: EndianType = None) -> int:
        """Read a signed 16-bit integer (-32768 to 32767)."""
        return self._unpack_read("h", 2, endian)

    def read_uint32(self, endian: EndianType = None) -> int:
        """Read an unsigned 32-bit integer (0 to 4294967295)."""
        return self._unpack_read("I", 4, endian)

    def read_int32(self, endian: EndianType = None) -> int:
        """Read a signed 32-bit integer (-2147483648 to 2147483647)."""
        return self._unpack_read("i", 4, endian)

    def read_uint64(self, endian: EndianType = None) -> int:
        """Read an unsigned 64-bit integer (0 to 18446744073709551615)."""
        return self._unpack_read("Q", 8, endian)

    def read_int64(self, endian: EndianType = None) -> int:
        """Read a signed 64-bit integer (-9223372036854775808 to 9223372036854775807)."""
        return self._unpack_read("q", 8, endian)

    # --- Floating-point & Boolean Readers ---

    def read_float32(self, endian: EndianType = None) -> float:
        """Read a 32-bit single precision IEEE 754 float."""
        return self._unpack_read("f", 4, endian)

    def read_float64(self, endian: EndianType = None) -> float:
        """Read a 64-bit double precision IEEE 754 float."""
        return self._unpack_read("d", 8, endian)

    def read_bool(self, size: int = 1, endian: EndianType = None) -> bool:
        """Read a boolean value with configurable byte size (0 is False, any non-zero is True)."""
        if not isinstance(size, int) or size <= 0:
            raise ValueError(f"Bool size must be a positive integer, got {size}")
        if size == 1:
            return self.read_uint8() != 0
        elif size == 2:
            return self.read_uint16(endian=endian) != 0
        elif size == 4:
            return self.read_uint32(endian=endian) != 0
        elif size == 8:
            return self.read_uint64(endian=endian) != 0
        else:
            raw = self.read_bytes(size)
            return any(b != 0 for b in raw)

    def read_bytes(self, count: Optional[int] = None) -> bytes:
        """Read raw bytes from the stream.

        If count is None, reads all remaining bytes until EOF.
        Otherwise, reads exactly `count` bytes (raises EOFError if insufficient).
        """
        if count is None:
            return self._stream.read()
        return self._read_exact(count)

    # --- String Readers ---

    def read_cstring(self, encoding: str = "utf-8") -> str:
        """Read a null-terminated (C-style) string."""
        chars = bytearray()
        while True:
            b = self._stream.read(1)
            if not b:
                raise EOFError(f"Unexpected EOF while reading null-terminated string at offset {self.tell()}")
            if b == b"\x00":
                break
            chars.extend(b)
        return chars.decode(encoding)

    def read_prefixed_string(
        self,
        prefix_bytes: int = 1,
        endian: EndianType = None,
        encoding: str = "utf-8",
    ) -> str:
        """Read a length-prefixed string (Pascal style)."""
        if prefix_bytes == 1:
            length = self.read_uint8()
        elif prefix_bytes == 2:
            length = self.read_uint16(endian=endian)
        elif prefix_bytes == 4:
            length = self.read_uint32(endian=endian)
        elif prefix_bytes == 8:
            length = self.read_uint64(endian=endian)
        else:
            raise ValueError(f"Unsupported prefix_bytes: {prefix_bytes}. Must be 1, 2, 4, or 8.")

        raw = self._read_exact(length)
        return raw.decode(encoding)

    def read_fixed_string(
        self,
        length: int,
        pad_byte: bytes = b"\x00",
        encoding: str = "utf-8",
    ) -> str:
        """Read a fixed-length string, stripping trailing pad bytes."""
        raw = self._read_exact(length)
        raw = raw.rstrip(pad_byte)
        return raw.decode(encoding)

    def read_string(self, length: int, encoding: str = "utf-8") -> str:
        """Read exact length bytes and decode as string."""
        raw = self._read_exact(length)
        return raw.decode(encoding)

    # --- Structure Deserialization ---

    def read_struct(self, cls: type[T], endian: EndianType = None) -> T:
        """Deserialize a @binary_struct class from this reader."""
        from binary_master.binary_struct import read_struct

        return read_struct(cls, reader=self, endian=endian)

    # --- Debugging & Inspection ---

    def hexdump(
        self,
        *,
        width: int = 16,
        color: bool = False,
        show_ascii: bool = True,
        show_header: bool = True,
        max_bytes: Optional[int] = None,
    ) -> str:
        """Generate a hexdump of the reader's buffer showing cursor position and remaining bytes."""
        from binary_master.debug import hexdump as _hexdump

        return _hexdump(
            self,
            width=width,
            color=color,
            annotate=True,
            show_ascii=show_ascii,
            show_header=show_header,
            max_bytes=max_bytes,
        )

    def dump(
        self,
        format: str = "hexdump",
        **kwargs: Any,
    ) -> Union[str, list[dict[str, Any]]]:
        """Generate a debug dump of this reader's buffer and cursor position."""
        from binary_master.debug import debug_dump as _debug_dump

        return _debug_dump(self, format=format, **kwargs)


Reader = BinaryReader
