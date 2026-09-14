"""Sample 06: Advanced v2 Features.

Demonstrates:
1. Declarative CRC / Checksum calculation & validation (CRC32, CRC16, Adler32, Checksum8)
2. Native Enum support with explicit binary integer sizing (BinaryEnum[UInt8])
3. Magic numbers and Constant constraints (Magic[b'...'], Constant[Type, Value])
4. JSON & Dictionary interop (.to_dict(), .from_dict(), .to_json(), .from_json())
5. Huge file streaming & zero-copy iteration (reader.iter_struct(), BinaryReader.from_mmap())
6. Variable-Length Integers (LEB128 VarUInt, VarInt)
7. Arbitrary Bitstream manipulation (BitWriter, BitReader, writer.write_bits)
8. CLI binary inspector usage (binary-master inspect/diff/spec/export)
"""

import os
import tempfile
from binary_master import (
    binary_struct,
    BinaryReader,
    BinaryWriter,
    BinaryEnum,
    Magic,
    Constant,
    CRC32,
    VarUInt,
    VarInt,
    UInt8,
    UInt16,
    UInt32,
    FixedString,
    BitWriter,
    BitReader,
    Endian,
)


# 1 & 2 & 3 & 6: Comprehensive packet definition
class MessageType(BinaryEnum):
    HEARTBEAT = 0x01
    DATA_PAYLOAD = 0x02
    SHUTDOWN = 0xFF


@binary_struct(endian="big")
class AdvancedPacket:
    """Demonstrates Magic, Constant, Enum, VarInt, and Checksum in a single struct."""
    magic: Magic[b"PKT\x01"]              # Auto-defaults to b'PKT\x01', validates on read
    version: Constant[UInt16, 2]         # Fixed constant protocol version
    msg_type: MessageType[UInt8]         # Enum serialized as 1 byte (UInt8)
    sequence: VarUInt                    # LEB128 variable-length unsigned int
    temperature_delta: VarInt            # LEB128 variable-length signed int
    label: FixedString[8]                # 8-byte fixed string
    checksum: CRC32                      # Automatically calculated & validated IEEE 802.3 CRC32


def main():
    print("=== Sample 06: Advanced v2 Features ===")

    # 1. Instantiation (notice: magic and version are automatically filled!)
    packet = AdvancedPacket(
        msg_type=MessageType.DATA_PAYLOAD,
        sequence=1024,
        temperature_delta=-5,
        label="SENSOR_A",
    )

    # 2. Serialization & Automatic Checksum
    raw_bytes = packet.to_bytes()
    print(f"\nSerialized {len(raw_bytes)} bytes:")
    print("Hex:", raw_bytes.hex(" "))

    # 3. Deserialization & Automatic Validation
    restored = AdvancedPacket.from_bytes(raw_bytes)
    print(f"\nDeserialized Successfully:")
    print(f"  Magic:       {restored.magic!r}")
    print(f"  Version:     {restored.version}")
    print(f"  Msg Type:    {restored.msg_type.name} ({restored.msg_type.value})")
    print(f"  Sequence:    {restored.sequence}")
    print(f"  Delta:       {restored.temperature_delta}")
    print(f"  Label:       {restored.label}")
    print(f"  CRC32:       0x{restored.checksum:08X}")

    # 4. JSON / Dict Interop
    print("\n--- JSON & Dict Serialization ---")
    json_repr = packet.to_json(indent=2, bytes_format="hex")
    print("JSON Representation:\n", json_repr)

    from_json_packet = AdvancedPacket.from_json(json_repr)
    assert from_json_packet.sequence == packet.sequence
    print("Restored from JSON successfully!")

    # 5. Streaming & iter_struct
    print("\n--- Streaming & iter_struct ---")
    stream_packets = [
        AdvancedPacket(msg_type=MessageType.HEARTBEAT, sequence=i, temperature_delta=i - 2, label=f"DEV_{i}")
        for i in range(3)
    ]
    stream_data = b"".join(p.to_bytes() for p in stream_packets)
    reader = BinaryReader(stream_data, default_endian=Endian.BIG)
    print("Iterating over streaming packets:")
    for idx, p in enumerate(reader.iter_struct(AdvancedPacket)):
        print(f"  Packet {idx}: seq={p.sequence}, label={p.label}, crc=0x{p.checksum:08X}")

    # 6. Arbitrary Bitstream
    print("\n--- Arbitrary Bitstream (BitWriter & BitReader) ---")
    bw = BitWriter()
    bw.write_bits(0b1101, 4)      # 4 bits
    bw.write_bits(0b010, 3)       # 3 bits
    bw.write_bits(0b1, 1)         # 1 bit -> byte 0: 0b11010101 (0xD5)
    bw.write_bits(0b11110000, 8)  # 8 bits -> byte 1: 0xF0
    bit_data = bw.to_bytes()
    print(f"Bit packed {bw.total_bits} bits into {len(bit_data)} bytes: {bit_data.hex()}")

    br = BitReader(bit_data)
    b1 = br.read_bits(4)
    b2 = br.read_bits(3)
    b3 = br.read_bits(1)
    b4 = br.read_bits(8)
    print(f"Read back: 4-bits={bin(b1)}, 3-bits={bin(b2)}, 1-bit={bin(b3)}, 8-bits={bin(b4)}")

    print("\nAdvanced v2 features demonstrated successfully!")


if __name__ == "__main__":
    main()
