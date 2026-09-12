"""Sample 05: Schema-First ManualBuilder and Automated Reader.

Demonstrates:
- Constructing specification manuals upfront without runtime instances
- Narrative documentation chapters with builder.add_document()
- Declarative polymorphic choices with builder.add_choice()
- Conditional structures with condition expressions
- Writing the Markdown manual to file with builder.write("path.md")
- Mermaid flowchart diagrams with decision diamond nodes
- Automated schema-driven binary deserialization with builder.read(data)
"""

from pathlib import Path

from binary_master import (
    BinaryWriter,
    FixedArray,
    Float32,
    ManualBuilder,
    UInt8,
    UInt16,
    UInt32,
    binary_struct,
)


# 1. Define Protocol Structures
@binary_struct(endian="little")
class PacketHeader:
    """Protocol header packet."""

    magic: UInt32  # Signature: 0x4D534750 ('MSGP')
    version: UInt16  # Protocol version
    msg_type: UInt16  # 1 = Text, 2 = Sensor Data
    payload_size: UInt32  # Length of following payload
    flags: UInt16  # Bit 0: Has Checksum Footer


@binary_struct
class TextMessage:
    """Variant 1: UTF-8 Text Message Payload."""

    encoding: UInt16  # 1 = UTF-8, 2 = ASCII
    text_len: UInt16  # Length of text in bytes
    content: FixedArray[UInt8, 16]  # Fixed buffer for text


@binary_struct
class SensorReport:
    """Variant 2: Telemetry Sensor Data Payload."""

    sensor_id: UInt32  # Unique sensor ID
    temperature: Float32  # Temperature in Celsius
    pressure: Float32  # Pressure in hPa
    humidity: Float32  # Relative humidity (0.0 - 100.0)


@binary_struct
class ChecksumFooter:
    """Optional CRC32 trailing verification block."""

    crc32: UInt32  # IEEE 802.3 CRC32 checksum


def main():
    print("=== Sample 05: Schema-First ManualBuilder & Automated Reader ===")

    # 1. Create ManualBuilder schema
    builder = ManualBuilder(
        title="Network Telemetry Protocol Specification",
        version="1.0.0",
        default_endian="little",
        description="Unified binary messaging format supporting text messages and sensor telemetry packets.",
    )

    # 2. Add narrative documentation chapters
    builder.add_document(
        "Protocol Overview & Scope",
        """This document specifies the Network Telemetry Protocol (NTP-v1).
All multi-byte numeric fields are encoded in Little-Endian byte order.

Packets begin with a fixed 14-byte `PacketHeader`. The `msg_type` field dictates
which payload structure immediately follows:
- `0x0001`: `TextMessage`
- `0x0002`: `SensorReport`

If bit 0 of `flags` is set (`flags & 0x01 != 0`), a 4-byte `ChecksumFooter` is appended.""",
    )

    # 3. Register sequential structs and choice branches
    builder.add_struct(PacketHeader, name="header", desc="Fixed 14-byte packet header")

    builder.add_choice(
        name="payload",
        tag_field="msg_type",
        variants={
            1: (TextMessage, "Human-readable plaintext message payload"),
            2: (SensorReport, "Multi-channel environmental sensor readings"),
        },
        desc="Dynamic payload dispatched by PacketHeader.msg_type",
    )

    builder.add_struct(
        ChecksumFooter,
        name="footer",
        desc="Trailing CRC32 checksum verification",
        condition="flags & 0x01 != 0",
    )

    # 4. Generate and save the specification manual using builder.write()
    spec_path = Path(__file__).parent / "telemetry_protocol_spec.md"
    builder.write(spec_path, diagram_direction="TD")
    print(f"Generated specification manual saved to: {spec_path.name}")

    # 5. Export multi-language definition files
    header_path = Path(__file__).parent / "telemetry_protocol.h"
    builder.write_c_header(header_path)
    print(f"Generated C header file saved to:         {header_path.name}")

    rust_path = Path(__file__).parent / "telemetry_protocol.rs"
    builder.write_rust(rust_path)
    print(f"Generated Rust definitions saved to:       {rust_path.name}")

    cpp_path = Path(__file__).parent / "telemetry_protocol.hpp"
    builder.write_cpp(cpp_path)
    print(f"Generated C++ header saved to:             {cpp_path.name}")

    csharp_path = Path(__file__).parent / "telemetry_protocol.cs"
    builder.write_csharp(csharp_path, namespace="TelemetryProtocol")
    print(f"Generated C# structures saved to:          {csharp_path.name}")

    go_path = Path(__file__).parent / "telemetry_protocol.go"
    builder.write_go(go_path, package_name="telemetry")
    print(f"Generated Go package definitions saved to: {go_path.name}")


    # =========================================================================
    # 5. Automated Schema-Driven Reading (builder.read)
    # =========================================================================
    print("\n--- Testing Automated Reading (builder.read) ---")

    # Packet A: SensorReport (msg_type = 2, with checksum footer flags = 1)
    w_sensor = BinaryWriter()
    w_sensor.write_struct(
        PacketHeader(magic=0x5047534D, version=1, msg_type=2, payload_size=16, flags=1)
    )
    w_sensor.write_struct(
        SensorReport(sensor_id=101, temperature=23.5, pressure=1013.25, humidity=48.0)
    )
    w_sensor.write_struct(ChecksumFooter(crc32=0xDEADBEEF))
    sensor_binary = w_sensor.to_bytes()

    # Automate deserialization with builder.read()
    res_sensor = builder.read(sensor_binary)

    print("Parsed Packet A (Sensor Report):")
    print(f"  Header magic:      0x{res_sensor.header.magic:08X}")
    print(f"  Header msg_type:   {res_sensor.header.msg_type}")
    print(f"  Payload type:      {type(res_sensor.payload).__name__}")
    print(f"  Sensor ID:         {res_sensor.payload.sensor_id}")
    print(f"  Temperature:       {res_sensor.payload.temperature:.1f} C")
    print(f"  Pressure:          {res_sensor.payload.pressure:.2f} hPa")
    print(f"  Footer CRC32:      0x{res_sensor.footer.crc32:08X}")

    assert isinstance(res_sensor.payload, SensorReport)
    assert res_sensor.footer.crc32 == 0xDEADBEEF

    # Packet B: TextMessage (msg_type = 1, NO footer flags = 0)
    w_text = BinaryWriter()
    w_text.write_struct(
        PacketHeader(magic=0x5047534D, version=1, msg_type=1, payload_size=20, flags=0)
    )
    msg_str = "SYSTEM_OK\x00".encode("utf-8").ljust(16, b"\x00")
    w_text.write_struct(TextMessage(encoding=1, text_len=9, content=msg_str))
    text_binary = w_text.to_bytes()

    # Automate deserialization with builder.read()
    res_text = builder.read(text_binary)

    print("\nParsed Packet B (Text Message):")
    print(f"  Header msg_type:   {res_text.header.msg_type}")
    print(f"  Payload type:      {type(res_text.payload).__name__}")
    print(f"  Message Text:      {bytes(res_text.payload.content).rstrip(b'\\x00').decode('utf-8')}")
    print(f"  Footer present:    {'footer' in res_text}")

    assert isinstance(res_text.payload, TextMessage)
    assert "footer" not in res_text  # Correctly skipped because flags & 0x01 == 0!

    print("\nSchema-first manual generation and automated reading verified successfully!")


if __name__ == "__main__":
    main()
