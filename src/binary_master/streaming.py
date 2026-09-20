"""Continuous packet streaming generators for binary streams."""

from __future__ import annotations

import io
from pathlib import Path
from typing import (
    IO,
    Any,
    AsyncIterator,
    Iterator,
    Optional,
    Type,
    TypeVar,
    Union,
)

from binary_master.binary_struct import read_struct
from binary_master.reader import BinaryReader
from binary_master.zero_copy import ZeroCopyView

T = TypeVar("T")


def iter_packets(
    source: Union[bytes, bytearray, memoryview, BinaryReader, IO[bytes], str, Path],
    cls: Type[T],
    max_count: Optional[int] = None,
    ignore_errors: bool = False,
    endian: Optional[str] = None,
) -> Iterator[T]:
    """Yield deserialized packets of type `cls` from a continuous binary stream or buffer.

    Args:
        source: Binary buffer, BinaryReader, open stream, or file path.
        cls: The @binary_struct class to decode.
        max_count: Maximum number of packets to yield.
        ignore_errors: If True, terminates stream on decode error instead of raising.
        endian: Optional endianness override.

    Yields:
        Deserialized instances of `cls`.
    """
    if isinstance(source, (str, Path)):
        with open(source, "rb") as f:
            reader = BinaryReader(f)
            yield from _iter_reader(reader, cls, max_count, ignore_errors, endian)
        return

    if isinstance(source, BinaryReader):
        reader = source
    elif isinstance(source, memoryview):
        reader = BinaryReader(bytes(source))
    elif isinstance(source, (bytes, bytearray)):
        reader = BinaryReader(source)
    elif hasattr(source, "read"):
        reader = BinaryReader(source)
    else:
        raise TypeError(f"Unsupported packet source type: {type(source)}")

    yield from _iter_reader(reader, cls, max_count, ignore_errors, endian)


def _iter_reader(
    reader: BinaryReader,
    cls: Type[T],
    max_count: Optional[int] = None,
    ignore_errors: bool = False,
    endian: Optional[str] = None,
) -> Iterator[T]:
    count = 0
    while max_count is None or count < max_count:
        if reader.is_eof:
            break

        start_pos = reader.tell()
        try:
            packet = read_struct(cls, reader, endian=endian)
            # Guard against zero-byte struct creating infinite loop
            if reader.tell() == start_pos and reader.remaining() > 0:
                raise RuntimeError(
                    f"Struct {cls.__name__} consumed 0 bytes; aborting to prevent infinite loop"
                )
            yield packet
            count += 1
        except (EOFError, io.BlockingIOError):
            break
        except Exception:
            if ignore_errors:
                break
            raise


def iter_views(
    source: Union[bytes, bytearray, memoryview, str, Path],
    cls: Type[T],
    max_count: Optional[int] = None,
    endian: Optional[str] = None,
) -> Iterator[ZeroCopyView[T]]:
    """Yield zero-copy views of continuous packets over an in-memory or memory-mapped buffer.

    Args:
        source: Binary buffer or file path.
        cls: The @binary_struct class to view.
        max_count: Maximum number of packet views to yield.
        endian: Optional endianness override.

    Yields:
        ZeroCopyView instances pointing to each packet in sequence.
    """
    if isinstance(source, (str, Path)):
        view = ZeroCopyView.from_file(cls, source, endian=endian)
        with view:
            buf = view.as_buffer()
            yield from _iter_buffer_views(cls, buf, max_count, endian)
        return

    buf = memoryview(source) if not isinstance(source, memoryview) else source
    yield from _iter_buffer_views(cls, buf, max_count, endian)


def _iter_buffer_views(
    cls: Type[T],
    buf: memoryview,
    max_count: Optional[int] = None,
    endian: Optional[str] = None,
) -> Iterator[ZeroCopyView[T]]:
    offset = 0
    total_len = len(buf)
    count = 0

    while offset < total_len and (max_count is None or count < max_count):
        v = ZeroCopyView(cls, buf, offset=offset, endian=endian)
        sz = v.byte_size
        if sz <= 0:
            raise RuntimeError(f"Struct {cls.__name__} has non-positive size {sz}; cannot stream views")
        if offset + sz > total_len:
            break
        yield v
        offset += sz
        count += 1


async def async_iter_packets(
    source: Any,
    cls: Type[T],
    max_count: Optional[int] = None,
    ignore_errors: bool = False,
    endian: Optional[str] = None,
) -> AsyncIterator[T]:
    """Asynchronously yield packets from an AsyncBinaryReader or asyncio.StreamReader.

    Args:
        source: AsyncBinaryReader or asyncio.StreamReader.
        cls: The @binary_struct class to decode.
        max_count: Maximum number of packets to yield.
        ignore_errors: If True, terminates on decode error.
        endian: Endianness override.

    Yields:
        Deserialized instances of `cls`.
    """
    import asyncio

    from binary_master.async_stream import AsyncBinaryReader

    if isinstance(source, AsyncBinaryReader):
        reader = source
    elif hasattr(source, "read"):
        reader = AsyncBinaryReader(source)
    else:
        raise TypeError(f"Unsupported async packet source: {type(source)}")

    count = 0
    while max_count is None or count < max_count:
        start_pos = reader.tell()
        try:
            packet = await reader.read_struct(cls, endian=endian)
            if reader.tell() == start_pos:
                # If no bytes consumed, break to prevent infinite loop
                break
            yield packet
            count += 1
        except (EOFError, io.BlockingIOError, asyncio.IncompleteReadError):
            break
        except Exception:
            if ignore_errors:
                break
            raise


__all__ = ["iter_packets", "iter_views", "async_iter_packets"]
