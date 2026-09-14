import pytest
from binary_master import (
    binary_struct,
    UInt16,
    UInt32,
    OffsetTable,
    BinaryWriter,
    BinaryReader,
    generate_manual,
    to_c_struct,
    inspect_struct_layout,
)


def test_offset_table_variable_declarative():
    @binary_struct
    class ChunkData:
        data: UInt32

    @binary_struct
    class DynamicHeader:
        num_chunk: UInt16
        offsets: OffsetTable["num_chunk", UInt32]

    # Serialization with targets
    c1 = ChunkData(data=0x11111111)
    c2 = ChunkData(data=0x22222222)
    c3 = ChunkData(data=0x33333333)

    header = DynamicHeader(num_chunk=3, offsets=[c1, c2, c3])
    writer = BinaryWriter()
    writer.write_struct(header)

    data = writer.to_bytes()
    # Layout:
    # 0x00: num_chunk (2B)
    # 0x02: offset 0 (4B) -> 14 (0x000E)
    # 0x06: offset 1 (4B) -> 18 (0x0012)
    # 0x0A: offset 2 (4B) -> 22 (0x0016)
    # 0x0E: c1 data (4B)
    # 0x12: c2 data (4B)
    # 0x16: c3 data (4B)
    assert len(data) == 2 + 3 * 4 + 3 * 4  # 26 bytes

    # Deserialization of header
    reader = BinaryReader(data)
    unpacked_hdr = DynamicHeader.from_bytes(reader)
    assert unpacked_hdr.num_chunk == 3
    assert unpacked_hdr.offsets == [14, 18, 22]

    # Inspect layout / dummy
    layout = inspect_struct_layout(DynamicHeader)
    assert len(layout) == 2
    assert layout[0].name == "num_chunk"
    assert layout[1].caption_repeat == "num_chunk"

    # C header generation
    c_code = to_c_struct(DynamicHeader)
    assert "uint32_t offsets[num_chunk];" in c_code

    # Manual generation with repeated offset table
    manual = generate_manual(writer.entries, title="Dynamic Table Manual")
    assert "🔁 **繰り返し**: `num_chunk` 回" in manual
    assert "offsets[i]" in manual


def test_offset_table_procedural_spec_count():
    writer = BinaryWriter()
    writer.write_uint16(5, name="num_chunk", desc="Number of chunks")
    table = writer.write_offset_table(
        count=5,
        offset_size=4,
        name="offsets",
        desc="Table of chunk offsets",
        spec_count="num_chunk",
    )
    for i in range(5):
        pos = writer.tell()
        table.set_offset(i, pos)
        writer.write_uint32(i * 100, name=f"chunk_{i}")

    manual = generate_manual(writer.entries, title="Procedural Offset Manual")
    assert "🔁 **繰り返し**: `num_chunk` 回" in manual
    assert "offsets[i]" in manual
    assert "🔁 xnum_chunk" in manual


def test_offset_table_procedural_repeat_alias():
    writer = BinaryWriter()
    table = writer.write_offset_table(
        count=3,
        repeat="chunk_num",
    )
    assert writer.entries[0].caption_repeat == "chunk_num"
