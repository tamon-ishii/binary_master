# Binary Master (`binary-master`)

[![Python](https://img.shields.io/badge/python-3.14+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-299%20passed-brightgreen.svg)]()

**Binary Master** は、Python 3.14+ 向けの高速・型安全なバイナリシリアライザ兼仕様書・コード自動生成ツールキットです。  
宣言的データクラス記法によるパケット定義、ビットフィールド、相対オフセットの自動解決、CRC検証、圧縮ペイロード（zlib/gzip/bz2/lzma）、Mermaid/HTML仕様書生成、Wireshark Lua ディセクタおよび 5 言語（C, Rust, Modern C++, C#, Go）へのコード出力を包括的にサポートします。

### 🌟 主な特徴
- **⚡ 超高速**: `StructPlan` キャッシュとゼロコピー読み込みにより、700,000+ ops/sec の高速処理を実現。
- **🛡️ 型安全 & 自動検証**: `Magic` シグネチャ、`CRC32` 計算、`Range` 値域制約、`LengthOf`/`CountOf` 連動計算を宣言的に定義・自動検証。
- **🗜️ 透過的圧縮 & ビットマスク**: `Compressed[T, algo]` による構造体・バイト列の透過的圧縮（zlib/gzip/bz2/lzma）、`BinaryFlag`（`IntFlag`）による直感的なビットマスク。
- **📡 非同期ストリーム & ファイルI/O**: `.to_file()` / `.from_file()` に加え、`asyncio` ネイティブな `AsyncBinaryReader` / `AsyncBinaryWriter` / `.to_async_stream()` を標準提供。
- **📊 仕様書・Wireshark・多言語コード生成**: Mermaid パケット構造図、双方向 Hex Inspector 付き HTML 仕様書、Wireshark Lua ディセクタ、5 言語のヘッダー/コードをワンライナーで生成。

```python
from binary_master import binary_struct, Magic, UInt16, Float32, CString, CRC32

# 1. 宣言的にパケット構造を定義（データクラス感覚）
@binary_struct
class SensorPacket:
    magic: Magic[b"PKT\x01"]               # ヘッダーシグネチャ（自動検証）
    sensor_id: UInt16                      # 2バイト符号なし整数
    temperature: Float32                   # 4バイト浮動小数点数
    device_name: CString                   # Null終端文字列
    checksum: CRC32                        # CRC32（シリアライズ時自動計算・読み込み時自動検証）

# 2. シリアライズ & ファイル / バイト列のデシリアライズ
packet = SensorPacket(sensor_id=101, temperature=24.5, device_name="Sensor-A")
packet.to_file("sensor.bin")               # ファイルへ直接出力
restored = SensorPacket.from_file("sensor.bin")  # ファイルから自動復元・検証

# 3. HTML 仕様書・Wireshark ディセクタ・多言語コード生成
packet.write_html("sensor_spec.html", title="センサー通信パケット仕様書")
packet.write_wireshark("sensor.lua", port=9999) # Wireshark で解析可能な Lua ディセクタ
print(packet.to_rust())                         # Rust 構造体を即時出力
```

> 📖 **実践チュートリアル & ガイド**: 実行結果や図解付きで学べる対話型 **[Jupyter Notebook サンプル集 (sample/)](sample/)** および **[総合ガイド (sample/README.md)](sample/README.md)** をご覧ください。  
> 🤖 **AI・LLM コンテキスト**: LLM へのプロンプト入力に最適な情報密度の **[AI向け完全リファレンス (FOR_AI.md)](FOR_AI.md)** も用意されています。

---

## 動作要件・インストール

- **動作要件**: Python 3.14 以上

```bash
# uv を使用する場合（GitHub から直接追加）
uv add https://github.com/tamon-ishii/binary_master.git

# またはパッケージ名から追加
uv add binary-master

# pip を使用する場合
pip install git+https://github.com/tamon-ishii/binary_master.git
# またはローカルクローンからインストール
pip install .
```

### パッケージのビルド（Wheel / `.whl`）

```bash
# uv によるビルド（dist/ に .whl および .tar.gz を生成）
uv build

# または標準 build ツール (PEP 517)
python -m build
```

---

## 対話型サンプルガイド (Jupyter Notebooks)

詳細なコード例やチュートリアルは、リポジトリ内の `sample/` ディレクトリに Jupyter Notebook 形式で網羅されています。GitHub 上でも実行結果付きでそのまま閲覧可能です。

| Notebook | テーマ | 主な学習内容・トピック |
|---|---|---|
| [**01_basic_struct.ipynb**](sample/01_basic_struct.ipynb) | 基本的な宣言的構造体 | `@binary_struct`, 静的型付け基底クラス `BinaryStruct`, プリミティブ数値型, エンディアン制御, `to_dict()` / `from_dict()` |
| [**02_bitfields_and_alignment.ipynb**](sample/02_bitfields_and_alignment.ipynb) | ビットフィールドとアライメント | `Bits[N]` によるビットパッキング, `align=4` パディング, `auto_align=True` 自然アライメント |
| [**03_offsets_and_tables.ipynb**](sample/03_offsets_and_tables.ipynb) | 相対ポインタ & オフセットテーブル | `Offset[T, Base.SELF]`, オフセット演算 (`Base.SELF + 0x20`), `OffsetTable`, 遅延バックパッチ |
| [**04_procedural_writer.ipynb**](sample/04_procedural_writer.ipynb) | 手続き的ストリーム操作 | `BinaryWriter` / `BinaryReader`, `peek()`, `preserve_position()`, `diff_dump()`, 注釈付き Hexdump |
| [**05_builder_and_reader.ipynb**](sample/05_builder_and_reader.ipynb) | Builder とスキーマ駆動パース | 事前スキーマ定義 (`Builder`), 多態選択 (`add_choice`), スキーマ駆動自動リーダー (`builder.read()`) |
| [**06_advanced_v2_features.ipynb**](sample/06_advanced_v2_features.ipynb) | 信頼性・高度プロトコル機能 | `CRC32`/`CRC16`/`Checksum8`, `BinaryEnum`, `Magic`/`Constant`, LEB128 `VarInt`, `BitWriter`/`BitReader` |
| [**07_v0_3_0_features.ipynb**](sample/07_v0_3_0_features.ipynb) | モダン宣言的機能 & 仕様書 | `Float16`, `LengthOf`/`CountOf` 連動計算, `total_size`/`pad_to`, `Range` バリデーション, HTML仕様書 |
| [**08_real_world_recipes.ipynb**](sample/08_real_world_recipes.ipynb) | 実践業界別レシピ集 | ゲームセーブデータ, IoT テレメトリ, 金融ティックログ (`from_mmap`), 多態RPCメッセージ (`Variant`) |

```bash
# 全サンプルの自動実行・検証
python sample/main.py
```

---

## 主要な使い方

### 1. 宣言的構造体 (`@binary_struct` / `BinaryStruct`)

パケット構造を Python の型アノテーションで直感的に定義できます。

```python
from binary_master import (
    binary_struct,
    Bits,
    FixedArray,
    Offset,
    UInt8,
    UInt16,
    UInt32,
    sizeof,
)

# 1バイト（8ビット）のビットフィールド
@binary_struct(bits=8)
class HeaderFlags:
    compressed: Bits[1]
    encrypted: Bits[1]
    reserved: Bits[6]

# 子構造体
@binary_struct
class Image:
    width: UInt16
    height: UInt16
    pixels: FixedArray[UInt8, 4]

# メインヘッダー（Image へのオフセットを保持）
@binary_struct
class Header:
    magic: UInt32 = 0x474E5089
    flags: HeaderFlags
    image: Offset[Image] = None  # オフセット位置は to_bytes() 時に自動解決

header = Header(flags=HeaderFlags(compressed=1, encrypted=0, reserved=0))
header.image = Image(width=1920, height=1080, pixels=[255, 0, 0, 255])

# シリアライズとデバッグ表示
data = header.to_bytes()
print(header.hexdump())  # フィールド境界が色分けされた注釈付き Hexdump を表示
```

また、型安全性を高め、IDE のコード補完や静的型チェッカー（mypy / pyright）の警告を完全に解消したい場合は、`BinaryStruct` を継承して定義することも可能です：

```python
from binary_master import BinaryStruct, UInt32, Float32

class Telemetry(BinaryStruct):
    timestamp: UInt32
    voltage: Float32

# IDE 上で引数の型ヒント・補完が完全に動作
packet = Telemetry(timestamp=1700000000, voltage=3.3)
```

### 2. 手続き的ライター & リーダー (`BinaryWriter` / `BinaryReader`)

動的なパケット構築や、低レイヤのバイトストリーム操作を直感的に行えます。

```python
from binary_master import BinaryWriter, BinaryReader

w = BinaryWriter()
w.write_uint16(0x0102)
w.write_cstring("Hello")
w.align(4)  # 4バイト境界に自動パディング
data = w.to_bytes()

r = BinaryReader(data)
val = r.read_uint16()
msg = r.read_cstring()

# カーソルを進めずに先読み
magic = r.peek_uint16()

# 一時的な位置移動と自動復帰
with r.preserve_position():
    r.seek(0)
    first_bytes = r.read_bytes(4)
```

### 3. 非同期ストリーミング (`asyncio` 連携)

`asyncio.StreamReader` / `asyncio.StreamWriter` と連携し、ネットワークソケットやパイプからパケットを非同期送受信できます。

```python
import asyncio
from binary_master import AsyncBinaryReader, AsyncBinaryWriter

async def handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    # 非同期リーダーでパケットを受信
    async_reader = AsyncBinaryReader(reader)
    packet = await async_reader.read_struct(SensorPacket)
    print(f"Received sensor data: {packet.temperature} °C")

    # 構造体インスタンスからソケットへ直接送信
    await packet.to_async_stream(writer)
```

### 4. 仕様書 & Wireshark / 多言語コード生成

単一の構造体定義や `Builder` スキーマから、仕様書と Wireshark Lua ディセクタ、および 5 言語のヘッダー・ソースコードをワンライナーで出力できます。

```python
# 1. 仕様書生成
header.write_markdown("spec.md")      # Mermaid パケット図付き Markdown
header.write_html("spec.html")        # 双方向 Hex Inspector 付き HTML 仕様書

# 2. Wireshark Lua ディセクタ生成
header.write_wireshark("proto.lua", port=9999)  # Wireshark 解析用スクリプト

# 3. 多言語コード生成
header.to_c()                         # C言語ヘッダー (.h)
header.to_cpp()                       # Modern C++20 ヘッダー (.hpp)
header.to_rust()                      # Rust 構造体 (.rs)
header.to_csharp()                    # C# クラス (.cs)
header.to_go()                        # Go 構造体 (.go)
```

---

## 型システム一覧

| カテゴリ | 型名 | サイズ | 説明 / 使用例 |
|---|---|---|---|
| **整数型** | `UInt8`, `Int8`<br>`UInt16`, `Int16`<br>`UInt32`, `Int32`<br>`UInt64`, `Int64` | 1B<br>2B<br>4B<br>8B | 符号なし / 符号付き整数 |
| **浮動小数点** | `Float16`<br>`Float32`<br>`Float64` | 2B<br>4B<br>8B | IEEE 754 半精度浮動小数点数<br>IEEE 754 単精度浮動小数点数<br>IEEE 754 倍精度浮動小数点数 |
| **真偽値** | `Bool` | 1B | 1バイトブール値 (`0x00` / `0x01`) |
| **ビットフィールド** | `Bits[N]` | N bit | `@binary_struct(bits=N)` 内で 1 ビット単位でパッキング |
| **ビットマスクフラグ** | `BinaryFlag` (または `enum.IntFlag`) | 基底型依存 | ビット論理演算 (`\|`, `&`) をサポートする型安全フラグ |
| **可変長整数** | `VarInt`, `VarUInt` | 1〜10B | LEB128 可変長整数 (Protocol Buffers / WebAssembly 互換) |
| **透過的圧縮** | `Compressed[T, algo]`<br>`CompressedBytes[algo]` | 4B(長さ) + 圧縮列 | `zlib`, `gzip`, `bz2`, `lzma` による自動圧縮・展開 |
| **文字列** | `FixedString[N, enc]`<br>`CString[enc]`<br>`PascalString[len_t, enc]` | N バイト<br>可変 (Null終端)<br>可変 (長さプレフィックス) | 固定長文字列<br>CスタイルNull終端文字列<br>Pascal文字列（UTF-8, Shift-JIS等対応） |
| **配列** | `FixedArray[T, N]`<br>`VariableArray[T, count_expr]` | `sizeof(T) * N`<br>可変 | 固定長要素配列<br>動的要素配列 |
| **オフセット・ポインタ** | `Offset[T, Base]`<br>`OffsetTable[T, Count, Base]` | 指定サイズ (既定 4B)<br>`sizeof(T) * Count` | 相対オフセット（自動解決・遅延バックパッチ）<br>ポインタテーブル |
| **列挙型** | `BinaryEnum` (または `enum.IntEnum`) | 基底型依存 | 型安全な名前付き列挙値 |
| **定数・制約** | `Magic[b"..."]`<br>`Constant[val]` | 固定長<br>基底型依存 | ヘッダーシグネチャ検証（不一致時エラー）<br>固定値アサーション |
| **チェックサム** | `CRC32`, `CRC16`<br>`Checksum8`, `Checksum16` | 4B / 2B<br>1B / 2B | シリアライズ時に自動計算、デシリアライズ時に自動検証 |
| **値域バリデーション** | `Range[Type, min, max]` | `sizeof(Type)` | 許容範囲外の値を検知（`RangeValidationError`） |
| **連動サイズ計算** | `LengthOf[Type, "field"]`<br>`CountOf[Type, "field"]` | `sizeof(Type)` | 指定フィールドのバイト長 / 配列要素数を自動計算＆連動 |

---

## CLI ツール (`binary-master`)

バイナリファイルの検査、差分比較、仕様書生成、コードエクスポートを行うコマンドラインツールが付属しています。

```bash
# 構造体を指定してバイナリファイルを検査（注釈付き Hexdump / 表 / JSON）
binary-master inspect data.bin --struct my_module:SensorPacket --color

# 2つのバイナリファイルの差分をカラーハイライト比較
binary-master diff expected.bin actual.bin --color

# 構造体定義から仕様書（Markdown / HTML）を自動生成
binary-master spec my_module:SensorPacket -o spec.html --html

# Wireshark Lua ディセクタおよび多言語コード（c, rust, cpp, csharp, go, wireshark）のエクスポート
binary-master export my_module:SensorPacket -l wireshark -o packet.lua
binary-master export my_module:SensorPacket -l rust -o packet.rs
```

---

## テストの実行

```bash
# ユニットテスト (280+ tests)
pytest

# 全 Jupyter Notebook サンプルの一括実行・検証
python sample/main.py
```

---

## ドキュメント一覧

- 📘 **[実践チュートリアル & ガイド (sample/README.md)](sample/README.md)**: 基礎から応用、アーキテクチャ選定、トラブルシューティングまで徹底解説
- 📓 **[Jupyter Notebook サンプル集 (sample/)](sample/)**: GitHub 上でもそのまま閲覧・実行できる 8 本の対話型ノートブック
- 🤖 **[AI向け完全リファレンス (FOR_AI.md)](FOR_AI.md)**: LLM/AI エージェント向け凝縮仕様書

---

## ライセンス

MIT License
