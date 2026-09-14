"""Tests for Writer-driven variant validation, specification, and code generation."""

from pathlib import Path

import pytest

from binary_master import (
    BinaryWriter,
    UInt8,
    UInt16,
    UInt32,
    binary_struct,
    generate_code,
    to_c_header,
    write_variant,
)


@binary_struct
class Header:
    magic: UInt32
    msg_type: UInt8


@binary_struct
class StatusPayload:
    """Status message payload."""
    status_code: UInt16


@binary_struct
class SensorPayload:
    """Sensor reading payload."""
    sensor_id: UInt8
    temperature: UInt16


@binary_struct
class ErrorPayload:
    """Error information payload."""
    error_code: UInt32


def test_write_variant_with_list_candidates():
    """Test write_variant with simple list of struct classes."""
    w = BinaryWriter()
    w.write_struct(Header(magic=0x1234, msg_type=1))

    # Writing valid candidate
    w.write_variant(
        StatusPayload(status_code=200),
        candidates=[StatusPayload, SensorPayload],
        name="Payload",
    )
    data = w.to_bytes()
    assert len(data) == 5 + 2  # Header (5) + StatusPayload (2)

    # Invalid candidate should raise TypeError
    w2 = BinaryWriter()
    with pytest.raises(TypeError, match="not in variant candidates"):
        w2.write_variant(
            ErrorPayload(error_code=404),
            candidates=[StatusPayload, SensorPayload],
        )


def test_write_variant_with_dict_and_tag_check():
    """Test write_variant with dict candidates and tag_field consistency check."""
    w = BinaryWriter()
    w.write_uint8(1, name="msg_type")

    # Correct tag match (msg_type=1 matches tag 1: StatusPayload)
    w.write_variant(
        StatusPayload(status_code=200),
        candidates={1: StatusPayload, 2: SensorPayload},
        tag_field="msg_type",
        name="PayloadChoice",
    )
    assert len(w.to_bytes()) == 1 + 2

    # Tag mismatch should raise ValueError
    w_mismatch = BinaryWriter()
    w_mismatch.write_uint8(1, name="msg_type")
    with pytest.raises(ValueError, match="Tag mismatch"):
        w_mismatch.write_variant(
            SensorPayload(sensor_id=5, temperature=25),
            candidates={1: StatusPayload, 2: SensorPayload},
            tag_field="msg_type",
        )


def test_writer_expect_validation():
    """Test writer.expect pre-registering candidates and validating subsequent write_struct."""
    w = BinaryWriter()
    w.expect(candidates=[StatusPayload, SensorPayload], name="ExpectedSlot")

    # Disallowed struct raises TypeError
    with pytest.raises(TypeError, match="not in expected variant candidates"):
        w.write_struct(ErrorPayload(error_code=500))

    # Allowed struct succeeds
    w2 = BinaryWriter()
    w2.expect(candidates=[StatusPayload, SensorPayload], name="ExpectedSlot")
    w2.write_struct(StatusPayload(status_code=200))
    assert len(w2.to_bytes()) == 2


def test_writer_to_markdown():
    """Test writer.to_markdown() generates full specification with diagrams and variants."""
    w = BinaryWriter()
    w.caption("Packet Header")
    w.write_struct(Header(magic=0x42494E59, msg_type=1))
    w.caption("Payload")
    w.write_variant(
        StatusPayload(status_code=200),
        candidates={1: StatusPayload, 2: SensorPayload},
        tag_field="msg_type",
        name="PayloadChoice",
        desc="Dynamic payload dispatched by msg_type",
    )

    md = w.to_markdown(title="Telemetry Protocol")
    assert "# Telemetry Protocol" in md
    assert "Packet Header" in md
    assert "Payload" in md
    assert "StatusPayload" in md
    assert "SensorPayload" in md
    assert "Tag `0x0001`" in md
    assert "Tag `0x0002`" in md
    assert "```mermaid" in md


def test_writer_to_c_header():
    """Test writer.to_c_header() generates complete C header with enum, structs, and union."""
    w = BinaryWriter()
    w.write_struct(Header(magic=0x42494E59, msg_type=1))
    w.write_variant(
        StatusPayload(status_code=200),
        candidates={1: StatusPayload, 2: SensorPayload},
        tag_field="msg_type",
        name="PayloadChoice",
    )

    header = w.to_c_header()
    assert "typedef struct Header {" in header
    assert "typedef enum PayloadChoiceTag {" in header
    assert "PAYLOAD_CHOICE_TAG_STATUS_PAYLOAD = 0x01" in header
    assert "PAYLOAD_CHOICE_TAG_SENSOR_PAYLOAD = 0x02" in header
    assert "typedef struct StatusPayload {" in header
    assert "typedef struct SensorPayload {" in header
    assert "typedef union PayloadChoiceUnion {" in header
    assert "StatusPayload status_payload;" in header
    assert "SensorPayload sensor_payload;" in header

    # Test top-level function to_c_header(w)
    assert to_c_header(w) == header


def test_writer_to_code_all_languages():
    """Test multi-language code export directly from BinaryWriter."""
    w = BinaryWriter(default_endian="little")
    w.write_struct(Header(magic=0x42494E59, msg_type=1))
    w.write_variant(
        StatusPayload(status_code=200),
        candidates={1: StatusPayload, 2: SensorPayload},
        tag_field="msg_type",
        name="PayloadChoice",
    )

    rust_code = w.to_rust()
    assert "pub struct Header" in rust_code
    assert "pub enum PayloadChoiceTag" in rust_code
    assert "pub struct StatusPayload" in rust_code
    assert "pub struct SensorPayload" in rust_code
    assert "pub enum PayloadChoiceUnion" in rust_code

    cpp_code = w.to_cpp()
    assert "struct Header" in cpp_code
    assert "struct StatusPayload" in cpp_code
    assert "enum class PayloadChoiceTag" in cpp_code or "PayloadChoiceTag" in cpp_code

    csharp_code = w.to_csharp()
    assert "public struct Header" in csharp_code
    assert "public enum PayloadChoiceTag" in csharp_code

    go_code = w.to_go()
    assert "type Header struct" in go_code
    assert "PayloadChoiceTag" in go_code

    # generate_code helper directly on writer
    for lang in ["c", "rust", "cpp", "csharp", "go"]:
        code = generate_code(w, lang)
        assert len(code) > 0


def test_top_level_write_variant_function():
    """Test top-level write_variant function."""
    w = write_variant(
        StatusPayload(status_code=100),
        candidates=[StatusPayload, SensorPayload],
        name="Payload",
    )
    assert isinstance(w, BinaryWriter)
    assert len(w.to_bytes()) == 2
    assert "StatusPayload" in w.to_c_header()


def test_write_variant_file_export(tmp_path: Path):
    """Test writing markdown and C header to disk directly from writer."""
    w = BinaryWriter()
    w.write_struct(Header(magic=0x42494E59, msg_type=1))
    w.write_variant(
        StatusPayload(status_code=200),
        candidates={1: StatusPayload, 2: SensorPayload},
        tag_field="msg_type",
    )

    md_file = tmp_path / "spec.md"
    c_file = tmp_path / "protocol.h"
    rs_file = tmp_path / "protocol.rs"

    w.write_markdown(md_file)
    w.write_c_header(c_file)
    w.write_code(rs_file, lang="rust")

    assert md_file.exists()
    assert "Header" in md_file.read_text(encoding="utf-8")

    assert c_file.exists()
    assert "typedef struct Header" in c_file.read_text(encoding="utf-8")

    assert rs_file.exists()
    assert "pub struct Header" in rs_file.read_text(encoding="utf-8")
