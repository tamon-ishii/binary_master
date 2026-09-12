"""Sample demonstration of BinaryWriter.caption() and automatic manual generation."""

from binary_master import Writer, Endian


def main():
    writer = Writer(default_endian=Endian.LITTLE)

    # 1. ヘッダー部
    writer.caption("ファイルヘッダー")
    writer.write_uint32(0x4D594654, name="magic", desc="ファイル識別子 ('MYFT')")
    writer.write_uint16(1, name="version", desc="フォーマットバージョン")
    writer.write_uint16(0x0003, name="flags", desc="制御フラグ")

    # 2. プレイヤー情報部
    writer.caption("プレイヤー情報")
    writer.write_uint32(1001, name="player_id", desc="プレイヤー識別番号")
    writer.write_fixed_string("Hero", length=16, name="player_name", desc="プレイヤー名 (16バイト固定長)")
    writer.write_uint16(50, name="level", desc="現在のレベル")
    writer.write_uint32(9999, name="hp", desc="体力 (HP)")

    # 3. ペイロード部
    writer.caption("ペイロードデータ")
    writer.write_cstring("Stage 1 Clear!", name="message", desc="ステータスメッセージ")
    writer.pad(2, pad_byte=b"\x00", name="alignment_pad", desc="アライメントパディング")

    # 4. フッター部
    writer.caption("フッター（整合性検証）")
    writer.write_uint32(0xDEADBEEF, name="checksum", desc="CRC-32 チェックサム")

    # バイナリデータ取得
    binary_data = writer.to_bytes()
    print(f"Serialized binary size: {len(binary_data)} bytes")

    # 仕様書 (Markdown) の出力
    from pathlib import Path
    output_path = Path(__file__).parent / "sample_caption_manual.md"
    writer.write_manual(
        output_path,
        title="ゲームセーブデータ仕様書",
        diagram_type="packet",
        section_packet_diagrams=True,
    )
    print(f"Manual successfully written to {output_path}")


if __name__ == "__main__":
    main()
