"""Tests for BinaryReader and @binary_struct deserialization."""

import struct
from pathlib import Path

import pytest

from binary_master import (
    Array,
    BinaryReader,
    BinaryWriter,
    Bits,
    Endian,
    FixedArray,
    Float32,
    Int32,
    Offset,
    UInt8,
    UInt16,
    UInt32,
    binary_struct,
)

# ==========================================================
# 1. Primitive Reading Tests
# ==========================================================

def test_reader_integers_little_and_big_endian():
    """Test reading signed and unsigned integers across standard bit-widths."""
    raw = struct.pack("<BbHhIiQq", 255, -120, 60000, -30000, 3000000000, -1500000000, 100000000000, -50000000000)
    reader = BinaryReader(raw, default_endian=Endian.LITTLE)

    assert reader.read_uint8() == 255
    assert reader.read_int8() == -120
    assert reader.read_uint16() == 60000
    assert reader.read_int16() == -30000
    assert reader.read_uint32() == 3000000000
    assert reader.read_int32() == -1500000000
    assert reader.read_uint64() == 100000000000
    assert reader.read_int64() == -50000000000


def test_reader_endian_override():
    """Test reading with explicit per-call endianness override."""
    raw = struct.pack(">H", 0x1234) + struct.pack("<H", 0x1234)
    reader = BinaryReader(raw)

    assert reader.read_uint16(endian=Endian.BIG) == 0x1234
    assert reader.read_uint16(endian=Endian.LITTLE) == 0x1234


def test_reader_float_and_bool():
    """Test reading IEEE 754 floats and boolean values."""
    raw = struct.pack("<fd", 1.5, 3.141592653589793) + b"\x01\x00\xFF"
    reader = BinaryReader(raw)

    assert abs(reader.read_float32() - 1.5) < 1e-6
    assert abs(reader.read_float64() - 3.141592653589793) < 1e-12
    assert reader.read_bool() is True
    assert reader.read_bool() is False
    assert reader.read_bool() is True  # Non-zero byte is True


def test_reader_eof_error():
    """Test that reading past the end of the stream raises EOFError."""
    reader = BinaryReader(b"\x01\x02")
    assert reader.read_uint8() == 1
    assert reader.read_uint8() == 2
    with pytest.raises(EOFError, match="Unexpected EOF"):
        reader.read_uint8()


# ==========================================================
# 2. String Reading Tests
# ==========================================================

def test_reader_cstring():
    """Test reading null-terminated C-strings."""
    reader = BinaryReader(b"Hello\x00World\x00Extra")
    assert reader.read_cstring() == "Hello"
    assert reader.read_cstring() == "World"
    assert reader.read_bytes() == b"Extra"


def test_reader_prefixed_string():
    """Test reading length-prefixed strings."""
    # 1-byte prefix
    data1 = b"\x05Hello"
    # 2-byte prefix in big-endian
    data2 = struct.pack(">H", 5) + b"World"
    # 4-byte prefix in little-endian
    data4 = struct.pack("<I", 4) + b"Test"

    reader = BinaryReader(data1 + data2 + data4)
    assert reader.read_prefixed_string(prefix_bytes=1) == "Hello"
    assert reader.read_prefixed_string(prefix_bytes=2, endian=Endian.BIG) == "World"
    assert reader.read_prefixed_string(prefix_bytes=4, endian=Endian.LITTLE) == "Test"


def test_reader_fixed_string():
    """Test reading fixed-length padded strings."""
    data = b"cat\x00\x00\x00" + b"dog###"
    reader = BinaryReader(data)
    assert reader.read_fixed_string(6, pad_byte=b"\x00") == "cat"
    assert reader.read_fixed_string(6, pad_byte=b"#") == "dog"


# ==========================================================
# 3. Stream Navigation & File Reading Tests
# ==========================================================

def test_reader_navigation():
    """Test tell, seek, skip, align, and remaining."""
    reader = BinaryReader(b"\x00\x01\x02\x03\x04\x05\x06\x07\x08")
    assert reader.tell() == 0
    assert reader.remaining() == 9

    reader.skip(3)
    assert reader.tell() == 3
    assert reader.read_uint8() == 3

    reader.seek(1)
    assert reader.read_uint8() == 1

    # Alignment: cursor is at 2, align to 4 should skip to 4
    assert reader.tell() == 2
    reader.align(4)
    assert reader.tell() == 4
    assert reader.read_uint8() == 4


def test_reader_from_file(tmp_path: Path):
    """Test reading from external file stream."""
    p = tmp_path / "test.bin"
    p.write_bytes(b"\xAA\xBB\xCC\xDD")

    with BinaryReader.from_file(p) as reader:
        assert reader.read_uint32(endian=Endian.BIG) == 0xAABBCCDD


# ==========================================================
# 4. @binary_struct Deserialization Tests
# ==========================================================

@binary_struct(endian="little")
class PrimitiveStruct:
    u8: UInt8
    u16: UInt16
    u32: UInt32
    i32: Int32
    f32: Float32


@binary_struct(bits=16)
class FlagsBitfield:
    enable: Bits[1]
    mode: Bits[3]
    priority: Bits[4]
    reserved: Bits[8]


@binary_struct(endian="little")
class PacketWithNested:
    magic: UInt32
    flags: FlagsBitfield
    count: UInt16


@binary_struct(endian="big")
class FixedArrayPacket:
    id: UInt16
    length: UInt8
    payload: FixedArray[UInt8, 16]


@binary_struct(endian="little")
class ImageSpec:
    width: UInt16
    height: UInt16
    pixels: Array[UInt8]


@binary_struct(endian="little")
class FileHeaderWithOffset:
    magic: UInt32
    image_offset: Offset["ImageSpec"]


def test_roundtrip_primitive_struct():
    """Test round-trip serialization and deserialization of primitive struct."""
    orig = PrimitiveStruct(
        u8=42,
        u16=1000,
        u32=100000,
        i32=-500,
        f32=2.5,
    )
    raw = orig.to_bytes()
    deserialized = PrimitiveStruct.from_bytes(raw)

    assert deserialized.u8 == orig.u8
    assert deserialized.u16 == orig.u16
    assert deserialized.u32 == orig.u32
    assert deserialized.i32 == orig.i32
    assert abs(deserialized.f32 - orig.f32) < 1e-6


def test_roundtrip_bitfield():
    """Test round-trip of bitfield struct."""
    flags = FlagsBitfield(enable=1, mode=5, priority=12, reserved=0xAB)
    raw = flags.to_bytes()
    unpacked = FlagsBitfield.from_bytes(raw)

    assert unpacked.enable == 1
    assert unpacked.mode == 5
    assert unpacked.priority == 12
    assert unpacked.reserved == 0xAB


def test_roundtrip_nested_struct():
    """Test round-trip of struct with nested bitfield."""
    pkt = PacketWithNested(
        magic=0x12345678,
        flags=FlagsBitfield(enable=1, mode=2, priority=7, reserved=0),
        count=10,
    )
    raw = pkt.to_bytes()
    unpacked = PacketWithNested.from_bytes(raw)

    assert unpacked.magic == 0x12345678
    assert unpacked.flags.enable == 1
    assert unpacked.flags.mode == 2
    assert unpacked.flags.priority == 7
    assert unpacked.count == 10


def test_roundtrip_fixed_array():
    """Test round-trip of FixedArray."""
    pkt = FixedArrayPacket(id=0xCAFE, length=4, payload=b"test\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00")
    raw = pkt.to_bytes()
    unpacked = FixedArrayPacket.from_bytes(raw)

    assert unpacked.id == 0xCAFE
    assert unpacked.length == 4
    assert unpacked.payload[:4] == b"test"


def test_roundtrip_offset_target():
    """Test round-trip struct with Offset[T] pointing to another struct."""
    img = ImageSpec(width=640, height=480, pixels=b"\xFF\x00\xFF\x00")
    header = FileHeaderWithOffset(magic=0x504B5431, image_offset=img)

    writer = BinaryWriter()
    writer.write_struct(header)
    raw = writer.to_bytes()

    unpacked = FileHeaderWithOffset.from_bytes(raw)
    assert unpacked.magic == 0x504B5431
    assert isinstance(unpacked.image_offset, ImageSpec)
    assert unpacked.image_offset.width == 640
    assert unpacked.image_offset.height == 480
    assert unpacked.image_offset.pixels == b"\xFF\x00\xFF\x00"


@binary_struct(endian="little", auto_align=True)
class AutoAlignedRoundTrip:
    tag: UInt8
    value: UInt32


def test_roundtrip_auto_aligned():
    """Test round-trip of auto_align struct with padding."""
    s = AutoAlignedRoundTrip(tag=0x77, value=0xAABBCCDD)
    raw = s.to_bytes()
    assert len(raw) == 8  # 1 byte tag + 3 bytes padding + 4 bytes value

    unpacked = AutoAlignedRoundTrip.from_bytes(raw)
    assert unpacked.tag == 0x77
    assert unpacked.value == 0xAABBCCDD


def test_reader_peek_and_is_eof():
    """Test BinaryReader.peek, typed peeks, is_eof, and preserve_position."""
    data = b"\x12\x34\x56\x78\x9A\xBC\xDE\xF0"
    reader = BinaryReader(data, default_endian="little")

    assert not reader.is_eof
    assert not reader.eof
    assert reader.tell() == 0

    # Peek raw bytes
    assert reader.peek(4) == b"\x12\x34\x56\x78"
    assert reader.peek_bytes(4) == b"\x12\x34\x56\x78"
    assert reader.tell() == 0

    # Peek typed integers
    assert reader.peek_uint8() == 0x12
    assert reader.peek_uint16() == 0x3412
    assert reader.peek_uint32() == 0x78563412
    assert reader.tell() == 0

    # Read some bytes
    assert reader.read_uint32() == 0x78563412
    assert reader.tell() == 4
    assert not reader.is_eof

    # preserve_position context manager
    with reader.preserve_position():
        val = reader.read_uint32()
        assert val == 0xF0DEBC9A
        assert reader.tell() == 8

    # Cursor restored
    assert reader.tell() == 4
    assert reader.read_uint32() == 0xF0DEBC9A
    assert reader.tell() == 8
    assert reader.is_eof
    assert reader.eof
    assert reader.peek(4) == b""
