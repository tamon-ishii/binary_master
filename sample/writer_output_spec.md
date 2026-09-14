# Procedural Binary Protocol Specification

## Overview

Configuration header parameters.

- **Total Size**: 98 bytes (`0x0062`)
- **Default Endianness**: Little
- **Total Fields**: 19

## Structure Diagram

```mermaid
flowchart TD
    subgraph SG_File_Header ["File Header (0x0000 - 0x0008, 8B)"]
        N0["0x0000: magic (UInt32, 4B)"]
        N1["0x0004: version_major (UInt16, 2B)"]
        N2["0x0006: version_minor (UInt16, 2B)"]
    end
    subgraph SG_Metadata ["Metadata (0x0008 - 0x0036, 46B)"]
        N3["0x0008: app_name (CString, 15B)"]
        N4["0x0017: doc_title (PrefixedString[2], 23B)"]
        N5["0x002E: author_tag (FixedString[8], 8B)"]
    end
    subgraph SG_Dynamic_Payload ["Dynamic Payload (0x0036 - 0x003C, 6B)"]
        N6["0x0036: chunk_type (UInt16, 2B)"]
        N7["0x0038: protocol_version (UInt16, 2B)"]
        N8["0x003A: flags (UInt16, 2B)"]
    end
    N9["0x003C: num_records (UInt16, 2B)"]
    subgraph SG_DataRecord ["DataRecord 🔁 xnum_records (0x003E - 0x0062, 36B)"]
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

## Memory Layout Table

### File Header (0x0000 - 0x0008, 8B)

Container header identifying format and version

| Offset (Hex) | Offset (Dec) | Size (B) | Field Name | Type | Endian | Description |
|---|---|---|---|---|---|---|
| `0x0000` | 0 | 4 | `magic` | `UInt32` | Little | Magic 'FILE' |
| `0x0004` | 4 | 2 | `version_major` | `UInt16` | Little | Major version |
| `0x0006` | 6 | 2 | `version_minor` | `UInt16` | Little | Minor version |

### Metadata (0x0008 - 0x0036, 46B)

Textual metadata and application properties

| Offset (Hex) | Offset (Dec) | Size (B) | Field Name | Type | Endian | Description |
|---|---|---|---|---|---|---|
| `0x0008` | 8 | 15 | `app_name` | `CString` | - | App Name |
| `0x0017` | 23 | 23 | `doc_title` | `PrefixedString[2]` | Little | Doc Title |
| `0x002E` | 46 | 8 | `author_tag` | `FixedString[8]` | - | Author Tag |

### Dynamic Payload (0x0036 - 0x003C, 6B)

Dynamic payload dispatched by chunk_type

| Offset (Hex) | Offset (Dec) | Size (B) | Field Name | Type | Endian | Description |
|---|---|---|---|---|---|---|
| `0x0036` | 54 | 2 | `chunk_type` | `UInt16` | Little | 1=HeaderChunk, 2=TextChunk |
| `0x0038` | 56 | 2 | `protocol_version` | `UInt16` | Little | - |
| `0x003A` | 58 | 2 | `flags` | `UInt16` | Little | - |

この領域には、条件（種別タグ等）に応じて以下のいずれかの構造体が格納されます。

#### [Variant] Tag `0x0001`: `HeaderChunk`

Configuration header parameters.

| Relative Offset | Size (B) | Field Name | Type | Endian | Description |
|---|---|---|---|---|---|
| `+0x00` | 2 | `protocol_version` | `UInt16` | Little | - |
| `+0x02` | 2 | `flags` | `UInt16` | Little | - |

#### [Variant] Tag `0x0002`: `TextChunk`

Text data chunk payload.

| Relative Offset | Size (B) | Field Name | Type | Endian | Description |
|---|---|---|---|---|---|
| `+0x00` | 2 | `length` | `UInt16` | Little | - |
| `+0x02` | 16 | `content` | `FixedArray[UInt8, 16]` | Little | - |

### (0x003C - 0x003E, 2B)

| Offset (Hex) | Offset (Dec) | Size (B) | Field Name | Type | Endian | Description |
|---|---|---|---|---|---|---|
| `0x003C` | 60 | 2 | `num_records` | `UInt16` | Little | Number of following data records |

### DataRecord (0x003E - 0x0062, 36B)

Repeating measurement data record.

- 🔁 **繰り返し**: `num_records` 回
- **1要素サイズ**: `12` bytes (0xC)
- **サンプルデータ**: 3 件 (合計 `36` bytes)

| Relative Offset | Size (B) | Field Name | Type | Endian | Description |
|---|---|---|---|---|---|
| `+0x00` | 4 | `record_id` | `UInt32` | Little | - |
| `+0x04` | 4 | `timestamp` | `UInt32` | Little | - |
| `+0x08` | 4 | `value` | `Float32` | Little | - |
