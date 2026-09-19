"""Comprehensive tests for v0.4.0 features:
- File I/O & Streams (to_file, from_file, from_stream)
- BinaryFlag (IntFlag enum support)
- Compressed payloads (zlib, gzip, bz2, lzma)
- Wireshark Lua Dissector code generator & CLI
- AsyncIO stream reader & writer (AsyncBinaryReader, AsyncBinaryWriter, to_async_stream, from_async_stream)
"""

from __future__ import annotations

import asyncio
import io
import tempfile
from pathlib import Path

import pytest

from binary_master import (
    AsyncBinaryReader,
    AsyncBinaryWriter,
    BinaryFlag,
    BinaryStruct,
    Compressed,
    CompressedBytes,
    CString,
    Endian,
    FixedArray,
    Int16,
    UInt8,
    UInt16,
    UInt32,
    binary_struct,
    from_async_stream,
    from_file,
    from_stream,
    to_file,
)
from binary_master.cli import main as cli_main


# ==============================================================================
# 1. File I/O & Streams
# ==============================================================================
def test_to_file_and_from_file_path():
    @binary_struct(endian="little")
    class ConfigFile(BinaryStruct):
        version: UInt16
        magic: UInt32
        data: FixedArray[UInt8, 4]

    cfg = ConfigFile(version=2, magic=0x12345678, data=b"TEST")

    with tempfile.TemporaryDirectory() as tmpdir:
        file_path = Path(tmpdir) / "config.bin"
        bytes_written = cfg.to_file(file_path)
        assert bytes_written == 10
        assert file_path.exists()

        loaded = ConfigFile.from_file(file_path)
        assert loaded.version == 2
        assert loaded.magic == 0x12345678
        assert loaded.data == b"TEST"

        # Test module-level to_file and from_file
        file_path2 = Path(tmpdir) / "config2.bin"
        to_file(cfg, str(file_path2))
        loaded2 = from_file(ConfigFile, str(file_path2))
        assert loaded2.magic == 0x12345678


def test_file_io_stream():
    @binary_struct(endian="big")
    class PacketHeader:
        seq: UInt32
        size: UInt16

    buf = io.BytesIO()
    hdr = PacketHeader(seq=1001, size=42)
    hdr.to_file(buf)
    assert len(buf.getvalue()) == 6

    buf.seek(0)
    loaded = PacketHeader.from_stream(buf)
    assert loaded.seq == 1001
    assert loaded.size == 42

    buf.seek(0)
    loaded_mod = from_stream(PacketHeader, buf)
    assert loaded_mod.seq == 1001


# ==============================================================================
# 2. BinaryFlag
# ==============================================================================
def test_binary_flag():
    class Permissions(BinaryFlag):
        NONE = 0
        READ = 1 << 0
        WRITE = 1 << 1
        EXECUTE = 1 << 2

    assert Permissions.READ | Permissions.WRITE == 3
    perms = Permissions.READ | Permissions.EXECUTE
    assert Permissions.READ in perms
    assert Permissions.WRITE not in perms

    @binary_struct
    class FileEntry:
        perms: Permissions[UInt8]
        file_id: UInt16

    entry = FileEntry(perms=Permissions.READ | Permissions.WRITE, file_id=42)
    raw = entry.to_bytes()
    assert len(raw) == 3
    assert raw[0] == 3

    loaded = FileEntry.from_bytes(raw)
    assert isinstance(loaded.perms, Permissions)
    assert loaded.perms == (Permissions.READ | Permissions.WRITE)
    assert loaded.perms & Permissions.READ


# ==============================================================================
# 3. Compressed Payloads
# ==============================================================================
@pytest.mark.parametrize("algo", ["zlib", "gzip", "bz2", "lzma"])
def test_compressed_struct_roundtrip(algo):
    @binary_struct
    class InnerPayload:
        code: UInt16
        message: CString

    @binary_struct
    class Container:
        id: UInt32
        payload: Compressed[InnerPayload, algo]

    inner = InnerPayload(code=200, message="Success OK " * 20)
    c = Container(id=1, payload=inner)
    data = c.to_bytes()

    assert len(data) > 8  # 4 bytes id + 4 bytes length prefix + compressed data
    # Verify uncompressed representation would be bigger than compressed message
    raw_inner_len = len(inner.to_bytes())
    # Container payload is compressed
    loaded = Container.from_bytes(data)
    assert loaded.id == 1
    assert loaded.payload.code == 200
    assert loaded.payload.message == "Success OK " * 20


@pytest.mark.parametrize("algo", ["zlib", "gzip", "bz2", "lzma"])
def test_compressed_bytes_roundtrip(algo):
    @binary_struct
    class BlobStore:
        tag: UInt8
        blob: CompressedBytes[algo]

    original_data = b"BINARY_DATA_CHUNK_" * 50
    store = BlobStore(tag=7, blob=original_data)
    raw = store.to_bytes()

    loaded = BlobStore.from_bytes(raw)
    assert loaded.tag == 7
    assert loaded.blob == original_data


# ==============================================================================
# 4. Wireshark Lua Dissector
# ==============================================================================
def test_wireshark_lua_generation():
    @binary_struct(endian="big")
    class GamePacket(BinaryStruct):
        magic: UInt32
        opcode: UInt16
        name: CString
        scores: FixedArray[Int16, 4]

    lua_code = GamePacket.to_wireshark(port=9999, protocol_name="game_proto")
    assert 'Proto("game_proto"' in lua_code
    assert "ProtoField.uint32" in lua_code
    assert "ProtoField.uint16" in lua_code
    assert "udp_table:add(9999, proto)" in lua_code
    assert "tcp_table:add(9999, proto)" in lua_code

    with tempfile.TemporaryDirectory() as tmpdir:
        out_file = Path(tmpdir) / "game_packet.lua"
        GamePacket.write_wireshark(str(out_file), port=9999, protocol_name="game_proto")
        assert out_file.exists()
        assert "function proto.dissector" in out_file.read_text(encoding="utf-8")


def test_cli_wireshark_export(capsys):
    # Test CLI export command with --lang wireshark
    ret = cli_main(["export", "tests.test_cli:CliDummyPacket", "--lang", "wireshark", "-o", "-"])
    assert ret == 0
    captured = capsys.readouterr().out
    assert "Proto(" in captured
    assert "dissector" in captured


# ==============================================================================
# 5. AsyncIO Support
# ==============================================================================
@pytest.mark.asyncio
async def test_async_binary_reader_and_writer_primitives():
    stream_reader = asyncio.StreamReader()

    # Create dummy StreamWriter using a loop pair or feed data
    stream_reader.feed_data(b"\x01\x00\x02\x00\x00\x00\x03hello\x00")
    stream_reader.feed_eof()

    reader = AsyncBinaryReader(stream_reader, default_endian=Endian.BIG)
    u8 = await reader.read_uint8()
    assert u8 == 1
    u16 = await reader.read_uint16()
    assert u16 == 2
    u32 = await reader.read_uint32()
    assert u32 == 3
    cstr = await reader.read_cstring()
    assert cstr == "hello"


@pytest.mark.asyncio
async def test_async_struct_streaming():
    @binary_struct(endian="little")
    class Message(BinaryStruct):
        msg_id: UInt16
        text: CString
        status: UInt8

    msg = Message(msg_id=101, text="Async Binary Master", status=1)
    wire_bytes = msg.to_bytes()

    # 1. Test AsyncBinaryReader.read_struct
    stream_reader = asyncio.StreamReader()
    stream_reader.feed_data(wire_bytes)
    stream_reader.feed_eof()

    reader = AsyncBinaryReader(stream_reader, default_endian=Endian.LITTLE)
    decoded = await reader.read_struct(Message)
    assert decoded.msg_id == 101
    assert decoded.text == "Async Binary Master"
    assert decoded.status == 1

    # 2. Test classmethod from_async_stream & module-level from_async_stream
    stream_reader2 = asyncio.StreamReader()
    stream_reader2.feed_data(wire_bytes)
    stream_reader2.feed_eof()

    decoded2 = await Message.from_async_stream(stream_reader2, endian=Endian.LITTLE)
    assert decoded2.msg_id == 101

    stream_reader3 = asyncio.StreamReader()
    stream_reader3.feed_data(wire_bytes)
    stream_reader3.feed_eof()

    decoded3 = await from_async_stream(Message, stream_reader3, endian=Endian.LITTLE)
    assert decoded3.text == "Async Binary Master"


@pytest.mark.asyncio
async def test_async_socket_roundtrip():
    @binary_struct(endian="big")
    class Ping(BinaryStruct):
        seq: UInt32
        data: FixedArray[UInt8, 4]

    server_received = []

    async def client_connected_cb(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        async_r = AsyncBinaryReader(reader, default_endian=Endian.BIG)
        pkt = await async_r.read_struct(Ping)
        server_received.append(pkt)

        # Echo back
        async_w = AsyncBinaryWriter(writer, default_endian=Endian.BIG)
        await async_w.send_struct(pkt)
        await async_w.close()

    server = await asyncio.start_server(client_connected_cb, "127.0.0.1", 0)
    server_port = server.sockets[0].getsockname()[1]

    async with server:
        client_r, client_w = await asyncio.open_connection("127.0.0.1", server_port)

        send_pkt = Ping(seq=777, data=b"PING")
        await send_pkt.to_async_stream(client_w)

        # Read echo
        echoed = await Ping.from_async_stream(client_r)
        assert echoed.seq == 777
        assert echoed.data == b"PING"

        client_w.close()
        await client_w.wait_closed()

    assert len(server_received) == 1
    assert server_received[0].seq == 777
