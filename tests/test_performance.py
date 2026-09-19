"""Tests for performance optimization: StructPlan caching, fast-pack, and fast-unpack."""

from __future__ import annotations

import pytest

from binary_master import (
    BinaryStruct,
    Bool,
    Bytes,
    Endian,
    Float32,
    Int32,
    Magic,
    Range,
    UInt8,
    UInt16,
    UInt32,
    binary_struct,
)
from binary_master.binary_struct import FieldKind, get_struct_plan


@binary_struct
class SimplePacket(BinaryStruct):
    packet_id: UInt16
    flags: UInt8
    sequence: UInt32
    speed: Float32


@binary_struct(endian="big")
class BigEndianPacket(BinaryStruct):
    code: UInt16
    value: Int32


@binary_struct
class ConstrainedPacket(BinaryStruct):
    magic: Magic[b"HEAD"]
    status: Range[UInt8, 0, 10]
    count: UInt16


def test_struct_plan_compilation_and_caching() -> None:
    plan1 = get_struct_plan(SimplePacket)
    plan2 = get_struct_plan(SimplePacket)
    assert plan1 is plan2
    assert plan1.can_fast_unpack is True
    assert plan1.can_fast_pack is True
    assert plan1.total_fixed_size == 2 + 1 + 4 + 4  # 11 bytes
    assert plan1.fast_field_names == ("packet_id", "flags", "sequence", "speed")


def test_fast_unpack_and_pack_correctness() -> None:
    pkt = SimplePacket(packet_id=0xABCD, flags=0x12, sequence=12345, speed=3.14)
    raw = pkt.to_bytes()
    assert len(raw) == 11

    # Deserialization via fast-path
    pkt_deser = SimplePacket.from_bytes(raw)
    assert pkt_deser.packet_id == 0xABCD
    assert pkt_deser.flags == 0x12
    assert pkt_deser.sequence == 12345
    assert pytest.approx(pkt_deser.speed, rel=1e-5) == 3.14


def test_big_endian_fast_path() -> None:
    plan = get_struct_plan(BigEndianPacket)
    assert plan.can_fast_unpack is True
    assert plan.can_fast_pack is True
    assert plan.endian == Endian.BIG

    pkt = BigEndianPacket(code=0x1234, value=-500)
    raw = pkt.to_bytes()
    assert raw[:2] == b"\x12\x34"

    pkt_deser = BigEndianPacket.from_bytes(raw)
    assert pkt_deser.code == 0x1234
    assert pkt_deser.value == -500


def test_constrained_struct_plan() -> None:
    plan = get_struct_plan(ConstrainedPacket)
    # Magic and Range cannot be fast-unpacked in one single struct.unpack call
    assert plan.can_fast_unpack is False
    assert len(plan.field_plans) == 3
    assert plan.field_plans[0].kind == FieldKind.MAGIC
    assert plan.field_plans[1].kind == FieldKind.RANGE
    assert plan.field_plans[2].kind == FieldKind.PRIMITIVE

    pkt = ConstrainedPacket(status=5, count=100)
    raw = pkt.to_bytes()
    assert raw.startswith(b"HEAD")

    pkt_deser = ConstrainedPacket.from_bytes(raw)
    assert pkt_deser.status == 5
    assert pkt_deser.count == 100


@binary_struct
class NetworkHeader(BinaryStruct):
    packet_id: UInt16
    payload: Bytes[16]
    is_active: Bool
    flags: UInt8


def test_bytes_and_bool_fast_path() -> None:
    plan = get_struct_plan(NetworkHeader)
    assert plan.can_fast_unpack is True
    assert plan.can_fast_pack is True
    assert plan.total_fixed_size == 2 + 16 + 1 + 1  # 20 bytes
    assert plan.fast_field_names == ("packet_id", "payload", "is_active", "flags")

    pkt = NetworkHeader(
        packet_id=0x1234,
        payload=b"0123456789abcdef",
        is_active=True,
        flags=0xAB,
    )
    raw = pkt.to_bytes()
    assert len(raw) == 20
    assert raw[:2] == b"\x34\x12"  # little-endian UInt16
    assert raw[2:18] == b"0123456789abcdef"
    assert raw[18] == 1
    assert raw[19] == 0xAB

    deser = NetworkHeader.from_bytes(raw)
    assert deser.packet_id == 0x1234
    assert deser.payload == b"0123456789abcdef"
    assert deser.is_active is True
    assert deser.flags == 0xAB


def test_zero_copy_deserialization() -> None:
    pkt = NetworkHeader(
        packet_id=0x5678,
        payload=b"ABCDEF0123456789",
        is_active=False,
        flags=0x42,
    )
    raw = pkt.to_bytes()

    # From memoryview (zero-copy buffer protocol)
    mv = memoryview(raw)
    deser_mv = NetworkHeader.from_bytes(mv)
    assert deser_mv.packet_id == 0x5678
    assert deser_mv.payload == b"ABCDEF0123456789"
    assert deser_mv.is_active is False
    assert deser_mv.flags == 0x42

    # From bytearray
    ba = bytearray(raw)
    deser_ba = NetworkHeader.from_bytes(ba)
    assert deser_ba.packet_id == 0x5678
    assert deser_ba.payload == b"ABCDEF0123456789"


def test_writer_stream_fast_pack() -> None:
    from binary_master import BinaryWriter

    pkt = NetworkHeader(
        packet_id=0x9999,
        payload=b"1111222233334444",
        is_active=True,
        flags=0xFF,
    )
    writer = BinaryWriter(record_entries=False)
    writer.write_struct(pkt)
    data = writer.to_bytes()
    assert len(data) == 20
    deser = NetworkHeader.from_bytes(data)
    assert deser.packet_id == 0x9999
    assert deser.payload == b"1111222233334444"


def test_named_offset_code_generation() -> None:
    from binary_master import Offset
    from binary_master.code_gen import generate_code

    @binary_struct
    class Chunk(BinaryStruct):
        magic: UInt32
        data_offset: Offset["data_tag", UInt32]

    for lang in ("c", "cpp", "csharp", "go", "rust"):
        code = generate_code(Chunk, lang=lang)
        assert "data_offset" in code
        assert "data_tag" in code

