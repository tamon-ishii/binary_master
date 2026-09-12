"""Binary Master: High-level binary writing library."""

from .enums import Endian, EndianType, normalize_endian
from .writer import BinaryWriter, Writer, OffsetTableHandle
from .reader import BinaryReader, Reader
from .binary_struct import (
    BinaryType,
    UInt8,
    UInt16,
    UInt32,
    UInt64,
    Int8,
    Int16,
    Int32,
    Int64,
    Float32,
    Float64,
    Offset,
    OffsetTable,
    Variant,
    Array,
    FixedArray,
    Bits,
    binary_struct,
    write_struct,
    read_struct,
    sizeof,
    binary_size,
)
from .manual import (
    LayoutEntry,
    generate_manual,
    generate_mermaid_diagram,
    generate_packet_diagram,
    generate_bitfield_packet_diagram,
    write_manual,
)

__version__ = "0.1.0"

__all__ = [
    "BinaryWriter",
    "Writer",
    "BinaryReader",
    "Reader",
    "OffsetTableHandle",
    "Endian",
    "EndianType",
    "normalize_endian",
    "BinaryType",
    "UInt8",
    "UInt16",
    "UInt32",
    "UInt64",
    "Int8",
    "Int16",
    "Int32",
    "Int64",
    "Float32",
    "Float64",
    "Offset",
    "OffsetTable",
    "Variant",
    "Array",
    "FixedArray",
    "Bits",
    "binary_struct",
    "write_struct",
    "read_struct",
    "sizeof",
    "binary_size",
    "LayoutEntry",
    "generate_manual",
    "generate_mermaid_diagram",
    "generate_packet_diagram",
    "generate_bitfield_packet_diagram",
    "write_manual",
]

