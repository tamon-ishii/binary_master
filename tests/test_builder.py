"""Tests for schema-first Builder and automated reader."""

import io
from pathlib import Path
import pytest

from binary_master import (
    Bits,
    FixedArray,
    BinaryBuilder,
    Builder,
    UInt8,
    UInt16,
    UInt32,
    binary_struct,
    write_struct,
    BinaryWriter,
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

    # Test write_manual alias
    alias_res = builder.write_manual()
    assert alias_res == res


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
    """Verify BinaryBuilder and Builder are identical and functional, and ManualBuilder is removed."""
    import binary_master
    from binary_master import BinaryBuilder, Builder
    from binary_master.builder import BinaryBuilder as BB1, Builder as B1

    assert BinaryBuilder is Builder
    assert BB1 is BinaryBuilder
    assert B1 is Builder

    # Ensure ManualBuilder is completely removed
    assert not hasattr(binary_master, "ManualBuilder")

    b = Builder(title="Alias Test", version="1.0")
    b.add_struct(Header, name="header")
    assert len(b.elements) == 1

    bb = BinaryBuilder(title="Alias Test 2")
    bb.add_struct(Header, name="header")
    assert len(bb.elements) == 1
