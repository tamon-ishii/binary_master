import struct
import pytest
from binary_master import (
    binary_struct,
    BinaryWriter,
    NamedOffset,
    UInt32,
    UInt16,
    read_struct,
    DuplicateNamedOffsetError,
    NamedOffsetNotFoundError,
)


@binary_struct
class ChunkHeader:
    magic: UInt32
    payload_offset: NamedOffset["payload"]


def test_named_offset_isolated_namespaces():
    """Verify that multiple structs with identical NamedOffset keys do not collide across namespaces."""
    writer = BinaryWriter()

    # Chunk A
    with writer.namespace("chunk_a"):
        assert writer.current_namespace == "chunk_a"
        writer.write_struct(ChunkHeader(magic=0xAAAA))  # offset at 4..8
        writer.write_string("metadata_a")  # len 10
        # Resolve chunk_a/payload at tell() == 4 + 4 + 10 = 18
        writer.write_named_offset("payload")

    # Chunk B
    with writer.namespace("chunk_b"):
        assert writer.current_namespace == "chunk_b"
        writer.write_struct(ChunkHeader(magic=0xBBBB))  # offset at 18 + 4 = 22..26
        writer.write_bytes(b"\x00" * 8)
        # Resolve chunk_b/payload at tell() == 18 + 8 + 8 = 34
        writer.write_named_offset("payload")

    raw = writer.to_bytes()
    # Chunk A payload offset at byte 4..8
    ofs_a = struct.unpack("<I", raw[4:8])[0]
    assert ofs_a == 18

    # Chunk B payload offset at byte 22..26
    ofs_b = struct.unpack("<I", raw[22:26])[0]
    assert ofs_b == 34


def test_named_offset_nested_namespaces():
    """Verify nested namespaces concatenate path segments."""
    writer = BinaryWriter()

    with writer.namespace("section") as ns_section:
        assert ns_section == "section"
        with writer.namespace("sub") as ns_sub:
            assert ns_sub == "section/sub"
            assert writer.current_namespace == "section/sub"

            writer.write_struct(ChunkHeader(magic=0x1234))
            writer.write_string("nested_data")
            writer.write_named_offset("payload")

    raw = writer.to_bytes()
    ofs = struct.unpack("<I", raw[4:8])[0]
    assert ofs == 8 + len("nested_data")


def test_named_offset_root_escape_with_leading_slash():
    """Verify that leading slash '/' escapes active namespace to target root scope."""
    @binary_struct
    class ScopedWithGlobalRef:
        local_ref: NamedOffset["local"]
        global_ref: NamedOffset["/global_target"]

    writer = BinaryWriter()

    with writer.namespace("worker"):
        writer.write_struct(ScopedWithGlobalRef())
        writer.write_string("worker_local_data")
        # Resolve local
        writer.write_named_offset("local")

    # Outside namespace, resolve global_target (or using /global_target)
    writer.write_string("extra_data")
    writer.write_named_offset("global_target")

    raw = writer.to_bytes()
    local_ofs = struct.unpack("<I", raw[0:4])[0]
    global_ofs = struct.unpack("<I", raw[4:8])[0]

    assert local_ofs == 8 + len("worker_local_data")
    assert global_ofs == 8 + len("worker_local_data") + len("extra_data")


def test_named_offset_auto_id():
    """Verify auto_id=True generates incrementing sequence names."""
    writer = BinaryWriter()

    with writer.namespace("chunk", auto_id=True) as ns0:
        assert ns0 == "chunk_0"
        writer.write_struct(ChunkHeader(magic=0))
        writer.write_named_offset("payload")

    with writer.namespace("chunk", auto_id=True) as ns1:
        assert ns1 == "chunk_1"
        writer.write_struct(ChunkHeader(magic=1))
        writer.write_named_offset("payload")

    with writer.namespace("", auto_id=True) as ns2:
        assert ns2 == "scope_0"


def test_named_offset_empty_name_without_auto_id_raises():
    """Verify empty name without auto_id raises ValueError."""
    writer = BinaryWriter()
    with pytest.raises(ValueError):
        with writer.namespace(""):
            pass


def test_named_offset_rewrite_in_namespace():
    """Verify rewrite_named_offset respects current namespace."""
    writer = BinaryWriter()

    with writer.namespace("ns"):
        writer.write_struct(ChunkHeader(magic=42))
        writer.write_named_offset("payload")
        assert struct.unpack("<I", writer.to_bytes()[4:8])[0] == 8

        # Rewrite within namespace
        writer.rewrite_named_offset("payload", 200)
        assert struct.unpack("<I", writer.to_bytes()[4:8])[0] == 200


def test_named_offset_direct_reserve_in_namespace():
    """Verify reserve_named_offset is scoped inside namespace."""
    writer = BinaryWriter()

    with writer.namespace("module"):
        pos = writer.reserve_named_offset("my_offset")
        writer.write_bytes(b"\x00" * 10)
        writer.write_named_offset("my_offset")

    assert struct.unpack("<I", writer.to_bytes()[0:4])[0] == 14


def test_named_offset_with_enum_keys():
    """Verify that Enum members can be used as NamedOffset keys seamlessly."""
    from enum import Enum

    class ChunkKey(Enum):
        HEADER = "header_key"
        BODY = "body_key"

    @binary_struct
    class EnumKeyStruct:
        magic: UInt32
        body_offset: NamedOffset[ChunkKey.BODY]

    writer = BinaryWriter()
    writer.write_struct(EnumKeyStruct(magic=0x11223344))
    writer.write_bytes(b"padding")  # 7 bytes
    writer.write_named_offset(ChunkKey.BODY, target=b"PAYLOAD_DATA")

    raw = writer.to_bytes()
    assert len(raw) == 4 + 4 + 7 + len(b"PAYLOAD_DATA")
    offset_val = struct.unpack("<I", raw[4:8])[0]
    assert offset_val == 4 + 4 + 7  # 15


def test_named_offset_with_target_type_auto_dereferencing():
    """Verify NamedOffset[key, TargetStruct] automatically deserializes TargetStruct on read."""
    @binary_struct
    class ImageData:
        width: UInt16
        height: UInt16

    @binary_struct
    class ImageContainer:
        magic: UInt32
        image: NamedOffset["img_payload", ImageData]

    payload = ImageData(width=640, height=480)
    container = ImageContainer(magic=0x494D4730, image=payload)

    writer = BinaryWriter()
    writer.write_struct(container)
    writer.write_string("some arbitrary metadata string")
    # write_named_offset without explicit target automatically uses container.image!
    writer.write_named_offset("img_payload")

    data = writer.to_bytes()

    # Deserialize: restored.image should be an instance of ImageData!
    restored = ImageContainer.from_bytes(data)
    assert restored.magic == 0x494D4730
    assert isinstance(restored.image, ImageData)
    assert restored.image.width == 640
    assert restored.image.height == 480


def test_named_offset_with_target_type_and_enum_key():
    """Verify combination of Enum key, target type, offset type, and relative base."""
    from enum import Enum
    from binary_master import Base

    class MyKeys(Enum):
        SUB_RECORD = "sub_record"

    @binary_struct
    class SubRecord:
        val: UInt32

    @binary_struct
    class MasterRecord:
        magic: UInt32
        sub: NamedOffset[MyKeys.SUB_RECORD, SubRecord, UInt16, Base.SELF]

    sub_obj = SubRecord(val=0xDEADBEEF)
    master = MasterRecord(magic=0xAA55AA55, sub=sub_obj)

    writer = BinaryWriter()
    writer.write_struct(master)
    writer.pad(8)
    writer.write_named_offset(MyKeys.SUB_RECORD)

    data = writer.to_bytes()
    # Header: magic(4) + sub(2) = 6 bytes. Base.SELF is offset 0.
    # Target starts at 6 + 8 = 14 bytes.
    stored_off = struct.unpack("<H", data[4:6])[0]
    assert stored_off == 14

    restored = MasterRecord.from_bytes(data)
    assert isinstance(restored.sub, SubRecord)
    assert restored.sub.val == 0xDEADBEEF


def test_named_offset_type_label_in_manual():
    """Verify that generate_manual renders target type and enum key in the specification table."""
    from enum import Enum
    from binary_master.manual import generate_manual

    class FileKeys(Enum):
        PAYLOAD = "payload"

    @binary_struct
    class ChunkPayload:
        code: UInt32

    @binary_struct
    class Container:
        magic: UInt32
        payload_ptr: NamedOffset[FileKeys.PAYLOAD, ChunkPayload, UInt16]

    md = generate_manual(Container, lang="en")
    assert "`NamedOffset['payload', ChunkPayload, UInt16]`" in md


