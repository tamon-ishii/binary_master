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


@binary_struct(bits=8)
class HeaderFlags:
    compressed: Bits[1]
    encrypted: Bits[1]
    reserved: Bits[6]


@binary_struct
class Image:
    width: UInt16
    height: UInt16
    pixels: FixedArray[UInt8, 4]


@binary_struct
class Header:
    magic: UInt32
    version: UInt16
    flags: HeaderFlags
    image_offset: Offset[Image]


def main():
    header = Header(
        magic=0x474E5089,
        version=1,
        flags=HeaderFlags(compressed=1, encrypted=0, reserved=0),
        image_offset=Image(width=1920, height=1080, pixels=[255, 0, 0, 255]),
    )

    writer = BinaryWriter()
    writer.write_struct(header)

    from pathlib import Path
    output_path = Path(__file__).parent / "sample_manual.md"
    writer.write_manual(output_path, title="Sample Image File Format Manual")
    print(f"Manual successfully written to {output_path}")


if __name__ == "__main__":
    main()