# Binary Master 実践チュートリアル (Step-by-Step Tutorial)

[![Python 3.14+](https://img.shields.io/badge/python-3.14+-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

**Binary Master (`binary-master`)** は、Python 3.14+ 向けの高機能な構造化バイナリ生成・解析＆仕様書自動生成ライブラリです。

Python標準の `struct` モジュールによるフォーマット文字列（`"<I2sH"` など）や手動オフセット計算の煩雑さを解消し、**型安全・宣言的・直感的**にバイナリデータをシリアライズ／デシリアライズできます。さらに、定義した構造から **Mermaid 図付きの仕様書（Markdown）** や **多言語コード（C / C++ / Rust / C# / Go）** を自動出力できます。

本チュートリアルでは、基本から応用までを **5つのステップ** で実際にコードを動かしながら学びます。

---

## 📚 目次

- [前提条件・環境セットアップ](#前提条件環境セットアップ)
- [Step 1: はじめてのバイナリ構造体（基礎編）](#step-1-はじめてのバイナリ構造体基礎編)
  - 1.1 構造体の宣言 (`@binary_struct`)
  - 1.2 シリアライズとデシリアライズ
  - 1.3 サイズ確認とエンディアンの指定
  - 1.4 メンバのバイトオフセット取得 (`offsetof`)
- [Step 2: ビットフィールドとアライメント（応用編）](#step-2-ビットフィールドとアライメント応用編)
  - 2.1 1ビット単位のフラグ定義 (`Bits[N]`)
  - 2.2 パケット境界アライメント (`align=4`, `auto_align=True`)
- [Step 3: 相対オフセットとポインタテーブル（高度なデータ構造）](#step-3-相対オフセットとポインタテーブル高度なデータ構造)
  - 3.1 自動オフセット計算 (`Offset[T, Base.SELF]`)
  - 3.2 オフセット演算とポインタテーブル (`OffsetTable`)
- [Step 4: 手続き的ライター & リーダーとデバッグ機能（低レベル制御）](#step-4-手続き的ライター--リーダーとデバッグ機能低レベル制御)
  - 4.1 `BinaryWriter` によるストリーム書き込みとセクションキャプション (`caption`)
  - 4.2 文字列戦略（Null終端 / 長さプレフィックス / 固定長）
  - 4.3 `BinaryReader` によるストリーム読み込み
  - 4.4 充実したデバッグダンプ（注釈付き Hexdump / テーブル出力 / 差分比較）
  - 4.5 `BinaryWriter` による仕様書・多言語ヘッダーの直接出力 (`write_markdown`, `write_c_header`)
  - 4.6 多態バリアント (`write_variant`) とチャンクの繰り返し集約 (`repeat`)
- [Step 5: スキーマ駆動設計・仕様書自動生成・多言語出力（統合編）](#step-5-スキーマ駆動設計仕様書自動生成多言語出力統合編)
  - 5.1 `Builder` によるプロトコルスキーマ定義
  - 5.2 多態パケットの分岐 (`add_choice`)
  - 5.3 仕様書（Markdown & Mermaid 図）のワンライナー出力
  - 5.4 多言語ヘッダー出力 (C, Rust, Modern C++, C#, Go)
  - 5.5 スキーマ駆動の自動デシリアライズ (`builder.read`)
  - 5.6 スキーマ駆動のデバッグ検査 (`builder.hexdump` / `builder.dump`)
- [まとめ & サンプルコードとの対応](#まとめ--サンプルコードとの対応)

---

## 前提条件・環境セットアップ

- **Python**: 3.14 以上

### インストール方法

```bash
# uv を使用する場合
uv add binary-master

# pip を使用する場合（ローカルリポジトリから）
pip install .
```

リポジトリ内のサンプルコードは `sample/` ディレクトリに格納されており、いつでも動作を確認できます：

```bash
python sample/main.py
```

---

## Step 1: はじめてのバイナリ構造体（基礎編）

> 対応サンプルコード: [`sample/01_basic_struct.py`](sample/01_basic_struct.py)

バイナリデータの読み書きで最も基本となるのが、`@binary_struct` デコレータを用いた宣言的構造体の定義です。

### 1.1 構造体の宣言 (`@binary_struct`)

Pythonの標準型アノテーションと同じ感覚でフィールドを定義します。

```python
from binary_master import (
    UInt8,
    UInt16,
    UInt32,
    Float32,
    FixedArray,
    binary_struct,
    sizeof,
    read_struct,
)

@binary_struct(endian="little")
class PlayerProfile:
    """プレイヤーのプロファイルセーブデータ"""
    magic: UInt32              # シグネチャ: 0x504C4159 ('PLAY')
    player_id: UInt16          # プレイヤーID
    level: UInt8               # レベル (0-255)
    lives: UInt8               # 残機
    score: UInt32              # スコア
    health_ratio: Float32      # 体力比率 (0.0 - 1.0)
    tag: FixedArray[UInt8, 4]  # 4バイトのクランタグ
```

#### ポイント
- **プリミティブ型**: `UInt8`, `UInt16`, `UInt32`, `UInt64`, `Int8`, `Int16`, `Int32`, `Int64`, `Float32`, `Float64` などを直接指定できます。
- **固定長配列**: `FixedArray[Type, Length]` で固定長のバイト配列や構造体配列を定義できます。
- **Docstring とインラインコメント**: クラス docstring や `# コメント` は、後述する仕様書生成時に自動抽出され、マニュアルの「説明」に反映されます。

### 1.2 シリアライズとデシリアライズ

定義した構造体は通常のクラスのようにインスタンス化でき、`.to_bytes()` で直ちに `bytes` 列へシリアライズできます。

```python
# 1. インスタンス生成
player = PlayerProfile(
    magic=0x59414C50,   # 'PLAY' (リトルエンディアン)
    player_id=1042,
    level=50,
    lives=3,
    score=999999,
    health_ratio=0.85,
    tag=b"PROG",
)

# 2. バイナリ列へシリアライズ
binary_data = player.to_bytes()
print(f"バイト長: {len(binary_data)} bytes")
print(f"Hex: {binary_data.hex(' ')}")

# 3. バイナリ列から構造体を復元 (デシリアライズ)
restored = PlayerProfile.from_bytes(binary_data)
# または: restored = read_struct(PlayerProfile, binary_data)

print(f"復元されたプレイヤーID: {restored.player_id}")
print(f"復元されたスコア: {restored.score}")
print(f"復元されたクランタグ: {bytes(restored.tag).decode('ascii')}")
```

### 1.3 サイズ確認とエンディアンの指定

クラスの静的バイトサイズは `sizeof()` または `.binary_size` で取得可能です。

```python
print(sizeof(PlayerProfile))         # => 20
print(PlayerProfile.binary_size)     # => 20
```

エンディアンは `@binary_struct(endian="little")` または `@binary_struct(endian="big")` で指定します。シリアライズ時に一時的にオーバーライドすることも可能です：

```python
# ビッグエンディアンで書き出し
big_data = player.to_bytes(endian="big")
```

### 1.4 メンバのバイトオフセット取得 (`offsetof`)

C言語の `offsetof(Struct, member)` と同様に、各フィールドの構造体先頭からのバイトオフセット（開始位置）を `offsetof()` 関数または `.offsetof("フィールド名")` メソッドで直接取得できます。

```python
from binary_master import offsetof

# クラスから直接取得
print(PlayerProfile.offsetof("magic"))        # => 0
print(PlayerProfile.offsetof("player_id"))    # => 4
print(PlayerProfile.offsetof("score"))        # => 8

# 関数形式でも呼び出し可能
print(offsetof(PlayerProfile, "score"))       # => 8

# インスタンスからも呼び出し可能
print(player.offsetof("score"))              # => 8
```

- **アライメント考慮**: `auto_align=True` やパディングフィールドによってオフセットがずれる場合も、パディング後の正確なバイトオフセットを返します。
- **ネスト対応**: 入れ子構造体の内部フィールドも `"header.version"` のようにドット記法で階層を辿ってオフセットを取得できます。
- **レイアウト一覧の取得**: 全メンバのオフセット・サイズ一覧を確認したい場合は `inspect_struct_layout(PlayerProfile)` も利用できます。

---

## Step 2: ビットフィールドとアライメント（応用編）

> 対応サンプルコード: [`sample/02_bitfields_and_alignment.py`](sample/02_bitfields_and_alignment.py)

通信パケットやハードウェア制御では、1バイト未満のフラグビットを詰め込む「ビットフィールド」や、CPUアクセス効率のための「メモリアライメント」が不可欠です。

### 2.1 1ビット単位のフラグ定義 (`Bits[N]`)

`@binary_struct(bits=16)` のようにコンテナ全体の合計ビット数を指定し、各フィールドに `Bits[N]` を割り当てます。

```python
from binary_master import Bits, binary_struct

@binary_struct(bits=16)
class DeviceStatus:
    """16ビットにパックされたデバイスステータスフラグ"""
    powered_on:  Bits[1]  # Bit 0: 電源 (1=ON, 0=OFF)
    busy:        Bits[1]  # Bit 1: 処理中フラグ
    mode:        Bits[3]  # Bits 2..4: 動作モード (0〜7)
    error_code:  Bits[3]  # Bits 5..7: エラーコード (0〜7)
    battery_pct: Bits[7]  # Bits 8..14: バッテリー残量 (0〜100%)
    reserved:    Bits[1]  # Bit 15: 予約領域
```

インスタンス化時に各ビット値を個別に指定でき、自動的に1つの整数値（この例では 16-bit / 2バイト）にビットパッキングされます。

```python
status = DeviceStatus(
    powered_on=1,
    busy=0,
    mode=5,
    error_code=2,
    battery_pct=95,
    reserved=0,
)
data = status.to_bytes()
print(f"サイズ: {len(data)} bytes, Hex: 0x{int.from_bytes(data, 'little'):04X}")

# 復元
loaded = DeviceStatus.from_bytes(data)
print(f"Battery: {loaded.battery_pct}%, Mode: {loaded.mode}")
```

### 2.2 パケット境界アライメント (`align=4`, `auto_align=True`)

C言語の構造体パディング規則に準拠したい場合、2つのアライメント指定が利用できます。

#### 明示的アライメント境界 (`align=4`)
構造体の末尾やフィールド間に指定境界（例: 4バイト境界）のパディングを自動挿入します。

```python
from binary_master import UInt8, UInt32, binary_struct

@binary_struct(align=4)
class AlignedPacket:
    type_id: UInt8        # 1 byte
    # -> 3バイトのパディングが自動挿入され、counter は offset 4 から配置
    counter: UInt32       # 4 bytes
    flags: DeviceStatus   # 2 bytes
    # -> 全体サイズを4の倍数にするため、末尾に2バイトのパディングが自動挿入（計12B）

print(sizeof(AlignedPacket))  # => 12
```

#### 自然アライメント (`auto_align=True`)
各型が自身のサイズ境界（例: `UInt16` は2の倍数、`UInt32` は4の倍数）に自動配置されるようパディングが挿入されます。

```python
@binary_struct(auto_align=True)
class NaturalAlignedStruct:
    a: UInt8   # offset 0 (1B)
    # 1B パディング
    b: UInt16  # offset 2 (2B)
    c: UInt32  # offset 4 (4B)

print(sizeof(NaturalAlignedStruct))  # => 8
```

---

## Step 3: 相対オフセットとポインタテーブル（高度なデータ構造）

> 対応サンプルコード: [`sample/03_offsets_and_tables.py`](sample/03_offsets_and_tables.py)

バイナリファイルフォーマット（フォント、3Dモデル、ゲームアーカイブなど）では、ヘッダー内に「データ本体が存在するオフセット位置」を記録することが多々あります。

Binary Master は **オフセットの自動バックパッチ（遅延解決）** と **読み込み時の自動インスタンス化** を標準サポートしています。

### 3.1 自動オフセット計算 (`Offset[T, Base.SELF]`)

```python
from binary_master import (
    Base,
    FixedArray,
    Offset,
    OffsetTable,
    UInt8,
    UInt16,
    UInt32,
    binary_struct,
    BinaryWriter,
)

# 参照先ペイロード
@binary_struct
class TextureData:
    width: UInt16
    height: UInt16
    format: UInt8
    raw_pixels: FixedArray[UInt8, 8]

# コンテナヘッダー
@binary_struct
class AssetContainer:
    magic: UInt32
    version: UInt16
    # 自身の先頭 (Base.SELF) からの相対オフセットを 4バイト整数で格納
    primary_offset: Offset[TextureData, Base.SELF, UInt32]
    # オフセット基準位置にバイアスを付与 (Base.SELF + 0x20)
    aux_offset: Offset[TextureData, Base.SELF + 0x20, UInt32]
    # 2要素のテクスチャオフセット配列テーブル
    num_textures: UInt16
    texture_table: OffsetTable[2, UInt32, Base.SELF]
```

### 3.2 データの書き出しと自動バックパッチ

`BinaryWriter` を使用して書き出す際、オフセット値の手動計算は一切不要です：

```python
writer = BinaryWriter()

# 1. ターゲットデータを先に作成
tex_main = TextureData(width=256, height=256, format=1, raw_pixels=b"MAIN_TEX")
tex_aux  = TextureData(width=128, height=128, format=1, raw_pixels=b"AUX__TEX")
sub_tex1 = TextureData(width=64,  height=64,  format=2, raw_pixels=b"SUB_TEX1")
sub_tex2 = TextureData(width=32,  height=32,  format=2, raw_pixels=b"SUB_TEX2")

# 2. ヘッダーを定義（参照先オブジェクトをそのまま渡す）
container = AssetContainer(
    magic=0x54535341,  # 'ASST'
    version=1,
    primary_offset=tex_main,
    aux_offset=tex_aux,
    num_textures=2,
    texture_table=[sub_tex1, sub_tex2],
)

# 3. 構造体と実体をストリームに書き出す
writer.write_struct(container)
writer.write_struct(tex_main)
writer.write_struct(tex_aux)
writer.write_struct(sub_tex1)
writer.write_struct(sub_tex2)

# 4. バイト列を取得（この時点で全オフセット値が自動計算・書き換えされます）
binary_package = writer.to_bytes()
```

### 3.3 自動デリファレンスによる読み込み

`AssetContainer.from_bytes(binary_package)` で読み込むと、オフセットが指す先の実体データが自動的に `TextureData` インスタンスとして復元されます。

```python
loaded = AssetContainer.from_bytes(binary_package)
print(loaded.primary_offset.target.width)  # => 256
print(bytes(loaded.primary_offset.target.raw_pixels))  # => b'MAIN_TEX'
```

---

## Step 4: 手続き的ライター & リーダーとデバッグ機能（低レベル制御）

> 対応サンプルコード: [`sample/04_procedural_writer.py`](sample/04_procedural_writer.py)

> [!TIP]
> **Writer から直接仕様書や C/Rust ヘッダーを出力可能になりました！**  
> `BinaryWriter` で実際にバイナリを書き進めながら、ワンライナーで `writer.write_markdown("spec.md")` や `writer.write_c_header("spec.h")` を出力できます。  
> 実際の書き込みコードが存在する場合は `BinaryWriter` をそのまま使うのが最も手軽で直感的です。一方、事前にダミーデータなしでプロトコル仕様を設計したい場合や、受信パケットを自動デシリアライズ（`builder.read()`）したい場合は、[Step 5 (`Builder`)](#step-5-スキーマ駆動設計仕様書自動生成多言語出力統合編) を活用します。

構造体を定義するまでもない小さなスクラッチ処理や、ストリームを逐次読み書きしたい場合は `BinaryWriter` と `BinaryReader` を直接使用します。

### 4.1 `BinaryWriter` によるストリーム書き込みとセクションキャプション (`caption`)

`writer.caption("セクション名", "説明")` は、**デバッグ表示やログ出力において、どのバイト群がどの論理ブロック（ファイルヘッダー、メタデータ、ペイロード等）に属しているかをグループ分けして可視化するためのラベル付け機能** です（出力されるバイナリバイト列そのものには一切影響を与えません）。

```python
from binary_master import BinaryWriter

writer = BinaryWriter(default_endian="little")

# デバッグ表示用のセクション名（キャプション）を設定
writer.caption("File Header", "ファイル種別とバージョン情報")
writer.write_uint32(0x46494C45, name="magic", desc="Magic 'FILE'")
writer.write_uint16(2, name="ver_maj", desc="Major version")
writer.write_uint16(0, name="ver_min", desc="Minor version")
```

### 4.2 文字列戦略（Null終端 / 長さプレフィックス / 固定長）

実世界のプロトコルで登場する3大文字列フォーマットをネイティブサポートしています：

```python
# キャプションを "Metadata" に切り替え
writer.caption("Metadata", "テキストメタデータ")

# ① C言語スタイル: Null終端文字列 ('\0')
writer.write_string("SampleApp v2.0", strategy="null_terminated", name="app_name")

# ② Pascalスタイル: 長さプレフィックス（先頭2バイトに文字列長を記録）
writer.write_string("Confidential Document", strategy="prefixed", prefix_bytes=2, name="doc_title")

# ③ 固定長パディング文字列（8バイト固定、空白で埋める）
writer.write_string("AUTH", length=8, strategy="fixed", pad_byte=b" ", name="author_tag")
```

### 4.3 `BinaryReader` によるストリーム読み込み

`BinaryReader` はカーソル位置を追跡しながら、型安全にデータを順次デコードします。

```python
from binary_master import BinaryReader

data = writer.to_bytes()
reader = BinaryReader(data, default_endian="little")

magic = reader.read_uint32()
ver_maj = reader.read_uint16()
ver_min = reader.read_uint16()

app_name = reader.read_cstring(encoding="utf-8")
doc_title = reader.read_prefixed_string(prefix_bytes=2, encoding="utf-8")
author_tag = reader.read_fixed_string(length=8, encoding="utf-8").strip()

print(f"App: {app_name}, Title: {doc_title}, Tag: {author_tag}")
```

### 4.4 充実したデバッグダンプ

Binary Master には、開発効率を飛躍的に高める強力なデバッグツールが備わっています。

#### ① 注釈付き Hexdump (`writer.hexdump()`)
バイト列とASCII表示だけでなく、**どのバイトがどのフィールド名・型に対応しているか** の注釈が横に表示されます。

```python
print(writer.hexdump(color=True))
```

```text
Offset    00 01 02 03 04 05 06 07  08 09 0A 0B 0C 0D 0E 0F  |     ASCII      |  Field Annotations
-------------------------------------------------------------------------------------------------
00000000  45 4c 49 46 02 00 00 00  53 61 6d 70 6c 65 41 70  |ELIF....SampleAp|  magic=0x46494C45 (UInt32); ver_maj=2 (UInt16); ver_min=0 (UInt16); app_name=SampleApp .. (CString)
00000010  70 20 76 32 2e 30 00 15  00 43 6f 6e 66 69 64 65  |p v2.0...Confide|  app_name=SampleApp .. (CString); doc_title=Confidenti.. (PrefixedString[2])
```

#### ② 表形式トレース (`writer.dump("table")`)
全フィールドの Offset, Size, Type, Hex Bytes, Value に加え、**先ほど設定した `Caption`（セクション名）** が右端の列に表示されます。  
デバッグ時に「どのセクションの、どのフィールドを書き込んだか」を一目で突き合わせることができます。

```python
print(writer.dump("table"))
```

```text
+--------+------+---------------+-------------------+--------+----------------------------+-------------------------------------+--------------+
| Offset | Size | Field Name    | Type              | Endian | Hex Bytes                  | Value / Preview                     | Caption      |
+========+======+===============+===================+========+============================+=====================================+==============+
| 0x0000 |   4B | magic         | UInt32            | Little | 45 4c 49 46                | 0x46494C45                          | File Header  |
| 0x0004 |   2B | ver_maj       | UInt16            | Little | 02 00                      | 2                                   | File Header  |
| 0x0006 |   2B | ver_min       | UInt16            | Little | 00 00                      | 0                                   | File Header  |
| 0x0008 |  15B | app_name      | CString           | -      | 53 61 6d 70 6c 65 .. (15B) | SampleApp ..                        | Metadata     |
| 0x0017 |  23B | doc_title     | PrefixedString[2] | Little | 15 00 43 6f 6e 66 .. (23B) | Confidenti..                        | Metadata     |
| 0x002E |   8B | author_tag    | FixedString[8]    | -      | 41 55 54 48 20 20 20 20    | AUTH                                | Metadata     |
+--------+------+---------------+-------------------+--------+----------------------------+-------------------------------------+--------------+
Total: 46 bytes (0x002E) across 6 fields
```

#### ③ リーダーのカーソル位置・残りバイト検査 (`reader.hexdump()`)
現在どこまでパースしたか、残りが何バイトあるかを一目で確認できます。

```python
reader.read_uint32()
print(reader.hexdump())  # --> CURSOR @ 0x0004 と表示される
```

### 4.5 `BinaryWriter` による仕様書・多言語ヘッダーの直接出力 (`write_markdown`, `write_c_header`)

`BinaryWriter` でバイナリを書き進めた後、その書き込み履歴（エントリ）をもとに仕様書や多言語コードを直接生成できます。

```python
# 仕様書（Markdown）の出力
writer.write_markdown("packet_spec.md")

# 各種言語のコード・ヘッダー出力
writer.write_c_header("packet_spec.h")
writer.write_rust("packet_spec.rs")
writer.write_cpp("packet_spec.hpp")
writer.write_csharp("packet_spec.cs", namespace="MyProtocol")
writer.write_go("packet_spec.go", package_name="protocol")

# 拡張子からの自動判別出力
writer.write_code("packet_spec.rs")
```

### 4.6 多態バリアント (`write_variant`) とチャンクの繰り返し集約 (`repeat`)

#### ① 多態バリアント (`write_variant`)
「同じ領域に条件によって異なる構造体が書き込まれる」ケースでは、`candidates`（候補型辞書またはリスト）を指定して書き込みます。

```python
# 候補辞書: {ID: 構造体クラス}
candidates = {1: HeaderChunk, 2: TextChunk}

# タグフィールドと一致しているか検証しながら安全に書き込み
writer.write_uint16(1, name="chunk_type")
writer.write_variant(
    HeaderChunk(version=1, flags=0),
    candidates=candidates,
    tag_field="chunk_type",
    name="payload",
)
```
許可されていない型のインスタンスを渡した場合や、直前に書かれたタグ値と型が不一致の場合は即座にエラーとなります。また、仕様書や C ヘッダーにも候補構造体が自動的に登録されます。

#### ② チャンクの繰り返し集約 (`repeat`)
ループで何十個も同じチャンク構造体を書き込む場合、仕様書テーブルに全チャンクを展開するとドキュメントが肥大化してしまいます。  
`repeat` オプションを指定すると、仕様書上では **「1要素のテンプレート（相対オフセット `+0x00`, `+0x04`...）」** として美しく自動集約されます。

```python
# パターンA: write_struct で直接指定（section は省略可能、クラス名で自動グループ化）
for chunk in chunks:
    writer.write_struct(chunk, repeat="chunk_count")  # 変数名・式を指定可能
    # または不定回数:
    # writer.write_struct(chunk, repeat=-1)

# パターンB: コンテキストマネージャでスコープ化
with writer.repeat("DataChunks", count=-1, desc="可変個のデータチャンク"):
    for chunk in chunks:
        writer.write_struct(chunk)

# パターンC: リストを一括書き込み
writer.write_repeated(chunks, count="num_chunks")
```
- `repeat=-1` や負の数を指定すると、仕様書上には `不定回数 (0回以上 / 可変)`、Mermaid 図には `🔁 (不定回数)` と表記されます。
- `section=""`（デフォルト）のときは、構造体クラス名（例: `Chunk`）が自動的にセクション見出しとして使用されるため、セクション名を手動で書く必要もありません。

---

## Step 5: スキーマ駆動設計・仕様書自動生成・多言語出力（統合編）

> 対応サンプルコード: [`sample/05_builder_and_reader.py`](sample/05_builder_and_reader.py)

### 💡 Writer と Builder の使い分け：Builder の役割と存在理由

Step 4 で見たように、`BinaryWriter` でも仕様書（Markdown）や C/Rust ヘッダーの直接出力、多態バリアント、繰り返しチャンクの集約ができるようになりました。では、`Builder`（`BinaryBuilder`）はどのような場面で必要なのでしょうか？

1. **実データ不要の「スキーマ事前設計」**:
   バイナリデータを実際に書き出すコードやダミーデータを用意しなくても、構造体クラスの登録とプロトコルの章立て（`add_document`）だけで **仕様書や C/Rust ヘッダーを作成** できます。仕様策定フェーズに最適です。
2. **スキーマ駆動の「自動デシリアライズ」(`builder.read`)**:
   受信した生のバイナリ列を渡すだけで、ヘッダーのタグ値や条件分岐をスキーマに従って自動評価し、対応する構造体インスタンスとして一括復元できます（`Reader` で手動で `if/elif` を書く必要がありません）。
3. **コードジェネレータの「内部中間表現 (IR)」**:
   実は `writer.to_c_header()` や各種コード生成機能も、内部では `writer.to_builder()` を介して Builder 構造に変換されて動作しています。Builder はシステム全体の核となるスキーマ表現です。

| 観点 | `BinaryWriter` (コード駆動 / データ駆動) | `Builder` (スキーマ駆動 / 仕様・パーサー駆動) |
|---|---|---|
| **主な用途** | バイナリの生成・出力、書き込み実行ログからの仕様書/ヘッダー自動生成 | プロトコル仕様の先行策定、受信バイナリの自動デシリアライズ |
| **動的な条件分岐** | Python の自然な `if/elif` や `for` ループで柔軟に処理可能 | メタ定義（`add_choice`, `condition`）による静的スキーマ宣言 |
| **実データの要否** | 必要（実際に書き込まれたバイト列から仕様を抽出） | **不要**（クラス定義と章立てドキュメントのみで仕様書/コード出力可） |
| **読み込み (パース)** | 読み込み不可（別途 `BinaryReader` で手動実装） | **自動パース可能** (`builder.read(data)` で一括復元) |

**結論・使い分けの指針**:
- **「バイナリを出力する処理」がある場合（日常使いの 8〜9 割）**: `BinaryWriter` を使うのが最も直感的でコード量も少なくなります。
- **「仕様策定先行」または「受信バイナリの自動パース」を行う場合**: `Builder` が威力を発揮します。

`Builder`（`BinaryBuilder`）を使用することで、事前スキーマ定義から **「仕様書生成」「多言語ヘッダー出力」「自動パーサー」** を1本の定義で完結できます。

### 5.1 `Builder` によるプロトコルスキーマ定義

ネットワークパケットなどの通信仕様を設計します。

```python
from binary_master import (
    Builder,
    UInt8,
    UInt16,
    UInt32,
    Float32,
    FixedArray,
    binary_struct,
)

# 1. パケットの構成要素を定義
@binary_struct(endian="little")
class PacketHeader:
    """共通パケットヘッダー"""
    magic: UInt32         # 'MSGP' (0x4D534750)
    version: UInt16       # プロトコルバージョン
    msg_type: UInt16      # メッセージ種別: 1=Text, 2=Sensor
    payload_size: UInt32  # ペイロード長
    flags: UInt16         # Bit 0: チェックサムフッター有無

@binary_struct
class TextMessage:
    """テキストメッセージペイロード"""
    encoding: UInt16
    text_len: UInt16
    content: FixedArray[UInt8, 16]

@binary_struct
class SensorReport:
    """テレメトリセンサーデータペイロード"""
    sensor_id: UInt32
    temperature: Float32
    pressure: Float32
    humidity: Float32

@binary_struct
class ChecksumFooter:
    """末尾の CRC32 チェックサム"""
    crc32: UInt32
```

### 5.2 多態パケットの分岐 (`add_choice`) と条件分岐 (`condition`)

メッセージ種別（`msg_type`）によって直後のペイロード構造が変化する仕様を定義します。

```python
# Builder インスタンスの作成
builder = Builder(
    title="Network Telemetry Protocol Specification",
    version="1.0.0",
    default_endian="little",
    description="テキスト通信とセンサーテレメトリを統合したバイナリプロトコル仕様書。",
)

# 概要ドキュメント章を追加
builder.add_document("概要とスコープ", "本ドキュメントは NTP-v1 プロトコルの詳細仕様を定めます。")

# セクション（キャプション）で論理グループ化しながら構造体を登録
# （Mermaid フローチャートで自動的に subgraph 枠線としてグループ化されます）
with builder.section("Header Section", "固定長パケットヘッダー"):
    builder.add_struct(PacketHeader, name="header", desc="固定長パケットヘッダー")

with builder.caption("Payload Section", "メッセージ種別に応じたペイロード"):
    builder.add_choice(
        name="payload",
        tag_field="msg_type",
        variants={
            1: (TextMessage, "テキストメッセージペイロード"),
            2: (SensorReport, "環境センサー計測値ペイロード"),
        },
        desc="PacketHeader.msg_type に応じてディスパッチされるペイロード",
    )

with builder.caption("Footer Section", "整合性チェック"):
    builder.add_struct(
        ChecksumFooter,
        name="footer",
        desc="末尾 CRC32 チェックサム",
        condition="flags & 0x01 != 0",
    )
```

### 5.3 仕様書（Markdown & Mermaid 図）のワンライナー出力

`builder.write()` を呼び出すだけで、仕様書 Markdown ファイル（Mermaid フローチャートおよびパケットレイアウト図付き）が瞬時に生成されます。

```python
builder.write("telemetry_protocol_spec.md", diagram_direction="TD")
```

生成される Markdown には以下が含まれます：
- 目次・ドキュメント章
- プロトコルの **Mermaid Flowchart**（条件分岐や多態バリアントのひし形ノード付き）
- 各構造体の **Mermaid packet-beta** 配置図
- 詳細なオフセット・サイズ・型・説明テーブル

### 5.4 多言語ヘッダー出力 (C, Rust, Modern C++, C#, Go)

同じスキーマ定義から、各プログラミング言語の構造体定義コードを生成できます。

```python
# C言語ヘッダー (.h)
builder.write_c_header("telemetry_protocol.h")

# Rust 構造体定義 (.rs)
builder.write_rust("telemetry_protocol.rs")

# Modern C++ ヘッダー (.hpp)
builder.write_cpp("telemetry_protocol.hpp")

# C# クラス/構造体 (.cs)
builder.write_csharp("telemetry_protocol.cs", namespace="TelemetryProtocol")

# Go パッケージ (.go)
builder.write_go("telemetry_protocol.go", package_name="telemetry")
```

各出力には、ビットフィールドのアライメント属性（例: C言語の `#pragma pack(push, 1)`、Rustの `#[repr(C, packed)]` など）が適切に付与されます。

### 5.5 スキーマ駆動の自動デシリアライズ (`builder.read`)

受信した生のバイナリバイト列を `builder.read(data)` に渡すだけで、ヘッダーの `msg_type` や `flags` を自動判別し、適切なクラスのインスタンスとしてパースしてくれます。

```python
from binary_master import BinaryWriter

# パケットバイナリを構築
w = BinaryWriter()
w.write_struct(PacketHeader(magic=0x5047534D, version=1, msg_type=2, payload_size=16, flags=1))
w.write_struct(SensorReport(sensor_id=101, temperature=23.5, pressure=1013.25, humidity=48.0))
w.write_struct(ChecksumFooter(crc32=0xDEADBEEF))
packet_bytes = w.to_bytes()

# スキーマ情報から自動パース！
result = builder.read(packet_bytes)

print(result.header.magic)            # => 0x5047534D
print(type(result.payload).__name__)   # => 'SensorReport'
print(result.payload.temperature)      # => 23.5
print(result.footer.crc32)            # => 0xDEADBEEF
```

手動での `if msg_type == 1: ... elif msg_type == 2: ...` といった分岐処理を書く必要は一切ありません。

### 5.6 スキーマ駆動のデバッグ検査 (`builder.hexdump` / `builder.dump`)

受信したバイナリパケットがスキーマのどのフィールドにどう割り振られているかをデバッグ確認したい場合、`builder.hexdump(data)` や `builder.dump(data, "table")` を使用します。

スキーマ情報（構造体、Choice、条件分岐、セクション）に基づいて、**生のバイト列をフィールド名・値・セクション名付きで自動可視化** できます。

```python
# ① 注釈付き Hexdump（バイト列とフィールドの対応を表示）
print(builder.hexdump(packet_bytes))

# ② セクション（Caption）付きのレイアウト表
print(builder.dump(packet_bytes, format="table"))
```

```text
+--------+------+--------------+---------+--------+-------------+-----------------+-----------------+
| Offset | Size | Field Name   | Type    | Endian | Hex Bytes   | Value / Preview | Caption         |
+========+======+==============+=========+========+=============+=================+=================+
| 0x0000 |   4B | magic        | UInt32  | Little | 4d 53 47 50 | 0x5047534D      | Header Section  |
| 0x0004 |   2B | version      | UInt16  | Little | 01 00       | 1               | Header Section  |
| 0x0006 |   2B | msg_type     | UInt16  | Little | 02 00       | 2               | Header Section  |
| 0x0008 |   4B | payload_size | UInt32  | Little | 10 00 00 00 | 0x10            | Header Section  |
| 0x000C |   2B | flags        | UInt16  | Little | 01 00       | 1               | Header Section  |
| 0x000E |   4B | sensor_id    | UInt32  | Little | 65 00 00 00 | 0x65            | Payload Section |
| 0x0012 |   4B | temperature  | Float32 | Little | 00 00 bc 41 | 23.5            | Payload Section |
| 0x0016 |   4B | pressure     | Float32 | Little | 00 50 7d 44 | 1013            | Payload Section |
| 0x001A |   4B | humidity     | Float32 | Little | 00 00 40 42 | 48              | Payload Section |
| 0x001E |   4B | crc32        | UInt32  | Little | ef be ad de | 0xDEADBEEF      | Footer Section  |
+--------+------+--------------+---------+--------+-------------+-----------------+-----------------+
```

また、`res = builder.read(packet_bytes, trace=True)` で読み込むと、パース結果オブジェクトから直接 `res.hexdump()` や `res.dump("table")` を呼び出すことも可能です。

---

## まとめ & サンプルコードとの対応

| ステップ | トピック | 主な機能・API | 対応サンプルコード |
|---|---|---|---|
| **Step 1** | 基本的な構造体 | `@binary_struct`, プリミティブ型, `FixedArray`, `to_bytes()`, `from_bytes()` | [`sample/01_basic_struct.py`](sample/01_basic_struct.py) |
| **Step 2** | ビットフィールド & アライメント | `Bits[N]`, `bits=16`, `align=4`, `auto_align=True` | [`sample/02_bitfields_and_alignment.py`](sample/02_bitfields_and_alignment.py) |
| **Step 3** | 相対オフセット & テーブル | `Offset`, `Base.SELF`, `OffsetTable`, 自動バックパッチ | [`sample/03_offsets_and_tables.py`](sample/03_offsets_and_tables.py) |
| **Step 4** | 手続き的ライター & リーダー | `BinaryWriter`, `BinaryReader`, 文字列戦略, `hexdump()`, `dump("table")` | [`sample/04_procedural_writer.py`](sample/04_procedural_writer.py) |
| **Step 5** | スキーマ駆動設計 & 多言語出力 | `Builder`, `section()`, `caption()`, `write()`, `builder.read()`, `builder.hexdump()`, `builder.dump()` | [`sample/05_builder_and_reader.py`](sample/05_builder_and_reader.py) |

すべてのサンプルは以下のコマンドでまとめて実行・検証できます：

```bash
python sample/main.py
```

Binary Master を活用して、保守性が高く堅牢なバイナリプロトコル・ファイルフォーマット開発を体験してください！
