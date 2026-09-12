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
    Base,
    RelativeBase,
)
from .manual import (
    LayoutEntry,
    generate_manual,
    generate_mermaid_diagram,
    generate_packet_diagram,
    generate_bitfield_packet_diagram,
    write_manual,
    inspect_struct_layout,
)
from .builder import BinaryBuilder, Builder, BuilderReadResult
from .c_header import to_c_header, write_c_header, to_c_struct
from .code_gen import (
    generate_code,
    write_code,
    generate_rust_code,
    write_rust,
    generate_cpp_code,
    write_cpp,
    generate_csharp_code,
    write_csharp,
    generate_go_code,
    write_go,
)



__version__ = "0.2.0"

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
    "Base",
    "RelativeBase",
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
    "inspect_struct_layout",
    "BinaryBuilder",
    "Builder",
    "BuilderReadResult",
    "to_c_header",
    "write_c_header",
    "to_c_struct",
    "generate_code",
    "write_code",
    "generate_rust_code",
    "write_rust",
    "generate_cpp_code",
    "write_cpp",
    "generate_csharp_code",
    "write_csharp",
    "generate_go_code",
    "write_go",
]



