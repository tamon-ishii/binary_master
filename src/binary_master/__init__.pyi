from typing import Literal as Literal
L = Literal

from .binary_struct import (
    UInt8 as UInt8,
    UInt16 as UInt16,
    UInt32 as UInt32,
    UInt64 as UInt64,
    Int8 as Int8,
    Int16 as Int16,
    Int32 as Int32,
    Int64 as Int64,
    Float16 as Float16,
    Float32 as Float32,
    Float64 as Float64,
    Float as Float,
    Double as Double,
    Bool as Bool,
    Bytes as Bytes,
    FixedString as FixedString,
    CString as CString,
    PrefixedString as PrefixedString,
    FixedArray as FixedArray,
    Array as Array,
    Offset as Offset,
    NamedOffset as NamedOffset,
    OffsetTable as OffsetTable,
    Bits as Bits,
    Variant as Variant,
    Base as Base,
    RelativeBase as RelativeBase,
    binary_struct as binary_struct,
    BinaryStruct as BinaryStruct,
    Struct as Struct,
    to_bytes as to_bytes,
    from_bytes as from_bytes,
    read_struct as read_struct,
    sizeof as sizeof,
    binary_size as binary_size,
    offsetof as offsetof,
    bit_offsetof as bit_offsetof,
    Magic as Magic,
    Constant as Constant,
    Range as Range,
    LengthOf as LengthOf,
    CountOf as CountOf,
)
from .writer import BinaryWriter as BinaryWriter, Writer as Writer, OffsetTableHandle as OffsetTableHandle
from .reader import BinaryReader as BinaryReader, Reader as Reader
from .enums import Endian as Endian, EndianType as EndianType, normalize_endian as normalize_endian
from .manual import (
    generate_manual as generate_manual,
    generate_html as generate_html,
    write_html as write_html,
    resolve_language as resolve_language,
)

