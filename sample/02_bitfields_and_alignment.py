"""Sample 02: Bitfields and Alignment.

Demonstrates:
- Compact bitfield structures with Bits[N] and explicit total bits
- Struct alignment padding with align=4
- Automatic natural alignment with auto_align=True
- Roundtrip serialization and deserialization of bit-packed flags
"""

from binary_master import (
    Bits,
    UInt8,
    UInt16,
    UInt32,
    binary_struct,
    read_struct,
    sizeof,
)


# 1. A 16-bit bitfield container packing multiple flags and small integers
@binary_struct(bits=16)
class DeviceStatus:
    """16-bit packed hardware status flags."""

    powered_on: Bits[1]  # Bit 0: 1 = Online, 0 = Standby
    busy: Bits[1]  # Bit 1: 1 = Processing, 0 = Idle
    mode: Bits[3]  # Bits 2..4: Operating mode (0..7)
    error_code: Bits[3]  # Bits 5..7: Last error code (0..7)
    battery_pct: Bits[7]  # Bits 8..14: Battery percentage (0..100)
    reserved: Bits[1]  # Bit 15: Reserved for future expansion


# 2. A struct with explicit 4-byte boundary padding
@binary_struct(align=4)
class AlignedPacket:
    """Packet with struct-level 4-byte alignment."""

    type_id: UInt8  # 1 byte
    # 3 bytes padding inserted to reach 4-byte boundary
    counter: UInt32  # 4 bytes (starts at offset 4)
    flags: DeviceStatus  # 2 bytes (starts at offset 8)
    # 2 bytes tail padding inserted to align total size to multiple of 4 (total 12B)


# 3. Automatic natural alignment (fields align to their own size)
@binary_struct(auto_align=True)
class NaturalAlignedStruct:
    """Fields automatically aligned to their natural primitive sizes."""

    a: UInt8  # 1 byte at offset 0
    # 1 byte padding inserted so UInt16 starts at multiple of 2 (offset 2)
    b: UInt16  # 2 bytes at offset 2..4
    # 0 padding needed because UInt32 starts at multiple of 4 (offset 4)
    c: UInt32  # 4 bytes at offset 4..8


def main():
    print("=== Sample 02: Bitfields and Alignment ===")

    # 1. Bitfields
    status = DeviceStatus(
        powered_on=1,
        busy=0,
        mode=5,
        error_code=2,
        battery_pct=95,
        reserved=0,
    )
    status_bytes = status.to_bytes()
    print(f"DeviceStatus size: {sizeof(DeviceStatus)} bytes")
    print(f"DeviceStatus binary: 0x{status_bytes.hex()}")

    restored_status = read_struct(DeviceStatus, status_bytes)
    print("\nDeserialized DeviceStatus:")
    print(f"  powered_on:  {restored_status.powered_on}")
    print(f"  busy:        {restored_status.busy}")
    print(f"  mode:        {restored_status.mode}")
    print(f"  error_code:  {restored_status.error_code}")
    print(f"  battery_pct: {restored_status.battery_pct}%")

    # 2. Aligned structs
    print(f"\nAlignedPacket total size: {sizeof(AlignedPacket)} bytes (aligned to 4 bytes)")
    packet = AlignedPacket(type_id=0x01, counter=1000, flags=status)
    packet_bytes = packet.to_bytes()
    print(f"AlignedPacket binary ({len(packet_bytes)} bytes): {packet_bytes.hex(' ')}")

    restored_packet = read_struct(AlignedPacket, packet_bytes)
    assert restored_packet.counter == 1000
    assert restored_packet.flags.battery_pct == 95

    # 3. Natural alignment
    print(f"\nNaturalAlignedStruct total size: {sizeof(NaturalAlignedStruct)} bytes")
    natural = NaturalAlignedStruct(a=0xAA, b=0xBBCC, c=0x11223344)
    natural_bytes = natural.to_bytes()
    print(f"NaturalAlignedStruct binary: {natural_bytes.hex(' ')}")
    print("Alignment and bitfields verified successfully!")


if __name__ == "__main__":
    main()
