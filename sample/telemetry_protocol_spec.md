# Network Telemetry Protocol Specification

## 概要

Unified binary messaging format supporting text messages and sensor telemetry packets.

- **バージョン**: `1.0.0`
- **デフォルトエンディアン**: リトルエンディアン (Little)
- **定義された構造体数**: 2
- **条件分岐数**: 1

## Protocol Overview & Scope

This document specifies the Network Telemetry Protocol (NTP-v1).
All multi-byte numeric fields are encoded in Little-Endian byte order.

Packets begin with a fixed 14-byte `PacketHeader`. The `msg_type` field dictates
which payload structure immediately follows:
- `0x0001`: `TextMessage`
- `0x0002`: `SensorReport`

If bit 0 of `flags` is set (`flags & 0x01 != 0`), a 4-byte `ChecksumFooter` is appended.

## 構造図 (フローチャート)

```mermaid
flowchart TD
    subgraph SG_1_Header_Section ["Header Section - Fixed container identification header"]
        E2_header["header (PacketHeader, 14B)"]
    end
    subgraph SG_4_Payload_Section ["Payload Section - Polymorphic payload block"]
        Choice_E5_payload{"Choice: payload (msg_type?)"}
        E2_header --> Choice_E5_payload
        V_E5_payload_0["TextMessage, 20B"]
        Choice_E5_payload -->|"Tag 0x01"| V_E5_payload_0
        V_E5_payload_1["SensorReport, 16B"]
        Choice_E5_payload -->|"Tag 0x02"| V_E5_payload_1
    end
    subgraph SG_7_Footer_Section ["Footer Section - Optional trailing integrity verification"]
        Cond_E8_footer{"flags & 0x01 != 0?"}
        V_E5_payload_0 --> Cond_E8_footer
        V_E5_payload_1 --> Cond_E8_footer
        E8_footer["footer (ChecksumFooter, 4B)"]
        Cond_E8_footer -->|yes| E8_footer
    end
```

## データ構造とレイアウト

### セクション: Header Section

Fixed container identification header

### 構造体 `header` (PacketHeader)

Fixed 14-byte packet header

- **合計サイズ**: 14 バイト (`0x000E`)

```mermaid
packet-beta
title header レイアウト
0-31: "magic (UInt32)"
32-47: "version (UInt16)"
48-63: "msg_type (UInt16)"
64-95: "payload_size (UInt32)"
96-111: "flags (UInt16)"
```

| 相対オフセット | サイズ (B) | フィールド名 | 型 | エンディアン | 説明 |
|---|---|---|---|---|---|
| `+0x00` | 4 | `magic` | `UInt32` | Little | Signature: 0x4D534750 ('MSGP') |
| `+0x04` | 2 | `version` | `UInt16` | Little | Protocol version |
| `+0x06` | 2 | `msg_type` | `UInt16` | Little | 1 = Text, 2 = Sensor Data |
| `+0x08` | 4 | `payload_size` | `UInt32` | Little | Length of following payload |
| `+0x0C` | 2 | `flags` | `UInt16` | Little | Bit 0: Has Checksum Footer |

### セクション: Payload Section

Polymorphic payload block

### 条件分岐: `payload`

判定フィールド: `msg_type`

Dynamic payload dispatched by PacketHeader.msg_type

タグ値に応じて、以下のいずれかの構造体が使用されます:

#### [バリアント] Tag `0x01`: `TextMessage`

Human-readable plaintext message payload

- **バリアントサイズ**: 20 バイト (`0x0014`)

```mermaid
packet-beta
title TextMessage レイアウト
0-15: "encoding (UInt16)"
16-31: "text_len (UInt16)"
32-159: "content (FixedArray[UInt8, 16])"
```

| 相対オフセット | サイズ (B) | フィールド名 | 型 | エンディアン | 説明 |
|---|---|---|---|---|---|
| `+0x00` | 2 | `encoding` | `UInt16` | Little | 1 = UTF-8, 2 = ASCII |
| `+0x02` | 2 | `text_len` | `UInt16` | Little | Length of text in bytes |
| `+0x04` | 16 | `content` | `FixedArray[UInt8, 16]` | Little | Fixed buffer for text |

#### [バリアント] Tag `0x02`: `SensorReport`

Multi-channel environmental sensor readings

- **バリアントサイズ**: 16 バイト (`0x0010`)

```mermaid
packet-beta
title SensorReport レイアウト
0-31: "sensor_id (UInt32)"
32-63: "temperature (Float32)"
64-95: "pressure (Float32)"
96-127: "humidity (Float32)"
```

| 相対オフセット | サイズ (B) | フィールド名 | 型 | エンディアン | 説明 |
|---|---|---|---|---|---|
| `+0x00` | 4 | `sensor_id` | `UInt32` | Little | Unique sensor ID |
| `+0x04` | 4 | `temperature` | `Float32` | Little | Temperature in Celsius |
| `+0x08` | 4 | `pressure` | `Float32` | Little | Pressure in hPa |
| `+0x0C` | 4 | `humidity` | `Float32` | Little | Relative humidity (0.0 - 100.0) |

### セクション: Footer Section

Optional trailing integrity verification

### 構造体 `footer` (ChecksumFooter)

> [!NOTE]
> **適用条件**: `flags & 0x01 != 0`

Trailing CRC32 checksum verification

- **合計サイズ**: 4 バイト (`0x0004`)

```mermaid
packet-beta
title footer レイアウト
0-31: "crc32 (UInt32)"
```

| 相対オフセット | サイズ (B) | フィールド名 | 型 | エンディアン | 説明 |
|---|---|---|---|---|---|
| `+0x00` | 4 | `crc32` | `UInt32` | Little | IEEE 802.3 CRC32 checksum |
