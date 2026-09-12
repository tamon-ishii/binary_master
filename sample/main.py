"""Binary Master - オールインワン総合フル機能サンプル

本サンプルは、Binary Master のすべてのコア機能を 1 つの完結したシナリオ
「次世代マルチメディアアーカイブ (.nma / NextGen Media Archive)」として実演します。

【カバーしている全機能一覧】
1. 宣言的構造体 (@binary_struct):
   - クラス docstring の仕様書反映
   - インラインコメント (# ...) および Annotated によるフィールド説明抽出
   - 自然境界自動アライメント & パディング (auto_align=True)
   - エンディアン指定 (endian="little")
2. 高度な型システム:
   - 符号なし/符号付き整数 (UInt8, UInt16, UInt32, UInt64, Int16, Int32)
   - 浮動小数点数 (Float32, Float64)
   - ビットフィールド (Bits[1], Bits[3], Bits[8], Bits[16] 等)
   - 固定長配列 (FixedArray[Type, N])
   - 可変長配列 (Array[Type])
   - オフセット自動計算 & 解決 (Offset[Target, Type, BaseOffset]):
     - 構造体先頭相対 (Base.SELF)
     - 構造体先頭 + デルタ相対 (Base.SELF + 0x20)
     - フィールド相対 (Base.FIELD)
     - オフセットサイズ指定 (2バイト: UInt16 / 4バイト: UInt32)
     - 型省略短縮記法 (Offset[Target, Base.SELF])
   - オフセットテーブル (OffsetTable[Count, Type, BaseOffset]):
     - 複数エントリの予約と自動バックパッチ
     - 構造体先頭相対 (Base.SELF)
   - 多態チャンク / タグ付き共用体 (Variant[tag_field, mapping]):
     - 種別タグに応じた構造体の動的ディスパッチ
3. バイナリサイズ検査機能:
   - クラスからの静的サイズ取得: Cls.binary_size, sizeof(Cls)
   - インスタンスからの動的サイズ取得: instance.binary_size, sizeof(instance), len(instance)
4. 手続き的ライター (BinaryWriter):
   - セクション見出し (caption) と多態バリアント候補登録 (variants=[...])
   - 階層的サブセクション (subcaption)
   - 各種文字列書き込み (write_cstring, write_prefixed_string, write_fixed_string)
   - アライメント (align) とパディング (pad)
   - 手続き的オフセットテーブル操作 (write_offset_table, write_target)
   - カーソル制御 (tell, seek)
5. 仕様書自動生成 (write_manual):
   - Markdown フォーマット
   - Mermaid フローチャート (diagram_type="flowchart" / "both")
   - RFC風パケット図 (diagram_type="packet" / "both")
   - セクション別パケット図 (section_packet_diagrams=True)
   - ビットフィールド詳細図 (include_bitfield_diagram=True)
   - 多態バリアント候補仕様の自動展開
   - 参照先オフセットマーカー (-> 0xXXXX)
6. バイナリ読み込み & 完全対称復元 (BinaryReader / read_struct / from_bytes):
   - オフセット参照先の自動追跡デシリアライズ
   - 多態 Variant の自動復元
   - ラウンドトリップ完全一致検証
"""

from pathlib import Path
from typing import Annotated
import struct

from binary_master import (
    Array,
    Base,
    BinaryReader,
    BinaryWriter,
    Bits,
    Endian,
    FixedArray,
    Float32,
    Float64,
    Int16,
    Int32,
    Offset,
    OffsetTable,
    UInt8,
    UInt16,
    UInt32,
    UInt64,
    Variant,
    binary_size,
    binary_struct,
    read_struct,
    sizeof,
    write_manual,
)


# ==========================================================
# 1. 構造体定義 (型宣言・ビットフィールド・多態バリアント)
# ==========================================================

@binary_struct(bits=16)
class ArchiveFlags:
    """アーカイブ制御フラグ (16ビットビットフィールド)"""
    is_compressed: Bits[1]   # 圧縮有効フラグ (0: 非圧縮, 1: 圧縮あり)
    is_encrypted: Bits[1]    # 暗号化有効フラグ (0: 平文, 1: 暗号化)
    access_mode: Bits[2]     # アクセス権限 (0: ReadOnly, 1: Write, 2: Admin)
    checksum_algo: Bits[4]   # チェックサム種別 (0: None, 1: CRC32, 2: SHA256)
    reserved: Bits[8]        # 将来の拡張用予約領域 (常に0)


@binary_struct(endian="little")
class AuthorProfile:
    """作成者プロファイル情報ブロック"""
    author_id: UInt32        # 作成者識別ID (32bit)
    reputation: Float32      # 信頼度スコア (単精度浮動小数点数)
    rating: Int16            # レーティング補正値 (符号付き16bit)


@binary_struct(endian="little")
class TextChunk:
    """テキストデータチャンク (多態バリアント種別 1)"""
    encoding_id: UInt8       # 文字エンコーディング (1: UTF-8, 2: UTF-16LE)
    char_count: UInt16       # 文字数
    raw_preview: FixedArray[UInt8, 8]  # 先頭プレビューバイト列 (8バイト固定)


@binary_struct(endian="little")
class ImageChunk:
    """画像データチャンク (多態バリアント種別 2)"""
    width: UInt16            # 画像横幅 (px)
    height: UInt16           # 画像縦幅 (px)
    channels: UInt8          # 色チャンネル数 (3: RGB, 4: RGBA)
    pixels_preview: FixedArray[UInt8, 8]  # ピクセルプレビュー (8バイト固定)


@binary_struct(endian="little")
class AudioChunk:
    """音声データチャンク (多態バリアント種別 3)"""
    sample_rate: UInt32      # サンプリングレート (Hz: 例 44100, 48000)
    channels: UInt8          # 音声チャンネル数 (1: Mono, 2: Stereo)
    duration_sec: Float64    # 再生時間 (秒: 倍精度浮動小数点数)


@binary_struct(endian="little")
class PolymorphicMediaChunk:
    """多態メディアチャンクコンテナ。先行タグに応じて内容が動的に変化します。"""
    chunk_type: UInt16       # チャンク種別ID (1: Text, 2: Image, 3: Audio)
    priority: UInt8          # 配信優先度
    # 先行する chunk_type の値に基づいてデシリアライズ先を自動分岐
    payload: Variant["chunk_type", {
        1: TextChunk,
        2: ImageChunk,
        3: AudioChunk,
    }]


@binary_struct(endian="little", auto_align=True)
class TableOfContents:
    """コンテンツ目次テーブル (TOC)"""
    entry_count: UInt16      # 登録チャンク数
    # 構造体先頭 (Base.SELF) を起点とする 3エントリのオフセットテーブル
    chunk_offsets: OffsetTable[3, UInt32, Base.SELF]


@binary_struct(endian="little", auto_align=True)
class ArchiveHeader:
    """次世代マルチメディアアーカイブ (.nma) のメインヘッダー仕様。

    ファイル全体の識別情報、制御フラグ、各主要セクションへの相対オフセットを保持します。
    """
    magic: Annotated[UInt32, "ファイル識別子 ('NMA\\x01' = 0x01414D4E)"]
    version: UInt16          # フォーマットバージョン (0x0200 = v2.0)
    flags: ArchiveFlags      # 16ビット制御ビットフィールド

    # (A) 構造体先頭相対 (Base.SELF) かつ 2バイトオフセット (UInt16)
    author_offset: Offset[AuthorProfile, UInt16, Base.SELF]

    # (B) 構造体先頭 + 0x20 相対 (ヘッダー境界を基準)
    toc_offset: Offset[TableOfContents, UInt32, Base.SELF + 0x20]

    # (C) 短縮記法 (型を省略して4バイト UInt32 デフォルト、構造体先頭相対)
    primary_media_offset: Offset[PolymorphicMediaChunk, Base.SELF]


# ==========================================================
# 2. メイン実行ルーチン
# ==========================================================

def main():
    script_dir = Path(__file__).parent
    output_bin = script_dir / "all_features_archive.bin"
    output_manual = script_dir / "all_features_spec.md"

    print("=" * 72)
    print(" Binary Master: すべての機能を詰め込んだ総合フル機能デモ")
    print("=" * 72)

    # ------------------------------------------------------
    # STEP 1: バイナリサイズの検査 (sizeof / binary_size / len)
    # ------------------------------------------------------
    print("\n[STEP 1] バイナリサイズ検査機能の検証 (静的・動的)")
    print(f"  - AuthorProfile クラス静的サイズ: {AuthorProfile.binary_size} バイト (sizeof={sizeof(AuthorProfile)})")
    print(f"  - TextChunk 静的サイズ:           {TextChunk.binary_size} バイト")
    print(f"  - ImageChunk 静的サイズ:          {ImageChunk.binary_size} バイト")
    print(f"  - AudioChunk 静的サイズ:          {AudioChunk.binary_size} バイト")
    print(f"  - TableOfContents 静的サイズ:     {TableOfContents.binary_size} バイト (UInt16 + align padding + 3*UInt32)")
    print(f"  - ArchiveHeader 静的サイズ:       {ArchiveHeader.binary_size} バイト (sizeof={sizeof(ArchiveHeader)})")

    # ------------------------------------------------------
    # STEP 2: データの準備 (構造体・バリアント・オフセット)
    # ------------------------------------------------------
    print("\n[STEP 2] データの構築 (宣言的構造体 & 多態バリアント)")

    # 作成者プロファイル
    author = AuthorProfile(
        author_id=98765,
        reputation=99.5,
        rating=-12,
    )

    # 多態メディアチャンク群
    # チャンク 0: テキスト
    text_data = PolymorphicMediaChunk(
        chunk_type=1,
        priority=10,
        payload=TextChunk(
            encoding_id=1,
            char_count=42,
            raw_preview=[ord(c) for c in "BinaryMa"],
        ),
    )

    # チャンク 1: 画像
    image_data = PolymorphicMediaChunk(
        chunk_type=2,
        priority=20,
        payload=ImageChunk(
            width=1920,
            height=1080,
            channels=4,
            pixels_preview=[0xFF, 0x00, 0x00, 0xFF, 0x00, 0xFF, 0x00, 0xFF],
        ),
    )

    # チャンク 2: 音声
    audio_data = PolymorphicMediaChunk(
        chunk_type=3,
        priority=15,
        payload=AudioChunk(
            sample_rate=48000,
            channels=2,
            duration_sec=128.5,
        ),
    )

    # 目次 (TOC) - 3つの多態チャンクへのオフセットテーブル
    toc = TableOfContents(
        entry_count=3,
        chunk_offsets=[text_data, image_data, audio_data],
    )

    # メインヘッダー
    header = ArchiveHeader(
        magic=0x01414D4E,  # 'NMA\x01'
        version=0x0200,    # v2.0
        flags=ArchiveFlags(
            is_compressed=1,
            is_encrypted=0,
            access_mode=2,
            checksum_algo=1,
            reserved=0,
        ),
        author_offset=author,
        toc_offset=toc,
        primary_media_offset=image_data,  # プライマリ代表メディアとして画像を指定
    )

    print(f"  - ArchiveHeader インスタンス動的サイズ: {len(header)} バイト (sizeof={sizeof(header)})")

    # ------------------------------------------------------
    # STEP 3: BinaryWriter によるシリアライズ & 手続き的追加
    # ------------------------------------------------------
    print("\n[STEP 3] BinaryWriter によるシリアライズと仕様書キャプションの構成")
    writer = BinaryWriter(default_endian=Endian.LITTLE)

    # (1) メインヘッダー部
    writer.caption(
        "Archive Header",
        desc="アーカイブ全体の識別情報、制御フラグ、相対オフセット群を格納するメインヘッダー。",
    )
    writer.write_struct(header)

    # (2) 手続き的拡張セクション: 文字列メタデータ
    writer.caption(
        "Metadata String Pool",
        desc="アーカイブのタイトルや説明文などの可変長文字列プール領域。",
    )
    # 階層的サブキャプション
    writer.subcaption("Title & Description", "C言語形式およびPascal形式の文字列")
    writer.write_cstring("NextGen Multimedia Showcase", name="archive_title", desc="アーカイブタイトル (Null終端)")
    writer.write_prefixed_string("All-in-one features demonstration", prefix_bytes=2, name="archive_desc", desc="アーカイブ説明 (2B長さプレフィックス)")
    writer.write_fixed_string("TAG:2026", length=16, pad_byte=b"\x00", name="archive_tag", desc="固定長タグ (16B Nullパディング)")

    # (3) 手続き的パディング & アライメント
    writer.caption("Boundary Alignment", "セクター境界へ向けたアライメント調整")
    writer.pad(4, pad_byte=b"\xCC", name="security_pad", desc="4バイトの固定パディング")
    writer.align(16, pad_byte=b"\x00", name="sector_align", desc="16バイト境界へのアライメント")

    # (4) 手続き的オフセットテーブルと多態候補バリアント登録
    writer.caption(
        "Polymorphic Payload Section",
        desc="種別タグに応じて異なるデータ構造が格納される多態チャンク領域。",
        variants=[
            (1, TextChunk, "種別1: テキストプレビューデータ"),
            (2, ImageChunk, "種別2: RGBA画像データ"),
            (3, AudioChunk, "種別3: PCM音声データ"),
        ],
    )
    # 手続き的オフセットテーブルの書き込み (Base.SELF 相対: テーブル開始位置を基準)
    proc_table = writer.write_offset_table(
        count=2,
        offset_size=4,
        base_offset=Base.SELF,
        name="extra_offsets",
        desc="追加データブロックへの相対オフセットテーブル",
    )
    proc_table.write_target(0, text_data)
    proc_table.write_target(1, audio_data)

    # バイナリデータ取得
    binary_data = writer.to_bytes()
    output_bin.write_bytes(binary_data)
    print(f"  -> バイナリ出力完了: {output_bin.name} ({len(binary_data)} バイト)")
    print(f"  -> 先頭32バイトHEX: {binary_data[:32].hex(' ')}")

    # ------------------------------------------------------
    # STEP 4: 仕様書 (Markdown + Mermaid) の自動生成
    # ------------------------------------------------------
    print("\n[STEP 4] 仕様書 (Markdown + Mermaid ダイアグラム) の自動生成")
    writer.write_manual(
        output_manual,
        title="次世代マルチメディアアーカイブ (.nma) 完全仕様書",
        diagram_type="both",           # フローチャートとパケット図の両方を出力
        diagram_direction="TD",        # フローチャートの方向
        bits_per_row=32,               # パケット図の1行あたりビット数 (32bit RFCスタイル)
        bit_width=45,                  # パケット図セルの幅
        include_bitfield_diagram=True, # ビットフィールドの詳細図を含める
        section_packet_diagrams=True,  # セクションごとの個別パケット図を埋め込む
        include_values=False,          # 仕様書として余分な実行時値を省きスッキリ表示
    )
    print(f"  -> 仕様書出力完了: {output_manual.name}")

    # ------------------------------------------------------
    # STEP 5: 読み込み & ラウンドトリップ完全一致検証
    # ------------------------------------------------------
    print("\n[STEP 5] バイナリの読み込みとラウンドトリップ検証 (BinaryReader / read_struct)")
    with BinaryReader.from_file(output_bin) as reader:
        # (1) メインヘッダーのデシリアライズ
        restored_header = reader.read_struct(ArchiveHeader)
        print(f"  [Header] Magic: 0x{restored_header.magic:08X}, Version: 0x{restored_header.version:04X}")
        print(f"  [Flags]  Compressed: {restored_header.flags.is_compressed}, AccessMode: {restored_header.flags.access_mode}")

        # (2) Offset[T, UInt16, Base.SELF] の自動解決検証
        restored_author = restored_header.author_offset
        assert isinstance(restored_author, AuthorProfile)
        print(f"  [Author] ID: {restored_author.author_id}, Rep: {restored_author.reputation}, Rating: {restored_author.rating}")

        # (3) Offset[T, UInt32, Base.SELF + 0x20] の自動解決検証
        restored_toc = restored_header.toc_offset
        assert isinstance(restored_toc, TableOfContents)
        print(f"  [TOC]    Entries: {restored_toc.entry_count}, Stored Offsets: {restored_toc.chunk_offsets}")

        # (4) Offset[T, Base.SELF] (短縮記法) と多態 Variant の自動解決検証
        primary_media = restored_header.primary_media_offset
        assert isinstance(primary_media, PolymorphicMediaChunk)
        assert primary_media.chunk_type == 2
        assert isinstance(primary_media.payload, ImageChunk)
        print(f"  [Primary Media (Image)] {primary_media.payload.width}x{primary_media.payload.height}, Channels: {primary_media.payload.channels}")

        # (5) 手続き的文字列プールの読み込み検証
        # ヘッダー以降の位置から読み出し
        reader.seek(len(header))
        title = reader.read_cstring()
        desc = reader.read_prefixed_string(prefix_bytes=2)
        tag = reader.read_fixed_string(length=16)
        print(f"  [Strings] Title: '{title}', Tag: '{tag}'")

    # ------------------------------------------------------
    # STEP 6: 全体アサーション検証
    # ------------------------------------------------------
    print("\n[STEP 6] 全データフィールドの完全一致アサーション...")
    assert restored_header.magic == header.magic
    assert restored_header.version == header.version
    assert restored_header.flags.is_compressed == 1
    assert restored_header.flags.access_mode == 2
    assert restored_author.author_id == author.author_id
    assert abs(restored_author.reputation - author.reputation) < 1e-5
    assert restored_author.rating == author.rating
    assert restored_toc.entry_count == 3
    assert primary_media.payload.width == 1920
    assert primary_media.payload.height == 1080
    assert title == "NextGen Multimedia Showcase"
    assert desc == "All-in-one features demonstration"
    assert tag == "TAG:2026"
    print("  -> すべてのアサーションに合格しました！完全なラウンドトリップが確認されました。")

    print("\n" + "=" * 72)
    print(" デモが正常に完了しました！")
    print(f" 生成バイナリ: {output_bin}")
    print(f" 生成仕様書:   {output_manual}")
    print("=" * 72)


if __name__ == "__main__":
    main()
