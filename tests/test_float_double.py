"""Unit tests for Float and Double/double aliases."""

import pytest
from binary_master import (
    binary_struct,
    Float,
    Double,
    double,
    Float32,
    Float64,
    BinaryWriter,
    BinaryReader,
    Builder,
    Range,
    RangeValidationError,
    FixedArray,
    sizeof,
)


def test_float_double_identity():
    """Float is Float32, Double is Float64, double is Double."""
    assert Float is Float32
    assert Double is Float64
    assert double is Float64
    assert Float._size == 4
    assert Float._fmt == "f"
    assert Double._size == 8
    assert Double._fmt == "d"


def test_binary_struct_float_double():
    """Test declarative struct using Float and Double."""
    @binary_struct
    class Telemetry:
        temp: Float
        pressure: Double
        altitude: double

    assert sizeof(Telemetry) == 20
    t = Telemetry(temp=25.5, pressure=1013.25, altitude=150.75)
    data = t.to_bytes()
    assert len(data) == 20

    restored = Telemetry.from_bytes(data)
    assert abs(restored.temp - 25.5) < 1e-5
    assert abs(restored.pressure - 1013.25) < 1e-9
    assert abs(restored.altitude - 150.75) < 1e-9


def test_writer_reader_float_double():
    """Test BinaryWriter and BinaryReader write_float/double and read_float/double."""
    writer = BinaryWriter()
    writer.write_float(12.34)
    writer.write_double(56.789012)
    data = writer.to_bytes()
    assert len(data) == 12

    reader = BinaryReader(data)
    assert abs(reader.read_float() - 12.34) < 1e-4
    assert abs(reader.read_double() - 56.789012) < 1e-9


def test_float_double_range_validation():
    """Test Range[Float, min, max] and Range[Double, min, max]."""
    @binary_struct
    class CalibratedSensor:
        gain: Range[Float, 0.0, 10.0]
        offset: Range[Double, -100.0, 100.0]

    valid = CalibratedSensor(gain=5.0, offset=-25.0)
    data = valid.to_bytes()
    assert len(data) == 12

    restored = CalibratedSensor.from_bytes(data)
    assert abs(restored.gain - 5.0) < 1e-5
    assert abs(restored.offset - (-25.0)) < 1e-9

    with pytest.raises(RangeValidationError):
        CalibratedSensor(gain=15.0, offset=0.0).to_bytes()

    with pytest.raises(RangeValidationError):
        CalibratedSensor(gain=1.0, offset=150.0).to_bytes()


def test_float_double_arrays():
    """Test FixedArray with Float and Double."""
    @binary_struct
    class VectorBlock:
        f_vec: FixedArray[Float, 3]
        d_vec: FixedArray[Double, 2]

    assert sizeof(VectorBlock) == 12 + 16
    v = VectorBlock(f_vec=[1.0, 2.0, 3.0], d_vec=[10.0, 20.0])
    data = v.to_bytes()
    assert len(data) == 28

    restored = VectorBlock.from_bytes(data)
    assert restored.f_vec == [1.0, 2.0, 3.0]
    assert restored.d_vec == [10.0, 20.0]


def test_builder_float_double():
    """Test Builder ad-hoc fields with Float and Double."""
    b = Builder(title="Float Double Test")
    b.add_field("temperature", "Float", 4)
    b.add_field("coordinate", "Double", 8)

    raw = b.to_bytes({"temperature": 23.5, "coordinate": 139.767})
    assert len(raw) == 12

    res = b.read(raw)
    assert abs(res.temperature - 23.5) < 1e-4
    assert abs(res.coordinate - 139.767) < 1e-9


def test_code_gen_float_double():
    """Test code generation for structs using Float and Double."""
    @binary_struct
    class Point:
        x: Float
        y: Double

    c_code = Point.to_c()
    assert "float x;" in c_code
    assert "double y;" in c_code

    cpp_code = Point.to_cpp()
    assert "float x" in cpp_code
    assert "double y" in cpp_code

    rust_code = Point.to_rust()
    assert "pub x: f32," in rust_code
    assert "pub y: f64," in rust_code

    cs_code = Point.to_csharp()
    assert "public float X;" in cs_code
    assert "public double Y;" in cs_code

    go_code = Point.to_go()
    assert "float32" in go_code
    assert "float64" in go_code
