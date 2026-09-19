# Binary Master 実践チュートリアル & サンプル集 (Tutorial & Notebooks)

**Binary Master** の基本から実践的な業界別プロトコル設計までを、実行可能な Jupyter Notebook 形式で網羅した総合チュートリアルです。  
GitHub や VSCode、JupyterLab 上で実行結果・ダイアグラム・注釈付き Hexdump をそのまま確認しながら学習できます。

---

## 📚 チュートリアル・ステップ一覧

全 8 本のノートブックは、難易度順に段階的に学習できるように構成されています。

| ステップ | ノートブック | テーマ | 主な学習内容・機能 |
|:---:|---|---|---|
| **Step 1** | [**01_basic_struct.ipynb**](./01_basic_struct.ipynb) | 宣言的構造体と基本型 | `@binary_struct`, 静的型付け基底クラス `BinaryStruct`, 数値型 (`UInt8`〜`UInt64`, `Float32`, `Bool`), 固定長文字列, `to_bytes()`, `read_struct()`, `offsetof()`, エンディアン制御, 辞書/JSON相互変換 (`to_dict`) |
| **Step 2** | [**02_bitfields_and_alignment.ipynb**](./02_bitfields_and_alignment.ipynb) | ビットフィールド & メモリアライメント | `Bits[N]` によるビットパッキング, `align=4` による境界パディング, `auto_align=True` による自然アライメント |
| **Step 3** | [**03_offsets_and_tables.ipynb**](./03_offsets_and_tables.ipynb) | 相対ポインタ & オフセットテーブル | `Offset[Target, Base.SELF]`, オフセット演算 (`Base.SELF + 0x20`), `OffsetTable`, 遅延ポインタバックパッチ, 名前空間スコープ (`with writer.namespace`) |
| **Step 4** | [**04_procedural_writer.ipynb**](./04_procedural_writer.ipynb) | 手続き的ストリーム操作 | `BinaryWriter` / `BinaryReader`, 文字列戦略 (CString / Pascal / Fixed), 多態バリアント (`write_variant`), チャンク集約 (`repeat`), `peek()`, `preserve_position()`, `diff_dump()` |
| **Step 5** | [**05_builder_and_reader.ipynb**](./05_builder_and_reader.ipynb) | スキーマ駆動設計 & 多言語出力 | `Builder` スキーマ定義, セクション/キャプション (`section`), Mermaid パケット図, 5言語コード出力 (C/Rust/C++/C#/Go), `builder.read(data)` 自動逆シリアライズ |
| **Step 6** | [**06_advanced_v2_features.ipynb**](./06_advanced_v2_features.ipynb) | 信頼性・高度プロトコル機能 | `Magic` シグネチャ, `Constant` 制約, `BinaryEnum`, `CRC32` 自動チェックサム計算・検証, LEB128 可変長整数 (`VarInt`/`VarUInt`), 任意ビットストリーム (`BitWriter`/`BitReader`) |
| **Step 7** | [**07_v0_3_0_features.ipynb**](./07_v0_3_0_features.ipynb) | モダン宣言的機能 & 仕様書 | `Float16` (半精度浮動小数点), `LengthOf`/`CountOf` 自動連動計算, `total_size`/`pad_to` 固定サイズ保証, `Range` 値域バリデーション, 双方向 Hex Inspector 付き HTML 仕様書生成 (`write_html`) |
| **Step 8** | [**08_real_world_recipes.ipynb**](./08_real_world_recipes.ipynb) | 実践業界別レシピ集 | ゲームセーブデータ・アーカイブ, IoT / 車載センサーテレメトリ, 高頻度取引 (HFT) 金融ティックロガー (`from_mmap`), 多態RPCメッセージキュー (`Variant`) |

### 🌟 v0.4.0 新機能ハイライト
- **ファイル & ストリーム直接 I/O**: `packet.to_file("data.bin")`, `Packet.from_file("data.bin")`, `Packet.from_stream(stream)` により一時バイト列変換なしで直接入出力。
- **ビットマスクフラグ (`BinaryFlag`)**: `enum.IntFlag` を基底としたビット論理演算 (`|`, `&`, `~`) をフルサポートする型安全フラグ。
- **透過的圧縮 (`Compressed`)**: `Compressed[T, algo="zlib"]` および `CompressedBytes[algo]`（zlib, gzip, bz2, lzma 対応）による自動圧縮・展開。
- **Wireshark Lua ディセクタ生成**: `packet.to_wireshark(port=9999)` / `packet.write_wireshark("proto.lua")`、CLI `binary-master export --lang wireshark` によるパケット解析スクリプト自動生成。
- **非同期 I/O (`asyncio`) ネイティブ対応**: `AsyncBinaryReader` / `AsyncBinaryWriter`、`await packet.to_async_stream(writer)`、`await Packet.from_async_stream(reader)`。

---

## 🏛️ アーキテクチャ設計選定ガイド

### `@binary_struct` vs `BinaryWriter` vs `Builder` 使い分け早見表

| 目的・アプローチ | 推奨コンポーネント | 代表的なシチュエーション |
|---|---|---|
| **ヘッダー・パケットの型安全モデリング** | `@binary_struct` / `BinaryStruct` | Python のクラスとして綺麗に構造体を定義し、`to_bytes()` / `from_bytes()` で直感的に読み書きしたい時。IDE の型補完や静的型検査（ty, mypy, pyright）を活用したい時。 |
| **動的ストリーム・手動オフセット制御** | `BinaryWriter` / `BinaryReader` | 途中で長さをバックパッチしたい時、可変長の生データを順次流し込みたい時、位置保護（`preserve_position`）や先読み（`peek`）が必要な時。 |
| **スキーマ先行プロトコル設計・仕様書生成** | `Builder` | バイナリを書く前にまず仕様書（Markdown / Mermaid図）を確定させたい時、多言語コード（C/Rust/C++/C#/Go）を一斉生成したい時、辞書データから自動パースしたい時。 |

---

## ⚡ ゼロコピー & パフォーマンス最適化

1. **`from_mmap` の活用**:
   - 100MB 以上のファイルや複数GBのログファイルを処理する際は、`BinaryReader.from_mmap("file.bin")` を使用してください。OS のページキャッシュを直接参照し、Python のヒープメモリ消費をほぼゼロに抑えます。
2. **`iter_struct` によるストリーミング**:
   - リスト内包表記で全件を一度にリスト化せず、`for item in reader.iter_struct(Cls):` でイテレータ処理することで、メモリフットプリントを最小限かつ一定に保ちます。
3. **`bytearray` / `memoryview` の直接渡し**:
   - `BinaryReader(buf)` に渡すバッファは `bytes` だけでなく `bytearray` や `memoryview` もそのまま受け付けます。余計なメモリーコピーを発生させずにスライス可能です。

---

## 🛠️ よくある落とし穴 & トラブルシューティング FAQ

> [!WARNING]
> **Q. C言語と構造体のサイズが一致しない（パディングのズレ）**  
> - **原因**: Cコンパイラはデフォルトでメンバのアライメント境界（4バイト境界、8バイト境界）にパディングバイトを挿入します。  
> - **解決策**: `@binary_struct(auto_align=True)` を指定するか、C言語側で `#pragma pack(push, 1)` を指定してアライメント規則を一致させてください。

> [!TIP]
> **Q. エンディアンの指定が複数ある場合、どれが優先されるか？**  
> - **優先順位**:
>   1. フィールド定義時の個別指定（例: `UInt32` の `endian`）
>   2. 構造体デコレータの指定（`@binary_struct(endian="big")`）
>   3. `BinaryWriter` / `BinaryReader` のコンストラクタ指定（`BinaryWriter(default_endian="big")`）
>   4. ライブラリデフォルト（`Endian.LITTLE`）

> [!NOTE]
> **Q. `OffsetTable` のオフセット基準点（BaseOffset）が構造体の先頭からずれる**  
> - **解決策**: デフォルトのオフセットはファイル先頭（`0x0000`）基準です。構造体先頭からの相対オフセットにしたい場合は、`OffsetTable[Count, Type, Base.SELF]` または `Base.SELF + 0x10` などの相対指定を活用してください。

---

## 🚀 実行方法

### 1. 対話的実行 (JupyterLab / VSCode / PyCharm)
VSCode や PyCharm、JupyterLab でノートブックを直接開いて実行できます：

```bash
jupyter lab sample/
```

### 2. 全サンプルの一括自動実行 & 検証
すべてのサンプルノートブックを順番に自動実行し、アサーションと出力を一括検証します：

```bash
python sample/main.py
```
