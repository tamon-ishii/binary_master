"""Tests for multi-language code generation (Rust, C++, C#, Go)."""

import os
import shutil
import subprocess
import tempfile
from pathlib import Path
import pytest

from binary_master import (
    FixedArray,
    Float32,
    Builder,
    Offset,
    OffsetTable,
    UInt8,
    UInt16,
    UInt32,
    binary_struct,
)
from binary_master.code_gen import (
    generate_code,
    generate_cpp_code,
    generate_csharp_code,
    generate_go_code,
    generate_rust_code,
    write_code,
)


@binary_struct
class PacketHeader:
    """Header for packet."""
    magic: UInt32
    seq_num: UInt16
    payload_len: UInt16


@binary_struct(bits=16)
class FlagsRegister:
    """Control and status flags."""
    enabled: 1
    ready: 1
    mode: 2
    reserved: 12


@binary_struct
class StatusPayload:
    """Status variant payload."""
    status_code: UInt8
    temperature: Float32
    checksum: UInt16


@binary_struct
class SensorPayload:
    """Sensor array payload."""
    sensor_id: UInt8
    samples: FixedArray[UInt16, 4]


def create_sample_builder() -> Builder:
    builder = Builder(title="Telemetry Protocol", version="1.0.0")
    builder.add_document("Protocol Overview", "This protocol transmits telemetry data.")
    builder.add_section("Header and Registers")
    builder.add_struct(PacketHeader, name="Header", desc="Standard protocol header")
    builder.add_struct(FlagsRegister, name="Flags", desc="Bitfield flags register")
    builder.add_section("Dynamic Payload")
    builder.add_choice(
        "PayloadChoice",
        tag_field="msg_type",
        variants=[
            (0x01, StatusPayload, "Status message"),
            (0x02, SensorPayload, "Sensor data message"),
        ],
        desc="Dynamic payload choice based on msg_type",
    )
    return builder


class TestRustCodeGen:
    def test_generate_rust_code_structure(self):
        builder = create_sample_builder()
        code = builder.to_rust()

        assert "#![allow(dead_code, non_camel_case_types, non_snake_case)]" in code
        assert "pub struct PacketHeader" in code
        assert "#[repr(C, packed)]" in code
        assert "pub magic: u32," in code
        assert "pub seq_num: u16," in code
        assert "pub struct FlagsRegister" in code
        assert "pub raw: u16," in code
        assert "pub fn enabled(&self) -> u16" in code
        assert "pub enum PayloadChoiceTag" in code
        assert "StatusPayload = 0x01," in code
        assert "SensorPayload = 0x02," in code
        assert "pub enum PayloadChoiceUnion" in code
        assert "StatusPayload(StatusPayload)," in code
        assert "SensorPayload(SensorPayload)," in code
        assert "[u16; 4]" in code

    def test_binary_struct_to_rust(self):
        code = PacketHeader.to_rust()
        assert "pub struct PacketHeader" in code
        assert "pub magic: u32," in code

        code_bits = FlagsRegister.to_rust()
        assert "pub struct FlagsRegister" in code_bits
        assert "pub raw: u16," in code_bits
        assert "pub fn mode(&self) -> u16" in code_bits

    def test_rustc_compilation(self, tmp_path):
        rustc_path = shutil.which("rustc") or os.path.expanduser("~/.cargo/bin/rustc")
        if not os.path.exists(rustc_path):
            pytest.skip("rustc compiler not available")

        builder = create_sample_builder()
        out_file = tmp_path / "protocol.rs"
        builder.write_rust(out_file)

        # Compile as a library crate to check for syntax and type validity
        result = subprocess.run(
            [rustc_path, "--crate-type=lib", "--emit=metadata", str(out_file), "-o", str(tmp_path / "libprotocol.rmeta")],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"rustc compilation failed:\n{result.stderr}"


class TestCppCodeGen:
    def test_generate_cpp_code_structure(self):
        builder = create_sample_builder()
        code = builder.to_cpp()

        assert "#pragma once" in code
        assert "#include <cstdint>" in code
        assert "#include <array>" in code
        assert "#include <variant>" in code
        assert "#pragma pack(push, 1)" in code
        assert "struct PacketHeader {" in code
        assert "uint32_t magic;" in code
        assert "struct FlagsRegister {" in code
        assert "uint16_t enabled : 1;" in code
        assert "enum class PayloadChoiceTag : uint16_t" in code
        assert "using PayloadChoiceVariant = std::variant<StatusPayload, SensorPayload>;" in code
        assert "std::array<uint16_t, 4> samples;" in code
        assert "#pragma pack(pop)" in code

    def test_binary_struct_to_cpp(self):
        code = PacketHeader.to_cpp()
        assert "struct PacketHeader {" in code
        assert "uint32_t magic;" in code

        code_bits = FlagsRegister.to_cpp()
        assert "struct FlagsRegister {" in code_bits
        assert "uint16_t enabled : 1;" in code_bits

    def test_gpp_compilation(self, tmp_path):
        gpp_path = shutil.which("g++")
        if not gpp_path:
            pytest.skip("g++ compiler not available")

        builder = create_sample_builder()
        out_file = tmp_path / "protocol.hpp"
        builder.write_cpp(out_file)

        # Create a tiny source file that includes the header
        test_cpp = tmp_path / "test.cpp"
        test_cpp.write_text(f'#include "{out_file.name}"\nint main() {{ return 0; }}\n')

        result = subprocess.run(
            [gpp_path, "-std=c++17", "-fsyntax-only", "-I", str(tmp_path), str(test_cpp)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"g++ syntax check failed:\n{result.stderr}"


class TestCSharpCodeGen:
    def test_generate_csharp_code_structure(self):
        builder = create_sample_builder()
        code = builder.to_csharp(namespace="TelemetryApp")

        assert "namespace TelemetryApp {" in code
        assert "using System.Runtime.InteropServices;" in code
        assert "[StructLayout(LayoutKind.Sequential, Pack = 1)]" in code
        assert "public struct PacketHeader {" in code
        assert "public uint Magic;" in code
        assert "public ushort SeqNum;" in code
        assert "public struct FlagsRegister {" in code
        assert "public ushort Raw;" in code
        assert "public ushort Enabled => (ushort)((Raw >> 0) & 0x1);" in code
        assert "public enum PayloadChoiceTag : ushort" in code
        assert "StatusPayload = 0x01," in code
        assert "[StructLayout(LayoutKind.Explicit, Pack = 1)]" in code
        assert "public struct PayloadChoiceUnion {" in code
        assert "[FieldOffset(0)] public StatusPayload StatusPayload;" in code
        assert "[MarshalAs(UnmanagedType.ByValArray, SizeConst = 4)]" in code
        assert "public ushort[] Samples;" in code

    def test_binary_struct_to_csharp(self):
        code = PacketHeader.to_csharp()
        assert "public struct PacketHeader {" in code
        assert "public uint Magic;" in code

        code_bits = FlagsRegister.to_csharp()
        assert "public struct FlagsRegister {" in code_bits
        assert "public ushort Raw;" in code_bits


class TestGoCodeGen:
    def test_generate_go_code_structure(self):
        builder = create_sample_builder()
        code = builder.to_go(package_name="telemetry")

        assert "package telemetry" in code
        assert "type PacketHeader struct {" in code
        assert "Magic uint32" in code
        assert "SeqNum uint16" in code
        assert "type FlagsRegister struct {" in code
        assert "Raw uint16" in code
        assert "func (b FlagsRegister) Enabled() uint16 {" in code
        assert "type PayloadChoiceTag uint16" in code
        assert "const (" in code
        assert "PayloadChoiceTagStatusPayload PayloadChoiceTag = 0x01" in code
        assert "type PayloadChoice interface {" in code
        assert "IsPayloadChoice()" in code
        assert "func (StatusPayload) IsPayloadChoice() {}" in code
        assert "Samples [4]uint16" in code

    def test_binary_struct_to_go(self):
        code = PacketHeader.to_go()
        assert "type PacketHeader struct {" in code
        assert "Magic uint32" in code

        code_bits = FlagsRegister.to_go()
        assert "type FlagsRegister struct {" in code_bits
        assert "func (b FlagsRegister) Enabled() uint16 {" in code_bits


class TestUnifiedDispatcher:
    def test_to_code_all_languages(self):
        builder = create_sample_builder()

        c_code = builder.to_code("c")
        assert "#ifndef" in c_code or "#pragma pack" in c_code

        rs_code = builder.to_code("rust")
        assert "pub struct PacketHeader" in rs_code

        cpp_code = builder.to_code("cpp")
        assert "#include <variant>" in cpp_code

        cs_code = builder.to_code("csharp")
        assert "namespace BinaryProtocol" in cs_code

        go_code = builder.to_code("go")
        assert "package protocol" in go_code

    def test_write_code_extension_inference(self, tmp_path):
        builder = create_sample_builder()

        rs_path = tmp_path / "packet.rs"
        builder.write_code(rs_path)
        assert rs_path.exists()
        assert "pub struct PacketHeader" in rs_path.read_text()

        cpp_path = tmp_path / "packet.hpp"
        builder.write_code(cpp_path)
        assert cpp_path.exists()
        assert "#include <variant>" in cpp_path.read_text()

        cs_path = tmp_path / "packet.cs"
        builder.write_code(cs_path)
        assert cs_path.exists()
        assert "namespace BinaryProtocol" in cs_path.read_text()

        go_path = tmp_path / "packet.go"
        builder.write_code(go_path)
        assert go_path.exists()
        assert "package protocol" in go_path.read_text()

        h_path = tmp_path / "packet.h"
        builder.write_code(h_path)
        assert h_path.exists()
        assert "TELEMETRY_PROTOCOL_H" in h_path.read_text()
        assert "PacketHeader" in h_path.read_text()

    def test_invalid_language_and_extension(self, tmp_path):
        builder = create_sample_builder()
        with pytest.raises(ValueError, match="Unsupported language"):
            builder.to_code("java")

        with pytest.raises(ValueError, match="Cannot infer language"):
            builder.write_code(tmp_path / "packet.unknown")
