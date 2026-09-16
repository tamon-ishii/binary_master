import struct
import pytest
from binary_master import (
    binary_struct,
    UInt8,
    UInt16,
    UInt32,
    Offset,
    OffsetTable,
    Base,
    FixedArray,
    Float32,
    Bool,
    FixedString,
    CString,
    PrefixedString,
    Bytes,
    dump_table,
)


@binary_struct
class LeafItem:
    item_id: UInt16
    val: UInt32


@binary_struct
class DirectTableContainer:
    magic: UInt32
    num_items: UInt16
    # Direct Offset to OffsetTable!
    table_offset: Offset[OffsetTable["num_items", UInt32, Base.SELF], Base.SELF]


@binary_struct
class FixedCountTableContainer:
    magic: UInt32
    table_offset: Offset[OffsetTable[2, UInt32, Base.SELF]]


def test_offset_to_offset_table_with_struct_instances():
    """Test serializing and deserializing Offset[OffsetTable[...]] with struct items."""
    item1 = LeafItem(item_id=1, val=100)
    item2 = LeafItem(item_id=2, val=200)

    # 1. Provide target structs directly in a list
    root = DirectTableContainer(
        magic=0x524F4F54,
        num_items=2,
        table_offset=[item1, item2],
    )

    data = root.to_bytes()
    # Layout:
    # 0..4: magic (0x524F4F54)
    # 4..6: num_items (2)
    # 6..10: table_offset (points to table at 10 -> stored value: 10 - 0 = 10)
    # 10..14: table[0] (points to item1 at 18 -> stored value: 18 - 10 = 8)
    # 14..18: table[1] (points to item2 at 24 -> stored value: 24 - 10 = 14)
    # 18..24: item1 (id=1, val=100, 6B)
    # 24..30: item2 (id=2, val=200, 6B)
    assert len(data) == 4 + 2 + 4 + 4 * 2 + 6 * 2  # 30 bytes

    tbl_offset_val = struct.unpack("<I", data[6:10])[0]
    assert tbl_offset_val == 10

    entry0 = struct.unpack("<I", data[10:14])[0]
    entry1 = struct.unpack("<I", data[14:18])[0]
    assert entry0 == 8   # 18 - 10
    assert entry1 == 14  # 24 - 10

    # 2. Deserialize
    restored = DirectTableContainer.from_bytes(data)
    assert restored.magic == 0x524F4F54
    assert restored.num_items == 2
    assert restored.table_offset == [8, 14]


def test_offset_to_offset_table_auto_count():
    """Test auto-populating count when num_items is omitted."""
    item1 = LeafItem(item_id=10, val=1000)
    item2 = LeafItem(item_id=20, val=2000)
    item3 = LeafItem(item_id=30, val=3000)

    # num_items is omitted! Should auto-detect len(table_offset) == 3
    root = DirectTableContainer(
        magic=0xAABBCCDD,
        table_offset=[item1, item2, item3],
    )
    assert root.num_items == 0  # Initial omitted value is 0

    data = root.to_bytes()
    assert root.num_items == 3  # Auto-populated during serialization

    restored = DirectTableContainer.from_bytes(data)
    assert restored.num_items == 3
    assert len(restored.table_offset) == 3


def test_offset_to_offset_table_with_raw_integers():
    """Test passing manual integer target offsets in Offset[OffsetTable]."""
    root = FixedCountTableContainer(
        magic=0x11223344,
        table_offset=[0x100, 0x200],  # Absolute target positions 256, 512
    )
    data = root.to_bytes()
    # Layout:
    # 0..4: magic (4B)
    # 4..8: table_offset (4B) -> points to 8
    # 8..16: table entries (8B). Base.SELF = 8, so stored values are 256-8=248, 512-8=504
    assert len(data) == 16

    restored = FixedCountTableContainer.from_bytes(data)
    assert restored.magic == 0x11223344
    assert restored.table_offset == [248, 504]  # Relative to table start (Base.SELF)


def test_implicit_zero_initialization_all_omitted():
    """Test that all fields default to zero/empty when constructor arguments are omitted."""
    @binary_struct
    class AllTypesStruct:
        u8: UInt8
        u16: UInt16
        u32: UInt32
        f32: Float32
        flag: Bool
        raw_bytes: FixedArray[UInt8, 4]
        numbers: FixedArray[UInt16, 2]
        single_offset: Offset[LeafItem]
        tbl_offset: Offset[OffsetTable[2, UInt32]]
        fixed_str: FixedString[8]
        c_str: CString
        p_str: PrefixedString[2]
        raw_b: Bytes[4]

    # All arguments omitted without '= 0' in field definitions
    obj = AllTypesStruct()
    assert obj.u8 == 0
    assert obj.u16 == 0
    assert obj.u32 == 0
    assert obj.f32 == 0.0
    assert obj.flag is False
    assert obj.raw_bytes == b"\x00\x00\x00\x00"
    assert obj.numbers == [0, 0]
    assert obj.single_offset == 0
    assert obj.tbl_offset == []
    assert obj.fixed_str == ""
    assert obj.c_str == ""
    assert obj.p_str == ""
    assert obj.raw_b == b"\x00\x00\x00\x00"

    # Can serialize cleanly
    raw = obj.to_bytes()
    assert len(raw) > 0


def test_partial_keyword_instantiation_with_defaults():
    """Test specifying only a subset of fields by keyword."""
    @binary_struct
    class HeaderWithOptional:
        magic: UInt32
        version: UInt16
        flags: UInt8

    # Only provide magic
    h = HeaderWithOptional(magic=0x12345678)
    assert h.magic == 0x12345678
    assert h.version == 0
    assert h.flags == 0


def test_named_offset_user_flow():
    """Test user's exact flow: declare NamedOffset in struct, write struct, write string, resolve with write_named_offset."""
    from binary_master import BinaryWriter, NamedOffset, read_struct

    @binary_struct
    class Data:
        num: UInt16
        offset: NamedOffset["ofs"]

    data = Data()
    writer = BinaryWriter()
    writer.write_struct(data)
    writer.write_string("oooooooooo")
    writer.write_named_offset("ofs")

    raw = writer.to_bytes()
    assert len(raw) == 2 + 4 + 10  # 16 bytes

    restored = read_struct(Data, raw)
    assert restored.num == 0
    assert restored.offset == 16


def test_named_offset_with_target_struct():
    """Test write_named_offset writing a target struct and patching relative offset."""
    from binary_master import BinaryWriter, NamedOffset, read_struct

    @binary_struct
    class Payload:
        val: UInt32

    @binary_struct
    class Header:
        magic: UInt32
        rel_offset: NamedOffset["payload_rel", UInt32, Base.SELF]

    h = Header(magic=0x12345678)
    writer = BinaryWriter()
    writer.write_struct(h)
    writer.write_string("padding_data")
    p = Payload(val=999)
    writer.write_named_offset("payload_rel", p)

    raw = writer.to_bytes()
    restored = read_struct(Header, raw)
    assert restored.magic == 0x12345678
    assert restored.rel_offset == 20


def test_named_offset_duplicate_struct_write_raises():
    """Writing a struct containing NamedOffset twice must raise DuplicateNamedOffsetError."""
    from binary_master import BinaryWriter, NamedOffset, DuplicateNamedOffsetError

    @binary_struct
    class Header:
        num: UInt16
        offset: NamedOffset["ofs"]

    h = Header()
    writer = BinaryWriter()
    writer.write_struct(h)

    with pytest.raises(DuplicateNamedOffsetError) as exc_info:
        writer.write_struct(h)

    assert "ofs" in str(exc_info.value)
    assert isinstance(exc_info.value, ValueError)


def test_named_offset_duplicate_key_raises():
    """Registering duplicate key via different structs or reserve_named_offset must raise."""
    from binary_master import BinaryWriter, NamedOffset, DuplicateNamedOffsetError

    @binary_struct
    class First:
        offset1: NamedOffset["shared_key"]

    @binary_struct
    class Second:
        offset2: NamedOffset["shared_key"]

    writer = BinaryWriter()
    writer.write_struct(First())

    with pytest.raises(DuplicateNamedOffsetError):
        writer.write_struct(Second())

    # Direct reserve_named_offset duplicate check
    writer2 = BinaryWriter()
    writer2.reserve_named_offset("manual_key")
    with pytest.raises(DuplicateNamedOffsetError):
        writer2.reserve_named_offset("manual_key")


def test_write_named_offset_missing_key_raises():
    """Calling write_named_offset with a non-existent key must raise NamedOffsetNotFoundError."""
    from binary_master import BinaryWriter, NamedOffsetNotFoundError

    writer = BinaryWriter()
    with pytest.raises(NamedOffsetNotFoundError) as exc_info:
        writer.write_named_offset("non_existent_key")

    assert "non_existent_key" in str(exc_info.value)
    assert isinstance(exc_info.value, KeyError)


def test_rewrite_named_offset_missing_key_raises():
    """Calling rewrite_named_offset with a non-existent key must raise NamedOffsetNotFoundError."""
    from binary_master import BinaryWriter, NamedOffsetNotFoundError

    writer = BinaryWriter()
    with pytest.raises(NamedOffsetNotFoundError) as exc_info:
        writer.rewrite_named_offset("missing_key", 0x100)

    assert "missing_key" in str(exc_info.value)
    assert isinstance(exc_info.value, KeyError)


def test_rewrite_named_offset_success():
    """Calling rewrite_named_offset on an existing slot updates the offset."""
    from binary_master import BinaryWriter, NamedOffset, read_struct

    @binary_struct
    class Header:
        val: UInt32
        data_offset: NamedOffset["my_data"]

    h = Header(val=42)
    writer = BinaryWriter()
    writer.write_struct(h)
    # Initially resolve at tell() == 8
    writer.write_named_offset("my_data")
    assert struct.unpack("<I", writer.to_bytes()[4:8])[0] == 8

    # Now rewrite to target 100
    writer.rewrite_named_offset("my_data", 100)
    assert struct.unpack("<I", writer.to_bytes()[4:8])[0] == 100


def test_user_snippet_data_uint8_default_zero():
    """Verify user snippet: Data() without arguments or '= 0' initializes data to 0."""
    @binary_struct
    class Data:
        data: UInt8

    d = Data()
    assert d.data == 0
    assert d.to_bytes() == b"\x00"



