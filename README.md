# Binary Master (`binary-master`)

[![Python](https://img.shields.io/badge/python-3.14+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-68%20passed-brightgreen.svg)]()

**Binary Master** は、Python 3.14+ 向けの高機能な構造化バイナリ生成・読み込み（シリアライズ／デシリアライズ）＆仕様書自動生成ライブラリです。

Python 標準の `struct` モジュールで生じがちなフォーマット文字列のミス、手作業でのオフセット計算、エンディアンの混在、バイト列の煩雑な結合・切り出し処理を排除し、**型安全・宣言的・直感的**にバイナリデータを読み書きできます。  
さらに、書き込んだバイナリ構造から **Mermaid ダイアグラム（フローチャート／パケット図）付きの仕様書（Markdown）** をワンライナーで自動生成する機能を備えています。

---

## 主な特徴

- 🚀 **宣言的バイナリ構造体 (`@binary_struct`)**  
  - Python の型ヒントとデータクラス記法を用いて、バイナリヘッダーやパケットフォーマットを直感的に定義可能。
  - **双方向シリアライズ**: `instance.to_bytes()` による書き込みと `Cls.from_bytes(data)` による自動デシリアライズの両方に対応。
  - **Docstring の仕様書自動反映**: クラスの docstring（`"""..."""`）が仕様書の概要やビットフィールド詳細にそのまま自動反映。
  - **コメントの自動抽出**: コード上のインラインコメント（`# ...`）や `Annotated[Type, "説明"]` を自動抽出し、仕様書の `Description` 列に反映。
  - **自動アライメント & パディング (`auto_align=True`, `align=N`)**: C言語の構造体アライメント規則に基づき、メンバ境界や構造体サイズのアライメントパディングを自動挿入。
- 🧩 **高度な型サポート**  
  - 符号付き / 符号なし整数（8, 16, 32, 64-bit）
  - 浮動小数点数（Float32, Float64）
  - **ビットフィールド (`Bits[N]`)**: 1ビット単位のフラグ定義と自動パッキング・アンパッキング
  - **オフセット自動計算 & 解決 (`Offset[T]`)**: ヘッダーのオフセット値の自動バックパッチおよび読み込み時の参照先自動インスタンス化
  - **オフセットテーブル (`OffsetTable[Count, Type]`)**: 複数エントリのオフセット配列の予約・自動バックパッチ
  - **多態チャンク & タグ付き共用体 (`Variant[TagField, Mapping]`)**: 種別IDに応じて切り替わる多態構造体の自動ディスパッチ
  - 固定長配列 (`FixedArray[T, N]`) および可変長配列 (`Array[T]`)
  - 構造体のネスト
- ✍️ **柔軟な手続き的ライター & リーダー (`BinaryWriter` / `BinaryReader`)**  
  - インメモリ（`BytesIO` / `bytes`）またはファイル/ストリームへの直接読み書き
  - 厳格な境界・EOFチェック（オーバーフローや切り捨ての即時エラー検知）
  - 各種文字列形式（C言語スタイルの Null 終端、Pascal スタイルの長さプレフィックス、固定長パディング）
  - バイト境界アライメント（`align`）およびパディング（`pad`）
  - メソッドチェーン対応ライター、カーソル操作（`seek`, `tell`, `skip`, `remaining`）
  - **キャプション & サブキャプション (`caption`, `subcaption`)**: セクションとサブセクションの階層化、多態バリアント候補の指定
- 📊 **仕様書 & Mermaid 図の自動生成 (`write_manual`)**  
  - シリアライズされた全フィールドのオフセット（16進/10進）、サイズ、エンディアン、参照先ターゲット（`-> 0xXXXX`）を記録した Markdown ドキュメントを出力
  - **Mermaid Flowchart**: 構造体ごとのサブグラフとオフセット参照関係の矢印表示
  - **Mermaid packet-beta**: ネットワークパケット形式のビット/バイト配置図およびビットフィールド詳細図の生成
  - **多態チャンク・バリアント仕様の自動展開**: 条件に応じて格納される候補構造体のレイアウト表と相対パケット図の自動生成

---

## 動作要件・インストール

- **Python**: 3.14 以上

```bash
# uv を使用する場合
uv add binary-master

# pip を使用する場合
pip install .
```

---

## クイックスタート

### 1. 宣言的構造体の定義とバイナリ化

`@binary_struct` を使うことで、画像フォーマットやネットワークパケットなどの複雑なバイナリ構造を数行で定義できます。

```python
from binary_master import (
    BinaryWriter,
    Bits,
    FixedArray,
    Offset,
    UInt8,
    UInt16,
    UInt32,
    binary_struct,
)

# 1バイト（8ビット）のビットフィールド
@binary_struct(bits=8)
class HeaderFlags:
    compressed: Bits[1]
    encrypted: Bits[1]
    reserved: Bits[6]

# 画像データ本体
@binary_struct
class Image:
    width: UInt16
    height: UInt16
    pixels: FixedArray[UInt8, 4]

# メインヘッダー（Image へのオフセットを保持）
@binary_struct
class Header:
    magic: UInt32
    version: UInt16
    flags: HeaderFlags
    image_offset: Offset[Image]  # オフセット位置は自動計算されます

# データの構築
header = Header(
    magic=0x474E5089,
    version=1,
    flags=HeaderFlags(compressed=1, encrypted=0, reserved=0),
    image_offset=Image(width=1920, height=1080, pixels=[255, 0, 0, 255]),
)

# バイト列に変換
data: bytes = header.to_bytes()
print(f"Serialized {len(data)} bytes: {data.hex()}")
```

### 2. 仕様書（Markdown & Mermaid）の自動生成

バイナリを書き込むだけで、フォーマット仕様書（マニュアル）が自動生成されます。

```python
writer = BinaryWriter()
writer.write_struct(header)

# 仕様書を Markdown ファイルに出力
writer.write_manual("image_spec.md", title="Sample Image File Specification")
```

#### 生成される仕様書のイメージ

生成された Markdown には、概要、Mermaid 図、メモリレイアウト表、ビットフィールド詳細が含まれます。

````markdown
# Sample Image File Specification

## Overview
- **Total Size**: 19 bytes (`0x0013`)
- **Default Endianness**: Little
- **Total Fields**: 7

## Structure Diagram
```mermaid
flowchart TD
    subgraph SG_Header ["Header (0x0000 - 0x000B, 11B)"]
        N0["0x0000: magic (UInt32, 4B)"]
        N1["0x0004: version (UInt16, 2B)"]
        N2["0x0006: flags (HeaderFlags, 1B)"]
        N3["0x0007: image_offset (Offset[Image], 4B)"]
    end
    subgraph SG_Image ["Image (0x000B - 0x0013, 8B)"]
        N4["0x000B: width (UInt16, 2B)"]
        N5["0x000D: height (UInt16, 2B)"]
        N6["0x000F: pixels (FixedArray[UInt8, 4], 4B)"]
    end
    N0 --> N1
    N1 --> N2
    N2 --> N3
    N3 --> N4
    N4 --> N5
    N5 --> N6
    N3 -.->|"offset: 0x000B"| N4
```

## Memory Layout Table
| Offset (Hex) | Offset (Dec) | Size (B) | Field Name | Type | Endian | Value / Preview | Description |
|---|---|---|---|---|---|---|---|
| `0x0000` | 0 | 4 | `magic` | `UInt32` | Little | `1196314761 (0x474E5089)` | - |
| `0x0004` | 4 | 2 | `version` | `UInt16` | Little | `1 (0x1)` | - |
| `0x0006` | 6 | 1 | `flags` | `HeaderFlags` | Little | `1 (0x1)` | - |
| `0x0007` | 7 | 4 | `image_offset` | `Offset[Image]` | Little | `11 (0xB)` | - |
| `0x000B` | 11 | 2 | `width` | `UInt16` | Little | `1920 (0x780)` | - |
| `0x000D` | 13 | 2 | `height` | `UInt16` | Little | `1080 (0x438)` | - |
| `0x000F` | 15 | 4 | `pixels` | `FixedArray[UInt8, 4]` | Little | `[255, 0, 0, 255]` | - |

## Bitfield Details
### `flags` (Offset: `0x0006`, Size: 1B)
```mermaid
---
config:
  packet:
    bitsPerRow: 8
---
packet-beta
title flags (8 bits)
0: "compressed (1)"
1: "encrypted (0)"
2-7: "reserved (0)"
```
````

---

## 詳細ガイド

### 1. `BinaryWriter` の逐次書き込み

低レベルな制御や動的なプロトコル書き込みには `BinaryWriter` を直接利用します。メソッドチェーンにも対応しています。

```python
from binary_master import BinaryWriter, Endian

writer = BinaryWriter(default_endian=Endian.LITTLE)

# セクションタイトル（キャプション）の設定
# これを呼ぶと、それ以降のバイナリがこのキャプションの内容としてマニュアルにグループ化されます
writer.caption("File Header")
writer.write_uint32(0xDEADBEEF, name="magic", desc="マジックナンバー")
writer.write_uint16(1, name="version")

# 新しいキャプションを設定すると、以降は新しいグループに属します
writer.caption("Payload Data")
writer.write_cstring("Hello", name="c_str")                         # Null終端 (b"Hello\x00")
writer.write_prefixed_string("World", prefix_bytes=2, name="p_str")  # 2バイト長さプレフィックス
writer.write_fixed_string("Fixed", length=10, pad_byte=b"\x00")    # 10バイト固定長パディング

# アライメントとパディング
writer.pad(4, pad_byte=b"\xFF", name="padding")   # 4バイトのパディング
writer.align(16, name="alignment")                # 16バイト境界へアライメント

# 結果の取得
binary_data: bytes = writer.to_bytes()

# 仕様書を出力すると、各キャプションごとの見出しやMermaidサブグラフが自動生成されます
writer.write_manual("output_spec.md", title="Protocol Specification")
```

### 2. `@binary_struct` の詳細機能

#### ビットフィールド (`Bits[N]`)
`bits` 引数を指定することで、ビット単位のフラグを効率よく 1/2/4/8 バイト等の整数にパッキングします。

```python
@binary_struct(bits=16)
class ControlFlags:
    enable: Bits[1]      # 0ビット目
    mode: Bits[3]        # 1-3ビット目
    priority: Bits[4]    # 4-7ビット目
    reserved: Bits[8]    # 8-15ビット目
```

#### オフセット自動計算 (`Offset[T]`)
ファイルフォーマットなどで頻出する「ヘッダー内に後続ブロックの開始オフセットを格納する」構造を自動処理します。

```python
@binary_struct
class FileHeader:
    magic: UInt32
    body_offset: Offset[FileBody]  # 自動的に FileBody の開始バイト位置が書き込まれます

@binary_struct
class FileBody:
    data_length: UInt32
    raw_data: FixedArray[UInt8, 128]

header = FileHeader(
    magic=0x12345678,
    body_offset=FileBody(data_length=128, raw_data=b"\xAA" * 128)
)
```

#### 配列 (`FixedArray` & `Array`)
- `FixedArray[Type, Size]`: 固定長配列（サイズ不足時は自動パディング、サイズ超過時はエラー検知）。
- `Array[Type]`: 可変長配列。

#### 自動アライメント & パディング (`auto_align`, `align`)
C言語の構造体のように、各メンバ型のサイズに合わせた自然境界アライメント（または指定バイト境界アライメント）に自動でパディングを挟むことができます。

- デフォルト (`auto_align=False`, `align=None`): `#pragma pack(1)` 相当で、パディングなしで詰めて配置されます。
- `auto_align=True`: 各フィールドの自然境界（UInt16=2B, UInt32=4B, UInt64=8Bなど）に合わせて手前にパディング（`padding`）を自動挿入し、末尾も最大メンバサイズ境界に合わせてパディングします。
- `align=N`: フィールド境界および構造体末尾を N バイト境界（例: 4 や 8）にアライメントします。

```python
@binary_struct(auto_align=True)
class AlignedHeader:
    flag: UInt8        # 1バイト
    # -> ここに3バイトの自動パディングが挿入される
    data_length: UInt32 # 4バイト（0x0004から開始）
```

#### オフセットテーブル (`OffsetTable`) & `write_offset_table`
複数のブロックやセクションへのオフセットをテーブル（配列）形式で保持し、後からそのオフセットを書き込む（またはターゲットオブジェクトを直接シリアライズする）ことができます。

**1. `@binary_struct` での利用 (`OffsetTable[Count, Type]`)**
```python
from binary_master import OffsetTable, binary_struct, UInt32, UInt16

@binary_struct
class ChunkHeader:
    chunk_id: UInt32

@binary_struct
class Container:
    magic: UInt32
    # 2エントリのUInt32オフセットテーブル
    chunk_offsets: OffsetTable[2, UInt32]

c1 = ChunkHeader(chunk_id=10)
c2 = ChunkHeader(chunk_id=20)
# 対象構造体を渡すと、自動的にオフセットが計算されてテーブルに書き込まれます
container = Container(magic=0x12345678, chunk_offsets=[c1, c2])
```

**2. `BinaryWriter` 手続き的利用 (`write_offset_table`)**
オフセットサイズ（1, 2, 4, 8バイト）とテーブル数を指定して領域を予約し、返り値の `OffsetTableHandle` を使ってオフセット値をセットできます。

```python
writer = BinaryWriter()

# 3エントリ・各4バイト(32bit)のオフセットテーブル枠を予約
table = writer.write_offset_table(count=3, offset_size=4, name="section_offsets")

# 方法A: 戻り値の write_offset() で現在位置をセット
table.write_offset(0)
writer.write_cstring("Section 0 Data")

# 方法B: 戻り値の set_offset(index, offset) で明示的にセット
pos1 = writer.tell()
table.set_offset(1, pos1)
writer.write_cstring("Section 1 Data")

# 方法C: インデックス代入 table[index] = offset
table[2] = writer.tell()
writer.write_cstring("Section 2 Data")

# 方法D: write_target(index, object) で現在オフセット記録＋対象の書き込みを一括実行
# table.write_target(0, my_struct)
```
※ マニュアル出力時、オフセットテーブルの各スロットには参照先オフセットを示す `-> 0xXXXX` マーカーや Mermaid の矢印（`-.->|offset: 0xXXXX|`）が自動的に付与されます。

#### 多態チャンク（タグ付き共用体 / バリアント）とサブキャプション
チャンク形式のバイナリなど、**「同じオフセット位置に、種別タグやフラグに応じて異なる種類の構造体が格納される」** ケースを強力にサポートしています。

**1. 宣言的タグ付き共用体 (`Variant[tag_field, mapping]`)**
先行するタグフィールド（例: `chunk_type`）の値に基づいて、デシリアライズ先を自動分岐させます。

```python
from binary_master import Variant, UInt16, UInt32, binary_struct

@binary_struct
class HeaderChunk:
    """設定ヘッダ情報"""
    version: UInt16
    flags: UInt16

@binary_struct
class TextChunk:
    """文字列データ情報"""
    length: UInt32

@binary_struct
class Chunk:
    """多態チャンクコンテナ"""
    chunk_type: UInt16
    # chunk_type が 1 なら HeaderChunk、2 なら TextChunk に自動ディスパッチ
    payload: Variant["chunk_type", {1: HeaderChunk, 2: TextChunk}]

# 書き込み
c = Chunk(chunk_type=1, payload=HeaderChunk(version=1, flags=0))
raw = c.to_bytes()

# 読み込み（タグ値に応じて自動的に HeaderChunk インスタンスとして復元されます）
parsed = Chunk.from_bytes(raw)
assert isinstance(parsed.payload, HeaderChunk)
```

**2. キャプションでの候補バリアント登録 & マニュアル自動展開 (`variants`)**
同一領域に入る候補構造体を `caption(..., variants=[...])` に指定しておくと、マニュアル上に各候補構造体の説明、相対オフセット（`+0x00`）のパケット図およびレイアウト表が展開されます。

```python
writer = BinaryWriter()
writer.caption(
    "ペイロード領域",
    desc="チャンク種別に応じていずれかの構造体が格納されます",
    variants=[
        (1, HeaderChunk, "種別1: ヘッダ"),
        (2, TextChunk, "種別2: テキスト"),
    ],
)
writer.write_struct(header_chunk)
```

**3. 階層的サブキャプション (`subcaption`)**
共通セクションの中で種類ごとに手続き的に書き分けたい場合、`subcaption()` を使うと大見出しの下に小見出しが生成されます。

```python
writer = BinaryWriter()
writer.caption("チャンクボディ", "多態データ領域")

writer.subcaption("ヘッダ種別 (Type=1)", "Type 1 の設定パラメータ")
writer.write_uint16(0x0100, name="version")

writer.subcaption("テキスト種別 (Type=2)", "Type 2 の文字列パラメータ")
writer.write_uint32(42, name="length")
```

#### Docstring の仕様書反映
構造体やビットフィールドに記述した Python 標準の docstring（`"""..."""`）は、自動的に仕様書（マニュアル）の見出し下や概要欄にドキュメントとして反映されます。

```python
@binary_struct
class NetworkPacket:
    """イーサネットフレームおよびペイロードをカプセル化するパケット仕様。"""
    magic: UInt32  # プロトコル識別子 (0x4E504B54)
    length: UInt16 # ペイロード長
```
マニュアル出力時、`## Overview` に上記クラスの docstring がそのまま出力され、フィールドのインラインコメントは `Description` 列に出力されます。

### 3. 仕様書（マニュアル）生成オプション

`write_manual` では、出力形式やダイアグラムの表示スタイルを柔軟にカスタマイズできます。

```python
from binary_master import write_manual

# 構造体インスタンスまたは BinaryWriter から直接出力可能
write_manual(
    header,
    path_or_file="spec.md",
    title="Network Protocol Spec",
    diagram_type="both",      # 'flowchart', 'packet', 'both'
    diagram_direction="TD",   # フローチャートの向き ('TD', 'LR')
    bits_per_row=32,          # パケット図の1行あたりのビット数 (8, 16, 32)
    bit_width=40,             # パケット図の1ビットあたりの横幅 (px)。横に大きく広げたい場合に指定
    include_bitfield_diagram=True,  # ビットフィールドの詳細パケット図を含めるか
    section_packet_diagrams=True,   # Memory Layout Tableの各セクション(caption)ごとにパケット図を埋め込むか
    include_values=False,     # 実行時の値(Value / Preview)を含めるか (デフォルト: False、純粋な仕様書として出力)
)
```

- **`diagram_type="flowchart"`**: 構造体の入れ子構造やオフセット参照（矢印）を可視化するフローチャート。
- **`diagram_type="packet"`**: RFC風のパケットレイアウト図（`packet-beta` 記法）を生成。
- **`diagram_type="both"`**: フローチャートとパケット図の両方を並記。
- **`section_packet_diagrams=True`**: `caption` で区切られた各メモリ領域（ヘッダー、ボディ等）の直前に、その領域専用のパケット図を埋め込みます。ブロックごとのビット配置が直感的に把握できます。
- **`include_values=False` (デフォルト)**: フォーマット仕様書として不要な特定インスタンスのダミー値（`Value / Preview` 列やパケット図内の値表示）を省き、すっきりとした表を出力します。デバッグ時などで値も確認したい場合は `True` を指定できます。

### 4. バイナリの読み込みとデシリアライズ (`BinaryReader` / `from_bytes`)

書き込んだバイナリデータは、[`BinaryReader`](file:///home/ishii/PycharmProjects/binary_master/src/binary_master/reader.py) または構造体の `from_bytes()` メソッドで完全に対称復元（ラウンドトリップ）できます。

#### ① `@binary_struct.from_bytes()` による宣言的復元
```python
# バイト列から直接復元
header = Header.from_bytes(binary_data)
print(header.magic)
print(header.flags.compressed)
print(header.image_offset.width) # Offset[Image] の参照先も自動的にデシリアライズ
```

#### ② `BinaryReader` による逐次読み込み
```python
from binary_master import BinaryReader, Endian

reader = BinaryReader(binary_data, default_endian=Endian.LITTLE)

# プリミティブ値の読み込み
magic = reader.read_uint32()
version = reader.read_uint16()
name = reader.read_cstring()

# カーソル操作
pos = reader.tell()
reader.seek(0)
reader.skip(4)
reader.align(8)

# 構造体の読み込み
header = reader.read_struct(Header)
```

---

## API リファレンス

### プリミティブ型 (`binary_struct`)
| 型 | サイズ | 説明 |
|---|---|---|
| `UInt8` / `Int8` | 1 バイト | 8ビット 符号なし / 符号付き整数 |
| `UInt16` / `Int16` | 2 バイト | 16ビット 符号なし / 符号付き整数 |
| `UInt32` / `Int32` | 4 バイト | 32ビット 符号なし / 符号付き整数 |
| `UInt64` / `Int64` | 8 バイト | 64ビット 符号なし / 符号付き整数 |
| `Float32` | 4 バイト | IEEE 754 単精度浮動小数点数 |
| `Float64` | 8 バイト | IEEE 754 倍精度浮動小数点数 |
| `Bits[N]` | N ビット | ビットフィールドのフィールド幅 |
| `Offset[T]` | 4 バイト | 構造体 `T` へのバイトオフセット（自動解決） |
| `OffsetTable[Count, Type]` | `sizeof(Type) * Count` | オフセットテーブル配列（自動解決） |
| `FixedArray[T, N]` | `sizeof(T) * N` | 固定長要素配列 |
| `Array[T]` | 可変 | 可変長要素配列 |
| `Variant[TagField, Mapping]` | 可変 | タグ値に応じた多態構造体（自動ディスパッチ） |

### `BinaryWriter` 主要メソッド
- **整数書き込み**: `write_uint8`, `write_int8`, `write_uint16`, `write_int16`, `write_uint32`, `write_int32`, `write_uint64`, `write_int64`
- **浮動小数点数**: `write_float32`, `write_float64`
- **論理値 / バイト**: `write_bool`, `write_bytes`
- **文字列**: `write_cstring`, `write_prefixed_string`, `write_fixed_string`, `write_string`
- **オフセットテーブル**: `write_offset_table(count, offset_size=4, ...)`（戻り値 `OffsetTableHandle` で `set_offset`, `write_offset`, `write_target` 等が可能）
- **構造体**: `write_struct(instance, endian=None)`
- **位置制御**: `tell()`, `seek(offset, whence)`
- **セクションタイトル**: `caption(title=None, desc="", variants=None)`（マニュアル・図のグループ化見出し、説明、候補バリアントを設定）
- **サブセクションタイトル**: `subcaption(title=None, desc="")`（大見出し内の階層的サブグループを設定）
- **パディング & アライメント**: `pad(count, pad_byte)`, `align(boundary, pad_byte)`
- **仕様書生成**: `write_manual(path_or_file, title=..., diagram_type=...)`
- **データ取り出し**: `to_bytes()`, `to_bytearray()`

### `BinaryReader` 主要メソッド
- **整数読み込み**: `read_uint8`, `read_int8`, `read_uint16`, `read_int16`, `read_uint32`, `read_int32`, `read_uint64`, `read_int64`
- **浮動小数点数**: `read_float32`, `read_float64`
- **論理値 / バイト**: `read_bool`, `read_bytes(count=None)`
- **文字列**: `read_cstring`, `read_prefixed_string`, `read_fixed_string`, `read_string`
- **構造体**: `read_struct(cls, endian=None)`
- **位置制御**: `tell()`, `seek(offset, whence)`, `skip(count)`, `remaining()`, `align(boundary)`
- **初期化**: `BinaryReader(source)`, `BinaryReader.from_bytes(data)`, `BinaryReader.from_file(path)`

---

## テストの実行

テストスイートは `pytest` を使用して実行できます。

```bash
pytest
```

---

## ライセンス

MIT License
