"""Tests for Float16 (IEEE 754 half-precision floating point) support."""

import shutil
import subprocess
from pathlib import Path

import pytest

from binary_master import (
    BinaryReader,
    BinaryWriter,
    Builder,
    Endian,
    FixedArray,
    Float16,
    Float32,
    UInt8,
    UInt16,
    binary_struct,
    offsetof,
    sizeof,
    to_c_struct,
)
from binary_master.code_gen import (
    generate_cpp_code,
    generate_csharp_code,
    generate_go_code,
    generate_rust_code,
)


def test_float16_sizeof():
    """Verify sizeof(Float16) returns 2."""
    assert sizeof(Float16) == 2
    assert Float16._size == 2
    assert Float16._fmt == "e"


def test_writer_and_reader_float16_roundtrip():
    """Verify write_float16 and read_float16 round-trip with various values."""
    writer = BinaryWriter(default_endian=Endian.LITTLE)
    writer.write_float16(1.5)
    writer.write_float16(-2.0)
    writer.write_float16(0.0)
    writer.write_float16(65504.0)  # Max normal half-precision float

    data = writer.to_bytes()
    assert len(data) == 8

    reader = BinaryReader(data, default_endian=Endian.LITTLE)
    assert reader.read_float16() == 1.5
    assert reader.read_float16() == -2.0
    assert reader.read_float16() == 0.0
    assert reader.read_float16() == 65504.0


def test_writer_and_reader_float16_endianness():
    """Verify Float16 endianness handling (little vs big endian)."""
    # 1.5 in IEEE 754 half:
    # sign=0, exponent=15, fraction=0.5 -> 0x3E00
    # Big-endian: b'\x3e\x00', Little-endian: b'\x00\x3e'
    w_le = BinaryWriter(default_endian=Endian.LITTLE)
    w_le.write_float16(1.5)
    assert w_le.to_bytes() == b"\x00\x3e"

    w_be = BinaryWriter(default_endian=Endian.BIG)
    w_be.write_float16(1.5)
    assert w_be.to_bytes() == b"\x3e\x00"

    r_le = BinaryReader(b"\x00\x3e", default_endian=Endian.LITTLE)
    assert r_le.read_float16() == 1.5

    r_be = BinaryReader(b"\x3e\x00", default_endian=Endian.BIG)
    assert r_be.read_float16() == 1.5


def test_writer_float16_invalid_type():
    """Verify write_float16 raises TypeError on invalid types."""
    writer = BinaryWriter()
    with pytest.raises(TypeError, match="write_float16 requires a float or int"):
        writer.write_float16("invalid")  # type: ignore


@binary_struct(endian="little")
class SensorReading:
    sensor_id: UInt8
    temperature: Float16
    humidity: Float16


def test_binary_struct_float16():
    """Verify @binary_struct works seamlessly with Float16 fields."""
    reading = SensorReading(sensor_id=1, temperature=23.5, humidity=55.0)
    data = reading.to_bytes()
    assert len(data) == 5

    restored = SensorReading.from_bytes(data)
    assert restored.sensor_id == 1
    assert abs(restored.temperature - 23.5) < 1e-3
    assert abs(restored.humidity - 55.0) < 1e-3


def test_binary_struct_float16_sizeof_and_offsetof():
    """Verify sizeof and offsetof with Float16."""
    assert sizeof(SensorReading) == 5
    assert offsetof(SensorReading, "sensor_id") == 0
    assert offsetof(SensorReading, "temperature") == 1
    assert offsetof(SensorReading, "humidity") == 3


@binary_struct(auto_align=True)
class AlignedFloat16Struct:
    flag: UInt8
    # 1 byte padding automatically inserted for 2-byte alignment of Float16
    temp: Float16
    val32: Float32


def test_binary_struct_float16_auto_alignment():
    """Verify natural 2-byte alignment for Float16."""
    assert offsetof(AlignedFloat16Struct, "flag") == 0
    assert offsetof(AlignedFloat16Struct, "temp") == 2
    assert offsetof(AlignedFloat16Struct, "val32") == 4
    assert sizeof(AlignedFloat16Struct) == 8


@binary_struct
class Float16ArrayContainer:
    count: UInt16
    samples: FixedArray[Float16, 3]


def test_binary_struct_float16_fixed_array():
    """Verify FixedArray of Float16."""
    container = Float16ArrayContainer(count=3, samples=[1.0, 2.5, -0.5])
    data = container.to_bytes()
    assert len(data) == 2 + 3 * 2  # 8 bytes

    restored = Float16ArrayContainer.from_bytes(data)
    assert restored.count == 3
    assert [round(x, 2) for x in restored.samples] == [1.0, 2.5, -0.5]


def test_float16_json_and_dict():
    """Verify to_dict / from_dict / to_json / from_json with Float16."""
    reading = SensorReading(sensor_id=42, temperature=18.5, humidity=60.0)
    d = reading.to_dict()
    assert d["sensor_id"] == 42
    assert d["temperature"] == 18.5
    assert d["humidity"] == 60.0

    restored = SensorReading.from_dict(d)
    assert restored.sensor_id == 42
    assert restored.temperature == 18.5

    json_str = reading.to_json()
    assert '"temperature": 18.5' in json_str
    restored_json = SensorReading.from_json(json_str)
    assert restored_json.humidity == 60.0


def test_builder_float16_ad_hoc_field():
    """Verify Builder support with Float16."""
    builder = Builder(title="Float16 Test Protocol")
    builder.add_field("header", "UInt16", 2)
    builder.add_field("half_float", "Float16", 2)

    writer = BinaryWriter(default_endian=Endian.LITTLE)
    writer.write_uint16(0x1234)
    writer.write_float16(3.125)

    res = builder.read(writer.to_bytes(), endian="little")
    assert res.header == 0x1234
    assert abs(res.half_float - 3.125) < 1e-3


def test_code_generation_float16():
    """Verify code generation across C, C++, Rust, C#, and Go."""
    c_code = to_c_struct(SensorReading)
    assert "_Float16 temperature;" in c_code
    assert "_Float16 humidity;" in c_code

    builder = Builder(title="Sensor Protocol")
    builder.add_struct(SensorReading)

    # C++
    cpp_code = generate_cpp_code(builder)
    assert "_Float16 temperature;" in cpp_code

    # Rust
    rust_code = generate_rust_code(builder)
    assert "pub temperature: f16," in rust_code

    # C#
    csharp_code = generate_csharp_code(builder)
    assert "public Half Temperature;" in csharp_code

    # Go
    go_code = generate_go_code(builder)
    assert "Temperature uint16 // float16" in go_code


def test_c_header_float16_gcc_compilation(tmp_path: Path):
    """Verify GCC compilation of generated C header with _Float16."""
    if not shutil.which("gcc"):
        pytest.skip("gcc not available")

    builder = Builder(title="Float16 Protocol")
    builder.add_struct(SensorReading)

    header_file = tmp_path / "sensor.h"
    builder.write_c_header(header_file)
    assert header_file.exists()

    c_source = tmp_path / "test.c"
    c_source.write_text(
        """
#include "sensor.h"

void test(void) {
    SensorReading r;
    r.sensor_id = 1;
    r.temperature = (_Float16)23.5f;
    r.humidity = (_Float16)55.0f;
    (void)r;
}
""",
        encoding="utf-8",
    )

    res = subprocess.run(
        ["gcc", "-fsyntax-only", "-Wall", "-Werror", str(c_source)],
        capture_output=True,
        text=True,
    )
    assert res.returncode == 0, f"GCC error: {res.stderr}"


def test_float16_markdown_manual():
    """Verify Markdown manual generates correct entry for Float16."""
    md = SensorReading.to_markdown()
    assert "Float16" in md
    assert "temperature" in md
    assert "humidity" in md
