"""Tests for binary-master CLI."""

import io
from pathlib import Path
import pytest

from binary_master import UInt8, UInt32, binary_struct
from binary_master.cli import main


@binary_struct
class CliDummyPacket:
    """Packet for CLI tests."""
    magic: UInt32
    version: UInt8


def test_cli_spec_markdown(tmp_path: Path):
    out_file = tmp_path / "spec.md"
    ret = main(["spec", "tests.test_cli:CliDummyPacket", "-o", str(out_file)])
    assert ret == 0
    assert out_file.exists()
    content = out_file.read_text(encoding="utf-8")
    assert "CliDummyPacket" in content
    assert "magic" in content


def test_cli_spec_html(tmp_path: Path):
    out_file = tmp_path / "spec.html"
    ret = main(["spec", "tests.test_cli:CliDummyPacket", "-o", str(out_file), "--html"])
    assert ret == 0
    assert out_file.exists()
    content = out_file.read_text(encoding="utf-8")
    assert "<!DOCTYPE html>" in content or "<html" in content
    assert "CliDummyPacket" in content


def test_cli_manual_alias(tmp_path: Path):
    out_file = tmp_path / "manual.html"
    ret = main(["manual", "tests.test_cli:CliDummyPacket", "-o", str(out_file), "--html"])
    assert ret == 0
    assert out_file.exists()
    content = out_file.read_text(encoding="utf-8")
    assert "<!DOCTYPE html>" in content or "<html" in content
    assert "CliDummyPacket" in content


def test_cli_export(tmp_path: Path):
    out_file = tmp_path / "packet.rs"
    ret = main(["export", "tests.test_cli:CliDummyPacket", "-l", "rust", "-o", str(out_file)])
    assert ret == 0
    assert out_file.exists()
    content = out_file.read_text(encoding="utf-8")
    assert "pub struct CliDummyPacket" in content
    assert "pub magic: u32" in content


def test_cli_inspect_and_diff(tmp_path: Path):
    p1 = tmp_path / "f1.bin"
    p2 = tmp_path / "f2.bin"
    p1.write_bytes(b"\x01\x02\x03\x04")
    p2.write_bytes(b"\x01\x02\x03\x05")

    # diff
    ret_diff = main(["diff", str(p1), str(p2)])
    assert ret_diff == 0

    # inspect
    ret_insp = main(["inspect", str(p1)])
    assert ret_insp == 0
