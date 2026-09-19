"""Tests for schema-first Builder and automated reader."""

import io
from pathlib import Path

import pytest

from binary_master import (
    BinaryWriter,
    Bits,
    Builder,
    FixedArray,
    UInt8,
    UInt16,
    UInt32,
    binary_struct,
)
from binary_master.builder import BuilderReadResult


# Sample structs for testing
@binary_struct
class Header:
    magic: UInt32
    version: UInt16
    msg_type: UInt16
    payload_size: UInt32


@binary_struct
class TextPayload:
    encoding: UInt16
    length: UInt16
    content: FixedArray[UInt8, 8]


@binary_struct
class AudioPayload:
    sample_rate: UInt32
    channels: UInt8
    bit_depth: UInt8


@binary_struct
class Item:
    item_id: UInt16
    value: UInt16


@binary_struct(bits=8)
class StatusFlags:
    enabled: Bits[1]
    priority: Bits[3]
    reserved: Bits[4]


@binary_struct
class OptionalFooter:
    checksum: UInt32


def test_builder_chaining_and_basic_build():
    """Test registering components and generating markdown output."""
    builder = Builder(
        title="Protocol Specification",
        version="1.0.0",
        description="A test binary communication protocol.",
        default_endian="little",
    )

    builder.add_document("Architecture", "This protocol is divided into headers and payloads.")
    builder.add_struct(Header, name="MainHeader", desc="Header of every message")
    builder.add_choice(
        name="payload",
        tag_field="msg_type",
        variants={
            1: (TextPayload, "Plaintext message payload"),
            2: (AudioPayload, "Audio stream payload"),
        },
        desc="Dynamic payload dispatched by msg_type",
    )
    builder.add_struct(
        OptionalFooter,
        name="Footer",
        desc="Optional trailing checksum",
        condition="has_footer == True",
    )

    md = builder.build()

    # Check headers and overview
    assert "# Protocol Specification" in md
    assert "**Version**: `1.0.0`" in md
    assert "- **Default Endianness**: Little" in md
    assert "A test binary communication protocol." in md


    # Check narrative chapter
    assert "## Architecture" in md
    assert "This protocol is divided into headers and payloads." in md

    # Check flowchart
    assert "```mermaid\nflowchart TD" in md
    assert "MainHeader" in md
    assert "Choice: payload (msg_type?)" in md
    assert "TextPayload" in md
    assert "AudioPayload" in md
    assert 'Cond_E3_Footer{"has_footer == True?"}' in md

    # Check layout tables
    assert "### Struct `MainHeader` (Header)" in md
    assert "`+0x00`" in md
    assert "`magic`" in md
    assert "`payload_size`" in md

    # Check choice section
    assert "### Choice Branch: `payload`" in md
    assert "Dispatched by field: `msg_type`" in md
    assert "[Variant] Tag `0x01`: `TextPayload`" in md
    assert "[Variant] Tag `0x02`: `AudioPayload`" in md
    assert "Plaintext message payload" in md


def test_builder_write_file(tmp_path: Path):
    """Test builder.write() to a file and stream."""
    builder = Builder(title="File Writing Test")
    builder.add_struct(Header)

    out_file = tmp_path / "manual.md"
    res = builder.write(out_file)

    assert out_file.exists()
    assert out_file.read_text(encoding="utf-8") == res
    assert "Struct `Header` (Header)" in res

    # Test writing to string stream
    buf = io.StringIO()
    builder.write(buf)
    assert "Struct `Header` (Header)" in buf.getvalue()

    # Ensure write_manual is removed
    assert not hasattr(builder, "write_manual")


def test_builder_with_bitfield_diagram():
    """Test that bitfields in structs are documented and packet diagrams generated."""
    builder = Builder(title="Bitfield Protocol")
    builder.add_struct(StatusFlags, name="Flags")

    md = builder.build(include_bitfield_diagram=True)

    assert "## Bitfield Details" in md
    assert "StatusFlags" in md
    assert "packet-beta" in md
    assert "enabled" in md
    assert "priority" in md


def test_builder_automated_read_choice():
    """Test automated deserialization of structs and choices from binary bytes."""
    builder = Builder("Dynamic Protocol")
    builder.add_struct(Header, name="header")
    builder.add_choice(
        name="payload",
        tag_field="msg_type",
        variants={
            1: TextPayload,
            2: AudioPayload,
        },
    )

    # 1. Test msg_type = 1 (TextPayload)
    w1 = BinaryWriter()
    w1.write_struct(Header(magic=0xCAFEBABE, version=1, msg_type=1, payload_size=12))
    w1.write_struct(TextPayload(encoding=1, length=4, content=b"TEST\x00\x00\x00\x00"))
    data1 = w1.to_bytes()

    res1 = builder.read(data1)
    assert isinstance(res1, BuilderReadResult)
    assert res1.header.magic == 0xCAFEBABE
    assert res1.header.msg_type == 1
    assert isinstance(res1.payload, TextPayload)
    assert res1.payload.length == 4
    assert res1.payload.content == b"TEST\x00\x00\x00\x00"

    # Both dot access and dict access work
    assert res1["header"].magic == 0xCAFEBABE
    assert res1["payload"].length == 4

    # 2. Test msg_type = 2 (AudioPayload)
    w2 = BinaryWriter()
    w2.write_struct(Header(magic=0xDEADBEEF, version=2, msg_type=2, payload_size=6))
    w2.write_struct(AudioPayload(sample_rate=44100, channels=2, bit_depth=16))
    data2 = w2.to_bytes()

    res2 = builder.read(data2)
    assert res2.header.magic == 0xDEADBEEF
    assert res2.header.msg_type == 2
    assert isinstance(res2.payload, AudioPayload)
    assert res2.payload.sample_rate == 44100
    assert res2.payload.channels == 2
    assert res2.payload.bit_depth == 16


def test_builder_automated_read_condition():
    """Test condition evaluation during automated read."""
    builder = Builder("Conditional Protocol")
    builder.add_struct(Header, name="header")
    builder.add_struct(
        OptionalFooter,
        name="footer",
        condition="version >= 2",
    )

    # Case A: version = 1 -> footer skipped
    w1 = BinaryWriter()
    w1.write_struct(Header(magic=1, version=1, msg_type=1, payload_size=0))
    res1 = builder.read(w1.to_bytes())
    assert "header" in res1
    assert "footer" not in res1

    # Case B: version = 2 -> footer read
    w2 = BinaryWriter()
    w2.write_struct(Header(magic=1, version=2, msg_type=1, payload_size=0))
    w2.write_struct(OptionalFooter(checksum=0x12345678))
    res2 = builder.read(w2.to_bytes())
    assert "header" in res2
    assert "footer" in res2
    assert res2.footer.checksum == 0x12345678


def test_builder_automated_read_repeated_struct():
    """Test count parameter with repeated structs."""
    @binary_struct
    class ListHeader:
        count: UInt16

    builder = Builder("List Protocol")
    builder.add_struct(ListHeader, name="hdr")
    builder.add_struct(Item, name="items", count="count")

    w = BinaryWriter()
    w.write_struct(ListHeader(count=3))
    w.write_struct(Item(item_id=1, value=100))
    w.write_struct(Item(item_id=2, value=200))
    w.write_struct(Item(item_id=3, value=300))

    res = builder.read(w.to_bytes())
    assert len(res.items) == 3
    assert res.items[0].item_id == 1
    assert res.items[0].value == 100
    assert res.items[2].item_id == 3
    assert res.items[2].value == 300


def test_builder_read_field_element():
    """Test ad-hoc primitive fields in builder."""
    builder = Builder("Ad-hoc Protocol")
    builder.add_field("magic", "UInt32", 4)
    builder.add_field("flags", "UInt16", 2)

    w = BinaryWriter()
    w.write_uint32(0x12345678)
    w.write_uint16(0x00FF)

    res = builder.read(w.to_bytes())
    assert res.magic == 0x12345678
    assert res.flags == 0x00FF


def test_builder_error_handling():
    """Test invalid configurations and unmatched tags."""
    builder = Builder("Error Test")
    builder.add_struct(Header, name="hdr")
    builder.add_choice(
        name="payload",
        tag_field="msg_type",
        variants={1: TextPayload},
    )

    # Invalid struct class
    with pytest.raises(TypeError):
        builder.add_struct(dict)

    # Unmatched tag
    w = BinaryWriter()
    w.write_struct(Header(magic=1, version=1, msg_type=99, payload_size=0))
    with pytest.raises(ValueError, match="did not match any variant"):
        builder.read(w.to_bytes())


def test_builder_aliases():
    """Verify Builder is functional, and BinaryBuilder and ManualBuilder are removed from binary_master."""
    import binary_master
    from binary_master import Builder
    from binary_master.builder import Builder as B1

    assert B1 is Builder

    # Ensure removed names are not in binary_master
    assert not hasattr(binary_master, "ManualBuilder")
    assert not hasattr(binary_master, "BinaryBuilder")

    b = Builder(title="Alias Test", version="1.0")
    b.add_struct(Header, name="header")
    assert len(b.elements) == 1


def test_builder_section_and_caption_context_managers():
    """Verify builder.section(), builder.caption(), and Mermaid subgraphs."""
    builder = Builder(title="Section Test")

    with builder.section("Header Section", "Headers and flags"):
        builder.add_struct(Header, name="MainHeader")

    with builder.caption("Payload Section", "Dynamic data"):
        builder.add_choice(
            "payload",
            tag_field="msg_type",
            variants={1: TextPayload, 2: AudioPayload},
        )

    builder.add_caption("Footer Section", "Verification").add_struct(
        OptionalFooter, condition="has_footer == True"
    )

    md = builder.build()

    # Flowchart should contain subgraphs for sections
    assert "subgraph SG_0_Header_Section" in md
    assert '["Header Section - Headers and flags"]' in md
    assert "subgraph SG_3_Payload_Section" in md
    assert '["Payload Section - Dynamic data"]' in md
    assert "subgraph SG_6_Footer_Section" in md

    # Markdown layout specifications should have section headings
    assert "### Section: Header Section" in md
    assert "Headers and flags" in md
    assert "### Section: Payload Section" in md
    assert "Dynamic data" in md
    assert "### Section: Footer Section" in md


def test_builder_hexdump_and_dump_inspection():
    """Verify builder.hexdump() and builder.dump() schema-driven inspection."""
    builder = Builder(title="Debug Inspection Protocol")

    with builder.section("Header Block"):
        builder.add_struct(Header, name="header")

    with builder.caption("Payload Block"):
        builder.add_choice(
            "payload",
            tag_field="msg_type",
            variants={
                1: TextPayload,
                2: AudioPayload,
            },
        )

    builder.add_struct(OptionalFooter, condition="version > 1")

    # Build test binary: TextPayload (msg_type=1) with version=2 (has footer)
    w = BinaryWriter()
    w.write_struct(Header(magic=0x12345678, version=2, msg_type=1, payload_size=12))
    w.write_struct(TextPayload(encoding=1, length=4, content=b"TEST\x00\x00\x00\x00"))
    w.write_struct(OptionalFooter(checksum=0xDEADBEEF))
    raw_data = w.to_bytes()

    # 1. Direct builder.hexdump()
    dump_hex = builder.hexdump(raw_data, color=False)
    assert "Header Block" in dump_hex or "magic=0x12345678" in dump_hex
    assert "TextPayload" in dump_hex or "encoding=1" in dump_hex
    assert "OptionalFooter" in dump_hex or "checksum=" in dump_hex

    # 2. Direct builder.dump('table')
    table_str = builder.dump(raw_data, format="table")
    assert "Header Block" in table_str
    assert "Payload Block" in table_str
    assert "magic" in table_str
    assert "encoding" in table_str
    assert "checksum" in table_str

    # 3. Direct builder.dump('json')
    json_str = builder.dump(raw_data, format="json")
    import json
    entries = json.loads(json_str)
    assert len(entries) >= 7

    # 4. read(trace=True) enables res.hexdump() and res.dump()
    res = builder.read(raw_data, trace=True)
    assert res.header.magic == 0x12345678
    assert res.payload.length == 4
    assert res.hexdump() == dump_hex
    assert res.dump("table") == table_str

    # 5. read(trace=False) raises RuntimeError on res.hexdump()
    res_no_trace = builder.read(raw_data, trace=False)
    with pytest.raises(RuntimeError, match="trace=True"):
        res_no_trace.hexdump()
    with pytest.raises(RuntimeError, match="trace=True"):
        res_no_trace.dump()


def test_builder_import_writer_and_captions():
    """Verify importing captions and fields from a BinaryWriter into Builder."""
    writer = BinaryWriter(default_endian="little")

    writer.caption("File Header", "Main container header")
    writer.write_uint32(0xCAFEBABE, name="magic", desc="Magic identifier")
    writer.write_uint16(3, name="version", desc="Format version")

    writer.caption("Data Payload", "Raw content block")
    writer.write_bytes(b"PAYLOAD_DATA", name="content", desc="Binary content")

    # 1. Builder.from_writer (imports captions and all fields)
    builder = Builder.from_writer(writer, title="Imported Spec")
    assert builder.title == "Imported Spec"
    assert builder.default_endian == "little"

    # Verify elements: 2 sections + 3 fields = 5 elements
    assert len(builder.elements) == 5
    from binary_master.builder import FieldElement, SectionElement
    assert isinstance(builder.elements[0], SectionElement)
    assert builder.elements[0].title == "File Header"
    assert isinstance(builder.elements[1], FieldElement)
    assert builder.elements[1].name == "magic"
    assert isinstance(builder.elements[3], SectionElement)
    assert builder.elements[3].title == "Data Payload"

    # Verify Markdown spec output
    md = builder.build()
    assert "### Section: File Header" in md
    assert "Main container header" in md
    assert "`magic`" in md
    assert "### Section: Data Payload" in md
    assert "subgraph SG_0_File_Header" in md
    assert "subgraph SG_3_Data_Payload" in md

    # Verify automated reading with imported builder schema!
    raw_bytes = writer.to_bytes()
    res = builder.read(raw_bytes)
    assert res.magic == 0xCAFEBABE
    assert res.version == 3
    assert res.content == b"PAYLOAD_DATA"

    # 2. builder.import_captions (imports captions only)
    b_cap = Builder(title="Captions Only")
    b_cap.import_captions(writer)
    assert len(b_cap.elements) == 2
    assert b_cap.elements[0].title == "File Header"
    assert b_cap.elements[1].title == "Data Payload"


def test_builder_serialize_and_roundtrip(tmp_path: Path):
    """Test schema-driven serialization (builder.to_bytes) and round-trip verification."""
    builder = Builder("Roundtrip Protocol")
    builder.add_section("Header Section")
    builder.add_struct(Header, name="header")
    builder.add_section("Payload Section")
    builder.add_choice(
        name="payload",
        tag_field="msg_type",
        variants={
            1: TextPayload,
            2: AudioPayload,
        },
    )
    builder.add_section("Footer Section")
    builder.add_struct(
        OptionalFooter,
        name="footer",
        condition="version >= 2",
    )

    # 1. Serialize via dict with msg_type = 1 (TextPayload), version = 1 (footer skipped)
    data1 = {
        "header": Header(magic=0x5047534D, version=1, msg_type=1, payload_size=4),
        "payload": TextPayload(encoding=1, length=4, content=b"TEST\x00\x00\x00\x00"),
        "footer": OptionalFooter(checksum=0xDEADBEEF),
    }
    raw1 = builder.to_bytes(data1)
    # Header: 4+2+2+4 = 12 bytes; TextPayload: 2+2+8 = 12 bytes; Total = 24 bytes (footer skipped by condition)
    assert len(raw1) == 24

    # Read back and verify
    res1 = builder.read(raw1)
    assert res1.header.magic == 0x5047534D
    assert res1.header.version == 1
    assert res1.payload.encoding == 1
    assert res1.payload.content[:4] == b"TEST"
    assert "footer" not in res1

    # Roundtrip from BuilderReadResult
    raw1_roundtrip = builder.to_bytes(res1)
    assert raw1_roundtrip == raw1

    # 2. Serialize with version = 2 (footer included)
    data2 = {
        "header": Header(magic=0x5047534D, version=2, msg_type=2, payload_size=6),
        "payload": AudioPayload(sample_rate=48000, channels=2, bit_depth=24),
        "footer": OptionalFooter(checksum=0x12345678),
    }
    raw2 = builder.to_bytes(data2)
    # Header: 12B; AudioPayload: 4+1+1 = 6B; OptionalFooter: 4B; Total = 22B
    assert len(raw2) == 22

    res2 = builder.read(raw2)
    assert res2.header.version == 2
    assert res2.payload.sample_rate == 48000
    assert res2.footer.checksum == 0x12345678

    # 3. Test serialization with list of struct instances
    raw3 = builder.to_bytes([
        Header(magic=0x5047534D, version=2, msg_type=2, payload_size=6),
        AudioPayload(sample_rate=48000, channels=2, bit_depth=24),
        OptionalFooter(checksum=0x12345678),
    ])
    assert raw3 == raw2

    # 4. Test write_markdown
    md_file = tmp_path / "test_spec.md"
    content = builder.write_markdown(md_file)
    assert md_file.exists()
    assert md_file.read_text(encoding="utf-8") == content
    assert "Header Section" in content


