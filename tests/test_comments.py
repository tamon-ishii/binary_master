"""Tests for extracting field descriptions from source comments and Annotated."""

from typing import Annotated

import binary_master
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
from binary_master.manual import generate_manual


@binary_struct(bits=8)
class StatusFlags:
    active: Bits[1]  # 有効状態フラグ
    busy: Bits[1]  # 処理中フラグ
    reserved: Bits[6]  # 予約領域


@binary_struct
class Character:
    id: UInt16  # キャラクターID
    # キャラクターのレベル
    level: UInt8
    flags: StatusFlags  # 状態フラグ
    score: Annotated[UInt32, "現在の合計スコア"]
    tags: FixedArray[UInt8, 4]  # 属性タグ (4要素)


def test_extract_inline_and_preceding_comments():
    """Test that inline comments, preceding comments, and Annotated descriptions are extracted."""
    char = Character(
        id=1001,
        level=25,
        flags=StatusFlags(active=1, busy=0, reserved=0),
        score=50000,
        tags=[1, 2, 3, 4],
    )

    assert not hasattr(binary_master, "write_manual")

    writer = BinaryWriter()
    writer.write_struct(char)
    md = generate_manual(writer.entries, title="Character Spec")

    # Assert field descriptions in Memory Layout Table (without runtime values)
    assert "| `0x0000` | 0 | 2 | `id` | `UInt16` | Little | キャラクターID |" in md
    assert "| `0x0002` | 2 | 1 | `level` | `UInt8` | Little | キャラクターのレベル |" in md
    assert "| `0x0003` | 3 | 1 | `flags` | `StatusFlags` | Little | 状態フラグ |" in md
    assert "| `0x0004` | 4 | 4 | `score` | `UInt32` | Little | 現在の合計スコア |" in md
    assert "| `0x0008` | 8 | 4 | `tags` | `FixedArray[UInt8, 4]` | Little | 属性タグ (4要素) |" in md

    # Assert bitfield descriptions in Bitfield Details
    assert "| `[0:1]` | `active` | 1 bit(s) | 有効状態フラグ |" in md
    assert "| `[1:2]` | `busy` | 1 bit(s) | 処理中フラグ |" in md
    assert "| `[2:8]` | `reserved` | 6 bit(s) | 予約領域 |" in md

    # When include_values=True, Value column is included
    md_with_val = generate_manual(writer.entries, title="Character Spec", include_values=True)
    assert "| `0x0000` | 0 | 2 | `id` | `UInt16` | Little | `1001 (0x3E9)` | キャラクターID |" in md_with_val
    assert "| `[0:1]` | `active` | 1 bit(s) | `1 (0x1)` | 有効状態フラグ |" in md_with_val

    # Test that Builder also extracts comments when documenting schemas
    builder = Builder(title="Character Spec")
    builder.add_struct(Character)
    b_md = builder.build()
    assert "キャラクターID" in b_md
    assert "キャラクターのレベル" in b_md
    assert "現在の合計スコア" in b_md
    assert "有効状態フラグ" in b_md
