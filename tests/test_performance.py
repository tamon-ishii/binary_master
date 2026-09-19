"""Tests for performance optimization: StructPlan caching, fast-pack, and fast-unpack."""

from __future__ import annotations

import pytest

from binary_master import (
    BinaryStruct,
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
