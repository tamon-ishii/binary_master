"""Tests for repeating sections, explicit repetition metadata, and section name arguments."""

from binary_master import (
    BinaryWriter,
    UInt8,
    UInt16,
    UInt32,
    binary_struct,
    generate_mermaid_diagram,
    write_struct,
)


@binary_struct
class Header:
    magic: UInt32
    chunk_count: UInt16


@binary_struct
class Chunk:
    chunk_id: UInt32
    data_size: UInt32


@binary_struct
class Footer:
    checksum: UInt32


def test_write_struct_section_optional_default():
    """Verify section defaults to empty string and existing behavior is untouched."""
    writer = BinaryWriter()
    h = Header(magic=0x12345678, chunk_count=2)
    # Called without section argument
    writer.write_struct(h)
    assert writer.current_caption is None
    assert len(writer.entries) == 2
    assert writer.entries[0].caption is None


def test_write_struct_section_grouping():
    """Verify multiple write_struct calls with same section are grouped."""
    writer = BinaryWriter()
    h = Header(magic=0x12345678, chunk_count=2)
    c1 = Chunk(chunk_id=1, data_size=100)
    c2 = Chunk(chunk_id=2, data_size=200)

    writer.write_struct(h, section="HeaderSection")
    assert writer.current_caption == "HeaderSection"
    assert writer.entries[0].caption == "HeaderSection"
    assert writer.entries[1].caption == "HeaderSection"

    writer.write_struct(c1, section="ChunksSection", repeat="chunk_count")
    writer.write_struct(c2, section="ChunksSection", repeat="chunk_count")

    assert writer.current_caption == "ChunksSection"
    assert writer.entries[2].caption == "ChunksSection"
    assert writer.entries[3].caption == "ChunksSection"
    assert writer.entries[4].caption == "ChunksSection"
    assert writer.entries[5].caption == "ChunksSection"

    md = writer.to_markdown()
    assert "### HeaderSection" in md
    assert "### ChunksSection" in md
    assert "🔁 **繰り返し**: `chunk_count` 回" in md
    assert "**1要素サイズ**: `8` bytes" in md
    assert "**サンプルデータ**: 2 件" in md
    assert "Relative Offset" in md
    assert "+0x00" in md
    assert "+0x04" in md


def test_single_loop_explicit_repeat():
    """Verify 1-iteration loop in sample data is recognized as repeated when repeat metadata is set."""
    writer = BinaryWriter()
    c = Chunk(chunk_id=0xAA, data_size=42)
    # Only 1 chunk written, but repeat metadata is specified!
    writer.write_struct(c, section="SingleChunkLoop", repeat="chunk_count")

    md = writer.to_markdown()
    assert "### SingleChunkLoop" in md
    assert "🔁 **繰り返し**: `chunk_count` 回" in md
    assert "**1要素サイズ**: `8` bytes" in md
    assert "**サンプルデータ**: 1 件" in md
    assert "Relative Offset" in md
    assert "+0x00" in md
    assert "+0x04" in md

    # Check Mermaid diagram
    mermaid = generate_mermaid_diagram(writer.entries)
    assert "SingleChunkLoop 🔁 xchunk_count" in mermaid
    assert "+0x00: chunk_id" in mermaid
    assert "+0x04: data_size" in mermaid


def test_repeat_context_manager():
    """Verify with writer.repeat('Section', count=N) scopes repetition and restores caption."""
    writer = BinaryWriter()
    writer.caption("FileHeader")
    writer.write_struct(Header(magic=0x42, chunk_count=3))

    with writer.repeat("DataChunks", count=3, desc="Array of chunks"):
        for i in range(3):
            writer.write_struct(Chunk(chunk_id=i, data_size=10 * i))

    # After exiting with block, caption is restored
    assert writer.current_caption == "FileHeader"
    assert writer.current_caption_repeat is None

    writer.write_struct(Footer(checksum=0x99), section="FileFooter")

    md = writer.to_markdown()
    assert "### FileHeader" in md
    assert "### DataChunks" in md
    assert "Array of chunks" in md
    assert "🔁 **繰り返し**: 3 回" in md
    assert "**サンプルデータ**: 3 件" in md
    assert "### FileFooter" in md

    # Check Mermaid diagram does not duplicate chunk nodes 3 times
    mermaid = generate_mermaid_diagram(writer.entries)
    assert "DataChunks 🔁 x3" in mermaid
    # Only 1 unit of chunk nodes should be present in the subgraph
    assert mermaid.count("+0x00: chunk_id") == 1
    assert mermaid.count("+0x04: data_size") == 1


def test_write_repeated_method():
    """Verify writer.write_repeated() correctly serializes list of items and generates spec."""
    writer = BinaryWriter()
    chunks = [
        Chunk(chunk_id=1, data_size=50),
        Chunk(chunk_id=2, data_size=60),
        Chunk(chunk_id=3, data_size=70),
    ]
    writer.write_repeated(chunks, section="ChunkList", count="total_chunks")

    md = writer.to_markdown()
    assert "### ChunkList" in md
    assert "🔁 **繰り返し**: `total_chunks` 回" in md
    assert "**サンプルデータ**: 3 件" in md
    assert "Relative Offset" in md


def test_top_level_write_struct_with_section_and_repeat():
    """Verify binary_master.write_struct top-level function supports section and repeat."""
    writer = BinaryWriter()
    c = Chunk(chunk_id=5, data_size=500)
    write_struct(c, writer=writer, section="TopSection", repeat="N")

    assert writer.current_caption == "TopSection"
    assert writer.current_caption_repeat == "N"
    md = writer.to_markdown()
    assert "### TopSection" in md
    assert "🔁 **繰り返し**: `N` 回" in md


def test_write_variant_with_section_and_repeat():
    """Verify write_variant supports section and repeat arguments."""
    @binary_struct
    class TypeA:
        tag: UInt8
        val_a: UInt16

    @binary_struct
    class TypeB:
        tag: UInt8
        val_b: UInt32

    writer = BinaryWriter()
    candidates = {0x01: TypeA, 0x02: TypeB}
    writer.write_variant(
        TypeA(tag=0x01, val_a=100),
        candidates=candidates,
        tag_field="tag",
        section="PolymorphicItems",
        repeat="item_count",
    )

    md = writer.to_markdown()
    assert "### PolymorphicItems" in md
    assert "🔁 **繰り返し**: `item_count` 回" in md
    assert "[Variant]" in md
    assert "TypeA" in md
    assert "TypeB" in md


def test_bitfield_deduplication_in_repeated_chunks():
    """Verify bitfields within repeated structures are documented only once in Bitfield Details."""
    from binary_master import Bits

    @binary_struct(bits=16)
    class StatusFlags:
        active: Bits[1]
        ready: Bits[1]
        reserved: Bits[14]

    @binary_struct
    class FlaggedItem:
        item_id: UInt16
        flags: StatusFlags

    writer = BinaryWriter()
    with writer.repeat("FlaggedItems", count=5):
        for i in range(5):
            writer.write_struct(FlaggedItem(item_id=i, flags=StatusFlags(active=1, ready=0, reserved=0)))

    md = writer.to_markdown()
    # "### `flags`" should appear only once under Bitfield Details
    assert md.count("### `flags`") == 1
    assert "active" in md
    assert "ready" in md


def test_repeat_minus_one_indefinite():
    """Verify repeat=-1 represents indefinite repetitions without needing a section name."""
    writer = BinaryWriter()
    c1 = Chunk(chunk_id=1, data_size=10)
    c2 = Chunk(chunk_id=2, data_size=20)

    # Note: section is completely omitted!
    writer.write_struct(c1, repeat=-1)
    writer.write_struct(c2, repeat=-1)

    assert writer.current_caption == "Chunk"
    assert writer.current_caption_repeat == -1

    md = writer.to_markdown()
    assert "### Chunk" in md
    assert "🔁 **繰り返し**: 不定回数 (0回以上 / 可変)" in md
    assert "**1要素サイズ**: `8` bytes" in md
    assert "**サンプルデータ**: 2 件" in md
    assert "Relative Offset" in md
    assert "+0x00" in md

    # Check Mermaid diagram
    mermaid = generate_mermaid_diagram(writer.entries)
    assert "Chunk 🔁 (不定回数)" in mermaid


def test_repeat_string_num_chunk_without_section():
    """Verify repeat='num_chunk' works directly on write_struct without section."""
    writer = BinaryWriter()
    c = Chunk(chunk_id=0xFF, data_size=1024)

    # section is omitted, repeat is a variable name string
    writer.write_struct(c, repeat="num_chunk")

    assert writer.current_caption == "Chunk"
    assert writer.current_caption_repeat == "num_chunk"

    md = writer.to_markdown()
    assert "### Chunk" in md
    assert "🔁 **繰り返し**: `num_chunk` 回" in md
    assert "**1要素サイズ**: `8` bytes" in md
    assert "**サンプルデータ**: 1 件" in md
    assert "Relative Offset" in md
