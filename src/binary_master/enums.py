"""Endian and binary type enumerations."""

from enum import Enum
from typing import Any, Optional, Union


class Endian(Enum):
    """Byte order enumeration."""

    LITTLE = "<"
    BIG = ">"
    NATIVE = "="


EndianType = Optional[Union[Endian, str]]

_ENDIAN_MAP = {
    "little": Endian.LITTLE,
    "le": Endian.LITTLE,
    "<": Endian.LITTLE,
    "big": Endian.BIG,
    "be": Endian.BIG,
    ">": Endian.BIG,
    "native": Endian.NATIVE,
    "=": Endian.NATIVE,
    "@": Endian.NATIVE,
}


def normalize_endian(
    endian: EndianType = None, default: Optional[Endian] = None
) -> Endian:
    """Normalize an endianness value to an Endian enum instance."""
    if endian is None:
        return default if default is not None else Endian.LITTLE
    if isinstance(endian, Endian):
        return endian
    if not isinstance(endian, str):
        raise TypeError(f"Expected Endian or str, got {type(endian).__name__}")

    key = endian.strip().lower()
    if key in _ENDIAN_MAP:
        return _ENDIAN_MAP[key]
    raise ValueError(f"Unknown endianness: {endian!r}")


class BinaryType:
    def __init__(self, name, fmt, size):
        self.name = name
        self.fmt = fmt
        self.size = size

    def __repr__(self):
        return self.name


UInt8  = BinaryType("UInt8",  "B", 1)
UInt16 = BinaryType("UInt16", "H", 2)
UInt32 = BinaryType("UInt32", "I", 4)
UInt64 = BinaryType("UInt64", "Q", 8)
Bool   = BinaryType("Bool",   "?", 1)


def normalize_offset_key(key: Any) -> str:
    """Normalize an Offset key (str, Enum, or object) to a standard string identifier."""
    if isinstance(key, str):
        return key
    if isinstance(key, Enum):
        if isinstance(key.value, str):
            return key.value
        return f"{key.__class__.__name__}.{key.name}"
    if hasattr(key, "name") and isinstance(key.name, str):
        return key.name
    return str(key)

