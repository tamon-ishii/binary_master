from __future__ import annotations

import pytest

from binary_master import (
    BinaryWriter,
    UInt8,
    UInt16,
    UInt32,
    Variant,
    binary_struct,
    generate_manual,
    write_struct,
)


@binary_struct
class HeaderChunk:
    """ヘッダチャンク情報"""
    version: UInt16
    flags: UInt16


@binary_struct
class TextChunk:
    """テキストチャンク情報"""
    length: UInt32
    encoding: UInt8


@binary_struct
class Chunk:
    """多態チャンクコンテナ"""
    chunk_type: UInt16
    payload: Variant["chunk_type", {1: HeaderChunk, 2: TextChunk}]


def test_writer_subcaption_rendering():
    """Test that writer.subcaption generates nested subheadings in manual."""
    writer = BinaryWriter.to_memory()
    writer.caption("チャンク共通ヘッダ", "チャンクのメタ情報")
    writer.write_uint16(1, name="magic", desc="マジック番号")

    writer.caption("チャンクボディ", "多態データ領域")
    writer.subcaption("ヘッダ種別 (Type=1)", "Type 1 用のパラメータ")
    writer.write_uint16(0x0100, name="version", desc="バージョン")
    writer.write_uint16(0x0001, name="flags", desc="フラグ")

    writer.subcaption("テキスト種別 (Type=2)", "Type 2 用のパラメータ")
    writer.write_uint32(42, name="length", desc="テキスト長")

    manual = generate_manual(writer)
    assert "### チャンク共通ヘッダ" in manual
    assert "### チャンクボディ" in manual
    assert "#### ヘッダ種別 (Type=1)" in manual
    assert "Type 1 用のパラメータ" in manual
    assert "#### テキスト種別 (Type=2)" in manual
    assert "Type 2 用のパラメータ" in manual


def test_writer_caption_with_variants():
    """Test that writer.caption with variants parameter documents candidate structs."""
    writer = BinaryWriter.to_memory()
    writer.caption("ファイルヘッダ")
    writer.write_uint32(0x1234, name="file_id")

    variants = [
        (1, HeaderChunk, "設定ヘッダチャンク"),
        (2, TextChunk, "文字列データチャンク"),
    ]
    writer.caption("ペイロード領域", "チャンク種別に応じた構造体", variants=variants)
    # Write actual instance
    hc = HeaderChunk(version=1, flags=0)
    write_struct(hc, writer=writer)

    manual = generate_manual(writer)
    assert "### ペイロード領域" in manual
    assert "この領域には、条件（種別タグ等）に応じて以下のいずれかの構造体が格納されます。" in manual
    assert "#### [Variant] Tag `0x0001`: `HeaderChunk`" in manual
    assert "設定ヘッダチャンク" in manual
    assert "#### [Variant] Tag `0x0002`: `TextChunk`" in manual
    assert "文字列データチャンク" in manual
    # Ensure relative offsets appear in variant tables
    assert "+0x00" in manual


def test_binary_struct_variant_serialization_deserialization():
    """Test @binary_struct with Variant tagged union field."""
    # 1. Serialization of HeaderChunk variant
    c1 = Chunk(chunk_type=1, payload=HeaderChunk(version=2, flags=5))
    raw1 = c1.to_bytes()
    assert len(raw1) == 2 + 4  # chunk_type(2) + version(2) + flags(2)

    # Deserialization of HeaderChunk variant
    parsed1 = Chunk.from_bytes(raw1)
    assert parsed1.chunk_type == 1
    assert isinstance(parsed1.payload, HeaderChunk)
    assert parsed1.payload.version == 2
    assert parsed1.payload.flags == 5

    # 2. Serialization of TextChunk variant
    c2 = Chunk(chunk_type=2, payload=TextChunk(length=100, encoding=3))
    raw2 = c2.to_bytes()
    assert len(raw2) == 2 + 4 + 1  # chunk_type(2) + length(4) + encoding(1)

    # Deserialization of TextChunk variant
    parsed2 = Chunk.from_bytes(raw2)
    assert parsed2.chunk_type == 2
    assert isinstance(parsed2.payload, TextChunk)
    assert parsed2.payload.length == 100
    assert parsed2.payload.encoding == 3


def test_binary_struct_variant_unknown_tag():
    """Test that deserialization fails with unknown variant tag."""
    # chunk_type = 99 (unknown)
    raw = (99).to_bytes(2, "little") + b"\x00" * 4
    with pytest.raises(ValueError, match="Unknown variant tag 99"):
        Chunk.from_bytes(raw)


def test_binary_struct_variant_manual_auto_registration():
    """Test that writing a struct with a Variant field auto-registers variants in manual."""
    writer = BinaryWriter.to_memory()
    writer.caption("チャンクブロック")
    c = Chunk(chunk_type=1, payload=HeaderChunk(version=1, flags=0))
    write_struct(c, writer=writer)

    manual = generate_manual(writer)
    assert "### チャンクブロック" in manual
    assert "この領域には、条件（種別タグ等）に応じて以下のいずれかの構造体が格納されます。" in manual
    assert "#### [Variant] Tag `0x0001`: `HeaderChunk`" in manual
    assert "#### [Variant] Tag `0x0002`: `TextChunk`" in manual


def test_binary_struct_variant_wrapped_instance():
    """Test that wrapping in Variant(...) instance works equivalently."""
    c = Chunk(chunk_type=1, payload=Variant(HeaderChunk(version=3, flags=7)))
    raw = c.to_bytes()
    parsed = Chunk.from_bytes(raw)
    assert parsed.chunk_type == 1
    assert isinstance(parsed.payload, HeaderChunk)
    assert parsed.payload.version == 3
    assert parsed.payload.flags == 7


def test_binary_struct_variant_missing_tag_error():
    """Test error when tag field is not present before Variant field."""
    @binary_struct
    class BadChunk:
        payload: Variant["non_existent_tag", {1: HeaderChunk}]
        non_existent_tag: UInt16

    with pytest.raises(ValueError, match="Tag field 'non_existent_tag' must precede"):
        BadChunk.from_bytes(b"\x00" * 8)


def test_variant_with_section_packet_diagrams():
    """Test that section_packet_diagrams includes packet diagrams for variants."""
    writer = BinaryWriter.to_memory()
    writer.caption("パケット領域", variants=[(1, HeaderChunk, "ヘッダ"), (2, TextChunk, "テキスト")])
    write_struct(HeaderChunk(version=1, flags=2), writer=writer)

    manual = generate_manual(writer, section_packet_diagrams=True)
    assert "#### [Variant] Tag `0x0001`: `HeaderChunk`" in manual
    assert "HeaderChunk Layout" in manual
    assert "TextChunk Layout" in manual
