"""Tests for the Bool type with configurable size."""

from typing import Annotated

import pytest

from binary_master import (
    BinaryReader,
    BinaryType,
    BinaryWriter,
    Bits,
    Bool,
    Builder,
    FixedArray,
    UInt8,
    binary_struct,
    offsetof,
    read_struct,
    sizeof,
    write_struct,
)
from binary_master.code_gen.c import c_type_of
from binary_master.code_gen.cpp import cpp_type_of
from binary_master.code_gen.csharp import csharp_type_of
from binary_master.code_gen.go import go_type_of
from binary_master.code_gen.rust import rust_type_of


def test_bool_type_properties():
    # Default 1 byte
    assert Bool.size == 1
    assert Bool.fmt == "?"
    assert repr(Bool) == "Bool"
    assert issubclass(Bool, BinaryType)

    # Bool(value) behaves like bool constructor
    assert Bool(True) is True
    assert Bool(False) is False
    assert Bool() is False

    # Configurable sizes
    assert Bool[1] is Bool
    assert Bool[2].size == 2
    assert Bool[2].fmt == "H"
    assert repr(Bool[2]) == "Bool[2]"

    assert Bool[4].size == 4
    assert Bool[4].fmt == "I"
    assert repr(Bool[4]) == "Bool[4]"

    assert Bool[8].size == 8
    assert Bool[8].fmt == "Q"
    assert repr(Bool[8]) == "Bool[8]"

    # Arbitrary custom byte size
    assert Bool[3].size == 3
    assert repr(Bool[3]) == "Bool[3]"

    # Subclass relationships
    assert issubclass(Bool[4], Bool)
    assert issubclass(Bool[4], BinaryType)

    # Function-call syntax for sizing
    assert Bool(4) is Bool[4]
    assert Bool(size=2) is Bool[2]

    # Invalid sizes
    with pytest.raises(ValueError):
        _ = Bool[0]
    with pytest.raises(ValueError):
        _ = Bool[-1]
    with pytest.raises(ValueError):
        _ = Bool["invalid"]


def test_writer_and_reader_bool_sizes():
    w = BinaryWriter()
    w.write_bool(True, size=1)
    w.write_bool(False, size=1)
    w.write_bool(True, size=2, endian="little")
    w.write_bool(True, size=3, endian="little")
    w.write_bool(True, size=4, endian="little")
    w.write_bool(True, size=4, endian="big")
    w.write_bool(False, size=4)
    data = w.to_bytes()

    assert data[0:1] == b"\x01"
    assert data[1:2] == b"\x00"
    assert data[2:4] == b"\x01\x00"
    assert data[4:7] == b"\x01\x00\x00"
    assert data[7:11] == b"\x01\x00\x00\x00"
    assert data[11:15] == b"\x00\x00\x00\x01"
    assert data[15:19] == b"\x00\x00\x00\x00"

    r = BinaryReader(data)
    assert r.read_bool(size=1) is True
    assert r.read_bool(size=1) is False
    assert r.read_bool(size=2, endian="little") is True
    assert r.read_bool(size=3, endian="little") is True
    assert r.read_bool(size=4, endian="little") is True
    assert r.read_bool(size=4, endian="big") is True
    assert r.read_bool(size=4) is False


def test_binary_struct_with_bool():
    @binary_struct
    class Config:
        enabled: Bool
        debug_mode: Bool[1]
        use_cache: Bool[2]
        custom_flag: Bool[3]
        is_admin: Bool[4]
        is_super: Bool[8]

    assert sizeof(Config) == 1 + 1 + 2 + 3 + 4 + 8  # 19
    assert offsetof(Config, "enabled") == 0
    assert offsetof(Config, "debug_mode") == 1
    assert offsetof(Config, "use_cache") == 2
    assert offsetof(Config, "custom_flag") == 4
    assert offsetof(Config, "is_admin") == 7
    assert offsetof(Config, "is_super") == 11

    cfg = Config(
        enabled=True,
        debug_mode=False,
        use_cache=True,
        custom_flag=True,
        is_admin=True,
        is_super=False,
    )

    data = write_struct(cfg).to_bytes()
    assert len(data) == 19

    decoded = read_struct(Config, data)
    assert decoded.enabled is True
    assert decoded.debug_mode is False
    assert decoded.use_cache is True
    assert decoded.custom_flag is True
    assert decoded.is_admin is True
    assert decoded.is_super is False


def test_binary_struct_bitfield_bool():
    @binary_struct(bits=8)
    class Flags:
        flag_a: Annotated[Bool, Bits[1]]
        flag_b: Annotated[Bool, Bits[1]]
        reserved: Annotated[UInt8, Bits[6]]

    f = Flags(flag_a=True, flag_b=False, reserved=0)
    data = write_struct(f).to_bytes()
    assert len(data) == 1
    assert data[0] == 0b00000001

    decoded = read_struct(Flags, data)
    assert decoded.flag_a is True
    assert decoded.flag_b is False
    assert decoded.reserved == 0


def test_bool_in_fixed_array():
    @binary_struct
    class BoolArrayStruct:
        flags1: FixedArray[Bool, 3]
        flags4: FixedArray[Bool[4], 2]

    assert sizeof(BoolArrayStruct) == 3 * 1 + 2 * 4  # 11

    s = BoolArrayStruct(
        flags1=[True, False, True],
        flags4=[False, True],
    )
    data = write_struct(s).to_bytes()
    assert len(data) == 11

    decoded = read_struct(BoolArrayStruct, data)
    assert decoded.flags1 == [True, False, True]
    assert decoded.flags4 == [False, True]


def test_builder_with_bool():
    builder = Builder(title="Bool Test")
    builder.add_field("flag1", "Bool", size=1)
    builder.add_field("flag4", "Bool[4]", size=4)

    raw_data = b"\x01\x01\x00\x00\x00"
    res = builder.read(raw_data)
    assert res["flag1"] is True
    assert res["flag4"] is True

    # Test trace writer
    _, w = builder._parse_and_trace(raw_data)
    assert len(w.entries) == 2
    assert w.entries[0].type_name == "Bool"
    assert w.entries[1].type_name == "Bool[4]"


def test_code_gen_types():
    # C
    assert c_type_of(Bool) == ("bool", None, None)
    assert c_type_of(Bool[2]) == ("uint16_t", None, "2-byte boolean")
    assert c_type_of(Bool[4]) == ("uint32_t", None, "4-byte boolean")

    # C++
    assert cpp_type_of(Bool) == ("bool", None)
    assert cpp_type_of(Bool[2]) == ("uint16_t", "2-byte boolean")
    assert cpp_type_of(Bool[4]) == ("uint32_t", "4-byte boolean")

    # C#
    assert csharp_type_of(Bool) == ("bool", None, None)
    assert csharp_type_of(Bool[2]) == ("ushort", None, "2-byte boolean")
    assert csharp_type_of(Bool[4]) == ("uint", None, "4-byte boolean")

    # Go
    assert go_type_of(Bool) == ("bool", None)
    assert go_type_of(Bool[2]) == ("uint16", "2-byte boolean")
    assert go_type_of(Bool[4]) == ("uint32", "4-byte boolean")

    # Rust
    assert rust_type_of(Bool) == ("bool", None)
    assert rust_type_of(Bool[2]) == ("u16", "2-byte boolean")
    assert rust_type_of(Bool[4]) == ("u32", "4-byte boolean")
