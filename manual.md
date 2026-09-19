# バイナリ仕様書

## 概要

イメージヘッダー構造体

- **合計サイズ**: 1004 バイト (`0x03EC`)
- **デフォルトエンディアン**: リトルエンディアン (Little)
- **合計フィールド数**: 401 (定義数: 5)
- **構造体数**: 2

## 構造図

```mermaid
flowchart TD
    subgraph SG_ImageHeader ["ImageHeader"]
        N0["0x0000: magic (UInt32, 4B)"]
        N1["0x0004: offset_table (OffsetTable[100, UInt16], 200B)"]
    end
    subgraph SG_ImagePayload ["ImagePayload 🔁 x100"]
        N101["+0x00: width (UInt16, 2B)"]
        N102["+0x02: height (UInt16, 2B)"]
        N103["+0x04: pixels (FixedArray[UInt8, 4], 4B)"]
    end
    N0 --> N1
    N101 --> N102
    N102 --> N103
    N1 -.->|"offset: 0x00CC"| N101
```

## メモリレイアウト表

### ImageHeader

イメージヘッダー構造体

```mermaid
packet-beta
title ImageHeader レイアウト
0-31: "magic (UInt32)"
32-1631: "offset_table (OffsetTable[100, UInt16], 200B)"
```

| オフセット (16進) | オフセット (10進) | サイズ (B) | フィールド名 | 型 | エンディアン | 説明 |
|---|---|---|---|---|---|---|
| `0x0000` | 0 | 4 | `magic` | `UInt32` | Little | - |
| `0x0004` | 4 | 2 | `offset_table[0]` | `Offset[UInt16]` | Little | Offset entry 0 (`-> 0x00CC` (ImagePayload[0])) |
| ... | ... | ... | ... | ... | ... | ... |
| `0x00CA` | 202 | 2 | `offset_table[99]` | `Offset[UInt16]` | Little | Offset entry 99 (`-> 0x03E4` (ImagePayload[99])) |

### ImagePayload

イメージペイロード構造体

- 🔁 **繰り返し**: 100 回
- **1要素サイズ**: `8` バイト (0x8)
- **配置範囲**: `0x00CC` 〜 `0x03EC` (`800` バイト)
- **サンプルデータ**: 100 件 (合計 `800` バイト)

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
