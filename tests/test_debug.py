"""Tests for dedicated binary debugging, annotated hexdumps, tabular dumps, and diffing."""

import json
import pytest
from binary_master import (
    BinaryWriter,
    BinaryReader,
    binary_struct,
    UInt8,
    UInt16,
    UInt32,
    FixedArray,
    hexdump,
    debug_dump,
    diff_dump,
    dump_table,
    dump_json,
    dump_dict,
)


@binary_struct(endian="little")
class PacketHeader:
    magic: UInt32
    seq: UInt16
    tag: UInt8


def test_hexdump_raw_bytes():
    """Test basic hexdump generation from raw bytes."""
    data = b"\x50\x4c\x41\x59\x12\x04\x32\x03\xaa\xbb\xcc\xdd\xee\xff\x00\x11\x22\x33"
    dump_str = hexdump(data)

    # Contains 16-byte offset headers
    assert "Offset" in dump_str
    assert "ASCII" in dump_str
    assert "00000000" in dump_str
    assert "00000010" in dump_str

    # Hex bytes present
    assert "50 4c 41 59" in dump_str
    assert "PLAY" in dump_str
    assert "Total: 18 bytes (`0x0012`)" in dump_str


def test_hexdump_custom_width_and_max_bytes():
    """Test hexdump width adjustments and truncation."""
    data = b"\x01" * 32
    dump_8 = hexdump(data, width=8, max_bytes=16)
    assert "00000000" in dump_8
    assert "00000008" in dump_8
    assert "16 bytes truncated" in dump_8


def test_hexdump_with_colors():
    """Test ANSI color codes in hexdump."""
    data = b"Hello, World!"
    dump_colored = hexdump(data, color=True)
    assert "\033[" in dump_colored


def test_annotated_hexdump_from_writer():
    """Test that writer.hexdump() and hexdump(writer) correlate byte offsets with fields."""
    writer = BinaryWriter(default_endian="little")
    writer.caption("Header Block")
    writer.write_uint32(0x59414C50, name="magic", desc="Magic identifier")
    writer.write_uint16(1042, name="player_id")
    writer.write_uint8(50, name="level")

    res = writer.hexdump()
    assert "00000000" in res
    assert "50 4c 41 59" in res
    assert "PLAY" in res
    assert "magic" in res
    assert "UInt32" in res
    assert "player_id" in res
    assert "level" in res
    assert "Total: 7 bytes (`0x0007`)" in res

    # Standalone function call matches
    assert hexdump(writer) == res


def test_reader_hexdump_with_cursor_tracking():
    """Test reader.hexdump() highlights cursor position and remaining bytes."""
    data = b"\x01\x02\x03\x04\x05\x06\x07\x08"
    reader = BinaryReader(data)

    # Initial state (cursor at 0)
    dump_start = reader.hexdump()
    assert "Cursor: 0x0000 (0/8)" in dump_start
    assert "Remaining: 8 bytes" in dump_start

    # Consume 4 bytes
    val = reader.read_uint32()
    assert reader.tell() == 4

    dump_mid = reader.hexdump()
    assert "Cursor: 0x0004 (4/8)" in dump_mid
    assert "Remaining: 4 bytes" in dump_mid
    assert "--> CURSOR @ 0x0004" in dump_mid

    # Ensure stream position was not altered by hexdump
    assert reader.tell() == 4
    val2 = reader.read_uint32()
    assert reader.tell() == 8
    assert "Remaining: 0 bytes" in reader.hexdump()


def test_dump_table():
    """Test monospace aligned table dump."""
    writer = BinaryWriter(default_endian="little")
    with writer.caption("Auth Header"):
        writer.write_uint32(0x12345678, name="token")
        writer.write_cstring("alice", name="username")

    tbl = dump_table(writer)
    assert "+--------+" in tbl
    assert "| Offset |" in tbl
    assert "Field Name" in tbl
    assert "Hex Bytes" in tbl
    assert "token" in tbl
    assert "UInt32" in tbl
    assert "username" in tbl
    assert "CString" in tbl
    assert "Auth Header" in tbl
    assert "Total: 10 bytes (0x000A) across 2 fields" in tbl

    # writer.dump(format="table") matches
    assert writer.dump(format="table") == tbl


def test_dump_json_and_dict():
    """Test structured dictionary and JSON export."""
    writer = BinaryWriter(default_endian="little")
    writer.write_uint16(0xCAFE, name="code")
    writer.write_uint8(1, name="active")

    records = dump_dict(writer)
    assert len(records) == 2
    assert records[0]["name"] == "code"
    assert records[0]["type"] == "UInt16"
    assert records[0]["offset"] == 0
    assert records[0]["size"] == 2
    assert records[0]["hex"] == "feca"

    assert records[1]["name"] == "active"
    assert records[1]["offset"] == 2
    assert records[1]["size"] == 1

    # Test JSON string
    json_str = dump_json(writer)
    parsed = json.loads(json_str)
    assert parsed == records

    # writer.dump(format="json") and writer.dump(format="dict")
    assert writer.dump(format="dict") == records
    assert json.loads(writer.dump(format="json")) == records


def test_diff_dump_identical():
    """Test diffing identical buffers."""
    b = b"\x01\x02\x03\x04"
    diff_res = diff_dump(b, b)
    assert "Identical" in diff_res
    assert "match completely (4 bytes)" in diff_res


def test_diff_dump_same_size_differences():
    """Test diffing buffers of the same size with field annotations."""
    w1 = BinaryWriter()
    w1.write_uint32(0x11111111, name="magic")
    w1.write_uint16(100, name="counter")

    w2 = BinaryWriter()
    w2.write_uint32(0x11111111, name="magic")
    w2.write_uint16(200, name="counter")  # Differs here!

    res = w1.diff(w2, name_left="Expected", name_right="Actual")
    assert "Binary Diff: Expected vs Actual" in res
    assert "Differing byte count: 1 bytes in 1 range(s)" in res
    assert "0x0004" in res
    assert "counter (UInt16)" in res


def test_diff_dump_length_difference():
    """Test diffing buffers with unequal lengths."""
    b1 = b"\xAA\xBB\xCC\xDD"
    b2 = b"\xAA\xBB\xCC\xDD\xEE\xFF"

    res = diff_dump(b1, b2, name_left="Short", name_right="Long")
    assert "Length difference: +2 bytes" in res
    assert "Extra in Long" in res

    # Inverse
    res_inv = diff_dump(b2, b1, name_left="Long", name_right="Short")
    assert "Length difference: -2 bytes" in res_inv
    assert "Missing in Short" in res_inv


def test_debug_dump_struct_instance():
    """Test passing @binary_struct instance directly to hexdump and debug_dump."""
    pkt = PacketHeader(magic=0x54534554, seq=7, tag=0xFF)
    dump_out = hexdump(pkt)
    assert "54 45 53 54" in dump_out
    assert "TEST" in dump_out
    assert "magic" in dump_out
    assert "seq" in dump_out
    assert "tag" in dump_out

    tbl_out = dump_table(pkt)
    assert "PacketHeader" in tbl_out or "magic" in tbl_out


def test_invalid_target_and_format():
    """Test error handling on invalid target or unsupported format."""
    with pytest.raises(TypeError, match="Unsupported target"):
        hexdump(12345)

    with pytest.raises(ValueError, match="Unsupported format 'invalid'"):
        debug_dump(b"\x00", format="invalid")
