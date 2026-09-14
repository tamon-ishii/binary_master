"""Tests for binary_struct serialization and writing."""

from pathlib import Path
import struct
import pytest

from binary_master import (
    BinaryWriter,
    Endian,
    UInt8,
    UInt16,
    UInt32,
    UInt64,
    Int8,
    Int16,
    Int32,
    Int64,
    Float32,
    Float64,
    Offset,
    Array,
    FixedArray,
    Bits,
    binary_struct,
    write_struct,
    sizeof,
    binary_size,
    offsetof,
    bit_offsetof,
)


# ==========================================================
# Test Struct Definitions
# ==========================================================

@binary_struct(bits=16)
class Flags:
    enable: Bits[1]
    mode: Bits[3]
    priority: Bits[4]
    reserved: Bits[8]


@binary_struct(endian="little")
class Header:
    magic: UInt32
    version: UInt16
    flags: Flags
    image_offset: Offset["Image"]


@binary_struct(endian="little")
class Image:
    width: UInt16
    height: UInt16
    pixels: Array[UInt8]


@binary_struct(endian="big")
class Packet:
    id: UInt16
    count: UInt8
    payload: FixedArray[UInt8, 64]


@binary_struct(endian="little")
class AllPrimitives:
    u8: UInt8
    u16: UInt16
    u32: UInt32
    u64: UInt64
    i8: Int8
    i16: Int16
    i32: Int32
    i64: Int64
    f32: Float32
    f64: Float64


# ==========================================================
# Tests
# ==========================================================

def test_write_primitive_struct():
    """Test writing a struct with all primitive binary types."""
    obj = AllPrimitives(
        u8=255,
        u16=1000,
        u32=100000,
        u64=10000000000,
        i8=-128,
        i16=-1000,
        i32=-100000,
        i64=-10000000000,
        f32=1.5,
        f64=3.141592653589793,
    )

    data = obj.to_bytes()
    expected_all = struct.pack(
        "<BHIQbhiqfd",
        obj.u8,
        obj.u16,
        obj.u32,
        obj.u64,
        obj.i8,
        obj.i16,
        obj.i32,
        obj.i64,
        obj.f32,
        obj.f64,
    )
    assert data == expected_all
    assert len(data) == 1 + 2 + 4 + 8 + 1 + 2 + 4 + 8 + 4 + 8


def test_write_bitfield_struct():
    """Test writing a bitfield struct with Bits[N]."""
    flags = Flags(enable=1, mode=5, priority=12, reserved=0xAB)

    # enable (1 bit, 1) -> 1
    # mode (3 bits, 5) -> 5 << 1 = 10
    # priority (4 bits, 12) -> 12 << 4 = 192
    # sum lower byte = 1 + 10 + 192 = 203 (0xCB)
    # reserved (8 bits, 0xAB) -> 0xAB << 8
    # little-endian: 0xCB 0xAB
    data = flags.to_bytes()
    assert data == b"\xCB\xAB"

    # Big-endian write override
    data_be = flags.to_bytes(endian=Endian.BIG)
    assert data_be == b"\xAB\xCB"


def test_write_fixed_array_packet():
    """Test writing a struct with FixedArray payload."""
    payload_data = b"Hello, BinaryMaster!"
    pkt = Packet(id=0x1234, count=len(payload_data), payload=payload_data)

    data = pkt.to_bytes()
    # Packet is endian="big"
    # id (2 bytes) = 0x1234 -> \x12\x34
    # count (1 byte) = 20 -> \x14
    # payload (64 bytes) = payload_data padded with \x00 to 64 bytes
    assert len(data) == 2 + 1 + 64
    assert data[:2] == b"\x12\x34"
    assert data[2] == len(payload_data)
    assert data[3:3 + len(payload_data)] == payload_data
    assert data[3 + len(payload_data):] == b"\x00" * (64 - len(payload_data))


def test_write_fixed_array_overflow():
    """Test that FixedArray raises ValueError if payload exceeds fixed size."""
    too_long = b"X" * 65
    pkt = Packet(id=1, count=65, payload=too_long)
    with pytest.raises(ValueError, match="exceeds 64"):
        pkt.to_bytes()


def test_write_nested_struct_and_offset():
    """Test writing a struct with a nested bitfield and an Offset pointing to another struct."""
    flags = Flags(enable=1, mode=5, priority=12, reserved=0xAB)
    img = Image(width=2, height=2, pixels=b"\x01\x02\x03\x04")
    hdr = Header(magic=0x42494E59, version=1, flags=flags, image_offset=img)

    # Use BinaryWriter directly
    writer = BinaryWriter()
    writer.write_struct(hdr)
    data = writer.to_bytes()

    # Total size:
    # Header:
    # - magic (4 bytes): 0x42494E59 LE -> \x59\x4E\x49\x42 (offset 0..3)
    # - version (2 bytes): 1 LE -> \x01\x00 (offset 4..5)
    # - flags (2 bytes): 0xABCB LE -> \xCB\xAB (offset 6..7)
    # - image_offset (4 bytes): points to 12 LE -> \x0C\x00\x00\x00 (offset 8..11)
    # Image (starts at offset 12):
    # - width (2 bytes): 2 LE -> \x02\x00 (offset 12..13)
    # - height (2 bytes): 2 LE -> \x02\x00 (offset 14..15)
    # - pixels (4 bytes): \x01\x02\x03\x04 (offset 16..19)
    assert len(data) == 20
    assert data[0:4] == b"\x59\x4E\x49\x42"
    assert data[4:6] == b"\x01\x00"
    assert data[6:8] == b"\xCB\xAB"
    assert data[8:12] == b"\x0C\x00\x00\x00"  # Auto-calculated offset: 12
    assert data[12:14] == b"\x02\x00"
    assert data[14:16] == b"\x02\x00"
    assert data[16:20] == b"\x01\x02\x03\x04"


def test_write_struct_with_raw_offset_integer():
    """Test writing Header with a pre-computed integer offset instead of a struct instance."""
    flags = Flags(enable=0, mode=0, priority=0, reserved=0)
    hdr = Header(magic=0x11223344, version=2, flags=flags, image_offset=0x00000080)

    data = hdr.to_bytes()
    assert len(data) == 12
    assert data[8:12] == b"\x80\x00\x00\x00"


def test_write_struct_to_file_stream(tmp_path: Path):
    """Test writing binary structs into a file stream with BinaryWriter.to_file."""
    file_path = tmp_path / "stream_struct.bin"
    pkt1 = Packet(id=1, count=4, payload=b"ABCD")
    pkt2 = Packet(id=2, count=4, payload=b"EFGH")

    with BinaryWriter.to_file(file_path) as writer:
        writer.write_struct(pkt1).write_struct(pkt2)

    content = file_path.read_bytes()
    assert len(content) == 67 * 2
    assert content[:2] == b"\x00\x01"
    assert content[67:69] == b"\x00\x02"


def test_write_struct_invalid_type():
    """Test that writing a non-binary_struct object raises TypeError."""
    writer = BinaryWriter()
    with pytest.raises(TypeError, match="not a binary_struct"):
        write_struct("plain_string")


def test_sizeof_primitives():
    """Test sizeof on primitive BinaryType classes."""
    assert sizeof(UInt8) == 1
    assert sizeof(UInt16) == 2
    assert sizeof(UInt32) == 4
    assert sizeof(UInt64) == 8
    assert binary_size(Float32) == 4
    assert binary_size(Float64) == 8


def test_sizeof_static_classes_and_instances():
    """Test Cls.binary_size, sizeof(Cls), instance.binary_size, len(instance)."""
    # Packet has UInt16(2) + UInt8(1) + FixedArray[UInt8, 64](64) = 67 bytes
    assert Packet.binary_size == 67
    assert sizeof(Packet) == 67

    pkt = Packet(id=1, count=10, payload=b"\x00" * 64)
    assert pkt.binary_size == 67
    assert sizeof(pkt) == 67
    assert len(pkt) == 67


def test_sizeof_with_sized_offset():
    """Test struct binary size with 2-byte sized offset."""
    @binary_struct
    class SubItem:
        val: UInt16

    @binary_struct
    class ContainerWith16BitOffset:
        magic: UInt32                    # 4 bytes
        sub_offset: Offset[SubItem, UInt16]  # 2 bytes

    assert ContainerWith16BitOffset.binary_size == 6
    assert sizeof(ContainerWith16BitOffset) == 6

    c = ContainerWith16BitOffset(magic=0x1234, sub_offset=SubItem(val=42))
    # Container itself is 6 bytes (sub_offset backpatched into 2 bytes placeholder)
    # len(c) is 6 bytes for the container + 2 bytes for the deferred sub_item target = 8 bytes
    assert len(c) == 8
    assert sizeof(c) == 8


def test_sizeof_with_alignment():
    """Test static size calculation with auto_align=True."""
    @binary_struct(auto_align=True)
    class AlignedStruct:
        a: UInt8   # 1 byte + 3 bytes padding
        b: UInt32  # 4 bytes
        # Total = 8 bytes

    assert AlignedStruct.binary_size == 8
    assert sizeof(AlignedStruct) == 8


def test_sizeof_variable_length():
    """Test that static class size raises ValueError for variable-length fields, but instance succeeds."""
    @binary_struct
    class VarStruct:
        data: Array[UInt8]

    with pytest.raises(ValueError, match="Cannot determine static binary size"):
        _ = VarStruct.binary_size

    with pytest.raises(ValueError, match="Cannot determine static binary size"):
        _ = sizeof(VarStruct)

    inst = VarStruct(data=b"hello")
    assert len(inst) == 5
    assert inst.binary_size == 5
    assert sizeof(inst) == 5


def test_offsetof_basic_and_alignment():
    """Test offsetof and Cls.offsetof with alignment padding."""
    @binary_struct(auto_align=True)
    class Sample:
        a: UInt8   # offset 0, size 1, 1 byte padding
        b: UInt16  # offset 2, size 2
        c: UInt32  # offset 4, size 4
        d: UInt8   # offset 8, size 1

    # Using standalone offsetof function
    assert offsetof(Sample, "a") == 0
    assert offsetof(Sample, "b") == 2
    assert offsetof(Sample, "c") == 4
    assert offsetof(Sample, "d") == 8

    # Using class method Sample.offsetof
    assert Sample.offsetof("a") == 0
    assert Sample.offsetof("b") == 2
    assert Sample.offsetof("c") == 4
    assert Sample.offsetof("d") == 8

    # Using instance method
    s = Sample(a=1, b=2, c=3, d=4)
    assert s.offsetof("a") == 0
    assert s.offsetof("b") == 2
    assert s.offsetof("c") == 4
    assert s.offsetof("d") == 8


def test_offsetof_manual_padding():
    """Test offsetof with explicit padding field matching user example."""
    @binary_struct
    class PaddedStruct:
        a: UInt8
        _pad: UInt8
        b: UInt8

    assert PaddedStruct.offsetof("a") == 0
    assert PaddedStruct.offsetof("_pad") == 1
    assert PaddedStruct.offsetof("b") == 2


def test_offsetof_nested_and_dot_notation():
    """Test offsetof with nested structs and dot notation access."""
    @binary_struct
    class Inner:
        x: UInt16  # 2 bytes
        y: UInt8   # 1 byte

    @binary_struct
    class Outer:
        tag: UInt8    # offset 0, 1 byte
        inner: Inner  # offset 1, 3 bytes
        extra: UInt8  # offset 4, 1 byte

    assert Outer.offsetof("tag") == 0
    assert Outer.offsetof("inner") == 1
    assert Outer.offsetof("inner.x") == 1
    assert Outer.offsetof("inner.y") == 3
    assert Outer.offsetof("extra") == 4

    out = Outer(tag=0xFF, inner=Inner(x=10, y=20), extra=0)
    assert out.offsetof("inner.y") == 3


def test_offsetof_bitfield():
    """Test offsetof and bit_offsetof on bitfield structs."""
    @binary_struct(bits=8)
    class TestBits:
        flag_a: 1
        flag_b: 3
        flag_c: 4

    # Bitfields all reside at byte offset 0
    assert TestBits.offsetof("flag_a") == 0
    assert TestBits.offsetof("flag_b") == 0
    assert TestBits.offsetof("flag_c") == 0

    # bit_offsetof returns (byte_offset, bit_start)
    assert bit_offsetof(TestBits, "flag_a") == (0, 0)
    assert bit_offsetof(TestBits, "flag_b") == (0, 1)
    assert bit_offsetof(TestBits, "flag_c") == (0, 4)
    assert TestBits.bit_offsetof("flag_b") == (0, 1)


def test_offsetof_errors():
    """Test error cases for offsetof."""
    @binary_struct
    class Simple:
        val: UInt8

    with pytest.raises(AttributeError, match="Field 'nonexistent' not found"):
        Simple.offsetof("nonexistent")

    class NotABinaryStruct:
        pass

    with pytest.raises(TypeError, match="not a @binary_struct"):
        offsetof(NotABinaryStruct, "val")


def test_offsetof_dynamic_fields():
    """Test offsetof on structs with variable-length fields."""
    @binary_struct
    class PacketWithArray:
        header_id: UInt16
        payload: Array[UInt8]
        checksum: UInt16

    # For class, preceding dynamic field makes static offset of checksum impossible
    assert PacketWithArray.offsetof("header_id") == 0
    with pytest.raises(ValueError, match="Cannot determine static binary size"):
        PacketWithArray.offsetof("checksum")

    # For instance, offsetof evaluates actual payload length
    pkt = PacketWithArray(header_id=1, payload=b"hello", checksum=0x1234)
    assert pkt.offsetof("header_id") == 0
    assert pkt.offsetof("checksum") == 7


def test_bytes_and_string_types_in_binary_struct():
    """Test Bytes[N], FixedString[N], CString, and PrefixedString in @binary_struct."""
    from binary_master import Bytes, FixedString, CString, PrefixedString, read_struct

    @binary_struct(endian="little")
    class UserProfile:
        magic: FixedString[4]          # 4-byte fixed string
        uuid: Bytes[8]                 # 8 raw bytes
        name: FixedString[16]         # 16-byte padded string
        description: CString           # Null-terminated
        auth_token: PrefixedString[2]  # Pascal string with 2-byte prefix

    # 1. Static size checks
    assert sizeof(Bytes[8]) == 8
    assert sizeof(FixedString[16]) == 16
    assert UserProfile.offsetof("magic") == 0
    assert UserProfile.offsetof("uuid") == 4
    assert UserProfile.offsetof("name") == 12

    # 2. Serialization
    user = UserProfile(
        magic="USER",
        uuid=b"\x01\x02\x03\x04\x05\x06\x07\x08",
        name="Alice",
        description="Software Engineer",
        auth_token="secret_token_123",
    )
    raw = user.to_bytes()

    # Verify binary contents
    assert raw[:4] == b"USER"
    assert raw[4:12] == b"\x01\x02\x03\x04\x05\x06\x07\x08"
    assert raw[12:28] == b"Alice" + b"\x00" * 11
    assert b"Software Engineer\x00" in raw

    # 3. Deserialization
    restored = read_struct(UserProfile, raw)
    assert restored.magic == "USER"
    assert isinstance(restored.uuid, bytes)
    assert restored.uuid == b"\x01\x02\x03\x04\x05\x06\x07\x08"
    assert restored.name == "Alice"
    assert restored.description == "Software Engineer"
    assert restored.auth_token == "secret_token_123"

    # 4. Instance size
    expected_size = 4 + 8 + 16 + (len("Software Engineer") + 1) + (2 + len("secret_token_123"))
    assert sizeof(user) == expected_size
    assert len(raw) == expected_size




