"""Example generating a comprehensive sample specification manual.

Demonstrates:
- Structure docstrings reflected in overview & section headers
- Field comments extracted into the Description column
- Auto-padding and alignment
- Bitfield packet diagram with comments
- Offset table reserving slots, backpatching, and arrows/markers in manual
- Section packet diagrams
"""

from binary_master import (
    BinaryWriter,
    Bits,
    Endian,
    FixedArray,
    OffsetTable,
    UInt8,
    UInt16,
    UInt32,
    binary_struct,
)


@binary_struct(bits=16)
class SystemFlags:
    """システム制御フラグ定義。動作モードおよび暗号化設定を制御します。"""
    active: Bits[1]       # 有効フラグ (1: アクティブ, 0: スタンバイ)
    mode: Bits[3]         # 動作モード (0: 通常, 1: 省電力, 2: 高負荷)
    encrypted: Bits[1]    # 暗号化フラグ (1: AES-256暗号化あり, 0: 平文)
    priority: Bits[3]     # 優先度レベル (0: 低 〜 7: 最高)
    reserved: Bits[8]     # 拡張用予約領域 (常に0)


@binary_struct(endian="little", auto_align=True)
class FileHeader:
    """総合バイナリコンテナフォーマット仕様。
ヘッダー、オフセットテーブル、各データブロックから構成されます。
"""
    magic: UInt32         # マジックナンバー ('PKT\x01' = 0x01544B50)
    version: UInt16       # プロトコルバージョン (0x0100 = v1.0)
    flags: SystemFlags    # システム制御フラグ (16ビット)
    chunk_count: UInt16   # 後続データチャンクの総数
    # auto_align=True により、16bit メンバ後に 32bit 境界パディングが自動挿入されます


@binary_struct(endian="little")
class MetadataBlock:
    """メタデータ情報ブロック。"""
    block_id: UInt32      # ブロック固有ID
    timestamp: UInt32     # 作成エポック秒 (UTC)
    author_id: UInt16     # 作成者識別ID


@binary_struct(endian="little")
class PayloadBlock:
    """ペイロード実データブロック。"""
    payload_type: UInt16  # ペイロード種別コード (0x0001: センサー, 0x0002: ログ)
    data_length: UInt16   # 実データ長 (バイト数)
    raw_bytes: FixedArray[UInt8, 8]  # ペイロードバイナリデータ


def main():
    writer = BinaryWriter(default_endian=Endian.LITTLE)

    # 1. ヘッダーセクション
    writer.caption("File Header", "コンテナ全体の基本情報とフラグを保持する領域です。")
    header = FileHeader(
        magic=0x01544B50,
        version=0x0100,
        flags=SystemFlags(active=1, mode=2, encrypted=1, priority=5, reserved=0),
        chunk_count=2,
    )
    writer.write_struct(header)

    # 2. オフセットテーブルセクション
    writer.caption("Offset Table", "各データチャンクの開始位置を指す32ビットオフセット配列です。")
    # 2エントリ、各4バイト(UInt32)のオフセットテーブル枠を予約
    table = writer.write_offset_table(
        count=2,
        offset_size=4,
        name="chunk_offsets",
        desc="データチャンク開始オフセット",
    )

    # 3. チャンク0: メタデータブロック
    writer.caption("Metadata Chunk (Chunk 0)", "管理用メタデータが格納されるブロックです。")
    meta = MetadataBlock(
        block_id=1001,
        timestamp=1700000000,
        author_id=42,
    )
    table.write_target(0, meta)

    # 4. チャンク1: ペイロードブロック
    writer.caption("Payload Chunk (Chunk 1)", "暗号化された実データが格納されるブロックです。")
    payload = PayloadBlock(
        payload_type=0x0001,
        data_length=8,
        raw_bytes=[0xDE, 0xAD, 0xBE, 0xEF, 0xCA, 0xFE, 0xBA, 0xBE],
    )
    table.write_target(1, payload)

    # 仕様書を出力
    output_path = "sample_full_manual.md"
    md_content = writer.write_manual(
        path_or_file=output_path,
        title="バイナリコンテナフォーマット仕様書",
        diagram_type="both",
        diagram_direction="TD",
        bits_per_row=32,
        bit_width=45,
        include_bitfield_diagram=True,
        section_packet_diagrams=True,
        include_values=False,
    )

    print(f"Generated manual successfully at: {output_path}")
    print(f"Total binary size: {len(writer.to_bytes())} bytes")


if __name__ == "__main__":
    main()
