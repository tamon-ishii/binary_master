"""Sample 01: Basic Declarative Structs and Endianness.

Demonstrates:
- Defining binary structures with @binary_struct
- Primitive types (UInt8, UInt16, UInt32, Float32) and FixedArray
- Serialization (.to_bytes()) and deserialization (read_struct())
- Static size checking with sizeof() and .binary_size
- Endianness control (little-endian vs big-endian)
"""

from binary_master import (
    Endian,
    FixedArray,
    Float32,
    UInt8,
    UInt16,
    UInt32,
    binary_size,
    binary_struct,
    read_struct,
    sizeof,
)


# 1. Define a basic header structure with docstrings and comments
@binary_struct(endian="little")
class PlayerProfile:
    """Player save data profile header."""

    magic: UInt32  # Signature: 0x504C4159 ('PLAY')
    player_id: UInt16  # Unique player ID
    level: UInt8  # Player character level
    lives: UInt8  # Remaining lives
    score: UInt32  # Current score
    health_ratio: Float32  # Normalized health: 0.0 to 1.0
    tag: FixedArray[UInt8, 4]  # 4-byte clan tag


def main():
    print("=== Sample 01: Basic Struct Serialization & Inspection ===")

    # 1. Inspect static size
    print(f"PlayerProfile size: {sizeof(PlayerProfile)} bytes (via sizeof())")
    print(f"PlayerProfile size: {PlayerProfile.binary_size} bytes (via .binary_size)")

    # 2. Instantiate and serialize
    player = PlayerProfile(
        magic=0x59414C50,  # 'PLAY' in little endian
        player_id=1042,
        level=50,
        lives=3,
        score=999999,
        health_ratio=0.85,
        tag=b"PROG",
    )

    data = player.to_bytes()
    print(f"Serialized binary ({len(data)} bytes): {data.hex(' ')}")

    # 3. Deserialize back into a struct instance
    restored = read_struct(PlayerProfile, data)
    print("\nDeserialized PlayerProfile:")
    print(f"  magic:        0x{restored.magic:08X}")
    print(f"  player_id:    {restored.player_id}")
    print(f"  level:        {restored.level}")
    print(f"  lives:        {restored.lives}")
    print(f"  score:        {restored.score}")
    print(f"  health_ratio: {restored.health_ratio:.2f}")
    print(f"  tag:          {bytes(restored.tag).decode('ascii')}")

    # 4. Big-endian override
    data_be = player.to_bytes(endian=Endian.BIG)
    print(f"\nBig-endian serialized ({len(data_be)} bytes): {data_be.hex(' ')}")
    restored_be = read_struct(PlayerProfile, data_be, endian=Endian.BIG)
    assert restored_be.player_id == player.player_id
    print("Big-endian roundtrip verified successfully!")


if __name__ == "__main__":
    main()
