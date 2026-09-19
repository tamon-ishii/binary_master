"""Tests for Mermaid Markdown manual generation."""

from pathlib import Path

import binary_master
from binary_master import (
    Array,
    BinaryWriter,
    Bits,
    Builder,
    Endian,
    FixedArray,
    LayoutEntry,
    Offset,
    OffsetTable,
    UInt8,
    UInt16,
    UInt32,
    binary_struct,
    generate_html,
    generate_manual,
)
from binary_master.manual import (
    generate_bitfield_packet_diagram,
    generate_mermaid_diagram,
    generate_packet_diagram,
)


@binary_struct(bits=16)
class Flags:
    enable: Bits[1]
    mode: Bits[3]
    priority: Bits[4]
    reserved: Bits[8]


@binary_struct(endian="little")
class Header:
    magic: UInt32
    version: UInt16
    flags: Flags
    image_offset: Offset["Image"]


@binary_struct(endian="little")
class Image:
    width: UInt16
    height: UInt16
    pixels: Array[UInt8]


@binary_struct(endian="big")
class Packet:
    id: UInt16
    count: UInt8
    payload: FixedArray[UInt8, 64]


def test_manual_from_writer_primitives():
    """Test generating a manual from direct BinaryWriter primitive writes."""
    writer = BinaryWriter(default_endian=Endian.LITTLE)
    assert not hasattr(writer, "write_manual")
    writer.write_uint32(0xDEADBEEF, name="magic", desc="Magic header identifier")
    writer.write_uint16(42, name="seq", desc="Sequence counter")
    writer.write_cstring("OK", name="status", desc="Status text")

    md = generate_manual(writer.entries, title="Packet Specification")

    # Assert Markdown structure
    assert "# Packet Specification" in md
    assert "## Overview" in md
    assert "- **Total Size**: 9 bytes (`0x0009`)" in md
    assert "- **Default Endianness**: Little" in md
    assert "- **Total Fields**: 3" in md

    # Assert Mermaid diagram
    assert "```mermaid" in md
    assert "flowchart TD" in md
    assert 'N0["0x0000: magic (UInt32, 4B)"]' in md
    assert 'N1["0x0004: seq (UInt16, 2B)"]' in md
    assert 'N2["0x0006: status (CString, 3B)"]' in md
    assert "N0 --> N1" in md
    assert "N1 --> N2" in md

    # Assert Memory Layout Table
    assert "## Memory Layout Table" in md
    assert "| `0x0000` | 0 | 4 | `magic` | `UInt32` | Little | Magic header identifier |" in md
    assert "| `0x0004` | 4 | 2 | `seq` | `UInt16` | Little | Sequence counter |" in md
    assert "| `0x0006` | 6 | 3 | `status` | `CString` | - | Status text |" in md

    # Assert include_values=True restores Value / Preview column
    md_with_val = generate_manual(writer.entries, title="Packet Specification", include_values=True)
    assert "| `0x0000` | 0 | 4 | `magic` | `UInt32` | Little | `3735928559 (0xDEADBEEF)` | Magic header identifier |" in md_with_val


def test_manual_from_binary_struct():
    """Test generating a manual from binary_struct with bitfields and offset references."""
    flags = Flags(enable=1, mode=5, priority=12, reserved=0xAB)
    img = Image(width=2, height=2, pixels=b"\x01\x02\x03\x04")
    hdr = Header(magic=0x42494E59, version=1, flags=flags, image_offset=img)

    writer = BinaryWriter()
    writer.write_struct(hdr)
    md = generate_manual(writer.entries, title="Image File Format Manual", diagram_direction="LR")

    # Assert Mermaid diagram and subgraphs (clean by default)
    assert "flowchart LR" in md
    assert 'subgraph SG_Header ["Header"]' in md
    assert 'subgraph SG_Image ["Image"]' in md

    # Assert with include_section_offsets=True
    md_offsets = generate_manual(writer.entries, title="Image File Format Manual", diagram_direction="LR", include_section_offsets=True)
    assert 'subgraph SG_Header ["Header (0x0000 - 0x000C, 12B)"]' in md_offsets
    assert 'subgraph SG_Image ["Image (0x000C - 0x0014, 8B)"]' in md_offsets

    # Assert offset pointer relationship in Mermaid diagram
    assert '-.->|"offset: 0x000C"|' in md

    # Assert Bitfield Details section
    assert "## Bitfield Details" in md
    assert "### `flags`" in md
    assert "packet-beta" in md
    assert '0: "enable"' in md
    assert '1-3: "mode"' in md
    assert '4-7: "priority"' in md
    assert '8-15: "reserved"' in md
    assert "| `[0:1]` | `enable` | 1 bit(s) | - |" in md
    assert "| `[1:4]` | `mode` | 3 bit(s) | - |" in md
    assert "| `[4:8]` | `priority` | 4 bit(s) | - |" in md
    assert "| `[8:16]` | `reserved` | 8 bit(s) | - |" in md

    # With include_values=True
    md_val = generate_manual(writer.entries, include_values=True)
    assert '0: "enable (1)"' in md_val
    assert "| `[0:1]` | `enable` | 1 bit(s) | `1 (0x1)` | - |" in md_val


def test_builder_write_to_file(tmp_path: Path):
    """Test writing the specification directly to a markdown file on disk via Builder."""
    file_path = tmp_path / "format_manual.md"

    builder = Builder(title="Binary Specification Manual", default_endian="big")
    builder.add_struct(Packet)
    returned_md = builder.write(file_path)

    assert file_path.exists()
    content = file_path.read_text(encoding="utf-8")
    assert content == returned_md
    assert "# Binary Specification Manual" in content
    assert "Packet" in content


def test_no_write_manual_exists():
    """Verify that write_manual is completely removed from writer, builder, and module."""
    writer = BinaryWriter()
    assert not hasattr(writer, "write_manual")
    assert not hasattr(binary_master, "write_manual")
    builder = Builder()
    assert not hasattr(builder, "write_manual")


def test_generate_bitfield_packet_diagram():
    """Test generating a Mermaid packet-beta diagram for bitfields with gaps and single bits."""
    entry = LayoutEntry(
        offset=0,
        size=1,
        type_name="TestFlags",
        name="flags",
        subfields=[
            {"name": "a", "width": 1, "bit_start": 0, "bit_end": 1, "value": 1},
            {"name": "b", "width": 2, "bit_start": 2, "bit_end": 4, "value": 3},
        ],
    )
    diag = generate_bitfield_packet_diagram(entry)
    assert "packet-beta" in diag
    assert '0: "a"' in diag
    assert '1: "(reserved)"' in diag
    assert '2-3: "b"' in diag
    assert '4-7: "(reserved)"' in diag
    assert "bitsPerRow: 8" in diag

    diag_val = generate_bitfield_packet_diagram(entry, include_values=True)
    assert '0: "a (1)"' in diag_val
    assert '2-3: "b (3)"' in diag_val


def test_generate_packet_diagram():
    """Test generating a full binary layout packet diagram."""
    writer = BinaryWriter()
    writer.write_uint16(0x1234, name="port")
    writer.write_uint8(1, name="proto")
    diag = generate_packet_diagram(writer._entries, title="Network Header")
    assert "packet-beta" in diag
    assert "title Network Header" in diag
    assert '0-15: "port (UInt16)"' in diag
    assert '16-23: "proto (UInt8)"' in diag


def test_generate_manual_diagram_types():
    """Test generate_manual with different diagram_type parameters."""
    flags = Flags(enable=1, mode=1, priority=2, reserved=0)
    img = Image(width=10, height=10, pixels=b"\x00")
    hdr = Header(magic=0x12345678, version=1, flags=flags, image_offset=img)

    writer = BinaryWriter()
    writer.write_struct(hdr)

    # diagram_type="packet"
    md_packet = generate_manual(writer.entries, diagram_type="packet")
    assert "## Structure Diagram (Packet)" in md_packet
    assert "packet-beta" in md_packet

    # diagram_type="both" (default full_packet_diagram=False suppresses top packet diagram when sections exist)
    md_both = generate_manual(writer.entries, diagram_type="both")
    assert "## Structure Diagram\n" in md_both
    assert "## Structure Diagram (Packet)" not in md_both
    # Each section still has its own packet diagram
    assert "### Header" in md_both
    assert "### Image" in md_both

    # diagram_type="both" with full_packet_diagram=True retains the top packet diagram
    md_both_full = generate_manual(writer.entries, diagram_type="both", full_packet_diagram=True)
    assert "## Structure Diagram (Flowchart)" in md_both_full
    assert "## Structure Diagram (Packet)" in md_both_full

    # include_bitfield_diagram=False
    md_no_bf = generate_manual(writer.entries, include_bitfield_diagram=False)
    assert "| Bit Range | Field Name | Width | Description |" in md_no_bf

    md_no_bf_val = generate_manual(writer.entries, include_bitfield_diagram=False, include_values=True)
    assert "| Bit Range | Field Name | Width | Value | Description |" in md_no_bf_val


def test_generate_manual_section_packet_diagrams():
    """Test generating packet diagrams per section under Memory Layout Table."""
    writer = BinaryWriter()
    writer.caption("Header Section")
    writer.write_uint16(0x1234, name="magic")
    writer.write_uint16(1, name="version")

    writer.caption("Body Section")
    writer.write_uint32(100, name="data")

    md = generate_manual(writer.entries, diagram_type="flowchart", section_packet_diagrams=True)
    assert "## Memory Layout Table" in md
    assert "### Header Section\n" in md
    assert "title Header Section Layout" in md
    assert '0-15: "magic (UInt16)"' in md
    assert '16-31: "version (UInt16)"' in md

    assert "### Body Section\n" in md
    assert "title Body Section Layout" in md
    # Notice relative offset: data starts at 0 bit inside Body Section!
    assert '0-31: "data (UInt32)"' in md

    # With include_section_offsets=True
    md_offsets = generate_manual(writer.entries, diagram_type="flowchart", section_packet_diagrams=True, include_section_offsets=True)
    assert "### Header Section (0x0000 - 0x0004, 4B)" in md_offsets
    assert "### Body Section (0x0004 - 0x0008, 4B)" in md_offsets


def test_generate_manual_auto_sections_by_struct_name():
    """Verify that multiple structs automatically divide into sections with docstrings and packet diagrams."""
    @binary_struct
    class SubPayload:
        """SubPayload detailed docstring."""
        x: UInt16
        y: UInt16

    @binary_struct
    class MainHeader:
        """MainHeader detailed docstring."""
        tag: UInt32
        sub: Offset[SubPayload]

    hdr = MainHeader(tag=0x12345678, sub=SubPayload(x=10, y=20))
    writer = BinaryWriter()
    writer.write_struct(hdr)

    # Even without section_packet_diagrams=True, diagram_type="both" automatically produces section packet diagrams!
    md = generate_manual(writer.entries, diagram_type="both")

    # Automatic sections by struct name (clean by default)
    assert "### MainHeader\n" in md
    assert "MainHeader detailed docstring." in md
    assert "title MainHeader Layout" in md

    assert "### SubPayload\n" in md
    assert "SubPayload detailed docstring." in md
    assert "title SubPayload Layout" in md
    assert '0-15: "x (UInt16)"' in md
    assert '16-31: "y (UInt16)"' in md

    # With include_section_offsets=True
    md_offsets = generate_manual(writer.entries, diagram_type="both", include_section_offsets=True)
    assert "### MainHeader (0x0000 - 0x0008, 8B)" in md_offsets
    assert "### SubPayload (0x0008 - 0x000C, 4B)" in md_offsets


def test_generate_manual_lang_ja():
    """Test generating Markdown manual with Japanese localization (lang='ja')."""
    flags = Flags(enable=1, mode=5, priority=12, reserved=0xAB)
    hdr = Header(magic=0x42494E59, version=1, flags=flags, image_offset=None)

    writer = BinaryWriter()
    writer.write_struct(hdr)

    md = generate_manual(writer.entries, title="画像ヘッダ仕様", lang="ja", diagram_type="both")

    # Japanese Headings & Overview
    assert "# 画像ヘッダ仕様" in md
    assert "## 概要" in md
    assert "- **合計サイズ**:" in md
    assert "- **デフォルトエンディアン**:" in md
    assert "- **合計フィールド数**:" in md

    # Japanese Diagrams
    assert "## 構造図 (フローチャート)" in md
    assert "## 構造図 (パケット図)" in md

    # Japanese Memory Layout Table
    assert "## メモリレイアウト表" in md
    assert "| オフセット (16進) | オフセット (10進) | サイズ (B) | フィールド名 | 型 | エンディアン | 説明 |" in md

    # Japanese Bitfield Details
    assert "## ビットフィールド詳細" in md
    assert "| ビット範囲 | フィールド名 | ビット幅 | 説明 |" in md
    assert "| `[0:1]` | `enable` | 1 bit |" in md


def test_writer_and_html_lang_ja():
    """Test BinaryWriter to_markdown and to_html with lang='ja'."""
    writer = BinaryWriter(lang="ja")
    writer.write_uint16(0x1234, name="magic", desc="マジックコード")
    writer.write_uint8(1, name="status", desc="ステータス")

    md = writer.to_markdown()
    assert "## 概要" in md
    assert "| オフセット (16進) | オフセット (10進) | サイズ (B) | フィールド名 | 型 | エンディアン | 説明 |" in md
    assert "マジックコード" in md

    html = writer.to_html()
    assert '<html lang="ja"' in html
    assert "バイナリ仕様書" in html
    assert "合計サイズ:" in html
    assert "フィールド名" in html
    assert "未マッピング / パディング" in html



def test_builder_lang_ja():
    """Test Builder with lang='ja' generating Japanese markdown and html."""
    builder = Builder(title="パケット構造定義", lang="ja")
    builder.add_struct(Packet)

    md = builder.build()
    assert "# パケット構造定義" in md
    assert "## 概要" in md
    assert "## 構造図 (フローチャート)" in md
    assert "## データ構造とレイアウト" in md
    assert "### 構造体 `Packet` (Packet)" in md
    assert "| 相対オフセット | サイズ (B) | フィールド名 | 型 | エンディアン | 説明 |" in md


def test_resolve_language_and_auto_locale(monkeypatch):
    """Test resolve_language function and automatic locale detection with lang='auto'."""
    from binary_master.manual import resolve_language

    # Explicit languages
    assert resolve_language("ja") == "ja"
    assert resolve_language("JA") == "ja"
    assert resolve_language("jp") == "ja"
    assert resolve_language("en") == "en"
    assert resolve_language("EN") == "en"

    # Auto mode with Japanese locale
    monkeypatch.setenv("LANG", "ja_JP.UTF-8")
    monkeypatch.delenv("LC_ALL", raising=False)
    monkeypatch.delenv("LC_MESSAGES", raising=False)
    assert resolve_language("auto") == "ja"
    assert resolve_language() == "ja"

    writer = BinaryWriter()  # default lang is "auto"
    writer.write_uint16(0x1234, name="magic")
    md_ja = generate_manual(writer.entries)
    assert "## 概要" in md_ja
    assert "- **合計サイズ**:" in md_ja

    # Auto mode with English locale
    monkeypatch.setenv("LANG", "en_US.UTF-8")
    assert resolve_language("auto") == "en"
    assert resolve_language() == "en"

    md_en = generate_manual(writer.entries)
    assert "## Overview" in md_en
    assert "- **Total Size**:" in md_en


def test_offset_table_manual_omits_intermediate_entries():
    """Verify that OffsetTable manual displays only first and last offsets, omitting intermediate ones in both tables and packet diagrams."""
    @binary_struct
    class LargeTableStruct:
        magic: UInt32
        count: UInt32
        offsets: OffsetTable[10, UInt32]

    md = generate_manual(LargeTableStruct, lang="en")
    # First entry offsets[0] and last entry offsets[9] are present
    assert "| `offsets[0]` |" in md
    assert "| `offsets[9]` |" in md
    # Intermediate entries are omitted with '...'
    assert "| `offsets[1]` |" not in md
    assert "| `offsets[5]` |" not in md
    assert "| `offsets[8]` |" not in md
    assert "| ... | ... | ... | ... | ... | ... | ... |" in md

    # Packet diagram aggregates the table into a clean slice without '...'
    assert 'offsets (OffsetTable[10, UInt32], 40B)' in md
    assert ': "..."' not in md

    # HTML manual test
    html = generate_html(LargeTableStruct, lang="en")
    assert "offsets[0]" in html
    assert "offsets[9]" in html
    assert "table-row-omitted" in html


def test_offset_table_small_not_omitted():
    """Verify that small OffsetTable (2 entries) retains both entries without omission."""
    @binary_struct
    class SmallTableStruct:
        magic: UInt32
        offsets: OffsetTable[2, UInt32]

    md = generate_manual(SmallTableStruct, lang="en")
    assert "| `offsets[0]` |" in md
    assert "| `offsets[1]` |" in md
    assert "| ... |" not in md


def test_anonymous_offset_table_title():
    """Verify that anonymous OffsetTable receives proper title ('オフセットテーブル' / 'Offset Table')."""
    from binary_master import BinaryWriter

    # Japanese manual
    w = BinaryWriter()
    w.set_caption("ヘッダー")
    w.write_uint32(0x1234)
    w.set_caption("")  # anonymous
    w.write_offset_table(5)
    w.set_caption("ボディ")
    w.write_uint32(0x5678)

    md_ja = generate_manual(w.entries, lang="ja")
    assert "### オフセットテーブル\n" in md_ja
    assert 'subgraph SG_grp_1 ["オフセットテーブル"]' in md_ja
    assert "title オフセットテーブル レイアウト" in md_ja

    # With include_section_offsets=True
    md_ja_offsets = generate_manual(w.entries, lang="ja", include_section_offsets=True)
    assert "### オフセットテーブル (0x0004 - 0x0018, 20B)" in md_ja_offsets
    assert '["オフセットテーブル (0x0004 - 0x0018, 20B)"]' in md_ja_offsets

    # English manual
    md_en = generate_manual(w.entries, lang="en")
    assert "### Offset Table\n" in md_en
    assert '["Offset Table"]' in md_en
    assert "title Offset Table Layout" in md_en


def test_structure_diagram_repeated_elements_omitted():
    """Verify that repeated items are aggregated cleanly into a single block in packet diagram without '...'."""
    from binary_master import binary_struct

    @binary_struct
    class SubItem:
        width: UInt16
        height: UInt16
        pixels: FixedArray[UInt8, 4]

    w = BinaryWriter()
    for _ in range(10):
        w.write_struct(SubItem(width=100, height=200, pixels=[1, 2, 3, 4]))

    md = generate_manual(w.entries, diagram_type="packet")
    # Clean repeated block summary without '...'
    assert '0-639: "SubItem 🔁 x10 (80B)"' in md
    assert ': "..."' not in md


def test_flowchart_indexed_omission():
    """Verify that flowchart aggregates indexed entries cleanly without '...' nodes."""
    w = BinaryWriter()
    w.write_offset_table(10)

    f_diag = generate_mermaid_diagram(w.entries)
    assert '["0x0000: offsets (OffsetTable[10, UInt32], 40B)"]' in f_diag
    assert '["..."]' not in f_diag


def test_packet_diagram_large_data_summarization():
    """Verify that large raw data blocks and large arrays are automatically summarized with byte sizes."""
    from binary_master import binary_struct

    # 1. Raw bytes >= 64B
    w = BinaryWriter()
    w.write_uint32(0x12345678, name="magic")
    w.write_bytes(b"\x00" * 10000, name="payload")
    w.write_uint32(0x87654321, name="checksum")

    diag = generate_packet_diagram(w.entries)
    assert '0-31: "magic (UInt32)"' in diag
    assert '32-80031: "payload (10000B)"' in diag
    assert '80032-80063: "checksum (UInt32)"' in diag

    # 2. Anonymous raw bytes >= 64B
    w2 = BinaryWriter()
    w2.write_bytes(b"\x00" * 256)
    diag2 = generate_packet_diagram(w2.entries)
    assert '0-2047: "Bytes (256B)"' in diag2

    # 3. FixedArray >= 64B with type name and byte size
    @binary_struct
    class LargeBlockStruct:
        magic: UInt32
        data: FixedArray[UInt8, 1024]
        checksum: UInt32

    inst = LargeBlockStruct(magic=1, data=b"\xaa" * 1024, checksum=2)
    w3 = BinaryWriter()
    w3.write_struct(inst)
    diag3 = generate_packet_diagram(w3.entries)
    assert '0-31: "magic (UInt32)"' in diag3
    assert '32-8223: "data (FixedArray[UInt8, 1024], 1024B)"' in diag3
    assert '8224-8255: "checksum (UInt32)"' in diag3

    # 4. Large pad entry (>= 64B) gets size tag
    w4 = BinaryWriter()
    w4.write_uint32(0x11223344, name="head")
    w4.pad(128)
    w4.write_uint32(0x55667788, name="tail")
    diag4 = generate_packet_diagram(w4.entries)
    assert '0-31: "head (UInt32)"' in diag4
    assert '32-1055: "padding (Padding[128], 128B)"' in diag4
    assert '1056-1087: "tail (UInt32)"' in diag4

    # 4b. Large unallocated gap (>= 64B) gets size tag
    w4b = BinaryWriter()
    w4b.write_uint32(0x11223344, name="head")
    w4b.seek(132)  # skip 128 bytes without creating entry
    w4b.write_uint32(0x55667788, name="tail")
    diag4b = generate_packet_diagram(w4b.entries)
    assert '32-1055: "(padding, 128B)"' in diag4b

    # 5. Custom threshold
    w5 = BinaryWriter()
    w5.write_bytes(b"\x00" * 32, name="small_buf")
    # Default (64) -> not summarized
    diag5_def = generate_packet_diagram(w5.entries)
    assert '0-255: "small_buf (Bytes[32])"' in diag5_def
    # threshold=16 -> summarized
    diag5_cust = generate_packet_diagram(w5.entries, large_data_threshold=16)
    assert '0-255: "small_buf (32B)"' in diag5_cust

    # 6. Manual generation integration
    md = w.to_markdown(diagram_type="packet")
    assert '32-80031: "payload (10000B)"' in md


def test_full_packet_diagram_and_section_packets():
    """Test that when multiple structs/sections exist, the top packet diagram is omitted by default

    while per-struct packet diagrams are preserved under section headings.
    """
    writer = BinaryWriter(lang="ja")
    writer.caption("ヘッダー部", desc="ヘッダー説明")
    writer.write_uint32(0x12345678, name="magic")

    writer.caption("ボディ部", desc="ボディ説明")
    writer.write_uint16(100, name="length")
    writer.write_uint16(200, name="checksum")

    # 1. Default (full_packet_diagram=False):
    # Top has flowchart with title "## 構造図", no top packet diagram.
    md_default = writer.to_markdown(diagram_type="both")
    assert "## 構造図\n" in md_default
    assert "## 構造図 (フローチャート)" not in md_default
    assert "## 構造図 (パケット図)" not in md_default

    # Both sections must retain their own packet diagrams
    assert "### ヘッダー部" in md_default
    assert "### ボディ部" in md_default
    assert "title ヘッダー部 レイアウト" in md_default
    assert "title ボディ部 レイアウト" in md_default

    # 2. full_packet_diagram=True:
    # Top retains both flowchart and packet diagrams.
    md_full = writer.to_markdown(diagram_type="both", full_packet_diagram=True)
    assert "## 構造図 (フローチャート)\n" in md_full
    assert "## 構造図 (パケット図)\n" in md_full
    assert "title バイナリ仕様書 レイアウト" in md_full
    assert "### ヘッダー部" in md_full
    assert "title ヘッダー部 レイアウト" in md_full

    # 3. HTML output with full_packet_diagram=False / True
    html_default = writer.to_html(diagram_type="both", full_packet_diagram=False)
    assert "バイナリ仕様書 レイアウト" not in html_default


def test_packet_diagram_compact_tables():
    """Verify that OffsetTable is smartly compacted in packet diagrams by default and expandable via compact_tables=False."""
    @binary_struct
    class HugeOffsetTableStruct:
        magic: UInt32
        offset_table: OffsetTable[100, UInt16]
        checksum: UInt32

    # Default: compact_tables=True
    md_compact = generate_manual(HugeOffsetTableStruct, lang="ja")
    assert '0-31: "magic (UInt32)"' in md_compact
    assert '32-63: "offset_table (OffsetTable[100, UInt16], 200B) [縮約]"' in md_compact
    assert '64-95: "checksum (UInt32)"' in md_compact

    # English tag: [compact]
    md_compact_en = generate_manual(HugeOffsetTableStruct, lang="en")
    assert '32-63: "offset_table (OffsetTable[100, UInt16], 200B) [compact]"' in md_compact_en

    # Explicit compact_tables=False expands to physical bits
    md_full = generate_manual(HugeOffsetTableStruct, compact_tables=False, lang="ja")
    assert '32-1631: "offset_table (OffsetTable[100, UInt16], 200B)"' in md_full
    assert '1632-1663: "checksum (UInt32)"' in md_full












