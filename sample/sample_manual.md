# バイナリコンテナフォーマット仕様書

## Overview

コンテナメインヘッダー。全体の基本情報とフラグを保持します。

- **Total Size**: 42 bytes (`0x002A`)
- **Default Endianness**: Little
- **Total Fields**: 13

## Structure Diagram (Flowchart)

```mermaid
flowchart TD
    subgraph SG_Container_Header ["Container Header (0x0000 - 0x000C, 12B)"]
        N0["0x0000: magic (UInt32, 4B)"]
        N1["0x0004: version (UInt16, 2B)"]
        N2["0x0006: flags (PacketFlags, 2B)"]
        N3["0x0008: chunk_count (UInt16, 2B)"]
        N4["0x000A: alignment_pad (Padding[2], 2B)"]
    end
    subgraph SG_Offset_Table ["Offset Table (0x000C - 0x0014, 8B)"]
        N5["0x000C: chunk_offsets[0] (Offset[UInt32], 4B)"]
        N6["0x0010: chunk_offsets[1] (Offset[UInt32], 4B)"]
    end
    subgraph SG_Metadata_Chunk_Chunk_0 ["Metadata Chunk (Chunk 0) (0x0014 - 0x001E, 10B)"]
        N7["0x0014: block_id (UInt32, 4B)"]
        N8["0x0018: timestamp (UInt32, 4B)"]
        N9["0x001C: author_id (UInt16, 2B)"]
    end
    subgraph SG_Payload_Chunk_Chunk_1 ["Payload Chunk (Chunk 1) (0x001E - 0x002A, 12B)"]
        N10["0x001E: payload_type (UInt16, 2B)"]
        N11["0x0020: data_length (UInt16, 2B)"]
        N12["0x0022: raw_bytes (FixedArray[UInt8, 8], 8B)"]
    end
    N0 --> N1
    N1 --> N2
    N2 --> N3
    N3 --> N4
    N4 --> N5
    N5 --> N6
    N6 --> N7
    N7 --> N8
    N8 --> N9
    N9 --> N10
    N10 --> N11
    N11 --> N12
    N5 -.->|"offset: 0x0014"| N7
    N6 -.->|"offset: 0x001E"| N10
```

## Structure Diagram (Packet)

```mermaid
---
config:
  packet:
    bitWidth: 45
---
packet-beta
title バイナリコンテナフォーマット仕様書 Layout
0-31: "magic (UInt32)"
32-47: "version (UInt16)"
48-63: "flags (PacketFlags)"
64-79: "chunk_count (UInt16)"
80-95: "alignment_pad (Padding[2])"
96-127: "chunk_offsets[0] (Offset[UInt32])"
128-159: "chunk_offsets[1] (Offset[UInt32])"
160-191: "block_id (UInt32)"
192-223: "timestamp (UInt32)"
224-239: "author_id (UInt16)"
240-255: "payload_type (UInt16)"
256-271: "data_length (UInt16)"
272-335: "raw_bytes (FixedArray[UInt8, 8])"
```

## Memory Layout Table

### Container Header (0x0000 - 0x000C, 12B)

コンテナ全体の基本メタデータ領域

```mermaid
---
config:
  packet:
    bitWidth: 45
---
packet-beta
title Container Header Layout
0-31: "magic (UInt32)"
32-47: "version (UInt16)"
48-63: "flags (PacketFlags)"
64-79: "chunk_count (UInt16)"
80-95: "alignment_pad (Padding[2])"
```

| Offset (Hex) | Offset (Dec) | Size (B) | Field Name | Type | Endian | Description |
|---|---|---|---|---|---|---|
| `0x0000` | 0 | 4 | `magic` | `UInt32` | Little | マジックナンバー ('PKT\x01' = 0x01544B50) |
| `0x0004` | 4 | 2 | `version` | `UInt16` | Little | プロトコルバージョン (0x0100 = v1.0) |
| `0x0006` | 6 | 2 | `flags` | `PacketFlags` | Little | パケット制御フラグ (16ビット) |
| `0x0008` | 8 | 2 | `chunk_count` | `UInt16` | Little | 後続データチャンクの総数 |
| `0x000A` | 10 | 2 | `alignment_pad` | `Padding[2]` | - | Struct size alignment |

### Offset Table (0x000C - 0x0014, 8B)

各データチャンクへの開始オフセット配列

```mermaid
---
config:
  packet:
    bitWidth: 45
---
packet-beta
title Offset Table Layout
0-31: "chunk_offsets[0] (Offset[UInt32])"
32-63: "chunk_offsets[1] (Offset[UInt32])"
```

| Offset (Hex) | Offset (Dec) | Size (B) | Field Name | Type | Endian | Description |
|---|---|---|---|---|---|---|
| `0x000C` | 12 | 4 | `chunk_offsets[0]` | `Offset[UInt32]` | Little | データチャンク開始オフセット [#0] (`-> 0x0014`) |
| `0x0010` | 16 | 4 | `chunk_offsets[1]` | `Offset[UInt32]` | Little | データチャンク開始オフセット [#1] (`-> 0x001E`) |

### Metadata Chunk (Chunk 0) (0x0014 - 0x001E, 10B)

管理用メタデータブロック

```mermaid
---
config:
  packet:
    bitWidth: 45
---
packet-beta
title Metadata Chunk (Chunk 0) Layout
0-31: "block_id (UInt32)"
32-63: "timestamp (UInt32)"
64-79: "author_id (UInt16)"
```

| Offset (Hex) | Offset (Dec) | Size (B) | Field Name | Type | Endian | Description |
|---|---|---|---|---|---|---|
| `0x0014` | 20 | 4 | `block_id` | `UInt32` | Little | ブロック固有識別ID |
| `0x0018` | 24 | 4 | `timestamp` | `UInt32` | Little | 作成エポック秒 (UTC) |
| `0x001C` | 28 | 2 | `author_id` | `UInt16` | Little | 作成者ユーザーID |

### Payload Chunk (Chunk 1) (0x001E - 0x002A, 12B)

ペイロードバイナリデータブロック

```mermaid
---
config:
  packet:
    bitWidth: 45
---
packet-beta
title Payload Chunk (Chunk 1) Layout
0-15: "payload_type (UInt16)"
16-31: "data_length (UInt16)"
32-95: "raw_bytes (FixedArray[UInt8, 8])"
```

| Offset (Hex) | Offset (Dec) | Size (B) | Field Name | Type | Endian | Description |
|---|---|---|---|---|---|---|
| `0x001E` | 30 | 2 | `payload_type` | `UInt16` | Little | ペイロード種別 (0x0001: センサー, 0x0002: ログ) |
| `0x0020` | 32 | 2 | `data_length` | `UInt16` | Little | 実データ長 (バイト数) |
| `0x0022` | 34 | 8 | `raw_bytes` | `FixedArray[UInt8, 8]` | Little | ペイロード実バイナリデータ (8バイト固定) |

## Bitfield Details

### `flags` (Offset: `0x0006`, Size: 2B)

パケット制御フラグ定義 (16ビットビットフィールド)

```mermaid
---
config:
  packet:
    bitsPerRow: 16
    bitWidth: 50
---
packet-beta
title flags (16 bits)
0: "active"
1-3: "mode"
4: "encrypted"
5-7: "priority"
8-15: "reserved"
```

| Bit Range | Field Name | Width | Description |
|---|---|---|---|
| `[0:1]` | `active` | 1 bit(s) | 有効フラグ (1: アクティブ, 0: スタンバイ) |
| `[1:4]` | `mode` | 3 bit(s) | 動作モード (0: 通常, 1: 省電力, 2: 高負荷) |
| `[4:5]` | `encrypted` | 1 bit(s) | 暗号化フラグ (1: 暗号化あり, 0: なし) |
| `[5:8]` | `priority` | 3 bit(s) | 優先度レベル (0: 低 〜 7: 最高) |
| `[8:16]` | `reserved` | 8 bit(s) | 将来の拡張用予約領域 (常に 0) |
