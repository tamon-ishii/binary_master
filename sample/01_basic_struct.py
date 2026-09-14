"""Sample 01: Basic Declarative Structs, Bool Types, and Offsets.

Demonstrates:
- Defining binary structures with @binary_struct
- Primitive types (UInt8, UInt16, UInt32, Float32, Bool) and FixedArray
- Field byte offset inspection with offsetof() and Cls.offsetof()
- Serialization (.to_bytes()) and deserialization (read_struct() / from_bytes())
- Static size checking with sizeof() and .binary_size
- Endianness control (little-endian vs big-endian)
"""

from binary_master import (
    Bool,
    Endian,
    FixedArray,
    Float32,
    UInt8,
    UInt16,
    UInt32,
    binary_struct,
    offsetof,
    read_struct,
    sizeof,
)


# 1. Define a basic header structure with docstrings, comments, and Bool
@binary_struct(endian="little")
class PlayerProfile:
    """Player save data profile header."""

    magic: UInt32  # Signature: 0x504C4159 ('PLAY')
    player_id: UInt16  # Unique player ID
    level: UInt8  # Player character level
    lives: UInt8  # Remaining lives
    score: UInt32  # Current score
    health_ratio: Float32  # Normalized health: 0.0 to 1.0
    is_vip: Bool  # VIP account status (1 byte boolean: 0x01 = True, 0x00 = False)
    tag: FixedArray[UInt8, 4]  # 4-byte clan tag


def main():
    print("=== Sample 01: Basic Struct Serialization & Inspection ===")

    # 1. Inspect static size
    print(f"PlayerProfile size: {sizeof(PlayerProfile)} bytes (via sizeof())")
    print(f"PlayerProfile size: {PlayerProfile.binary_size} bytes (via .binary_size)")

    # 2. Inspect field offsets
    print("\nField Byte Offsets (offsetof):")
    print(f"  magic:        {PlayerProfile.offsetof('magic')} bytes")
    print(f"  player_id:    {PlayerProfile.offsetof('player_id')} bytes")
    print(f"  score:        {PlayerProfile.offsetof('score')} bytes")
    print(f"  is_vip:       {offsetof(PlayerProfile, 'is_vip')} bytes")
    print(f"  tag:          {offsetof(PlayerProfile, 'tag')} bytes")

    # 3. Instantiate and serialize
    player = PlayerProfile(
        magic=0x59414C50,  # 'PLAY' in little endian
        player_id=1042,
        level=50,
        lives=3,
        score=999999,
        health_ratio=0.85,
        is_vip=True,
        tag=b"PROG",
    )

    data = player.to_bytes()
    print(f"\nSerialized binary ({len(data)} bytes): {data.hex(' ')}")

    # 4. Deserialize back into a struct instance
    restored = read_struct(PlayerProfile, data)
    print("\nDeserialized PlayerProfile:")
    print(f"  magic:        0x{restored.magic:08X}")
    print(f"  player_id:    {restored.player_id}")
    print(f"  level:        {restored.level}")
    print(f"  lives:        {restored.lives}")
    print(f"  score:        {restored.score}")
    print(f"  health_ratio: {restored.health_ratio:.2f}")
    print(f"  is_vip:       {restored.is_vip}")
    print(f"  tag:          {bytes(restored.tag).decode('ascii')}")

    assert restored.is_vip is True
    assert restored.score == 999999

    # 5. Big-endian override
    data_be = player.to_bytes(endian=Endian.BIG)
    print(f"\nBig-endian serialized ({len(data_be)} bytes): {data_be.hex(' ')}")
    restored_be = read_struct(PlayerProfile, data_be, endian=Endian.BIG)
    assert restored_be.player_id == player.player_id
    assert restored_be.is_vip is True
    print("Big-endian roundtrip verified successfully!")


if __name__ == "__main__":
    main()
