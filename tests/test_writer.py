"""Comprehensive integration tests covering all spec scenarios for BinaryWriter."""

from pathlib import Path
import pytest
from binary_master import BinaryWriter, Endian


def test_scenario_write_unsigned_and_signed_integers():
    """Scenario: Write unsigned and signed integers with specified endianness.

    WHEN user writes uint16 0x1234 in little-endian and int32 -100 in big-endian
    THEN writer appends \\x34\\x12 followed by the 4-byte big-endian representation of -100
    """
    writer = BinaryWriter(default_endian=Endian.LITTLE)
    writer.write_uint16(0x1234)
    writer.write_int32(-100, endian=Endian.BIG)

    # 0x1234 LE -> \x34\x12
    # -100 BE 32-bit -> \xFF\xFF\xFF\x9C
    expected = b"\x34\x12\xFF\xFF\xFF\x9C"
    assert writer.to_bytes() == expected


def test_scenario_integer_value_out_of_range():
    """Scenario: Integer value out of range.

    WHEN user writes value 300 as uint8 (range 0 to 255)
    THEN writer raises an error indicating the value exceeds the type range and leaves the position unmodified
    """
    writer = BinaryWriter()
    writer.write_uint8(42)
    initial_pos = writer.tell()

    with pytest.raises(ValueError):
        writer.write_uint8(300)

    assert writer.tell() == initial_pos
    assert writer.to_bytes() == b"*"  # 42 is b'*'


def test_scenario_write_float32_and_float64():
    """Scenario: Write float32 and float64.

    WHEN user writes float32 1.5 and float64 3.141592653589793
    THEN writer serializes standard IEEE 754 representations in the requested endianness
    """
    writer = BinaryWriter(default_endian=Endian.BIG)
    writer.write_float32(1.5).write_float64(3.141592653589793)

    # 1.5 float32 BE: 0x3FC00000 -> \x3F\xC0\x00\x00
    # 3.141592653589793 float64 BE: 0x400921FB54442D18
    data = writer.to_bytes()
    assert len(data) == 12
    assert data[:4] == b"\x3f\xc0\x00\x00"
    assert data[4:] == b"\x40\x09\x21\xfb\x54\x44\x2d\x18"


def test_scenario_write_boolean_values():
    """Scenario: Write boolean values.

    WHEN user writes True and False
    THEN writer writes single bytes 0x01 and 0x00 respectively
    """
    writer = BinaryWriter()
    writer.write_bool(True).write_bool(False)
    assert writer.to_bytes() == b"\x01\x00"


def test_scenario_write_raw_byte_payloads():
    """Scenario: Write raw byte payloads.

    WHEN user writes bytes b"\\xDE\\xAD\\xBE\\xEF"
    THEN writer appends the exact byte sequence to the output stream
    """
    writer = BinaryWriter()
    writer.write_bytes(b"\xDE\xAD\xBE\xEF")
    assert writer.to_bytes() == b"\xDE\xAD\xBE\xEF"


def test_scenario_write_null_terminated_string():
    """Scenario: Write null-terminated string.

    WHEN user writes string "hello" as null-terminated with UTF-8 encoding
    THEN writer writes b"hello\\x00" to the stream
    """
    writer = BinaryWriter()
    writer.write_cstring("hello")
    assert writer.to_bytes() == b"hello\x00"


def test_scenario_write_length_prefixed_string():
    """Scenario: Write length-prefixed string.

    WHEN user writes string "world" with a 2-byte unsigned integer prefix in big-endian
    THEN writer writes \\x00\\x05 followed by b"world"
    """
    writer = BinaryWriter()
    writer.write_prefixed_string("world", prefix_bytes=2, endian=Endian.BIG)
    assert writer.to_bytes() == b"\x00\x05world"


def test_scenario_write_fixed_length_padded_string():
    """Scenario: Write fixed-length padded string.

    WHEN user writes string "cat" into a fixed length of 6 bytes with null byte padding
    THEN writer writes b"cat\\x00\\x00\\x00"
    """
    writer = BinaryWriter()
    writer.write_fixed_string("cat", length=6, pad_byte=b"\x00")
    assert writer.to_bytes() == b"cat\x00\x00\x00"


def test_scenario_in_memory_accumulation_and_retrieval():
    """Scenario: In-memory buffer accumulation and retrieval.

    WHEN user creates an in-memory writer, writes several data types, and calls to_bytes()
    THEN writer returns the complete accumulated binary output as bytes
    """
    writer = BinaryWriter.to_memory()
    writer.write_uint8(10).write_cstring("test").write_uint16(200)
    res = writer.to_bytes()
    assert isinstance(res, bytes)
    assert res == b"\x0Atest\x00\xC8\x00"


def test_scenario_writing_to_external_file_stream(tmp_path: Path):
    """Scenario: Writing to an external file stream.

    WHEN user creates a writer wrapping a writable file or stream object and writes data
    THEN writer writes bytes directly into the stream object without buffering everything exclusively in a separate buffer
    """
    file_path = tmp_path / "output.bin"

    with BinaryWriter.to_file(file_path) as writer:
        writer.write_uint32(0xAABBCCDD, endian="big")
        writer.write_cstring("ok")

    content = file_path.read_bytes()
    assert content == b"\xAA\xBB\xCC\xDDok\x00"


def test_scenario_query_cursor_position_and_seek():
    """Scenario: Query cursor position and seek.

    WHEN user writes 4 bytes, checks position tell(), seeks back to offset 0, and overwrites 2 bytes
    THEN position reports 4 after initial write, and the first 2 bytes are overwritten after seeking
    """
    writer = BinaryWriter()
    writer.write_bytes(b"\x01\x02\x03\x04")
    assert writer.tell() == 4

    writer.seek(0)
    assert writer.tell() == 0
    writer.write_bytes(b"\xAA\xBB")

    assert writer.to_bytes() == b"\xAA\xBB\x03\x04"


def test_scenario_align_cursor_to_boundary_with_padding():
    """Scenario: Align cursor to boundary with padding.

    WHEN write cursor is at offset 3 and user requests alignment to a 4-byte boundary using pad byte 0x00
    THEN writer writes 1 padding byte 0x00 and cursor position becomes 4
    """
    writer = BinaryWriter()
    writer.write_bytes(b"\x01\x02\x03")
    assert writer.tell() == 3

    writer.align(4, pad_byte=b"\x00")
    assert writer.tell() == 4
    assert writer.to_bytes() == b"\x01\x02\x03\x00"


def test_end_to_end_packet_builder():
    """Full binary packet construction test combining headers, flags, payload, and alignment."""
    writer = BinaryWriter(default_endian=Endian.BIG)

    # Magic: 4 bytes
    writer.write_bytes(b"PKT\x01")
    # Flags: 1 byte (bools/bits packed)
    writer.write_uint8(0b00000001)
    # Sequence number: uint32
    writer.write_uint32(42)
    # Payload: length-prefixed string (uint16 prefix)
    writer.write_prefixed_string("BinaryMasterPayload", prefix_bytes=2)
    # Align to 8-byte boundary
    writer.align(8, pad_byte=b"\xFF")
    # Checksum / Footer: uint32
    writer.write_uint32(0xDEADBEEF)

    data = writer.to_bytes()
    assert data.startswith(b"PKT\x01\x01\x00\x00\x00\x2a")
    assert data.endswith(b"\xDE\xAD\xBE\xEF")
    assert len(data) % 4 == 0

