"""Sample 03: Relative Offsets, Pointer Tables, and Self-Relative Bases.

Demonstrates:
- Pointer offsets with Offset[Target]
- Self-relative offsets using Base.SELF and arithmetic (Base.SELF + 0x10)
- Dynamic pointer tables with OffsetTable["num_textures", Base.SELF]
- Automatic deferred patching during serialization
- Procedural offset table reservation using BinaryWriter.write_offset_table(spec_count="num_chunks")
- Scoped namespaces with with writer.namespace("chunk", auto_id=True) for NamedOffset
"""

from binary_master import (
    Base,
    BinaryWriter,
    FixedArray,
    NamedOffset,
    Offset,
    OffsetTable,
    UInt8,
    UInt16,
    UInt32,
    binary_struct,
    generate_manual,
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


# Container using relative offsets and dynamic offset tables
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
    #    Uses "num_textures" to link count to the preceding field
    num_textures: UInt16
    texture_table: OffsetTable["num_textures", UInt32, Base.SELF]



def main():
    print("=== Sample 03: Offsets and Pointer Tables ===")

    # -------------------------------------------------------------
    # Part 1: Declarative OffsetTable with @binary_struct
    # -------------------------------------------------------------
    print("\n--- Part 1: Declarative @binary_struct OffsetTable ---")
    # 1. ヘッダーを先に宣言（Offset / OffsetTable / 要素数カウントはすべて省略可能）
    container = AssetContainer(
        magic=0x54535341,  # 'ASST'
        version=1,
    )

    # 2. 実体オブジェクトを作成して後からセット
    container.primary_offset = TextureData(width=256, height=256, format=1, raw_pixels=b"MAIN_TEX")
    container.aux_offset = TextureData(width=128, height=128, format=2, raw_pixels=b"AUX__TEX")

    # 3. OffsetTable にもリストを直接代入（num_textures はリストの長さから自動補完）
    container.texture_table = [
        TextureData(width=64, height=64, format=1, raw_pixels=b"ICON_001"),
        TextureData(width=32, height=32, format=1, raw_pixels=b"ICON_002"),
    ]

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

    # -------------------------------------------------------------
    # Part 2: Procedural write_offset_table with spec_count
    # -------------------------------------------------------------
    print("\n--- Part 2: Procedural write_offset_table with spec_count ---")
    pw = BinaryWriter()
    pw.write_cstring("ARCHIVE", name="magic", desc="Archive magic")
    pw.write_uint16(3, name="num_chunks", desc="Number of chunks")

    # Reserve offset table inside a set_caption context block
    # Section title, description, and spec_count metadata are cleanly centralized!
    with pw.set_caption("chunk_offsets", desc="Offset table pointing to chunks", spec_count="num_chunks"):
        table = pw.write_offset_table(count=3, offset_size=4)

    # Write each chunk payload and record its start offset in the table
    for i in range(3):
        pos = pw.tell()
        table[i] = pos
        pw.write_cstring(f"Payload data for chunk #{i}", name=f"chunk_data_{i}")

    pdata = pw.to_bytes()
    print(f"Procedural archive written ({len(pdata)} bytes).")
    print(f"Recorded offsets: {[hex(table.get_target_offset(i)) for i in range(3)]}")

    # Generate Markdown manual showing aggregated offsets[i] with spec_count
    manual_md = generate_manual(pw.entries, title="Procedural Offset Archive")
    print("\nGenerated Manual Preview (Offsets section):")
    for line in manual_md.splitlines():
        if "### chunk_offsets" in line or "🔁" in line or "chunk_offsets[i]" in line:
            print("  ", line)

    # -------------------------------------------------------------
    # Part 3: NamedOffset with Scoped Namespaces (with writer.namespace)
    # -------------------------------------------------------------
    print("\n--- Part 3: NamedOffset with Scoped Namespaces (with writer.namespace) ---")

    @binary_struct
    class ChunkHeader:
        chunk_id: UInt16
        # 汎用的なキー名 "payload" で宣言
        payload_offset: NamedOffset["payload"]

    nw = BinaryWriter()

    # チャンク0: with nw.namespace("chunk", auto_id=True) で "chunk_0" スコープ化
    chunk0_pos = nw.tell()
    with nw.namespace("chunk", auto_id=True) as ns0:
        nw.write_struct(ChunkHeader(chunk_id=101))
        nw.write_cstring("Metadata for chunk 0 (variable length)...")
        # write_named_offset で実体構造体を書き込み、"chunk_0/payload" を自動バックパッチ！
        nw.write_named_offset("payload", TextureData(width=64, height=64, format=1, raw_pixels=b"TILE_001"))

    # チャンク1: "chunk_1" スコープ化（同一のキー名 "payload" でも衝突しない！）
    chunk1_pos = nw.tell()
    with nw.namespace("chunk", auto_id=True) as ns1:
        nw.write_struct(ChunkHeader(chunk_id=102))
        nw.write_cstring("Metadata for chunk 1 (different length)...")
        nw.write_named_offset("payload", TextureData(width=32, height=32, format=2, raw_pixels=b"TILE_002"))

    ndata = nw.to_bytes()
    print(f"Scoped NamedOffset stream written ({len(ndata)} bytes).")

    # デシリアライズ検証
    hdr0 = read_struct(ChunkHeader, ndata[chunk0_pos:chunk0_pos + 6])
    tex0 = read_struct(TextureData, ndata[hdr0.payload_offset:hdr0.payload_offset + 13])
    print(f"  Chunk 0: id={hdr0.chunk_id}, payload_offset=0x{hdr0.payload_offset:04X}, tex={tex0.width}x{tex0.height}")

    hdr1 = read_struct(ChunkHeader, ndata[chunk1_pos:chunk1_pos + 6])
    tex1 = read_struct(TextureData, ndata[hdr1.payload_offset:hdr1.payload_offset + 13])
    print(f"  Chunk 1: id={hdr1.chunk_id}, payload_offset=0x{hdr1.payload_offset:04X}, tex={tex1.width}x{tex1.height}")

    assert hdr0.chunk_id == 101 and tex0.width == 64
    assert hdr1.chunk_id == 102 and tex1.width == 32

    print("\nAll offset patterns (Offset, OffsetTable, NamedOffset with namespace) verified successfully!")


if __name__ == "__main__":
    main()
