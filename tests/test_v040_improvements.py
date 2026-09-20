"""Tests for v0.4.0 improvements:
- Compact Pattern Language Types (u8, u16, u32, u64, i8, i16, i32, i64, s8, s16, s32, s64, f16, f32, f64)
- ImHex Pattern Language (.hexpat) generator
- ZeroCopyView lazy parsing and in-place editing
- Continuous packet streaming (iter_packets, iter_views, async_iter_packets)
- Dummy data generator (generate_dummy, cls.dummy)
- CLI inspect --interactive and export --lang hexpat
"""

from __future__ import annotations

from enum import IntEnum
from pathlib import Path

import pytest

from binary_master import (
    AsyncBinaryReader,
    AsyncBinaryWriter,
    BinaryReader,
    BinaryWriter,
    Builder,
    Constant,
    FixedArray,
    FixedString,
    Magic,
    Range,
    ZeroCopyView,
    binary_struct,
    f16,
    f32,
    f64,
    generate_dummy,
    i16,
    i32,
    i64,
    iter_packets,
    s16,
    s32,
    s64,
    u8,
    u16,
    u32,
    u64,
)
from binary_master.cli import main as cli_main

# ---------------------------------------------------------------------------
# 1. Compact Types in Structs, Reader, Writer, Async
# ---------------------------------------------------------------------------


@binary_struct(endian="little")
class CompactHeader:
    magic: Magic[b"PK"]
    version_major: u8
    version_minor: u8
    flags: u16
    packet_id: u32
    timestamp: u64
    temp_celsius: i16
    latitude: i32
    longitude: i64
    scale: f16
    ratio: f32
    precise: f64


def test_compact_types_serialization():
    hdr = CompactHeader(
        version_major=1,
        version_minor=2,
        flags=0x1234,
        packet_id=100000,
        timestamp=1700000000,
        temp_celsius=-15,
        latitude=-123456,
        longitude=-987654321,
        scale=1.5,
        ratio=3.14,
        precise=2.718281828,
    )
    raw = hdr.to_bytes()
    decoded = CompactHeader.from_bytes(raw)

    assert decoded.version_major == 1
    assert decoded.version_minor == 2
    assert decoded.flags == 0x1234
    assert decoded.packet_id == 100000
    assert decoded.timestamp == 1700000000
    assert decoded.temp_celsius == -15
    assert decoded.latitude == -123456
    assert decoded.longitude == -987654321
    assert abs(decoded.scale - 1.5) < 1e-3
    assert abs(decoded.ratio - 3.14) < 1e-5
    assert abs(decoded.precise - 2.718281828) < 1e-9

    @binary_struct
    class ImHexStyleStruct:
        a: s16
        b: s32
        c: s64

    im_obj = ImHexStyleStruct(a=-10, b=-200, c=-3000)
    im_bytes = im_obj.to_bytes()
    im_dec = ImHexStyleStruct.from_bytes(im_bytes)
    assert im_dec.a == -10
    assert im_dec.b == -200
    assert im_dec.c == -3000


def test_reader_writer_compact_methods():
    w = BinaryWriter()
    w.write_u8(10)
    w.write_u16(1000)
    w.write_u32(100000)
    w.write_u64(10000000000)
    w.write_i8(-5)
    w.write_s8(-8)
    w.write_i16(-500)
    w.write_s16(-800)
    w.write_i32(-50000)
    w.write_s32(-80000)
    w.write_i64(-5000000000)
    w.write_s64(-8000000000)
    w.write_f16(2.5)
    w.write_f32(3.5)
    w.write_f64(4.5)

    data = w.to_bytes()
    r = BinaryReader(data)

    assert r.read_u8() == 10
    assert r.read_u16() == 1000
    assert r.read_u32() == 100000
    assert r.read_u64() == 10000000000
    assert r.read_i8() == -5
    assert r.read_s8() == -8
    assert r.read_i16() == -500
    assert r.read_s16() == -800
    assert r.read_i32() == -50000
    assert r.read_s32() == -80000
    assert r.read_i64() == -5000000000
    assert r.read_s64() == -8000000000
    assert abs(r.read_f16() - 2.5) < 1e-3
    assert abs(r.read_f32() - 3.5) < 1e-5
    assert abs(r.read_f64() - 4.5) < 1e-9
    assert r.is_eof


@pytest.mark.asyncio
async def test_async_reader_writer_compact_methods():
    w = AsyncBinaryWriter()
    w.write_u16(42)
    w.write_i32(-100)
    w.write_s32(-200)
    w.write_f32(1.25)
    data = w.to_bytes()

    r = AsyncBinaryReader(data)
    assert await r.read_u16() == 42
    assert await r.read_i32() == -100
    assert await r.read_s32() == -200
    assert abs(await r.read_f32() - 1.25) < 1e-5


# ---------------------------------------------------------------------------
# 2. ImHex Pattern Language (.hexpat)
# ---------------------------------------------------------------------------


class StatusEnum(IntEnum):
    INIT = 0
    RUNNING = 1
    STOPPED = 2


@binary_struct(endian="big")
class TelemetryPacket:
    magic: Magic[b"TLM"]
    channel: u8
    status: StatusEnum
    temperature: f32
    device_name: FixedString[16]


def test_imhex_pattern_generation(tmp_path: Path):
    pat = TelemetryPacket.to_hexpat()
    assert "#pragma endian big" in pat
    assert "struct TelemetryPacket {" in pat
    assert "u8 channel;" in pat
    assert "StatusEnum status;" in pat
    assert "float temperature;" in pat
    assert "char device_name[16];" in pat
    assert "TelemetryPacket telemetry_packet @ 0x00;" in pat

    # Test file writing
    out_file = tmp_path / "telemetry.hexpat"
    TelemetryPacket.write_hexpat(out_file)
    assert out_file.exists()
    assert "#pragma endian big" in out_file.read_text(encoding="utf-8")

    # Test Builder to_hexpat
    b = Builder(title="TelemetrySpec")
    b.add_struct(TelemetryPacket)
    b_pat = b.to_hexpat()
    assert "struct TelemetryPacket {" in b_pat


def test_cli_export_hexpat(tmp_path: Path):
    # Test exporting via CLI
    out_file = tmp_path / "exported.hexpat"
    code = cli_main([
        "export",
        f"{__name__}:TelemetryPacket",
        "-l",
        "hexpat",
        "-o",
        str(out_file),
    ])
    assert code == 0
    assert out_file.exists()
    assert "TelemetryPacket" in out_file.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# 3. ZeroCopyView
# ---------------------------------------------------------------------------


@binary_struct(endian="little")
class SensorReading:
    sensor_id: u16
    reading: u32
    threshold: f32


def test_zero_copy_view_reading():
    reading = SensorReading(sensor_id=101, reading=54321, threshold=88.5)
    data = reading.to_bytes()

    view = SensorReading.view(data)
    assert view.sensor_id == 101
    assert view.reading == 54321
    assert abs(view.threshold - 88.5) < 1e-5
    assert len(view) == len(data)
    assert view.byte_size == len(data)

    # Convert to struct
    full = view.to_struct()
    assert isinstance(full, SensorReading)
    assert full.sensor_id == 101

    # Convert to dict
    d = view.to_dict()
    assert d["sensor_id"] == 101
    assert d["reading"] == 54321

    # Hexdump
    assert "00000000" in view.hexdump()


def test_zero_copy_view_in_place_editing():
    reading = SensorReading(sensor_id=101, reading=54321, threshold=88.5)
    buf = bytearray(reading.to_bytes())

    view = ZeroCopyView(SensorReading, buf)
    # Edit fields in place
    view.sensor_id = 202
    view.reading = 99999
    view.threshold = 12.5

    # Check updated view values
    assert view.sensor_id == 202
    assert view.reading == 99999
    assert abs(view.threshold - 12.5) < 1e-5

    # Check underlying buffer changed
    decoded = SensorReading.from_bytes(buf)
    assert decoded.sensor_id == 202
    assert decoded.reading == 99999
    assert abs(decoded.threshold - 12.5) < 1e-5


def test_zero_copy_view_from_file(tmp_path: Path):
    f_path = tmp_path / "sensor.bin"
    r1 = SensorReading(sensor_id=5, reading=123, threshold=4.5)
    f_path.write_bytes(r1.to_bytes())

    with SensorReading.view_from_file(f_path) as v:
        assert v.sensor_id == 5
        assert v.reading == 123
        assert abs(v.threshold - 4.5) < 1e-5


# ---------------------------------------------------------------------------
# 4. Continuous Packet Streaming
# ---------------------------------------------------------------------------


def test_iter_packets():
    packets = [
        SensorReading(sensor_id=i, reading=i * 100, threshold=float(i))
        for i in range(5)
    ]
    stream_bytes = b"".join(p.to_bytes() for p in packets)

    # 1. From bytes
    results = list(iter_packets(stream_bytes, SensorReading))
    assert len(results) == 5
    assert [p.sensor_id for p in results] == [0, 1, 2, 3, 4]

    # 2. With max_count
    limited = list(SensorReading.iter_packets(stream_bytes, max_count=3))
    assert len(limited) == 3
    assert [p.sensor_id for p in limited] == [0, 1, 2]


def test_iter_views():
    packets = [
        SensorReading(sensor_id=i + 10, reading=(i + 10) * 100, threshold=float(i))
        for i in range(4)
    ]
    stream_bytes = b"".join(p.to_bytes() for p in packets)

    views = list(SensorReading.iter_views(stream_bytes))
    assert len(views) == 4
    assert [v.sensor_id for v in views] == [10, 11, 12, 13]
    assert isinstance(views[0], ZeroCopyView)


@pytest.mark.asyncio
async def test_async_iter_packets():
    packets = [
        SensorReading(sensor_id=i * 2, reading=i * 500, threshold=float(i))
        for i in range(3)
    ]
    data = b"".join(p.to_bytes() for p in packets)

    results = []
    async for pkt in SensorReading.async_iter_packets(AsyncBinaryReader(data)):
        results.append(pkt)

    assert len(results) == 3
    assert [p.sensor_id for p in results] == [0, 2, 4]


# ---------------------------------------------------------------------------
# 5. Dummy Generator
# ---------------------------------------------------------------------------


@binary_struct
class MockNetworkPacket:
    magic: Magic[b"NET"]
    msg_type: u8
    code: Range[u16, 100, 200]
    fixed_tag: Constant[u32, 0xCAFEBABE]
    sensor_name: FixedString[8]
    flags: FixedArray[u8, 4]


def test_dummy_generator():
    # Deterministic seed test
    d1 = generate_dummy(MockNetworkPacket, seed=42)
    d2 = MockNetworkPacket.dummy(seed=42)

    assert d1.magic == b"NET"
    assert d1.fixed_tag == 0xCAFEBABE
    assert 100 <= d1.code <= 200
    assert len(d1.flags) == 4
    assert d1.msg_type == d2.msg_type
    assert d1.code == d2.code
    assert d1.sensor_name == d2.sensor_name

    # Overrides test
    d_over = MockNetworkPacket.dummy(msg_type=99, code=150, sensor_name="CUSTOM")
    assert d_over.magic == b"NET"
    assert d_over.msg_type == 99
    assert d_over.code == 150
    assert d_over.sensor_name == "CUSTOM"


# ---------------------------------------------------------------------------
# 6. CLI Inspect Non-TTY Fallback
# ---------------------------------------------------------------------------


def test_cli_inspect_interactive_fallback(tmp_path: Path):
    pkt = SensorReading(sensor_id=77, reading=888, threshold=1.23)
    f = tmp_path / "packet.bin"
    f.write_bytes(pkt.to_bytes())

    # When run in pytest (non-TTY), inspect -i safely falls back to standard hexdump
    code = cli_main([
        "inspect",
        str(f),
        "-s",
        f"{__name__}:SensorReading",
        "-i",
    ])
    assert code == 0
