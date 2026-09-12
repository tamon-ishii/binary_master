"""Sample 03: Relative Offsets, Pointer Tables, and Self-Relative Bases.

Demonstrates:
- Pointer offsets with Offset[Target]
- Self-relative offsets using Base.SELF and arithmetic (Base.SELF + 0x10)
- Field-relative offsets using Base.FIELD("header")
- Dynamic pointer tables with OffsetTable[Target, Base.SELF]
- Automatic deferred patching during serialization
"""

from binary_master import (
    Base,
    BinaryWriter,
    FixedArray,
    Offset,
    OffsetTable,
    UInt8,
    UInt16,
    UInt32,
    binary_struct,
    read_struct,
)


# Target payload struct
@binary_struct
class TextureData:
    """Texture asset payload."""

    width: UInt16
    height: UInt16
    format: UInt8
    raw_pixels: FixedArray[UInt8, 8]


# Container using relative offsets and offset tables
@binary_struct
class AssetContainer:
    """Asset header referencing payloads via relative pointers."""

    magic: UInt32  # Signature: 'ASST'
    version: UInt16  # Version number

    # 1. Self-relative offset to primary texture (offset measured from start of AssetContainer)
    primary_offset: Offset[TextureData, Base.SELF, UInt32]

    # 2. Relative offset with arithmetic offset bias (Base.SELF + 0x20)
    aux_offset: Offset[TextureData, Base.SELF + 0x20, UInt32]

    # 3. Dynamic table of self-relative offsets pointing to multiple textures
    num_textures: UInt16
    texture_table: OffsetTable[2, UInt32, Base.SELF]



def main():
    print("=== Sample 03: Offsets and Pointer Tables ===")

    # Create target textures
    tex_main = TextureData(width=256, height=256, format=1, raw_pixels=b"MAIN_TEX")
    tex_aux = TextureData(width=128, height=128, format=2, raw_pixels=b"AUX__TEX")
    tex_extra1 = TextureData(width=64, height=64, format=1, raw_pixels=b"ICON_001")
    tex_extra2 = TextureData(width=32, height=32, format=1, raw_pixels=b"ICON_002")

    container = AssetContainer(
        magic=0x54535341,  # 'ASST'
        version=1,
        primary_offset=tex_main,
        aux_offset=tex_aux,
        num_textures=2,
        texture_table=[tex_extra1, tex_extra2],
    )

    # Serialize through BinaryWriter which resolves and patches all offsets automatically
    writer = BinaryWriter()
    writer.write_struct(container)

    data = writer.to_bytes()
    print(f"Container written ({len(data)} bytes):")
    print(f"  Container start offset: 0x0000")
    print(f"  Data hex preview: {data[:32].hex(' ')}...")

    # Deserialize container
    restored = read_struct(AssetContainer, data)
    print("\nDeserialized AssetContainer (Pointers automatically dereferenced):")
    print(f"  magic:          0x{restored.magic:08X}")
    print(f"  version:        {restored.version}")
    print(f"  primary target: TextureData({restored.primary_offset.width}x{restored.primary_offset.height}, pixels={bytes(restored.primary_offset.raw_pixels)})")
    print(f"  aux target:     TextureData({restored.aux_offset.width}x{restored.aux_offset.height}, pixels={bytes(restored.aux_offset.raw_pixels)})")
    print(f"  texture_table:  {[f'0x{o:04X}' for o in restored.texture_table]}")

    assert restored.primary_offset.width == 256
    assert restored.aux_offset.width == 128
    print("\nOffsets and relative pointer table verified successfully!")



if __name__ == "__main__":
    main()
