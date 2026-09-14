"""Variable-length integer (LEB128) encoding and decoding."""

from __future__ import annotations

import io
from typing import Any, BinaryIO, Optional, Union


def encode_varuint(val: int) -> bytes:
    """Encode an unsigned integer using unsigned LEB128."""
    if val < 0:
        raise ValueError(f"VarUInt cannot encode negative values: {val}")
    if val == 0:
        return b"\x00"
    out = bytearray()
    while val > 0:
        byte = val & 0x7F
        val >>= 7
        if val > 0:
            byte |= 0x80
        out.append(byte)
    return bytes(out)


def decode_varuint(source: bytes | bytearray | BinaryIO, offset: int = 0) -> tuple[int, int]:
    """Decode an unsigned integer using unsigned LEB128.
    
    Returns (decoded_value, bytes_consumed).
    """
    result = 0
    shift = 0
    count = 0

    if isinstance(source, (bytes, bytearray, memoryview)):
        idx = offset
        length = len(source)
        while True:
            if idx >= length:
                raise EOFError("Unexpected EOF while decoding VarUInt")
            byte = source[idx]
            idx += 1
            count += 1
            result |= (byte & 0x7F) << shift
            shift += 7
            if not (byte & 0x80):
                break
            if count > 10:
                raise ValueError("VarUInt exceeds maximum 64-bit representation (10 bytes)")
        return result, count
    else:
        # Binary stream
        while True:
            raw = source.read(1)
            if not raw:
                raise EOFError("Unexpected EOF while decoding VarUInt")
            byte = raw[0]
            count += 1
            result |= (byte & 0x7F) << shift
            shift += 7
            if not (byte & 0x80):
                break
            if count > 10:
                raise ValueError("VarUInt exceeds maximum 64-bit representation (10 bytes)")
        return result, count


def encode_varint(val: int) -> bytes:
    """Encode a signed integer using signed LEB128."""
    out = bytearray()
    more = True
    while more:
        byte = val & 0x7F
        val >>= 7
        # Check if sign bit is consistent with remaining value
        if (val == 0 and not (byte & 0x40)) or (val == -1 and (byte & 0x40)):
            more = False
        else:
            byte |= 0x80
        out.append(byte)
    return bytes(out)


def decode_varint(source: bytes | bytearray | BinaryIO, offset: int = 0) -> tuple[int, int]:
    """Decode a signed integer using signed LEB128.
    
    Returns (decoded_value, bytes_consumed).
    """
    result = 0
    shift = 0
    count = 0

    if isinstance(source, (bytes, bytearray, memoryview)):
        idx = offset
        length = len(source)
        while True:
            if idx >= length:
                raise EOFError("Unexpected EOF while decoding VarInt")
            byte = source[idx]
            idx += 1
            count += 1
            result |= (byte & 0x7F) << shift
            shift += 7
            if not (byte & 0x80):
                # Sign extension if high bit (0x40) of last 7-bit chunk is set
                if (byte & 0x40) and shift < 64:
                    result |= -(1 << shift)
                break
            if count > 10:
                raise ValueError("VarInt exceeds maximum 64-bit representation (10 bytes)")
        return result, count
    else:
        while True:
            raw = source.read(1)
            if not raw:
                raise EOFError("Unexpected EOF while decoding VarInt")
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
        return result, count


class VarIntTypeMeta(type):
    """Metaclass for variable-length integer types."""
    _signed: bool = False
    _max_bits: int = 64

    @property
    def is_signed(cls) -> bool:
        return getattr(cls, "_signed", False)

    @property
    def max_bits(cls) -> int:
        return getattr(cls, "_max_bits", 64)

    @property
    def size(cls) -> int:
        return 0  # Dynamic size


class VarUInt(metaclass=VarIntTypeMeta):
    """Unsigned variable-length integer (LEB128)."""
    _signed = False
    _max_bits = 64


class VarInt(metaclass=VarIntTypeMeta):
    """Signed variable-length integer (LEB128)."""
    _signed = True
    _max_bits = 64


class VarUInt32(VarUInt):
    _signed = False
    _max_bits = 32


class VarInt32(VarInt):
    _signed = True
    _max_bits = 32


class VarUInt64(VarUInt):
    _signed = False
    _max_bits = 64


class VarInt64(VarInt):
    _signed = True
    _max_bits = 64
