"""Binary Master - 総合サンプルプログラム (書き込み・仕様書生成・読み込み復元)

本サンプルでは以下の機能を網羅して実演します:
1. @binary_struct による宣言的バイナリ構造体の定義 (docstring、インラインコメント、アライメント)
2. Bits[N] によるビットフィールド定義
3. BinaryWriter によるセクション分割 (caption) とオフセットテーブル (write_offset_table) の予約・書き込み
4. write_manual による仕様書 (Markdown + Mermaid フローチャート + パケット図) の自動生成
5. BinaryReader および from_bytes によるバイナリの読み込みとデシリアライズ (ラウンドトリップ検証)
"""

from pathlib import Path
from binary_master import (
    BinaryReader,
    BinaryWriter,
    Bits,
    Endian,
    FixedArray,
    Offset,
    UInt8,
    UInt16,
    UInt32,
    binary_struct,
)


# ==========================================================
# 1. 構造体定義 (宣言的バイナリ定義)
# ==========================================================

@binary_struct(bits=16)
class PacketFlags:
    """パケット制御フラグ定義 (16ビットビットフィールド)"""
    active: Bits[1]       # 有効フラグ (1: アクティブ, 0: スタンバイ)
    mode: Bits[3]         # 動作モード (0: 通常, 1: 省電力, 2: 高負荷)
    encrypted: Bits[1]    # 暗号化フラグ (1: 暗号化あり, 0: なし)
    priority: Bits[3]     # 優先度レベル (0: 低 〜 7: 最高)
    reserved: Bits[8]     # 将来の拡張用予約領域 (常に 0)


@binary_struct(endian="little", auto_align=True)
class ContainerHeader:
    """コンテナメインヘッダー。全体の基本情報とフラグを保持します。"""
    magic: UInt32         # マジックナンバー ('PKT\x01' = 0x01544B50)
    version: UInt16       # プロトコルバージョン (0x0100 = v1.0)
    flags: PacketFlags    # パケット制御フラグ (16ビット)
    chunk_count: UInt16   # 後続データチャンクの総数
    # auto_align=True により、次の境界に合わせたパディングが自動挿入されます


@binary_struct(endian="little")
class MetadataChunk:
    """メタデータ情報チャンク。"""
    block_id: UInt32      # ブロック固有識別ID
    timestamp: UInt32     # 作成エポック秒 (UTC)
    author_id: UInt16     # 作成者ユーザーID


@binary_struct(endian="little")
class PayloadChunk:
    """暗号化ペイロード実データチャンク。"""
    payload_type: UInt16  # ペイロード種別 (0x0001: センサー, 0x0002: ログ)
    data_length: UInt16   # 実データ長 (バイト数)
    raw_bytes: FixedArray[UInt8, 8]  # ペイロード実バイナリデータ (8バイト固定)


# ==========================================================
# 2. メイン実行ルーチン
# ==========================================================

def main():
    print("=" * 65)
    print(" Binary Master: 総合サンプルプログラム")
    print("=" * 65)

    bin_file = Path(__file__).parent / "sample_output.bin"
    manual_file = Path(__file__).parent / "sample_manual.md"

    # ------------------------------------------------------
    # STEP 1: バイナリデータの構築 & 書き込み (BinaryWriter)
    # ------------------------------------------------------
    print("\n[1] バイナリデータを構築・シリアライズ中...")
    writer = BinaryWriter(default_endian=Endian.LITTLE)

    # (A) ヘッダー領域
    writer.caption("Container Header", "コンテナ全体の基本メタデータ領域")
    header = ContainerHeader(
        magic=0x01544B50,
        version=0x0100,
        flags=PacketFlags(active=1, mode=2, encrypted=1, priority=5, reserved=0),
        chunk_count=2,
    )
    writer.write_struct(header)

    # (B) オフセットテーブル領域 (2エントリ x 4バイトのUInt32オフセット枠を予約)
    writer.caption("Offset Table", "各データチャンクへの開始オフセット配列")
    offset_table = writer.write_offset_table(
        count=2,
        offset_size=4,
        name="chunk_offsets",
        desc="データチャンク開始オフセット",
    )

    # (C) チャンク0 (メタデータ) の書き込み (オフセットを自動記録)
    writer.caption("Metadata Chunk (Chunk 0)", "管理用メタデータブロック")
    meta_chunk = MetadataChunk(
        block_id=1001,
        timestamp=1700000000,
        author_id=42,
    )
    offset_table.write_target(0, meta_chunk)

    # (D) チャンク1 (ペイロード) の書き込み (オフセットを自動記録)
    writer.caption("Payload Chunk (Chunk 1)", "ペイロードバイナリデータブロック")
    payload_chunk = PayloadChunk(
        payload_type=0x0001,
        data_length=8,
        raw_bytes=[0xDE, 0xAD, 0xBE, 0xEF, 0xCA, 0xFE, 0xBA, 0xBE],
    )
    offset_table.write_target(1, payload_chunk)

    # バイナリファイルに出力
    binary_data = writer.to_bytes()
    bin_file.write_bytes(binary_data)
    print(f" -> バイナリ出力完了: {bin_file} ({len(binary_data)} bytes)")
    print(f" -> HEXダンプ: {binary_data.hex(' ')}")

    # ------------------------------------------------------
    # STEP 2: 仕様書 (Markdown + Mermaid) の自動生成
    # ------------------------------------------------------
    print("\n[2] 仕様書 (Markdown) を自動生成中...")
    writer.write_manual(
        manual_file,
        title="バイナリコンテナフォーマット仕様書",
        diagram_type="both",           # フローチャートとパケット図の両方を出力
        diagram_direction="TD",        # フローチャートの向き
        bits_per_row=32,               # パケット図の1行あたりのビット数
        bit_width=45,                  # パケット図セルの横幅 (視認性向上)
        include_bitfield_diagram=True, # ビットフィールドの詳細図を含める
        section_packet_diagrams=True,  # セクションごとの個別パケット図を含める
        include_values=False,          # 仕様書として余分な実行時値を省きスッキリ表示
    )
    print(f" -> 仕様書出力完了: {manual_file}")

    # ------------------------------------------------------
    # STEP 3: バイナリデータの読み込み & 復元 (BinaryReader)
    # ------------------------------------------------------
    print("\n[3] バイナリファイルを読み込み・逆シリアライズ (デコード) 中...")
    with BinaryReader.from_file(bin_file) as reader:
        # ヘッダーをデシリアライズ
        restored_header = reader.read_struct(ContainerHeader)
        print(f"  [Header] Magic: 0x{restored_header.magic:08X}, Version: 0x{restored_header.version:04X}")
        print(f"  [Flags]  Active: {restored_header.flags.active}, Mode: {restored_header.flags.mode}, "
              f"Encrypted: {restored_header.flags.encrypted}, Priority: {restored_header.flags.priority}")
        print(f"  [Chunks] Total: {restored_header.chunk_count}")

        # オフセットテーブルを読み込み
        off0 = reader.read_uint32()
        off1 = reader.read_uint32()
        print(f"  [Offset Table] Chunk 0 @ 0x{off0:04X}, Chunk 1 @ 0x{off1:04X}")

        # オフセット位置から各チャンクをデシリアライズ
        reader.seek(off0)
        restored_meta = reader.read_struct(MetadataChunk)
        print(f"  [Chunk 0 (Metadata)] Block ID: {restored_meta.block_id}, Time: {restored_meta.timestamp}, Author: {restored_meta.author_id}")

        reader.seek(off1)
        restored_payload = reader.read_struct(PayloadChunk)
        print(f"  [Chunk 1 (Payload)]  Type: 0x{restored_payload.payload_type:04X}, Length: {restored_payload.data_length}")
        print(f"                       Data: {restored_payload.raw_bytes.hex(' ')}")

    # ------------------------------------------------------
    # STEP 4: ラウンドトリップの完全一致検証
    # ------------------------------------------------------
    print("\n[4] ラウンドトリップ検証...")
    assert restored_header.magic == header.magic
    assert restored_header.flags.active == header.flags.active
    assert restored_header.flags.priority == header.flags.priority
    assert restored_meta.block_id == meta_chunk.block_id
    assert restored_payload.raw_bytes == bytes(payload_chunk.raw_bytes)
    print(" -> すべてのフィールドが元データと完全一致しました (検証成功！)")
    print("=" * 65)


if __name__ == "__main__":
    main()
