"""Arbitrary bitstream reader and writer."""

from __future__ import annotations

import io
from typing import BinaryIO, IO, Optional, Union


class BitWriter:
    """Bit-level writer for packing arbitrary bit counts across byte boundaries."""

    def __init__(self, stream: Optional[Union[BinaryIO, IO[bytes]]] = None, msb_first: bool = True):
        self._stream = stream
        self._buffer = bytearray()
        self._accumulator = 0
        self._bit_count = 0  # number of bits currently in accumulator
        self._total_bits = 0
        self.msb_first = msb_first

    @property
    def total_bits(self) -> int:
        return self._total_bits

    @property
    def has_unaligned_bits(self) -> bool:
        return self._bit_count > 0

    def write_bits(self, value: int, bit_count: int) -> BitWriter:
        """Write specified number of bits from value."""
        if bit_count < 0:
            raise ValueError(f"bit_count must be non-negative, got {bit_count}")
        if bit_count == 0:
            return self

        # Mask value to bit_count bits
        value &= (1 << bit_count) - 1

        if self.msb_first:
            self._accumulator = (self._accumulator << bit_count) | value
            self._bit_count += bit_count
            self._total_bits += bit_count

            while self._bit_count >= 8:
                shift = self._bit_count - 8
                byte = (self._accumulator >> shift) & 0xFF
                if self._stream is not None:
                    self._stream.write(bytes([byte]))
                else:
                    self._buffer.append(byte)
                self._bit_count -= 8
                self._accumulator &= (1 << self._bit_count) - 1 if self._bit_count > 0 else 0
        else:
            # LSB-first
            self._accumulator |= (value << self._bit_count)
            self._bit_count += bit_count
            self._total_bits += bit_count

            while self._bit_count >= 8:
                byte = self._accumulator & 0xFF
                if self._stream is not None:
                    self._stream.write(bytes([byte]))
                else:
                    self._buffer.append(byte)
                self._accumulator >>= 8
                self._bit_count -= 8

        return self

    def flush_bits(self, pad_bit: int = 0) -> BitWriter:
        """Flush remaining fractional bits to the next byte boundary."""
        if self._bit_count > 0:
            needed = 8 - self._bit_count
            if self.msb_first:
                pad_val = (0xFF if pad_bit else 0x00) & ((1 << needed) - 1)
                byte = ((self._accumulator << needed) | pad_val) & 0xFF
            else:
                pad_val = ((0xFF if pad_bit else 0x00) & ((1 << needed) - 1)) << self._bit_count
                byte = (self._accumulator | pad_val) & 0xFF

            if self._stream is not None:
                self._stream.write(bytes([byte]))
            else:
                self._buffer.append(byte)

            self._accumulator = 0
            self._bit_count = 0
        return self

    def align_to_byte(self, pad_bit: int = 0) -> BitWriter:
        """Align bit position to next byte boundary."""
        return self.flush_bits(pad_bit=pad_bit)

    def to_bytes(self, pad_bit: int = 0) -> bytes:
        """Flush and return full buffer as bytes."""
        self.flush_bits(pad_bit=pad_bit)
        if self._stream is not None:
            if hasattr(self._stream, "getvalue"):
                return self._stream.getvalue()
        return bytes(self._buffer)


class BitReader:
    """Bit-level reader for extracting arbitrary bit counts across byte boundaries."""

    def __init__(self, data: bytes | bytearray | memoryview | BinaryIO, msb_first: bool = True):
        if isinstance(data, (bytes, bytearray, memoryview)):
            self._stream: BinaryIO = io.BytesIO(bytes(data))
        else:
            self._stream = data
        self._accumulator = 0
        self._bit_count = 0
        self.msb_first = msb_first

    def _ensure_bits(self, count: int) -> None:
        while self._bit_count < count:
            raw = self._stream.read(1)
            if not raw:
                break
            byte = raw[0]
            if self.msb_first:
                self._accumulator = (self._accumulator << 8) | byte
            else:
                self._accumulator |= (byte << self._bit_count)
            self._bit_count += 8

    def read_bits(self, bit_count: int) -> int:
        """Read and consume specified number of bits."""
        if bit_count < 0:
            raise ValueError(f"bit_count must be non-negative, got {bit_count}")
        if bit_count == 0:
            return 0

        self._ensure_bits(bit_count)
        if self._bit_count < bit_count:
            raise EOFError(f"Requested {bit_count} bits, but only {self._bit_count} bits available")

        if self.msb_first:
            shift = self._bit_count - bit_count
            val = (self._accumulator >> shift) & ((1 << bit_count) - 1)
            self._bit_count -= bit_count
            self._accumulator &= (1 << self._bit_count) - 1 if self._bit_count > 0 else 0
            return val
        else:
            val = self._accumulator & ((1 << bit_count) - 1)
            self._accumulator >>= bit_count
            self._bit_count -= bit_count
            return val

    def peek_bits(self, bit_count: int) -> int:
        """Peek bits without advancing bit position."""
        if bit_count < 0:
            raise ValueError(f"bit_count must be non-negative, got {bit_count}")
        if bit_count == 0:
            return 0

        self._ensure_bits(bit_count)
        if self._bit_count < bit_count:
            raise EOFError(f"Requested {bit_count} bits, but only {self._bit_count} bits available")

        if self.msb_first:
            shift = self._bit_count - bit_count
            return (self._accumulator >> shift) & ((1 << bit_count) - 1)
        else:
            return self._accumulator & ((1 << bit_count) - 1)

    def align_to_byte(self) -> None:
        """Discard unaligned bits to advance to the next whole byte boundary."""
        self._accumulator = 0
        self._bit_count = 0
