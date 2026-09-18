# Procedural Binary Protocol Specification

## 概要

Configuration header parameters.

- **合計サイズ**: 98 バイト (`0x0062`)
- **デフォルトエンディアン**: リトルエンディアン (Little)
- **合計フィールド数**: 19

## 構造図 (フローチャート)

```mermaid
flowchart TD
    subgraph SG_File_Header ["File Header"]
        N0["0x0000: magic (UInt32, 4B)"]
        N1["0x0004: version_major (UInt16, 2B)"]
        N2["0x0006: version_minor (UInt16, 2B)"]
    end
    subgraph SG_Metadata ["Metadata"]
        N3["0x0008: app_name (CString, 15B)"]
        N4["0x0017: doc_title (PrefixedString[2], 23B)"]
        N5["0x002E: author_tag (FixedString[8], 8B)"]
    end
    subgraph SG_Dynamic_Payload ["Dynamic Payload"]
        N6["0x0036: chunk_type (UInt16, 2B)"]
        N7["0x0038: protocol_version (UInt16, 2B)"]
        N8["0x003A: flags (UInt16, 2B)"]
        N9["0x003C: num_records (UInt16, 2B)"]
    end
    subgraph SG_DataRecord ["DataRecord 🔁 xnum_records"]
        N10["+0x00: record_id (UInt32, 4B)"]
        N11["+0x04: timestamp (UInt32, 4B)"]
        N12["+0x08: value (Float32, 4B)"]
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
```

## 構造図 (パケット図)

```mermaid
packet-beta
title Procedural Binary Protocol Specification レイアウト
0-31: "magic (UInt32)"
32-47: "version_major (UInt16)"
48-63: "version_minor (UInt16)"
64-183: "app_name (CString)"
184-367: "doc_title (PrefixedString[2])"
368-431: "author_tag (FixedString[8])"
432-447: "chunk_type (UInt16)"
448-463: "protocol_version (UInt16)"
464-479: "flags (UInt16)"
480-495: "num_records (UInt16)"
496-783: "DataRecord 🔁 xnum_records (36B)"
```

## メモリレイアウト表

### File Header

Container header identifying format and version

```mermaid
packet-beta
title File Header レイアウト
0-31: "magic (UInt32)"
32-47: "version_major (UInt16)"
48-63: "version_minor (UInt16)"
```

| オフセット (16進) | オフセット (10進) | サイズ (B) | フィールド名 | 型 | エンディアン | 説明 |
|---|---|---|---|---|---|---|
| `0x0000` | 0 | 4 | `magic` | `UInt32` | Little | Magic 'FILE' |
| `0x0004` | 4 | 2 | `version_major` | `UInt16` | Little | Major version |
| `0x0006` | 6 | 2 | `version_minor` | `UInt16` | Little | Minor version |

### Metadata

Textual metadata and application properties

```mermaid
packet-beta
title Metadata レイアウト
0-119: "app_name (CString)"
120-303: "doc_title (PrefixedString[2])"
304-367: "author_tag (FixedString[8])"
```

| オフセット (16進) | オフセット (10進) | サイズ (B) | フィールド名 | 型 | エンディアン | 説明 |
|---|---|---|---|---|---|---|
| `0x0008` | 8 | 15 | `app_name` | `CString` | - | App Name |
| `0x0017` | 23 | 23 | `doc_title` | `PrefixedString[2]` | Little | Doc Title |
| `0x002E` | 46 | 8 | `author_tag` | `FixedString[8]` | - | Author Tag |

### Dynamic Payload

Dynamic payload dispatched by chunk_type

```mermaid
packet-beta
title Dynamic Payload レイアウト
0-15: "chunk_type (UInt16)"
16-31: "protocol_version (UInt16)"
32-47: "flags (UInt16)"
48-63: "num_records (UInt16)"
```

| オフセット (16進) | オフセット (10進) | サイズ (B) | フィールド名 | 型 | エンディアン | 説明 |
|---|---|---|---|---|---|---|
| `0x0036` | 54 | 2 | `chunk_type` | `UInt16` | Little | 1=HeaderChunk, 2=TextChunk |
| `0x0038` | 56 | 2 | `protocol_version` | `UInt16` | Little | - |
| `0x003A` | 58 | 2 | `flags` | `UInt16` | Little | - |
| `0x003C` | 60 | 2 | `num_records` | `UInt16` | Little | Number of following data records |

この領域には、条件（種別タグ等）に応じて以下のいずれかの構造体が格納されます。

#### [バリアント] Tag `0x0001`: `HeaderChunk`

Configuration header parameters.

```mermaid
packet-beta
title HeaderChunk Layout
0-15: "protocol_version (UInt16)"
16-31: "flags (UInt16)"
```

| 相対オフセット | サイズ (B) | フィールド名 | 型 | エンディアン | 説明 |
|---|---|---|---|---|---|
| `+0x00` | 2 | `protocol_version` | `UInt16` | Little | - |
| `+0x02` | 2 | `flags` | `UInt16` | Little | - |

#### [バリアント] Tag `0x0002`: `TextChunk`

Text data chunk payload.

```mermaid
packet-beta
title TextChunk Layout
0-15: "length (UInt16)"
16-143: "content (FixedArray[UInt8, 16])"
```

| 相対オフセット | サイズ (B) | フィールド名 | 型 | エンディアン | 説明 |
|---|---|---|---|---|---|
| `+0x00` | 2 | `length` | `UInt16` | Little | - |
| `+0x02` | 16 | `content` | `FixedArray[UInt8, 16]` | Little | - |

### DataRecord

Repeating measurement data records

- 🔁 **繰り返し**: `num_records` 回
- **1要素サイズ**: `12` バイト (0xC)
- **サンプルデータ**: 3 件 (合計 `36` バイト)

```mermaid
packet-beta
title DataRecord (1要素の構造)
0-31: "record_id (UInt32)"
32-63: "timestamp (UInt32)"
64-95: "value (Float32)"
```

| 相対オフセット | サイズ (B) | フィールド名 | 型 | エンディアン | 説明 |
|---|---|---|---|---|---|
| `+0x00` | 4 | `record_id` | `UInt32` | Little | - |
| `+0x04` | 4 | `timestamp` | `UInt32` | Little | - |
| `+0x08` | 4 | `value` | `Float32` | Little | - |
