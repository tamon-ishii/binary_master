"""Checksum and CRC calculation algorithms and declarative types."""

from __future__ import annotations

import struct
import zlib
from typing import Any, Callable, Generic, Optional, TypeVar, Union


def calc_crc32(data: bytes | bytearray | memoryview) -> int:
    """Calculate 32-bit standard IEEE 802.3 CRC."""
    return zlib.crc32(bytes(data)) & 0xFFFFFFFF


def calc_crc16_ccitt(data: bytes | bytearray | memoryview, init: int = 0xFFFF) -> int:
    """Calculate 16-bit CRC-CCITT (poly 0x1021)."""
    crc = init
    for b in data:
        crc ^= (b << 8)
        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) ^ 0x1021) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF
    return crc & 0xFFFF


def calc_crc16_arc(data: bytes | bytearray | memoryview, init: int = 0x0000) -> int:
    """Calculate 16-bit CRC-16 / ARC (poly 0xA001, reflected)."""
    crc = init
    for b in data:
        crc ^= b
        for _ in range(8):
            if crc & 0x0001:
                crc = ((crc >> 1) ^ 0xA001) & 0xFFFF
            else:
                crc = (crc >> 1) & 0xFFFF
    return crc & 0xFFFF


def calc_checksum8(data: bytes | bytearray | memoryview) -> int:
    """Calculate 8-bit simple sum modulo 256."""
    return sum(data) & 0xFF


def calc_checksum16(data: bytes | bytearray | memoryview) -> int:
    """Calculate 16-bit sum modulo 65536."""
    return sum(data) & 0xFFFF


def calc_fletcher16(data: bytes | bytearray | memoryview) -> int:
    """Calculate 16-bit Fletcher checksum."""
    sum1 = 0
    sum2 = 0
    for b in data:
        sum1 = (sum1 + b) % 255
        sum2 = (sum2 + sum1) % 255
    return ((sum2 << 8) | sum1) & 0xFFFF


def calc_adler32(data: bytes | bytearray | memoryview) -> int:
    """Calculate 32-bit Adler checksum."""
    return zlib.adler32(bytes(data)) & 0xFFFFFFFF


_ALGORITHMS: dict[str, tuple[Callable[[bytes], int], int]] = {
    "crc32": (calc_crc32, 4),
    "crc16": (calc_crc16_ccitt, 2),
    "crc16_ccitt": (calc_crc16_ccitt, 2),
    "crc16_arc": (calc_crc16_arc, 2),
    "checksum8": (calc_checksum8, 1),
    "checksum16": (calc_checksum16, 2),
    "fletcher16": (calc_fletcher16, 2),
    "adler32": (calc_adler32, 4),
}


def register_checksum_algorithm(name: str, func: Callable[[bytes], int], size: int) -> None:
    """Register a custom checksum algorithm."""
    _ALGORITHMS[name.lower()] = (func, size)


def get_checksum_algorithm(name_or_func: str | Callable[[bytes], int]) -> tuple[Callable[[bytes], int], int]:
    """Resolve a checksum algorithm and its byte size."""
    if callable(name_or_func):
        return name_or_func, 4
    key = str(name_or_func).lower()
    if key in _ALGORITHMS:
        return _ALGORITHMS[key]
    raise ValueError(f"Unknown checksum algorithm: {name_or_func!r}. Available: {list(_ALGORITHMS.keys())}")


def compute_checksum(algorithm: str | Callable[[bytes], int], data: bytes | bytearray | memoryview) -> int:
    """Compute checksum of given data using algorithm."""
    func, _ = get_checksum_algorithm(algorithm)
    return func(bytes(data))


class ChecksumTypeMeta(type):
    """Metaclass for Checksum types enabling slicing like CRC32[0:...] or CRC32."""

    _algorithm: str = "crc32"
    _size: int = 4
    _range: Optional[slice] = None

    def __getitem__(cls, item: Any) -> type:
        if isinstance(item, slice):
            name = f"{cls.__name__}[{item.start}:{item.stop}]"
            return ChecksumTypeMeta(
                name,
                (cls,),
                {
                    "_algorithm": cls._algorithm,
                    "_size": cls._size,
                    "_range": item,
                    "__module__": cls.__module__,
                    "__qualname__": name,
                },
            )
        return cls

    @property
    def algorithm(cls) -> str:
        return getattr(cls, "_algorithm", "crc32")

    @property
    def size(cls) -> int:
        return getattr(cls, "_size", 4)

    @property
    def byte_range(cls) -> Optional[slice]:
        return getattr(cls, "_range", None)


class ChecksumBase(metaclass=ChecksumTypeMeta):
    """Base class for all checksum field types."""
    _algorithm = "crc32"
    _size = 4
    _range = None


class CRC32(ChecksumBase):
    """32-bit standard CRC (4 bytes). Covers bytes from start of struct to field by default."""
    _algorithm = "crc32"
    _size = 4


class CRC16(ChecksumBase):
    """16-bit CRC-CCITT (2 bytes). Covers bytes from start of struct to field by default."""
    _algorithm = "crc16"
    _size = 2


class CRC16CCITT(ChecksumBase):
    """16-bit CRC-CCITT (2 bytes)."""
    _algorithm = "crc16_ccitt"
    _size = 2


CRC16_CCITT = CRC16CCITT


class CRC16ARC(ChecksumBase):
    """16-bit CRC-16 ARC (2 bytes)."""
    _algorithm = "crc16_arc"
    _size = 2


CRC16_ARC = CRC16ARC


class Checksum8(ChecksumBase):
    """8-bit simple sum (1 byte)."""
    _algorithm = "checksum8"
    _size = 1


class Checksum16(ChecksumBase):
    """16-bit simple sum (2 bytes)."""
    _algorithm = "checksum16"
    _size = 2


class Adler32(ChecksumBase):
    """32-bit Adler checksum (4 bytes)."""
    _algorithm = "adler32"
    _size = 4


class Fletcher16(ChecksumBase):
    """16-bit Fletcher checksum (2 bytes)."""
    _algorithm = "fletcher16"
    _size = 2
