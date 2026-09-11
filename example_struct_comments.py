"""Example demonstrating automatic comment extraction from struct definitions."""

from binary_master import (
    Bits,
    UInt8,
    UInt16,
    UInt32,
    binary_struct,
    write_manual,
)


@binary_struct(bits=8)
class Flags:
    compressed: Bits[1]  # 圧縮フラグ (1: 圧縮あり, 0: なし)
    encrypted: Bits[1]   # 暗号化フラグ (1: 暗号化あり, 0: なし)
    reserved: Bits[6]    # 予約領域 (将来の拡張用)


@binary_struct
class Player:
    id: UInt16    # プレイヤー識別ID
    flags: Flags  # 各種ステータスフラグ
    level: UInt8  # 現在のレベル (1〜99)
    hp: UInt32    # 体力パラメータ (最大HP)


def main():
    player = Player(
        id=101,
        flags=Flags(compressed=1, encrypted=0, reserved=0),
        level=50,
        hp=9999,
    )

    output_path = "player_manual.md"
    write_manual(
        player,
        output_path,
        title="プレイヤーパケット仕様書",
        diagram_type="packet",
        bits_per_row=32,
    )
    print(f"Generated {output_path} with comments successfully")


if __name__ == "__main__":
    main()
