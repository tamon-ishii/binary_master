"""Unit tests for struct docstring in manual, auto padding/align, and offset tables."""

import pytest
import struct

from binary_master import (
    BinaryWriter,
    Endian,
    UInt8,
    UInt16,
    UInt32,
    UInt64,
    Bits,
    Offset,
    OffsetTable,
    OffsetTableHandle,
    binary_struct,
    write_struct,
)


# ==========================================================
# 1. Docstring Reflection Tests
# ==========================================================

@binary_struct(bits=16)
class BitfieldHeader:
    """Header control flags and mode bitfield."""
    enable: Bits[1]
    mode: Bits[3]
    reserved: Bits[12]


@binary_struct(endian="big")
class DocumentedPacket:
    """Documented network packet protocol definition."""
    magic: UInt32
    flags: BitfieldHeader
    length: UInt16


def test_struct_docstring_in_manual():
    """Verify that docstrings on structs and bitfields appear in the manual."""
    pkt = DocumentedPacket(
        magic=0x12345678,
        flags=BitfieldHeader(enable=1, mode=2, reserved=0),
        length=100,
    )
    writer = BinaryWriter()
    writer.write_struct(pkt)
    md = writer.write_manual(title="Documented Protocol Manual")

    # Struct docstring should be in ## Overview
    assert "## Overview" in md
    assert "Documented network packet protocol definition." in md

    # Bitfield docstring should be in ## Bitfield Details
    assert "## Bitfield Details" in md
    assert "Header control flags and mode bitfield." in md


def test_caption_description_in_manual():
    """Verify that caption description appears in the manual section."""
    writer = BinaryWriter()
    writer.caption("Header Section", "This section contains protocol metadata.")
    writer.write_uint32(0xCAFEBABE, name="magic")
    writer.caption("Body Section", "Payload contents follow.")
    writer.write_uint16(42, name="data")

    md = writer.write_manual()
    assert "### Header Section" in md
    assert "This section contains protocol metadata." in md
    assert "### Body Section" in md
    assert "Payload contents follow." in md


# ==========================================================
# 2. Auto-Padding & Alignment Tests
# ==========================================================

@binary_struct(endian="little")
class PackedStruct:
    a: UInt8
    b: UInt32


@binary_struct(endian="little", auto_align=True)
class AutoAlignedStruct:
    a: UInt8
    b: UInt32


@binary_struct(endian="little", auto_align=True)
class AutoAlignedWithTrailingPadding:
    a: UInt32
    b: UInt8  # Needs 3 bytes of trailing padding to align struct size to 4 bytes


@binary_struct(endian="little", align=8)
class ExplicitAlign8Struct:
    a: UInt8
    b: UInt16


def test_packed_struct_has_no_padding():
    """Default @binary_struct is packed without padding (pack 1)."""
    s = PackedStruct(a=0xAA, b=0x12345678)
    data = s.to_bytes()
    # 1 byte + 4 bytes = 5 bytes
    assert len(data) == 5
    assert data == b"\xaa\x78\x56\x34\x12"


def test_auto_aligned_struct_inserts_member_padding():
    """auto_align=True inserts padding before members that require alignment."""
    s = AutoAlignedStruct(a=0xAA, b=0x12345678)
    writer = BinaryWriter()
    writer.write_struct(s)
    data = writer.to_bytes()

    # 1 byte a + 3 bytes padding + 4 bytes b = 8 bytes
    assert len(data) == 8
    assert data == b"\xaa\x00\x00\x00\x78\x56\x34\x12"

    entries = writer.entries
    names = [e.name for e in entries]
    assert "padding" in names
    pad_entry = [e for e in entries if e.name == "padding"][0]
    assert pad_entry.offset == 1
    assert pad_entry.size == 3


def test_auto_aligned_struct_trailing_padding():
    """auto_align=True pads total struct size to multiple of max field alignment."""
    s = AutoAlignedWithTrailingPadding(a=0x11223344, b=0x55)
    data = s.to_bytes()
    # 4 bytes a + 1 byte b + 3 bytes alignment_pad = 8 bytes
    assert len(data) == 8
    assert data == b"\x44\x33\x22\x11\x55\x00\x00\x00"


def test_explicit_align_struct():
    """align=8 aligns fields and rounds up struct size to 8 bytes."""
    s = ExplicitAlign8Struct(a=0x01, b=0x0203)
    data = s.to_bytes()
    # 1 byte a + 1 byte padding (for uint16) + 2 bytes b + 4 bytes trailing = 8 bytes
    assert len(data) == 8
    assert data == b"\x01\x00\x03\x02\x00\x00\x00\x00"


# ==========================================================
# 3. Offset Table Tests
# ==========================================================

def test_offset_table_writer_basic():
    """Test writer.write_offset_table creating slots and updating them."""
    writer = BinaryWriter(default_endian=Endian.LITTLE)
    # Write an offset table with 3 entries of 4 bytes each
    table = writer.write_offset_table(count=3, offset_size=4, name="section_offsets", desc="Table of sections")
    assert isinstance(table, OffsetTableHandle)
    assert len(table) == 3
    assert table.count == 3
    assert table.offset_size == 4

    # Current offset should be 12 (3 * 4 bytes reserved)
    assert writer.tell() == 12

    # Write target 0
    pos0 = writer.tell()
    table.write_offset(0)
    writer.write_cstring("Section A")

    # Write target 1
    pos1 = writer.tell()
    table[1] = pos1
    writer.write_cstring("Section B")

    # Write target 2
    pos2 = writer.tell()
    table.set_offset(2, pos2)
    writer.write_cstring("Section C")

    data = writer.to_bytes()
    assert len(data) >= 12

    # Verify the table in the binary contains the exact offsets
    off0, off1, off2 = struct.unpack("<III", data[:12])
    assert off0 == pos0
    assert off1 == pos1
    assert off2 == pos2
    assert off0 == 12


def test_offset_table_write_target():
    """Test write_target helper method on OffsetTableHandle."""
    writer = BinaryWriter(default_endian=Endian.LITTLE)
    table = writer.write_offset_table(count=2, offset_size=4, name="items")

    @binary_struct(endian="little")
    class Item:
        val: UInt16

    table.write_target(0, Item(val=0x1111))
    table.write_target(1, Item(val=0x2222))

    data = writer.to_bytes()
    # table: 8 bytes (2 * 4). item0: 2 bytes at offset 8. item1: 2 bytes at offset 10.
    assert len(data) == 12
    off0, off1 = struct.unpack("<II", data[:8])
    assert off0 == 8
    assert off1 == 10
    v0, v1 = struct.unpack("<HH", data[8:])
    assert v0 == 0x1111
    assert v1 == 0x2222


def test_offset_table_manual_reflection():
    """Verify offset table and target pointers are reflected in Markdown manual."""
    writer = BinaryWriter(default_endian=Endian.LITTLE)
    table = writer.write_offset_table(count=2, offset_size=4, name="offsets", desc="Table of file offsets")

    pos0 = writer.tell()
    table.set_offset(0, pos0)
    writer.write_uint32(0xDEADBEEF, name="block_a", desc="Data block A")

    pos1 = writer.tell()
    table.set_offset(1, pos1)
    writer.write_uint32(0xFEEDFACE, name="block_b", desc="Data block B")

    md = writer.write_manual(title="Offset Table Specification")

    # Layout Table should contain target markers
    assert f"`-> 0x{pos0:04X}`" in md
    assert f"`-> 0x{pos1:04X}`" in md

    # Mermaid diagram should contain arrow links for the offsets
    assert f'-.->|"offset: 0x{pos0:04X}"|' in md
    assert f'-.->|"offset: 0x{pos1:04X}"|' in md


@binary_struct(endian="little")
class DataChunk:
    code: UInt32


@binary_struct(endian="little")
class ContainerWithOffsetTable:
    magic: UInt32
    num_chunks: UInt16
    chunk_offsets: OffsetTable[2, UInt32]


def test_offset_table_in_binary_struct():
    """Test using OffsetTable inside @binary_struct."""
    c1 = DataChunk(code=0x11111111)
    c2 = DataChunk(code=0x22222222)
    container = ContainerWithOffsetTable(
        magic=0x544F4254,
        num_chunks=2,
        chunk_offsets=[c1, c2],
    )
    writer = BinaryWriter()
    writer.write_struct(container)
    data = writer.to_bytes()

    # Container: magic(4) + num_chunks(2) + chunk_offsets(2*4=8) = 14 bytes
    # c1 starts at 14 (4 bytes), c2 starts at 18 (4 bytes)
    # Total = 22 bytes
    assert len(data) == 22
    magic, num_chunks = struct.unpack("<IH", data[:6])
    assert magic == 0x544F4254
    assert num_chunks == 2
    off0, off1 = struct.unpack("<II", data[6:14])
    assert off0 == 14
    assert off1 == 18

    # Check that manual reflects offsets
    md = writer.write_manual()
    assert f"`-> 0x{off0:04X}`" in md
    assert f"`-> 0x{off1:04X}`" in md


def test_offset_table_base_offset_procedural():
    """Test write_offset_table with custom base_offset."""
    writer = BinaryWriter(default_endian=Endian.LITTLE)
    # Write 32 bytes of header
    writer.write_bytes(b"\xAA" * 32, name="header", desc="Fixed header")
    base_pos = writer.tell()  # 32

    # Offset table starting at offset 32, with base_offset=32
    table = writer.write_offset_table(count=2, offset_size=4, base_offset=base_pos, name="rel_offsets")
    assert table.base_offset == 32

    # Table takes 8 bytes (offset 32..40). Targets will be at 40 and 44.
    table.write_target(0, DataChunk(code=0xAAAA1111))
    table.write_target(1, DataChunk(code=0xBBBB2222))

    assert table.get_target_offset(0) == 40
    assert table.get_stored_offset(0) == 8  # 40 - 32
    assert table.get_target_offset(1) == 44
    assert table.get_stored_offset(1) == 12  # 44 - 32

    data = writer.to_bytes()
    assert len(data) == 32 + 8 + 4 + 4  # 48 bytes
    stored_off0, stored_off1 = struct.unpack("<II", data[32:40])
    assert stored_off0 == 8
    assert stored_off1 == 12

    # Manual should show stored value 8 & 12, but target pointing to absolute 40 & 44
    md = writer.write_manual(include_values=True)
    assert "`-> 0x0028`" in md  # 40 in hex
    assert "`-> 0x002C`" in md  # 44 in hex


def test_offset_table_base_offset_validation():
    """Test validation errors for invalid base_offset or target < base."""
    writer = BinaryWriter()
    with pytest.raises(ValueError, match="base_offset must be non-negative"):
        writer.write_offset_table(count=1, base_offset=-5)

    table = writer.write_offset_table(count=1, base_offset=50)
    with pytest.raises(ValueError, match="is negative"):
        table.set_offset(0, 30)  # 30 - 50 < 0


@binary_struct(endian="little")
class ContainerRelativeTable:
    magic: UInt32
    num_chunks: UInt16
    chunk_offsets: OffsetTable[2, UInt32, 14]  # Base offset 14


def test_offset_table_base_offset_declarative():
    """Test OffsetTable with base_offset in @binary_struct."""
    c1 = DataChunk(code=0x11111111)
    c2 = DataChunk(code=0x22222222)
    container = ContainerRelativeTable(
        magic=0x544F4254,
        num_chunks=2,
        chunk_offsets=[c1, c2],
    )
    writer = BinaryWriter()
    writer.write_struct(container)
    data = writer.to_bytes()

    # Container size: 4 + 2 + 8 = 14 bytes.
    # Targets start at 14 and 18.
    # Stored offsets should be 14 - 14 = 0 and 18 - 14 = 4.
    off0, off1 = struct.unpack("<II", data[6:14])
    assert off0 == 0
    assert off1 == 4


@binary_struct(endian="little")
class TargetPayload:
    val: UInt16


@binary_struct(endian="little")
class SizedOffsetContainer:
    off_16: Offset[TargetPayload, UInt16]
    off_int_2: Offset[TargetPayload, 2]
    off_8: Offset[TargetPayload, UInt8]
    off_64: Offset[TargetPayload, UInt64]


def test_sized_offset_serialization_and_deserialization():
    """Test declaring 1, 2, 4, 8-byte Offset fields."""
    p1 = TargetPayload(val=0x1111)
    p2 = TargetPayload(val=0x2222)
    p3 = TargetPayload(val=0x3333)
    p4 = TargetPayload(val=0x4444)

    c = SizedOffsetContainer(
        off_16=p1,
        off_int_2=p2,
        off_8=p3,
        off_64=p4,
    )
    raw = c.to_bytes()

    # Field sizes:
    # off_16: 2 bytes (offset 0..2)
    # off_int_2: 2 bytes (offset 2..4)
    # off_8: 1 byte (offset 4..5)
    # off_64: 8 bytes (offset 5..13)
    # Total header size: 13 bytes
    # p1 at 13 (2 bytes), p2 at 15 (2 bytes), p3 at 17 (2 bytes), p4 at 19 (2 bytes)
    # Total raw size: 21 bytes
    assert len(raw) == 2 + 2 + 1 + 8 + 2 * 4

    # Verify binary offsets in header
    o16 = struct.unpack("<H", raw[0:2])[0]
    o_int2 = struct.unpack("<H", raw[2:4])[0]
    o8 = struct.unpack("<B", raw[4:5])[0]
    o64 = struct.unpack("<Q", raw[5:13])[0]

    assert o16 == 13
    assert o_int2 == 15
    assert o8 == 17
    assert o64 == 19

    # Deserialization round-trip
    parsed = SizedOffsetContainer.from_bytes(raw)
    assert isinstance(parsed.off_16, TargetPayload)
    assert parsed.off_16.val == 0x1111
    assert isinstance(parsed.off_int_2, TargetPayload)
    assert parsed.off_int_2.val == 0x2222
    assert isinstance(parsed.off_8, TargetPayload)
    assert parsed.off_8.val == 0x3333
    assert isinstance(parsed.off_64, TargetPayload)
    assert parsed.off_64.val == 0x4444


@binary_struct(endian="little")
class RelativeSizedOffsetContainer:
    header_pad: UInt16
    off_16_rel: Offset[TargetPayload, UInt16, 2]  # base_offset = 2


def test_sized_offset_with_base_offset():
    """Test sized Offset with non-zero base_offset."""
    p = TargetPayload(val=0x5555)
    c = RelativeSizedOffsetContainer(header_pad=0xAAAA, off_16_rel=p)
    raw = c.to_bytes()

    # header_pad: 2 bytes (0..2)
    # off_16_rel: 2 bytes (2..4)
    # p starts at 4.
    # Stored offset: 4 - 2 = 2.
    stored = struct.unpack("<H", raw[2:4])[0]
    assert stored == 2

    # Deserialization resolves at 2 + 2 = 4
    parsed = RelativeSizedOffsetContainer.from_bytes(raw)
    assert isinstance(parsed.off_16_rel, TargetPayload)
    assert parsed.off_16_rel.val == 0x5555


