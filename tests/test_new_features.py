"""Tests for the 8 new features added to binary-master:
1. CRC / Checksum calculation & validation
2. Enum & BinaryEnum support
3. Magic & Constant constraints
4. JSON / Dict serialization interop
5. Huge file streaming (iter_struct & mmap)
6. Variable-length integers (LEB128 VarInt / VarUInt)
7. Arbitrary bitstream reading & writing
8. CLI binary inspector, diff, spec & export
"""

import enum
import os
import tempfile

import pytest

from binary_master import (
    CRC16,
    CRC32,
    Adler32,
    BinaryEnum,
    BinaryReader,
    BinaryWriter,
    Bytes,
    Checksum8,
    Checksum16,
    ChecksumMismatchError,
    Constant,
    Endian,
    FixedString,
    Fletcher16,
    InvalidConstantError,
    InvalidEnumError,
    InvalidMagicError,
    Magic,
    UInt8,
    UInt16,
    UInt32,
    VarInt,
    VarUInt,
    binary_struct,
)
from binary_master.bitstream import BitReader, BitWriter
from binary_master.cli import main as cli_main

# ==========================================================
# 1. CRC / Checksum Tests
# ==========================================================

class TestChecksum:
    def test_writer_checksum_context(self):
        writer = BinaryWriter(default_endian=Endian.BIG)
        with writer.checksum("crc32") as chk:
            writer.write_bytes(b"Hello World")
            chk.write()  # Backpatches CRC32
        data = writer.to_bytes()
        assert len(data) == 11 + 4
        # Verify with reader
        reader = BinaryReader(data, default_endian=Endian.BIG)
        text = reader.read_bytes(11)
        assert text == b"Hello World"
        assert reader.verify_checksum("crc32") is True

    def test_struct_with_crc32(self):
        @binary_struct(endian="big")
        class PacketWithCRC:
            id: UInt16
            payload: Bytes[4]
            checksum: CRC32

        pkt = PacketWithCRC(id=1, payload=b"ABCD")
        raw = pkt.to_bytes()
        assert len(raw) == 2 + 4 + 4

        # Read back
        parsed = PacketWithCRC.from_bytes(raw)
        assert parsed.id == 1
        assert parsed.payload == b"ABCD"
        assert parsed.checksum != 0

        # Tamper payload and expect ChecksumMismatchError
        corrupted = bytearray(raw)
        corrupted[2] = ord(b"X")
        with pytest.raises(ChecksumMismatchError):
            PacketWithCRC.from_bytes(corrupted)

    def test_various_checksum_algorithms(self):
        for chk_type in (CRC16, Checksum8, Checksum16, Fletcher16, Adler32):
            @binary_struct(endian="little")
            class StructWithChk:
                val: UInt32
                chk: chk_type

            s = StructWithChk(val=0x12345678)
            raw = s.to_bytes()
            assert len(raw) == 4 + chk_type.size
            read_back = StructWithChk.from_bytes(raw)
            assert read_back.val == 0x12345678


# ==========================================================
# 2. Enum & BinaryEnum Tests
# ==========================================================

class TestEnum:
    class Status(BinaryEnum):
        OK = 0
        WARN = 1
        ERROR = 2

    class NativeEnum(enum.IntEnum):
        RED = 1
        GREEN = 2
        BLUE = 3

    def test_binary_enum_explicit_size(self):
        @binary_struct(endian="little")
        class Response:
            code: TestEnum.Status[UInt8]
            data: UInt16

        resp = Response(code=TestEnum.Status.WARN, data=100)
        raw = resp.to_bytes()
        assert len(raw) == 3
        assert raw[0] == 1

        parsed = Response.from_bytes(raw)
        assert parsed.code == TestEnum.Status.WARN
        assert isinstance(parsed.code, TestEnum.Status)
        assert parsed.data == 100

    def test_native_int_enum(self):
        @binary_struct(endian="big")
        class Pixel:
            color: TestEnum.NativeEnum
            alpha: UInt8

        px = Pixel(color=TestEnum.NativeEnum.BLUE, alpha=255)
        raw = px.to_bytes()
        parsed = Pixel.from_bytes(raw)
        assert parsed.color == TestEnum.NativeEnum.BLUE

    def test_invalid_enum_raises_error(self):
        @binary_struct
        class Simple:
            status: TestEnum.Status[UInt8]

        with pytest.raises(InvalidEnumError):
            Simple.from_bytes(b"\x99")


# ==========================================================
# 3. Magic & Constant Constraints Tests
# ==========================================================

class TestMagicAndConstant:
    def test_magic_bytes_and_constant(self):
        @binary_struct(endian="big")
        class FileHeader:
            magic: Magic[b"PK\x03\x04"]
            version: Constant[UInt16, 20]
            size: UInt32

        # Instantiation without passing magic or constant
        header = FileHeader(size=1024)
        raw = header.to_bytes()
        assert len(raw) == 4 + 2 + 4
        assert raw[:4] == b"PK\x03\x04"
        assert raw[4:6] == b"\x00\x14"

        # Reading valid
        parsed = FileHeader.from_bytes(raw)
        assert parsed.magic == b"PK\x03\x04"
        assert parsed.version == 20
        assert parsed.size == 1024

    def test_invalid_magic_raises_error(self):
        @binary_struct
        class PngHeader:
            magic: Magic[b"\x89PNG"]
            width: UInt32

        bad_data = b"\x00PNG\x00\x00\x01\x00"
        with pytest.raises(InvalidMagicError) as exc_info:
            PngHeader.from_bytes(bad_data)
        assert "magic mismatch" in str(exc_info.value).lower()

    def test_invalid_constant_raises_error(self):
        @binary_struct
        class Protocol:
            version: Constant[UInt8, 1]
            data: UInt16

        bad_data = b"\x02\x00\x0A"
        with pytest.raises(InvalidConstantError) as exc_info:
            Protocol.from_bytes(bad_data)
        assert "constant mismatch" in str(exc_info.value).lower()

    def test_magic_int(self):
        @binary_struct(endian="little")
        class IntMagicStruct:
            magic: Magic[0xABCD]
            val: UInt8

        s = IntMagicStruct(val=5)
        raw = s.to_bytes()
        parsed = IntMagicStruct.from_bytes(raw)
        assert parsed.magic == 0xABCD
        assert parsed.val == 5


# ==========================================================
# 4. JSON / Dict Serialization Tests
# ==========================================================

class TestJsonDictInterop:
    @binary_struct(endian="little")
    class Packet:
        id: UInt16
        name: FixedString[8]
        tag: Bytes[3]

    def test_to_dict_and_from_dict(self):
        pkt = self.Packet(id=42, name="Alpha", tag=b"\x01\x02\x03")
        d = pkt.to_dict(bytes_format="hex")
        assert d["id"] == 42
        assert d["name"] == "Alpha"
        assert d["tag"] == "0x010203"

        # from_dict roundtrip
        restored = self.Packet.from_dict(d)
        assert restored.id == 42
        assert restored.name == "Alpha"
        assert restored.tag == b"\x01\x02\x03"

    def test_json_roundtrip_base64(self):
        pkt = self.Packet(id=99, name="Beta", tag=b"\xFF\xFE\xFD")
        json_str = pkt.to_json(bytes_format="base64")
        assert isinstance(json_str, str)
        restored = self.Packet.from_json(json_str)
        assert restored.id == 99
        assert restored.name == "Beta"
        assert restored.tag == b"\xFF\xFE\xFD"

    def test_json_roundtrip_list(self):
        pkt = self.Packet(id=10, name="Gamma", tag=b"\x0A\x0B\x0C")
        json_str = pkt.to_json(bytes_format="list")
        restored = self.Packet.from_json(json_str)
        assert restored.tag == b"\x0A\x0B\x0C"


# ==========================================================
# 5. Huge Files & Streaming Tests
# ==========================================================

class TestStreamingAndMmap:
    @binary_struct(endian="little")
    class Record:
        id: UInt32
        score: UInt16

    def test_iter_struct(self):
        records = [self.Record(id=i, score=i * 10) for i in range(5)]
        raw = b"".join(r.to_bytes() for r in records)

        reader = BinaryReader(raw, default_endian=Endian.LITTLE)
        parsed = list(reader.iter_struct(self.Record))
        assert len(parsed) == 5
        for i, p in enumerate(parsed):
            assert p.id == i
            assert p.score == i * 10

    def test_from_mmap(self):
        records = [self.Record(id=i, score=i * 100) for i in range(10)]
        data = b"".join(r.to_bytes() for r in records)

        with tempfile.NamedTemporaryFile(delete=False) as tf:
            tf.write(data)
            tmp_path = tf.name

        try:
            with BinaryReader.from_mmap(tmp_path, default_endian=Endian.LITTLE) as reader:
                parsed = list(reader.iter_struct(self.Record))
                assert len(parsed) == 10
                assert parsed[0].score == 0
                assert parsed[9].score == 900
        finally:
            os.remove(tmp_path)


# ==========================================================
# 6. Variable-Length Integers (VarInt) Tests
# ==========================================================

class TestVarInt:
    def test_writer_reader_varuint(self):
        values = [0, 1, 127, 128, 255, 300, 16384, 2097151, 0xFFFFFFFF]
        writer = BinaryWriter()
        for v in values:
            writer.write_varuint(v)
        raw = writer.to_bytes()

        reader = BinaryReader(raw)
        decoded = [reader.read_varuint() for _ in values]
        assert decoded == values

    def test_writer_reader_varint(self):
        values = [0, -1, 1, -64, 64, -8192, 8192, -2147483648, 2147483647]
        writer = BinaryWriter()
        for v in values:
            writer.write_varint(v)
        raw = writer.to_bytes()

        reader = BinaryReader(raw)
        decoded = [reader.read_varint() for _ in values]
        assert decoded == values

    def test_varint_in_binary_struct(self):
        @binary_struct
        class VarIntMessage:
            msg_id: VarUInt
            delta: VarInt
            name: FixedString[4]

        msg = VarIntMessage(msg_id=300, delta=-42, name="test")
        raw = msg.to_bytes()
        parsed = VarIntMessage.from_bytes(raw)
        assert parsed.msg_id == 300
        assert parsed.delta == -42
        assert parsed.name == "test"


# ==========================================================
# 7. Arbitrary Bitstream Tests
# ==========================================================

class TestBitstream:
    def test_bitwriter_bitreader(self):
        bw = BitWriter()
        bw.write_bits(0b101, 3)     # 3 bits: 101
        bw.write_bits(0b11, 2)      # 2 bits: 11
        bw.write_bits(0b001, 3)     # 3 bits: 001 -> completes 1st byte: 10111001 (0xB9)
        bw.write_bits(0b1111, 4)    # 4 bits in 2nd byte
        data = bw.to_bytes()
        assert len(data) == 2

        br = BitReader(data)
        assert br.read_bits(3) == 0b101
        assert br.read_bits(2) == 0b11
        assert br.read_bits(3) == 0b001
        assert br.read_bits(4) == 0b1111

    def test_writer_bit_integration(self):
        writer = BinaryWriter()
        writer.write_uint8(0xFF)
        writer.write_bits(0b1010, 4)
        writer.write_bits(0b0101, 4)
        writer.write_uint16(0x1234, endian=Endian.BIG)
        data = writer.to_bytes()
        assert len(data) == 1 + 1 + 2

        reader = BinaryReader(data)
        assert reader.read_uint8() == 0xFF
        assert reader.read_bits(4) == 0b1010
        assert reader.read_bits(4) == 0b0101
        assert reader.read_uint16(endian=Endian.BIG) == 0x1234


# ==========================================================
# 8. CLI Tool Tests
# ==========================================================

@binary_struct(endian="little")
class CliTestHeader:
    magic: UInt32
    version: UInt16


class TestCLI:
    def test_cli_inspect(self, capsys):
        with tempfile.NamedTemporaryFile(delete=False) as tf:
            tf.write(b"\x00\x01\x02\x03\x04\x05\x06\x07Hello Binary Master CLI")
            path = tf.name

        try:
            cli_main(["inspect", path])
            captured = capsys.readouterr()
            assert "Hello Bi" in captured.out
            assert "Total: 31 bytes" in captured.out
        finally:
            os.remove(path)

    def test_cli_diff(self, capsys):
        with tempfile.NamedTemporaryFile(delete=False) as tf1, tempfile.NamedTemporaryFile(delete=False) as tf2:
            tf1.write(b"AAAA1234")
            tf2.write(b"AAAB1234")
            p1, p2 = tf1.name, tf2.name

        try:
            cli_main(["diff", p1, p2])
            captured = capsys.readouterr()
            assert "Binary Diff" in captured.out
        finally:
            os.remove(p1)
            os.remove(p2)

    def test_cli_spec(self, capsys):
        cli_main(["spec", "tests.test_new_features:CliTestHeader", "-o", "-"])
        captured = capsys.readouterr()
        assert "CliTestHeader" in captured.out

    def test_cli_export(self, capsys):
        cli_main(["export", "tests.test_new_features:CliTestHeader", "--lang", "rust", "-o", "-"])
        captured = capsys.readouterr()
        assert "struct CliTestHeader" in captured.out or "pub struct" in captured.out

    def test_to_dict_from_dict_with_magic_and_constant(self):
        @binary_struct
        class ConfigPacket:
            magic: Magic[b"CONF"]
            version: Constant[UInt8, 2]
            val: UInt32

        pkt = ConfigPacket(val=999)
        d = pkt.to_dict()
        assert d["magic"] == "0x434f4e46"
        assert d["version"] == 2
        assert d["val"] == 999

        restored = ConfigPacket.from_dict(d)
        assert restored.val == 999
        assert restored.to_bytes() == pkt.to_bytes()

