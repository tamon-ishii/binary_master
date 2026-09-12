"""Sample 04: Procedural BinaryWriter and BinaryReader Stream Operations.

Demonstrates:
- Imperative/procedural binary construction using BinaryWriter
- Encoded string strategies: null-terminated, length-prefixed, fixed-length
- Alignment padding, cursor seeking, and overwriting
- Layout captions and subcaptions for manual generation
- Procedural stream reading using BinaryReader
- Exporting concrete execution manuals with writer.write_manual()
"""

from binary_master import BinaryReader, BinaryWriter


def main():
    print("=== Sample 04: Procedural BinaryWriter & Reader ===")

    writer = BinaryWriter(default_endian="little")

    # 1. Section with Caption: File Header
    with writer.caption("File Header", "Container header identifying format and version"):
        writer.write_uint32(0x46494C45, name="magic", desc="Magic 'FILE'")
        writer.write_uint16(2, name="version_major", desc="Major version")
        writer.write_uint16(0, name="version_minor", desc="Minor version")

    # 2. Section with Caption: Metadata and Strings
    with writer.caption("Metadata", "Textual metadata and application properties"):
        # C-style null-terminated string
        writer.write_string("SampleApp v2.0", encoding="utf-8", strategy="null_terminated", name="app_name", desc="App Name")
        # 2-byte length prefixed string
        writer.write_string("Confidential Document", encoding="utf-8", strategy="prefixed", prefix_bytes=2, name="doc_title", desc="Doc Title")
        # Fixed length padded string
        writer.write_string("AUTH", length=8, strategy="fixed", pad_byte=b" ", name="author_tag", desc="Author Tag")

    # 3. Section: Alignment and seeking
    with writer.caption("Payload Data", "Binary data aligned to 4-byte boundary"):
        writer.align(4, pad_byte=b"\x00", name="padding", desc="Alignment padding")

        payload_pos = writer.tell()
        print(f"Payload aligned offset: 0x{payload_pos:04X}")
        writer.write_bytes(b"\xCA\xFE\xBA\xBE\xDE\xAD\xBE\xEF", name="payload_bytes", desc="Payload bytes")

    data = writer.to_bytes()
    print(f"Total procedural binary size: {len(data)} bytes")

    # 4. Read back using BinaryReader
    reader = BinaryReader(data, default_endian="little")
    magic = reader.read_uint32()
    ver_maj = reader.read_uint16()
    ver_min = reader.read_uint16()
    app_name = reader.read_cstring(encoding="utf-8")
    doc_title = reader.read_prefixed_string(prefix_bytes=2, encoding="utf-8")
    auth_tag = reader.read_fixed_string(length=8, encoding="utf-8").strip()

    print("\nDeserialized via BinaryReader:")
    print(f"  magic:      0x{magic:08X}")
    print(f"  version:    {ver_maj}.{ver_min}")
    print(f"  app_name:   {app_name}")
    print(f"  doc_title:  {doc_title}")
    print(f"  auth_tag:   {auth_tag}")

    assert magic == 0x46494C45
    assert app_name == "SampleApp v2.0"
    assert doc_title == "Confidential Document"
    assert auth_tag == "AUTH"

    # 5. Generate instance manual
    manual_md = writer.write_manual(title="Procedural Container Manual")
    print(f"\nGenerated manual length: {len(manual_md)} characters")
    print("Procedural writer and reader operations verified successfully!")


if __name__ == "__main__":
    main()
