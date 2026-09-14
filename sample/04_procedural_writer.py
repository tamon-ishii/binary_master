"""Sample 04: Procedural BinaryWriter, Variants, Repeating Chunks, and Direct Specs.

Demonstrates:
- Imperative binary construction using BinaryWriter
- Encoded string strategies: null-terminated, length-prefixed, fixed-length
- Polymorphic variants with candidate validation using writer.write_variant()
- Repeating chunk structures aggregated automatically in specifications using repeat
- Generating Markdown specs and C headers directly from BinaryWriter (no Builder required!)
- Procedural stream reading using BinaryReader
- Specialized debug dumping: annotated hexdump, tabular trace, and reader cursor inspection
"""

from pathlib import Path

from binary_master import (
    BinaryReader,
    BinaryWriter,
    FixedArray,
    Float32,
    UInt8,
    UInt16,
    UInt32,
    binary_struct,
)


# 1. Define struct classes for variants and repeated records
@binary_struct
class HeaderChunk:
    """Configuration header parameters."""

    protocol_version: UInt16
    flags: UInt16


@binary_struct
class TextChunk:
    """Text data chunk payload."""

    length: UInt16
    content: FixedArray[UInt8, 16]


@binary_struct
class DataRecord:
    """Repeating measurement data record."""

    record_id: UInt32
    timestamp: UInt32
    value: Float32


def main():
    print("=== Sample 04: Procedural BinaryWriter, Variants & Repeating Chunks ===")

    writer = BinaryWriter(default_endian="little")

    # 1. Section: File Header
    writer.caption("File Header", "Container header identifying format and version")
    writer.write_uint32(0x46494C45, name="magic", desc="Magic 'FILE'")
    writer.write_uint16(2, name="version_major", desc="Major version")
    writer.write_uint16(0, name="version_minor", desc="Minor version")

    # 2. Section: Metadata and Strings
    writer.caption("Metadata", "Textual metadata and application properties")
    writer.write_string("SampleApp v2.0", encoding="utf-8", strategy="null_terminated", name="app_name", desc="App Name")
    writer.write_string("Confidential Document", encoding="utf-8", strategy="prefixed", prefix_bytes=2, name="doc_title", desc="Doc Title")
    writer.write_string("AUTH", length=8, strategy="fixed", pad_byte=b" ", name="author_tag", desc="Author Tag")

    # 3. Section: Polymorphic Variant with candidate validation
    writer.caption("Dynamic Payload", "Dynamic payload dispatched by chunk_type")
    candidates = {
        1: HeaderChunk,
        2: TextChunk,
    }
    # Write tag field
    writer.write_uint16(1, name="chunk_type", desc="1=HeaderChunk, 2=TextChunk")
    # Write variant with runtime candidate validation and tag matching
    writer.write_variant(
        HeaderChunk(protocol_version=10, flags=0x0001),
        candidates=candidates,
        tag_field="chunk_type",
        name="payload",
        desc="Configuration header variant",
    )

    # 4. Section: Repeating Chunks (repeat="num_records")
    # Clear the previous caption.
    # When section="" is omitted on write_struct, it automatically creates a dedicated
    # section named after the struct class: "DataRecord" and aggregates repeated chunks!
    writer.caption(None)
    records = [
        DataRecord(record_id=1, timestamp=1000, value=25.5),
        DataRecord(record_id=2, timestamp=1001, value=26.0),
        DataRecord(record_id=3, timestamp=1002, value=26.5),
    ]
    writer.write_uint16(len(records), name="num_records", desc="Number of following data records")
    for record in records:
        writer.write_struct(record, repeat="num_records")

    data = writer.to_bytes()
    print(f"Total procedural binary size: {len(data)} bytes")

    # =========================================================================
    # 5. One-Stop Specification & C Header Generation Directly from Writer!
    # (No Builder required!)
    # =========================================================================
    sample_dir = Path(__file__).parent
    spec_path = sample_dir / "writer_output_spec.md"
    header_path = sample_dir / "writer_output.h"

    writer.write_markdown(spec_path, title="Procedural Binary Protocol Specification")
    writer.write_c_header(header_path)
    print(f"\nGenerated specification manual saved to: {spec_path.name}")
    print(f"Generated C header saved to:             {header_path.name}")

    # =========================================================================
    # 6. Read back using BinaryReader
    # =========================================================================
    reader = BinaryReader(data, default_endian="little")
    magic = reader.read_uint32()
    ver_maj = reader.read_uint16()
    ver_min = reader.read_uint16()
    app_name = reader.read_cstring(encoding="utf-8")
    doc_title = reader.read_prefixed_string(prefix_bytes=2, encoding="utf-8")
    auth_tag = reader.read_fixed_string(length=8, encoding="utf-8").strip()

    chunk_type = reader.read_uint16()
    payload = reader.read_struct(candidates[chunk_type])

    num_recs = reader.read_uint16()
    read_records = [reader.read_struct(DataRecord) for _ in range(num_recs)]

    print("\nDeserialized via BinaryReader:")
    print(f"  magic:        0x{magic:08X}")
    print(f"  version:      {ver_maj}.{ver_min}")
    print(f"  app_name:     {app_name}")
    print(f"  chunk_type:   {chunk_type} ({type(payload).__name__})")
    print(f"  payload ver:  {payload.protocol_version}")
    print(f"  num_records:  {num_recs}")
    print(f"  record[0]:    id={read_records[0].record_id}, val={read_records[0].value:.1f}")

    assert magic == 0x46494C45
    assert app_name == "SampleApp v2.0"
    assert isinstance(payload, HeaderChunk)
    assert len(read_records) == 3

    # =========================================================================
    # 7. Specialized Debug Dumping
    # =========================================================================
    print("\n--- Annotated Hexdump (first 48 bytes) ---")
    print(writer.hexdump()[:600] + "\n  ...")

    print("\n--- Field Trace Table (writer.dump('table')) ---")
    print(writer.dump("table"))

    print("\nProcedural writer, variants, repeat deduplication, and direct exports verified successfully!")


if __name__ == "__main__":
    main()
