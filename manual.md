# バイナリ仕様書

## 概要

イメージヘッダー構造体

- **合計サイズ**: 16 バイト (`0x0010`)
- **デフォルトエンディアン**: リトルエンディアン (Little)
- **合計フィールド数**: 5

## 構造図 (フローチャート)

```mermaid
flowchart TD
    subgraph SG_ImageHeader ["ImageHeader (0x0000 - 0x0008, 8B)"]
        N0["0x0000: magic (UInt32, 4B)"]
        N1["0x0004: image_offset (Offset[ImagePayload], 4B)"]
    end
    subgraph SG_ImagePayload ["ImagePayload (0x0008 - 0x0010, 8B)"]
        N2["0x0008: width (UInt16, 2B)"]
        N3["0x000A: height (UInt16, 2B)"]
        N4["0x000C: pixels (FixedArray[UInt8, 4], 4B)"]
    end
    N0 --> N1
    N1 --> N2
    N2 --> N3
    N3 --> N4
    N1 -.->|"offset: 0x0008"| N2
```

## 構造図 (パケット図)

```mermaid
packet-beta
title バイナリ仕様書 レイアウト
0-31: "magic (UInt32)"
32-63: "image_offset (Offset[ImagePayload])"
64-79: "width (UInt16)"
80-95: "height (UInt16)"
96-127: "pixels (FixedArray[UInt8, 4])"
```

## メモリレイアウト表

### ImageHeader (0x0000 - 0x0008, 8B)

イメージヘッダー構造体

```mermaid
packet-beta
title ImageHeader レイアウト
0-31: "magic (UInt32)"
32-63: "image_offset (Offset[ImagePayload])"
```

| オフセット (16進) | オフセット (10進) | サイズ (B) | フィールド名 | 型 | エンディアン | 説明 |
|---|---|---|---|---|---|---|
| `0x0000` | 0 | 4 | `magic` | `UInt32` | Little | - |
| `0x0004` | 4 | 4 | `image_offset` | `Offset[ImagePayload]` | Little | `-> 0x0008` |

### ImagePayload (0x0008 - 0x0010, 8B)

イメージペイロード構造体

```mermaid
packet-beta
title ImagePayload レイアウト
0-15: "width (UInt16)"
16-31: "height (UInt16)"
32-63: "pixels (FixedArray[UInt8, 4])"
```

| オフセット (16進) | オフセット (10進) | サイズ (B) | フィールド名 | 型 | エンディアン | 説明 |
|---|---|---|---|---|---|---|
| `0x0008` | 8 | 2 | `width` | `UInt16` | Little | - |
| `0x000A` | 10 | 2 | `height` | `UInt16` | Little | - |
| `0x000C` | 12 | 4 | `pixels` | `FixedArray[UInt8, 4]` | Little | - |
