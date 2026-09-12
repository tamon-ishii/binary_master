"""Tests for Mermaid Markdown manual generation."""

from pathlib import Path
import pytest

from binary_master import (
    BinaryWriter,
    Endian,
    UInt8,
    UInt16,
    UInt32,
    Offset,
    Array,
    FixedArray,
    Bits,
    binary_struct,
    generate_manual,
    Builder,
    LayoutEntry,
    generate_bitfield_packet_diagram,
    generate_packet_diagram,
)
import binary_master



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

    # Assert Mermaid diagram and subgraphs
    assert "flowchart LR" in md
    assert 'subgraph SG_Header ["Header (0x0000 - 0x000C, 12B)"]' in md
    assert 'subgraph SG_Image ["Image (0x000C - 0x0014, 8B)"]' in md

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

    # diagram_type="both"
    md_both = generate_manual(writer.entries, diagram_type="both")
    assert "## Structure Diagram (Flowchart)" in md_both
    assert "## Structure Diagram (Packet)" in md_both

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
    assert "### Header Section (0x0000 - 0x0004, 4B)" in md
    assert "title Header Section Layout" in md
    assert '0-15: "magic (UInt16)"' in md
    assert '16-31: "version (UInt16)"' in md

    assert "### Body Section (0x0004 - 0x0008, 4B)" in md
    assert "title Body Section Layout" in md
    # Notice relative offset: data starts at 0 bit inside Body Section!
    assert '0-31: "data (UInt32)"' in md


