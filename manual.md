# バイナリ仕様書

## 概要

イメージヘッダー構造体

- **合計サイズ**: 104 バイト (`0x0068`)
- **デフォルトエンディアン**: リトルエンディアン (Little)
- **合計フィールド数**: 41

## 構造図 (フローチャート)

```mermaid
flowchart TD
    subgraph SG_ImageHeader ["ImageHeader"]
        N0["0x0000: magic (UInt32, 4B)"]
        N1["0x0004: offset_table (OffsetTable[10, UInt16], 20B)"]
    end
    subgraph SG_ImagePayload ["ImagePayload 🔁 x10"]
        N11["+0x00: width (UInt16, 2B)"]
        N12["+0x02: height (UInt16, 2B)"]
        N13["+0x04: pixels (FixedArray[UInt8, 4], 4B)"]
    end
    N0 --> N1
    N1 --> N11
    N11 --> N12
    N12 --> N13
    N1 -.->|"offset: 0x0018"| N11
```

## 構造図 (パケット図)

```mermaid
packet-beta
title バイナリ仕様書 レイアウト
0-31: "magic (UInt32)"
32-191: "offset_table (OffsetTable[10, UInt16], 20B)"
192-831: "ImagePayload 🔁 x10 (80B)"
```

## メモリレイアウト表

### ImageHeader

イメージヘッダー構造体

```mermaid
packet-beta
title ImageHeader レイアウト
0-31: "magic (UInt32)"
32-191: "offset_table (OffsetTable[10, UInt16], 20B)"
```

| オフセット (16進) | オフセット (10進) | サイズ (B) | フィールド名 | 型 | エンディアン | 説明 |
|---|---|---|---|---|---|---|
| `0x0000` | 0 | 4 | `magic` | `UInt32` | Little | - |
| `0x0004` | 4 | 2 | `offset_table[0]` | `Offset[UInt16]` | Little | Offset entry 0 (`-> 0x0018`) |
| ... | ... | ... | ... | ... | ... | ... |
| `0x0016` | 22 | 2 | `offset_table[9]` | `Offset[UInt16]` | Little | Offset entry 9 (`-> 0x0060`) |

### ImagePayload

イメージペイロード構造体

- 🔁 **繰り返し**: 10 回
- **1要素サイズ**: `8` バイト (0x8)
- **サンプルデータ**: 10 件 (合計 `80` バイト)

```mermaid
packet-beta
title ImagePayload (1要素の構造)
0-15: "width (UInt16)"
16-31: "height (UInt16)"
32-63: "pixels (FixedArray[UInt8, 4])"
```

| 相対オフセット | サイズ (B) | フィールド名 | 型 | エンディアン | 説明 |
|---|---|---|---|---|---|
| `+0x00` | 2 | `width` | `UInt16` | Little | - |
| `+0x02` | 2 | `height` | `UInt16` | Little | - |
| `+0x04` | 4 | `pixels` | `FixedArray[UInt8, 4]` | Little | - |
