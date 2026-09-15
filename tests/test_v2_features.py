"""Tests for v2 features:
1. LengthOf and CountOf (automatic calculation and linked deserialization)
2. total_size and pad_to (fixed struct size and writer padding)
3. Range validation (Range[T, min, max] with RangeValidationError)
4. Interactive HTML documentation (to_html, write_html, generate_html)
"""

import pytest
from pathlib import Path
from binary_master import (
    binary_struct,
    UInt8,
    UInt16,
    UInt32,
    Int32,
    Float32,
    Bytes,
    Array,
    FixedArray,
    CString,
    BinaryWriter,
    BinaryReader,
    sizeof,
    Range,
    RangeValidationError,
    LengthOf,
    CountOf,
    TotalSizeExceededError,
    generate_html,
    write_html,
    Builder,
)


# ==========================================
# 1. Tests for LengthOf & CountOf
# ==========================================


def test_length_of_bytes_serialization():
    @binary_struct
    class Packet:
        payload_len: LengthOf[UInt16, "payload"]
        payload: Bytes

    # Leave payload_len as 0, should auto-calculate byte length (5 bytes)
    p = Packet(payload=b"hello")
    data = p.to_bytes()
    # payload_len is 2 bytes (uint16: 5), payload is 5 bytes
    assert data == b"\x05\x00hello"
    assert p.payload_len == 5


def test_length_of_bytes_deserialization():
    @binary_struct
    class Packet:
        payload_len: LengthOf[UInt16, "payload"]
        payload: Bytes
        footer: UInt8

    # When reading, payload_len (5) dictates payload reads exactly 5 bytes, then footer reads UInt8
    raw = b"\x05\x00hello\xFFextra_ignored"
    p = Packet.from_bytes(raw[:8])
    assert p.payload_len == 5
    assert p.payload == b"hello"
    assert p.footer == 0xFF


def test_count_of_array_serialization():
    @binary_struct
    class NumberList:
        count: CountOf[UInt32, "items"]
        items: Array[UInt16]

    nl = NumberList(items=[10, 20, 30])
    data = nl.to_bytes()
    # count: 3 (UInt32: 03 00 00 00), items: 3 * UInt16 (0A 00, 14 00, 1E 00)
    assert data == b"\x03\x00\x00\x00\x0a\x00\x14\x00\x1e\x00"
    assert nl.count == 3


def test_count_of_array_deserialization():
    @binary_struct
    class Item:
        x: UInt8
        y: UInt8

    @binary_struct
    class ItemContainer:
        item_count: CountOf[UInt8, "items"]
        items: Array[Item]
        checksum: UInt16

    # 2 items followed by checksum
    raw = b"\x02\x01\x02\x03\x04\x34\x12"
    container = ItemContainer.from_bytes(raw)
    assert container.item_count == 2
    assert len(container.items) == 2
    assert container.items[0].x == 1
    assert container.items[0].y == 2
    assert container.items[1].x == 3
    assert container.items[1].y == 4
    assert container.checksum == 0x1234


def test_length_of_cstring():
    @binary_struct
    class MessagePacket:
        msg_len: LengthOf[UInt8, "msg"]
        msg: CString

    # CString "Hi" byte length is 2 bytes (without null terminator)
    pkt = MessagePacket(msg="Hi")
    data = pkt.to_bytes()
    assert data == b"\x02Hi\x00"
    assert pkt.msg_len == 2


# ==========================================
# 2. Tests for total_size and pad_to
# ==========================================


def test_binary_writer_pad_to():
    w = BinaryWriter()
    w.write_uint8(0xAA)
    w.write_uint8(0xBB)
    assert w.tell() == 2
    w.pad_to(8, pad_byte=b"\x00")
    assert w.tell() == 8
    assert w.to_bytes() == b"\xaa\xbb\x00\x00\x00\x00\x00\x00"


def test_binary_writer_pad_to_custom_byte():
    w = BinaryWriter()
    w.write_uint16(0x1234)
    w.pad_to(5, pad_byte=b"\xFF")
    assert w.to_bytes() == b"\x34\x12\xff\xff\xff"


def test_binary_writer_pad_to_error_when_exceeded():
    w = BinaryWriter()
    w.write_uint32(0x12345678)
    with pytest.raises(ValueError, match="already exceeds pad_to target"):
        w.pad_to(2)


def test_struct_total_size_and_padding():
    @binary_struct(total_size=16, pad_byte=b"\xCC")
    class PaddedHeader:
        magic: UInt16
        version: UInt8

    # magic (2B) + version (1B) = 3B, padded to 16B with 0xCC
    h = PaddedHeader(magic=0x4242, version=1)
    data = h.to_bytes()
    assert len(data) == 16
    assert data[:3] == b"\x42\x42\x01"
    assert data[3:] == b"\xcc" * 13
    assert sizeof(PaddedHeader) == 16
    assert sizeof(h) == 16


def test_struct_total_size_deserialization():
    @binary_struct(total_size=12, pad_byte=b"\x00")
    class SectorData:
        id: UInt32
        val: UInt32

    raw = b"\x01\x00\x00\x00\x02\x00\x00\x00\x00\x00\x00\x00\x99"
    # Read from raw (first 12 bytes should be consumed)
    r = BinaryReader(raw)
    sec = r.read_struct(SectorData)
    assert sec.id == 1
    assert sec.val == 2
    # Reader should now be at offset 12
    assert r.tell() == 12
    # Next byte should be 0x99
    assert r.read_uint8() == 0x99


def test_struct_total_size_exceeded_error():
    @binary_struct(total_size=4)
    class SmallStruct:
        a: UInt32
        b: UInt32

    s = SmallStruct(a=1, b=2)
    with pytest.raises(TotalSizeExceededError, match="exceeds declared total_size"):
        s.to_bytes()


# ==========================================
# 3. Tests for Range Validation
# ==========================================


def test_range_validation_success():
    @binary_struct
    class SensorReading:
        temperature: Range[Int32, -40, 125]
        humidity: Range[UInt8, 0, 100]

    # Valid values
    s = SensorReading(temperature=25, humidity=60)
    data = s.to_bytes()
    assert len(data) == 5

    # Edge cases (min and max boundary)
    s_min = SensorReading(temperature=-40, humidity=0)
    assert len(s_min.to_bytes()) == 5

    s_max = SensorReading(temperature=125, humidity=100)
    assert len(s_max.to_bytes()) == 5


def test_range_validation_serialization_failure():
    @binary_struct
    class SensorReading:
        temperature: Range[Int32, -40, 125]
        humidity: Range[UInt8, 0, 100]

    # Out of range on temperature (too high)
    s1 = SensorReading(temperature=150, humidity=50)
    with pytest.raises(RangeValidationError, match="is out of valid range"):
        s1.to_bytes()

    # Out of range on temperature (too low)
    s2 = SensorReading(temperature=-50, humidity=50)
    with pytest.raises(RangeValidationError, match="is out of valid range"):
        s2.to_bytes()

    # Out of range on humidity
    s3 = SensorReading(temperature=20, humidity=101)
    with pytest.raises(RangeValidationError, match="is out of valid range"):
        s3.to_bytes()


def test_range_validation_deserialization_failure():
    @binary_struct
    class ScoreRecord:
        score: Range[UInt16, 0, 1000]

    # 1500 is 0x05DC -> out of range
    raw = b"\xdc\x05"
    with pytest.raises(RangeValidationError, match="is out of valid range"):
        ScoreRecord.from_bytes(raw)


# ==========================================
# 4. Tests for Interactive HTML Manual
# ==========================================


def test_generate_html_from_struct_class():
    @binary_struct
    class DeviceConfig:
        """Device hardware configuration payload."""
        device_id: UInt32
        baud_rate: UInt32
        flags: UInt8

    html = DeviceConfig.to_html(title="Device Config Spec")
    assert "<!DOCTYPE html>" in html
    assert "Device Config Spec" in html
    assert "device_id" in html
    assert "baud_rate" in html
    assert "flags" in html
    assert "Interactive Hex Inspector" in html
    assert 'class="hex-byte"' in html
    assert "mermaid" in html


def test_generate_html_from_struct_instance():
    @binary_struct
    class PlayerState:
        player_id: UInt16
        hp: UInt8
        mp: UInt8

    player = PlayerState(player_id=1001, hp=95, mp=40)
    html = player.to_html()
    assert "<!DOCTYPE html>" in html
    assert "player_id" in html
    assert "95" in html  # Value displayed
    assert "Interactive Hex Inspector" in html


def test_generate_html_from_writer(tmp_path: Path):
    w = BinaryWriter()
    w.write_uint16(0x1234, name="header_id")
    w.write_cstring("test_name", name="username")
    w.write_uint32(0xCAFEBABE, name="magic")

    html = w.to_html(title="Protocol Spec")
    assert "<!DOCTYPE html>" in html
    assert "header_id" in html
    assert "username" in html
    assert "magic" in html
    assert "hex-viewer" in html

    # Test write_html to file
    out_file = tmp_path / "manual.html"
    w.write_html(out_file, title="Protocol Spec")
    assert out_file.exists()
    assert out_file.read_text(encoding="utf-8") == html


def test_generate_html_from_builder():
    @binary_struct
    class ChunkHeader:
        signature: UInt32
        chunk_len: UInt32

    b = Builder(title="PNG Builder Manual", default_endian="big")
    b.add_struct(ChunkHeader, name="ChunkHeader", desc="PNG chunk header")

    html = b.to_html(title="PNG Builder Manual")
    assert "<!DOCTYPE html>" in html
    assert "PNG Builder Manual" in html
    assert "ChunkHeader" in html



# ==========================================
# 5. Multi-language Code Gen with v2 Features
# ==========================================


def test_code_gen_with_v2_features():
    @binary_struct(total_size=16)
    class V2Protocol:
        count: CountOf[UInt8, "items"]
        speed: Range[UInt16, 0, 500]
        items: FixedArray[UInt8, 4]

    c_code = V2Protocol.to_c()
    assert "Count of 'items'" in c_code
    assert "Range: [0, 500]" in c_code
    assert "_padding" in c_code  # Struct padded to total_size 16

    cpp_code = V2Protocol.to_cpp()
    assert "Count of 'items'" in cpp_code
    assert "Range: [0, 500]" in cpp_code
    assert "_padding" in cpp_code

    rust_code = V2Protocol.to_rust()
    assert "Count of 'items'" in rust_code
    assert "Range: [0, 500]" in rust_code
    assert "_padding" in rust_code

    cs_code = V2Protocol.to_csharp()
    assert "Count of 'items'" in cs_code
    assert "Range: [0, 500]" in cs_code
    assert "_Padding" in cs_code

    go_code = V2Protocol.to_go()
    assert "Count of 'items'" in go_code
    assert "Range: [0, 500]" in go_code
    assert "Padding" in go_code
