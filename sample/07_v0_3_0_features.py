"""Sample 07: v0.3.0 Features.

Demonstrates:
1. Float16: IEEE 754 half-precision 16-bit floating point
2. LengthOf & CountOf: Automatic length/count calculation and linked deserialization
3. total_size & pad_to: Struct fixed total size enforcement and writer padding
4. Range: Value range validation on serialization and deserialization
5. to_html() / write_html(): Standalone interactive HTML specification with Hex Inspector
"""

import tempfile
from pathlib import Path
from binary_master import (
    binary_struct,
    UInt8,
    UInt16,
    UInt32,
    Int16,
    Float16,
    Bytes,
    Array,
    LengthOf,
    CountOf,
    Range,
    RangeValidationError,
    TotalSizeExceededError,
    BinaryWriter,
    BinaryReader,
    sizeof,
)


# ==============================================================================
# 1. Float16 & Range Validation & total_size
# ==============================================================================
@binary_struct(total_size=16, pad_byte=b"\x00")
class EnvironmentalSensorBlock:
    """Fixed-size 16-byte sensor data block with range validation and half-precision floats."""
    sensor_id: UInt16
    # Validated range [-40, 85] degrees C
    temperature_c: Range[Float16, -40.0, 85.0]
    # Validated humidity [0, 100]%
    humidity_pct: Range[UInt8, 0, 100]
    # Battery voltage with 16-bit half precision
    battery_v: Float16


# ==============================================================================
# 2. LengthOf & CountOf with Linked Deserialization
# ==============================================================================
@binary_struct
class TelemetryFrame:
    """Telemetry packet with auto-calculated payload length and item count."""
    # payload length is automatically computed on write, and bounds read on deserialize
    payload_len: LengthOf[UInt16, "payload"]
    payload: Bytes
    # item count is automatically computed on write, and bounds read on deserialize
    item_count: CountOf[UInt8, "readings"]
    readings: Array[UInt16]
    footer_crc: UInt16


def main():
    print("=== Sample 07: v0.3.0 New Features ===")

    # --------------------------------------------------------------------------
    # 1. Float16, Range validation, and total_size padding
    # --------------------------------------------------------------------------
    print("\n--- 1. Float16, Range Validation & total_size ---")
    sensor = EnvironmentalSensorBlock(
        sensor_id=0x101,
        temperature_c=25.5,
        humidity_pct=60,
        battery_v=3.3,
    )
    data = sensor.to_bytes()
    print(f"Serialized 16-byte fixed block: {data.hex(' ')}")
    print(f"Struct sizeof: {sizeof(EnvironmentalSensorBlock)} bytes (total_size={sizeof(sensor)})")
    assert len(data) == 16, "Total size must be strictly 16 bytes"

    # Deserialization test
    recovered_sensor = EnvironmentalSensorBlock.from_bytes(data)
    print(f"Recovered ID: 0x{recovered_sensor.sensor_id:X}")
    print(f"Recovered Temp: {float(recovered_sensor.temperature_c):.1f}°C")
    print(f"Recovered Humidity: {recovered_sensor.humidity_pct}%")
    print(f"Recovered Battery: {float(recovered_sensor.battery_v):.2f}V")

    # Range validation failure test
    try:
        invalid_sensor = EnvironmentalSensorBlock(
            sensor_id=0x102,
            temperature_c=120.0,  # Exceeds max 85.0!
            humidity_pct=50,
            battery_v=3.3,
        )
        invalid_sensor.to_bytes()
    except RangeValidationError as e:
        print(f"Caught expected RangeValidationError: {e}")

    # --------------------------------------------------------------------------
    # 2. LengthOf & CountOf (Automatic calculation & linked parsing)
    # --------------------------------------------------------------------------
    print("\n--- 2. LengthOf & CountOf ---")
    # Notice: payload_len and item_count are omitted (or 0) — auto-calculated!
    frame = TelemetryFrame(
        payload=b"GPS_FIX_OK",
        readings=[100, 200, 300, 400],
        footer_crc=0xCAFE,
    )
    frame_bytes = frame.to_bytes()
    print(f"Auto-calculated payload_len: {frame.payload_len} (expected 10 bytes)")
    print(f"Auto-calculated item_count: {frame.item_count} (expected 4 items)")
    print(f"Serialized frame ({len(frame_bytes)} bytes): {frame_bytes.hex(' ')}")

    # Deserialization: payload_len bounds payload reading so footer_crc is correctly read
    recovered_frame = TelemetryFrame.from_bytes(frame_bytes)
    assert recovered_frame.payload == b"GPS_FIX_OK"
    assert recovered_frame.readings == [100, 200, 300, 400]
    assert recovered_frame.footer_crc == 0xCAFE
    print("Linked deserialization succeeded perfectly!")

    # --------------------------------------------------------------------------
    # 3. BinaryWriter pad_to
    # --------------------------------------------------------------------------
    print("\n--- 3. BinaryWriter.pad_to ---")
    w = BinaryWriter()
    w.write_uint32(0xDEADBEEF, name="magic")
    w.write_cstring("boot", name="cmd")
    print(f"Writer offset before pad_to: {w.tell()} bytes")
    w.pad_to(16, pad_byte=b"\xFF")
    print(f"Writer offset after pad_to(16): {w.tell()} bytes")
    print(f"Padded buffer: {w.to_bytes().hex(' ')}")
    assert len(w.to_bytes()) == 16

    # --------------------------------------------------------------------------
    # 4. Interactive Standalone HTML Documentation
    # --------------------------------------------------------------------------
    print("\n--- 4. Interactive HTML Manual Generation ---")
    with tempfile.TemporaryDirectory() as tmpdir:
        html_path = Path(tmpdir) / "sensor_manual.html"
        frame.write_html(html_path, title="Telemetry Frame Protocol Spec")
        print(f"Generated standalone HTML manual with Hex Inspector: {html_path.name}")
        html_content = html_path.read_text(encoding="utf-8")
        assert "<!DOCTYPE html>" in html_content
        assert "Interactive Hex Inspector" in html_content
        assert "mermaid" in html_content
        print(f"HTML size: {len(html_content)} characters (self-contained, ready for browser)")

    print("\n=== Sample 07 Completed Successfully! ===")


if __name__ == "__main__":
    main()
