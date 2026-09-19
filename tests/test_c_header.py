"""Tests for C/C++ header generation."""

import subprocess
from pathlib import Path

from binary_master import (
    Bits,
    Builder,
    FixedArray,
    Float32,
    UInt8,
    UInt16,
    UInt32,
    binary_struct,
    to_c_struct,
)


@binary_struct(endian="little")
class PacketHeader:
    """Fixed packet header."""

    magic: UInt32  # Signature: 'MSGP'
    version: UInt16  # Protocol version
    msg_type: UInt16  # Message type
    tag: FixedArray[UInt8, 4]  # 4-byte clan tag


@binary_struct(bits=16)
class DeviceFlags:
    """16-bit status bitfield."""

    online: Bits[1]  # Bit 0
    mode: Bits[3]  # Bits 1..3
    error: Bits[4]  # Bits 4..7
    battery: Bits[8]  # Bits 8..15


@binary_struct
class TextMessage:
    """Text message payload."""

    encoding: UInt16
    text_len: UInt16
    content: FixedArray[UInt8, 16]


@binary_struct
class SensorReport:
    """Sensor telemetry payload."""

    sensor_id: UInt32
    temperature: Float32


def test_to_c_struct_basic():
    """Test generating C struct from a basic @binary_struct."""
    c_code = to_c_struct(PacketHeader)

    assert "typedef struct PacketHeader {" in c_code
    assert "uint32_t magic;" in c_code
    assert "uint16_t version;" in c_code
    assert "uint16_t msg_type;" in c_code
    assert "uint8_t tag[4];" in c_code
    assert "} PacketHeader;" in c_code
    assert "Signature: 'MSGP'" in c_code


def test_to_c_struct_bitfield():
    """Test generating C bitfield struct from a @binary_struct(bits=16)."""
    c_code = to_c_struct(DeviceFlags)

    assert "typedef struct DeviceFlags {" in c_code
    assert "uint16_t online : 1;" in c_code
    assert "uint16_t mode : 3;" in c_code
    assert "uint16_t error : 4;" in c_code
    assert "uint16_t battery : 8;" in c_code
    assert "} DeviceFlags;" in c_code


def test_builder_to_c_header_full():
    """Test full C header generation including guards, pragmas, enums, unions, and docs."""
    builder = Builder(
        title="Network Telemetry Protocol",
        version="1.0.0",
        description="A sample telemetry protocol for testing.",
    )

    builder.add_document("Protocol Overview", "Detailed description of telemetry format.")
    builder.add_struct(PacketHeader, desc="Packet header")
    builder.add_choice(
        name="payload",
        tag_field="msg_type",
        variants={
            1: (TextMessage, "Text message variant"),
            2: (SensorReport, "Sensor report variant"),
        },
    )

    c_header = builder.to_c_header(guard="TELEMETRY_PROTOCOL_H")

    # Include guards
    assert "#ifndef TELEMETRY_PROTOCOL_H" in c_header
    assert "#define TELEMETRY_PROTOCOL_H" in c_header
    assert "#endif /* TELEMETRY_PROTOCOL_H */" in c_header

    # Standard headers & C++ extern "C"
    assert "#include <stdint.h>" in c_header
    assert "#include <stdbool.h>" in c_header
    assert 'extern "C"' in c_header

    # Packing pragmas
    assert "#pragma pack(push, 1)" in c_header
    assert "#pragma pack(pop)" in c_header

    # Narrative doc comment
    assert "Protocol Overview" in c_header
    assert "Detailed description of telemetry format." in c_header

    # Header struct
    assert "typedef struct PacketHeader {" in c_header

    # Choice Enum & Union
    assert "typedef enum PayloadTag {" in c_header
    assert "PAYLOAD_TAG_TEXT_MESSAGE = 0x01," in c_header
    assert "PAYLOAD_TAG_SENSOR_REPORT = 0x02," in c_header
    assert "} PayloadTag;" in c_header

    assert "typedef struct TextMessage {" in c_header
    assert "typedef struct SensorReport {" in c_header

    assert "typedef union PayloadUnion {" in c_header
    assert "TextMessage text_message;" in c_header
    assert "SensorReport sensor_report;" in c_header
    assert "} PayloadUnion;" in c_header


def test_write_c_header_and_gcc_syntax_check(tmp_path: Path):
    """Test saving header file and verify C syntax validity with GCC."""
    builder = Builder(title="GCC Compile Test Protocol")
    builder.add_document("Intro", "C compiler test.")
    builder.add_struct(PacketHeader)
    builder.add_struct(DeviceFlags)
    builder.add_choice(
        name="payload",
        tag_field="msg_type",
        variants={
            1: TextMessage,
            2: SensorReport,
        },
    )

    header_file = tmp_path / "protocol.h"
    builder.write_c_header(header_file)
    assert header_file.exists()

    # Create a small C source file to verify with gcc
    c_source = tmp_path / "test.c"
    c_source.write_text(
        """
#include "protocol.h"

void test_func(void) {
    PacketHeader hdr;
    hdr.magic = 0x12345678;
    hdr.version = 1;

    DeviceFlags flags;
    flags.online = 1;
    flags.mode = 2;

    PayloadUnion payload;
    payload.sensor_report.sensor_id = 42;
    payload.sensor_report.temperature = 25.5f;

    (void)hdr;
    (void)flags;
    (void)payload;
}
""",

        encoding="utf-8",
    )

    res = subprocess.run(
        ["gcc", "-fsyntax-only", "-Wall", "-Werror", str(c_source)],
        capture_output=True,
        text=True,
    )
    assert res.returncode == 0, f"GCC syntax error:\n{res.stderr}"
