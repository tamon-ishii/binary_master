from typing import Literal

from .binary_struct import (
    Array as Array,
)
from .binary_struct import (
    Base as Base,
)
from .binary_struct import (
    BinaryEnum as BinaryEnum,
)
from .binary_struct import (
    BinaryStruct as BinaryStruct,
)
from .binary_struct import (
    BinaryType as BinaryType,
)
from .binary_struct import (
    Bits as Bits,
)
from .binary_struct import (
    Bool as Bool,
)
from .binary_struct import (
    Bytes as Bytes,
)
from .binary_struct import (
    Constant as Constant,
)
from .binary_struct import (
    ConstantBase as ConstantBase,
)
from .binary_struct import (
    CountOf as CountOf,
)
from .binary_struct import (
    CountOfBase as CountOfBase,
)
from .binary_struct import (
    CString as CString,
)
from .binary_struct import (
    Double as Double,
)
from .binary_struct import (
    FixedArray as FixedArray,
)
from .binary_struct import (
    FixedString as FixedString,
)
from .binary_struct import (
    Float as Float,
)
from .binary_struct import (
    Float16 as Float16,
)
from .binary_struct import (
    Float32 as Float32,
)
from .binary_struct import (
    Float64 as Float64,
)
from .binary_struct import (
    Int8 as Int8,
)
from .binary_struct import (
    Int16 as Int16,
)
from .binary_struct import (
    Int32 as Int32,
)
from .binary_struct import (
    Int64 as Int64,
)
from .binary_struct import (
    LengthOf as LengthOf,
)
from .binary_struct import (
    LengthOfBase as LengthOfBase,
)
from .binary_struct import (
    Magic as Magic,
)
from .binary_struct import (
    MagicBase as MagicBase,
)
from .binary_struct import (
    NamedOffset as NamedOffset,
)
from .binary_struct import (
    Offset as Offset,
)
from .binary_struct import (
    OffsetTable as OffsetTable,
)
from .binary_struct import (
    PrefixedString as PrefixedString,
)
from .binary_struct import (
    Range as Range,
)
from .binary_struct import (
    RangeBase as RangeBase,
)
from .binary_struct import (
    RelativeBase as RelativeBase,
)
from .binary_struct import (
    Struct as Struct,
)
from .binary_struct import (
    UInt8 as UInt8,
)
from .binary_struct import (
    UInt16 as UInt16,
)
from .binary_struct import (
    UInt32 as UInt32,
)
from .binary_struct import (
    UInt64 as UInt64,
)
from .binary_struct import (
    Variant as Variant,
)
from .binary_struct import (
    binary_size as binary_size,
)
from .binary_struct import (
    binary_struct as binary_struct,
)
from .binary_struct import (
    bit_offsetof as bit_offsetof,
)
from .binary_struct import (
    from_bytes as from_bytes,
)
from .binary_struct import (
    offsetof as offsetof,
)
from .binary_struct import (
    read_struct as read_struct,
)
from .binary_struct import (
    sizeof as sizeof,
)
from .binary_struct import (
    to_bytes as to_bytes,
)
from .binary_struct import (
    write_struct as write_struct,
)
from .binary_struct import (
    write_variant as write_variant,
)
from .bitstream import (
    BitReader as BitReader,
)
from .bitstream import (
    BitWriter as BitWriter,
)
from .builder import (
    BinaryBuilder as BinaryBuilder,
)
from .builder import (
    Builder as Builder,
)
from .builder import (
    BuilderReadResult as BuilderReadResult,
)
from .c_header import (
    to_c_header as to_c_header,
)
from .c_header import (
    to_c_struct as to_c_struct,
)
from .c_header import (
    write_c_header as write_c_header,
)
from .checksum import (
    CRC16 as CRC16,
)
from .checksum import (
    CRC16_ARC as CRC16_ARC,
)
from .checksum import (
    CRC16_CCITT as CRC16_CCITT,
)
from .checksum import (
    CRC32 as CRC32,
)
from .checksum import (
    Adler32 as Adler32,
)
from .checksum import (
    Checksum8 as Checksum8,
)
from .checksum import (
    Checksum16 as Checksum16,
)
from .checksum import (
    ChecksumBase as ChecksumBase,
)
from .checksum import (
    Fletcher16 as Fletcher16,
)
from .checksum import (
    compute_checksum as compute_checksum,
)
from .code_gen import (
    generate_code as generate_code,
)
from .code_gen import (
    generate_cpp_code as generate_cpp_code,
)
from .code_gen import (
    generate_csharp_code as generate_csharp_code,
)
from .code_gen import (
    generate_go_code as generate_go_code,
)
from .code_gen import (
    generate_rust_code as generate_rust_code,
)
from .code_gen import (
    write_code as write_code,
)
from .code_gen import (
    write_cpp as write_cpp,
)
from .code_gen import (
    write_csharp as write_csharp,
)
from .code_gen import (
    write_go as write_go,
)
from .code_gen import (
    write_rust as write_rust,
)
from .debug import (
    debug_dump as debug_dump,
)
from .debug import (
    diff_dump as diff_dump,
)
from .debug import (
    dump_dict as dump_dict,
)
from .debug import (
    dump_json as dump_json,
)
from .debug import (
    dump_table as dump_table,
)
from .debug import (
    hexdump as hexdump,
)
from .enums import (
    Endian as Endian,
)
from .enums import (
    EndianType as EndianType,
)
from .enums import (
    normalize_endian as normalize_endian,
)
from .enums import (
    normalize_named_offset_key as normalize_named_offset_key,
)
from .exceptions import (
    BinaryMasterError as BinaryMasterError,
)
from .exceptions import (
    ChecksumMismatchError as ChecksumMismatchError,
)
from .exceptions import (
    DuplicateNamedOffsetError as DuplicateNamedOffsetError,
)
from .exceptions import (
    InvalidConstantError as InvalidConstantError,
)
from .exceptions import (
    InvalidEnumError as InvalidEnumError,
)
from .exceptions import (
    InvalidMagicError as InvalidMagicError,
)
from .exceptions import (
    NamedOffsetError as NamedOffsetError,
)
from .exceptions import (
    NamedOffsetNotFoundError as NamedOffsetNotFoundError,
)
from .exceptions import (
    RangeValidationError as RangeValidationError,
)
from .exceptions import (
    TotalSizeExceededError as TotalSizeExceededError,
)
from .manual import (
    LayoutEntry as LayoutEntry,
)
from .manual import (
    generate_bitfield_packet_diagram as generate_bitfield_packet_diagram,
)
from .manual import (
    generate_html as generate_html,
)
from .manual import (
    generate_manual as generate_manual,
)
from .manual import (
    generate_mermaid_diagram as generate_mermaid_diagram,
)
from .manual import (
    generate_packet_diagram as generate_packet_diagram,
)
from .manual import (
    inspect_struct_layout as inspect_struct_layout,
)
from .manual import (
    resolve_language as resolve_language,
)
from .manual import (
    write_html as write_html,
)
from .reader import (
    BinaryReader as BinaryReader,
)
from .reader import (
    Reader as Reader,
)
from .varint import (
    VarInt as VarInt,
)
from .varint import (
    VarInt32 as VarInt32,
)
from .varint import (
    VarInt64 as VarInt64,
)
from .varint import (
    VarUInt as VarUInt,
)
from .varint import (
    VarUInt32 as VarUInt32,
)
from .varint import (
    VarUInt64 as VarUInt64,
)
from .varint import (
    decode_varint as decode_varint,
)
from .varint import (
    decode_varuint as decode_varuint,
)
from .varint import (
    encode_varint as encode_varint,
)
from .varint import (
    encode_varuint as encode_varuint,
)
from .writer import (
    BinaryWriter as BinaryWriter,
)
from .writer import (
    OffsetTableHandle as OffsetTableHandle,
)
from .writer import (
    Writer as Writer,
)

L = Literal
__version__: str
