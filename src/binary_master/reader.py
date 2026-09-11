"""BinaryReader: Core sequential binary reader implementation."""

from __future__ import annotations

import io
from pathlib import Path
import struct
from typing import IO, Any, Optional, TypeVar, Union

from binary_master.enums import Endian, EndianType, normalize_endian

T = TypeVar("T")


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

    def close(self) -> None:
        """Close the reader and underlying stream if auto_close is True."""
        if self._auto_close and hasattr(self._stream, "close"):
            self._stream.close()

    def __enter__(self) -> BinaryReader:
        return self

    def __exit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        self.close()

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

    def read_bool(self) -> bool:
        """Read a boolean value (0x00 is False, any non-zero is True)."""
        b = self.read_uint8()
        return b != 0

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


Reader = BinaryReader
