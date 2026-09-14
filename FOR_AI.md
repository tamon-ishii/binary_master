
# Binary Master (`binary-master`) — AI Quick-Start & Complete Knowledge Base

> **Document Purpose**: High-density reference manual designed for AI coding assistants and LLMs to instantly comprehend, generate, debug, and inspect code using the `binary-master` library without requiring external context or additional web searches.  
> **Target Runtime**: Python 3.14+  
> **Key Value Proposition**: Type-safe declarative binary serialization/deserialization, schema-first protocol builder, automated Markdown/Mermaid specification generator, multi-language code export (C, Modern C++, C#, Rust, Go), and byte-level stream debugging.

---

## 1. Fast Architecture & Complete Symbol Index

### 1.1 Architectural Layers
1. **Declarative Layer (`@binary_struct`)**: Dataclass-based declarative schema definition with bitfields, offsets, variants, and alignment.
2. **Schema-First Builder Layer (`Builder` / `BinaryBuilder`)**: Specification-first protocol modeling, conditional logic, multi-language code export, and schema-driven automated deserialization (`builder.read`).
3. **Procedural Layer (`BinaryWriter` / `BinaryReader`)**: Low-level stream-oriented sequential reader/writer with strict bounds checking, string encodings, cursor navigation, and alignment.
4. **Code Generation Layer (`code_gen` / `c_header`)**: Exporting schemas to C typedefs, Modern C++, Rust structs/enums, C# structs, and Go structs.
5. **Debug & Inspection Layer (`debug`)**: Annotated terminal hexdumps with field correlation, tabular traces, JSON/dict dumps, and binary diffs.
6. **Documentation Layer (`manual`)**: Automated Markdown manual generation with Mermaid Flowcharts and Packet bit diagrams.

### 1.2 Full Top-Level Imports (`from binary_master import ...`)
```python
from binary_master import (
    # Core Structures & Decorators
    binary_struct,       # Class decorator for declarative structs
    write_struct,        # Procedural struct serializer
    write_variant,       # Procedural variant serializer with candidate validation
    read_struct,         # Procedural struct deserializer
    sizeof,              # Binary size in bytes (alias: binary_size)
    binary_size,         # Alias for sizeof
    offsetof,            # Byte offset of a field (supports dot notation)
    bit_offsetof,        # (byte_offset, bit_offset) tuple

    # Primitive Binary Types
    BinaryType,          # Base type for all primitives
    Bool,                # Configurable boolean type (default 1 byte, supports Bool[1], Bool[2], Bool[4])
    UInt8, UInt16, UInt32, UInt64,
    Int8,  Int16,  Int32,  Int64,
    Float32, Float64,

    # Generic & Advanced Type Annotations
    Bits,                # Bits[N]: Bitfield slice (used with @binary_struct(bits=N))
    Bytes,               # Bytes[N]: Static raw byte sequence (bytes)
    FixedString,         # FixedString[N]: Static fixed-length string (str)
    CString,             # CString: Null-terminated string (str)
    PrefixedString,      # PrefixedString[N]: Length-prefixed string (str)
    Offset,              # Offset[Target, OffsetType=UInt32, BaseOffset=0]
    OffsetTable,         # OffsetTable[Count, OffsetType=UInt32, BaseOffset=0]
    Variant,             # Variant[tag_field_name, {tag_val: StructCls, ...}]
    Array,               # Array[T]: Dynamic length sequence
    FixedArray,          # FixedArray[T, N]: Static N-element array
    Base,                # Base.SELF, Base.STRUCT, Base.FIELD origin markers
    RelativeBase,        # Result of Base + delta arithmetic

    # v2.0 Declarative Types & Constraints
    BinaryEnum,          # IntEnum with explicit sizing: MyEnum[UInt8]
    Magic,               # Magic[b"PNG..."] or Magic[0x1234]: signature constraint
    Constant,            # Constant[Type, Value]: fixed-value constant field
    CRC32, CRC16, CRC16_CCITT, CRC16_ARC, Checksum8, Checksum16, Fletcher16, Adler32,
    compute_checksum,
    VarUInt, VarInt, VarUInt32, VarInt32, VarUInt64, VarInt64,
    encode_varuint, decode_varuint, encode_varint, decode_varint,
    BitWriter, BitReader,

    # Exceptions
    BinaryMasterError,
    ChecksumMismatchError,
    InvalidMagicError,
    InvalidConstantError,
    InvalidEnumError,

    # Protocol Builder & Automated Deserialization
    Builder,             # Top-level protocol schema builder (alias: BinaryBuilder)
    BinaryBuilder,       # Alias for Builder
    BuilderReadResult,   # Deserialized dictionary & attribute accessible object

    # Procedural Writer & Reader
    Writer,              # Low-level binary writer (alias: BinaryWriter)
    BinaryWriter,        # Alias for Writer
    Reader,              # Low-level binary reader (alias: BinaryReader)
    BinaryReader,        # Alias for Reader
    OffsetTableHandle,   # Handle returned by write_offset_table for delayed patching

    # Enums & Endianness
    Endian,              # Enum: Endian.LITTLE ('<'), Endian.BIG ('>'), Endian.NATIVE ('=')
    EndianType,          # Union[Endian, str, None] ('little', 'big', 'native', '<', '>', '=')
    normalize_endian,    # Normalization helper returning Endian enum

    # Multi-Language Code Generation
    generate_code,       # generate_code(builder, lang="c"|"rust"|"cpp"|"csharp"|"go")
    write_code,          # write_code(builder, path, lang=None)
    to_c_header, write_c_header, to_c_struct,
    generate_rust_code, write_rust,
    generate_cpp_code, write_cpp,
    generate_csharp_code, write_csharp,
    generate_go_code, write_go,

    # Debugging & Inspection
    hexdump,             # hexdump(target, width=16, color=False, annotate=True, cursor=None)
    debug_dump,          # debug_dump(target, format="hexdump"|"table"|"json"|"dict")
    diff_dump,           # diff_dump(target_a, target_b, color=False)
    dump_table, dump_json, dump_dict,

    # Manual & Mermaid Generation
    generate_manual,
    generate_mermaid_diagram,
    generate_packet_diagram,
    generate_bitfield_packet_diagram,
    inspect_struct_layout,
    LayoutEntry,
)
```

---

## 2. Type System Reference

| Type Annotation | Binary Size | Python Input/Output | Notes & Examples |
|---|---|---|---|
| `UInt8`, `UInt16`, `UInt32`, `UInt64` | 1, 2, 4, 8 bytes | `int` | Unsigned standard integers |
| `Int8`, `Int16`, `Int32`, `Int64` | 1, 2, 4, 8 bytes | `int` | Signed 2's complement integers |
| `Float32`, `Float64` | 4, 8 bytes | `float` | IEEE 754 single / double precision |
| `Bool` / `bool` | 1 byte (or `Bool[N]` bytes) | `bool` | `0x00` = False, non-zero = True (supports `Bool[1]`, `Bool[2]`, `Bool[4]`) |
| `Bytes[N]` | `N` bytes | `bytes` | Static raw bytes buffer. Example: `Bytes[16]` |
| `FixedString[N]` | `N` bytes | `str` | Static fixed-length string (null/space-padded). Example: `FixedString[8]` |
| `CString` | Variable (`len + 1` bytes) | `str` | Null-terminated C string (`\0`) |
| `PrefixedString[N]` | Variable (`N + len` bytes) | `str` | Length-prefixed string with N-byte length prefix (1, 2, 4) |
| `FixedArray[T, N]` | `N * sizeof(T)` | `bytes` (if T is UInt8) or `list[T]` | Static fixed element buffer. Example: `FixedArray[UInt8, 16]` |
| `Array[T]` | Dynamic (`len * sizeof(T)`) | `bytes` (if T is UInt8) or `list[T]` | Dynamic sequence. Consumes remaining bytes on read unless bounded. |
| `Bits[N]` | `N` bits | `int` | Bitfield slice. Must be within struct decorated with `@binary_struct(bits=Total)`. |
| `Offset[Target, Type, Base]` | 1, 2, 4, or 8 bytes | Instance of `Target` or `int` | Pointer offset. Backpatched automatically on write; auto-dereferenced on read. Default: `UInt32`, Base `0`. |
| `OffsetTable[Count, Type, Base]` | `Count * sizeof(Type)` | `list[Target]` or `OffsetTableHandle` | Fixed-count table of pointer offsets. |
| `Variant[tag_field, mapping]` | Dynamic | Target struct instance | Polymorphic tagged union dispatched by `tag_field`. |
| `Base.SELF`, `Base.STRUCT`, `Base.FIELD` | 0 (Symbolic) | `RelativeBase` | Offset base origin. Supports arithmetic: `Base.SELF + 0x20`. |

---

## 3. Declarative Layer: `@binary_struct`

### 3.1 Decorator Syntax & Options
```python
@binary_struct(
    endian="little",      # "little" | "big" | "native" | Endian.LITTLE | Endian.BIG
    bits=None,            # Total bit width if this struct is a Bitfield container (e.g. 8, 16, 32, 64)
    align=None,           # Explicit struct-level boundary alignment (e.g. align=4)
    auto_align=False,     # True: aligns each field to its natural boundary (C struct behavior)
)
class MyStruct:
    ...
```

### 3.2 Injected Attributes and Methods on Decorated Classes
Every `@binary_struct` class receives:
- `instance.to_bytes(endian=None) -> bytes`: Serializes the instance to raw bytes.
- `Cls.from_bytes(data: bytes | bytearray, endian=None) -> Cls`: Deserializes raw bytes into an instance.
- `Cls.binary_size -> int` / `instance.binary_size -> int`: Returns binary byte size (identical to `sizeof(Cls)` or `len(instance)`).
- `Cls.offsetof(field_name: str) -> int` / `instance.offsetof(field_name: str) -> int`: Returns byte offset of field (supports `"nested.field"`).
- `Cls.bit_offsetof(field_name: str) -> tuple[int, int]`: Returns `(byte_offset, bit_offset)`.
- `Cls.to_c(name=None, desc="") -> str`: Generates C typedef struct code.
- `Cls.to_rust(name=None, desc="") -> str`: Generates Rust struct code.
- `Cls.to_cpp(name=None, desc="") -> str`: Generates Modern C++ struct code.
- `Cls.to_csharp(name=None, desc="") -> str`: Generates C# struct code.
- `Cls.to_go(name=None, desc="") -> str`: Generates Go struct code.
- `Cls.to_code(lang: str, **kwargs) -> str` / `instance.to_code(...)`: Unified code generator for any supported language.
- `Cls.write_code(path, lang=None, **kwargs) -> str` / `instance.write_code(...)`: Writes generated code to a file (infers language from extension if omitted).
- `Cls.to_markdown(title=..., **kwargs) -> str` / `instance.to_markdown(...)`: Generates comprehensive Markdown specification with Mermaid diagrams.
- `Cls.write_markdown(path, **kwargs) -> str` / `instance.write_markdown(...)`: Writes Markdown specification to file.
- `instance.to_dict(bytes_format="hex"|"base64"|"list") -> dict`: Serializes struct to Python dict recursively.
- `Cls.from_dict(d: dict, bytes_format="hex") -> Cls`: Deserializes struct from dict recursively.
- `instance.to_json(indent=None, bytes_format="hex") -> str`: Serializes struct to JSON string.
- `Cls.from_json(json_str: str, bytes_format="hex") -> Cls`: Deserializes struct from JSON string.
- `__len__(self)`: `len(instance)` returns `sizeof(instance)`.

### 3.3 Documentation & Comment Reflection
`@binary_struct` extracts docstrings and field descriptions automatically for specification generation:
- Class docstring `"""..."""` -> Spec `## Overview` or Bitfield Details.
- Inline comment `# ...` or `Annotated[Type, "description"]` -> Spec `Description` column.

### 3.4 Canonical Struct Examples

#### Basic Struct with Natural Alignment & Docstrings
```python
from binary_master import binary_struct, UInt8, UInt16, UInt32, Float32, FixedArray, sizeof

@binary_struct(endian="little", auto_align=True)
class TelemetryHeader:
    """Telemetry packet header."""
    magic: UInt32                # Signature: 0x54454C4D ('TELM')
    version: UInt16              # Protocol version number
    device_id: UInt8             # Source device identifier
    # 1 byte natural alignment padding automatically inserted here before Float32
    battery_voltage: Float32     # Battery level in Volts
    session_tag: FixedArray[UInt8, 4] # 4-byte session token

# Static size inspection
assert sizeof(TelemetryHeader) == 16
assert TelemetryHeader.binary_size == 16
assert TelemetryHeader.offsetof("battery_voltage") == 8
```

#### Compact Bitfields (`Bits[N]`)
Total bit width **must** be declared via `bits=N` (8, 16, 32, 64, or any byte multiple):
```python
from binary_master import binary_struct, Bits, read_struct

@binary_struct(bits=16)
class DeviceFlags:
    """16-bit packed hardware status flags."""
    powered_on:  Bits[1]   # Bit 0: Power state (0=off, 1=on)
    busy:        Bits[1]   # Bit 1: Processing state
    mode:        Bits[3]   # Bits 2..4: Operating mode (0..7)
    error_code:  Bits[3]   # Bits 5..7: Error code (0..7)
    battery_pct: Bits[7]   # Bits 8..14: Battery % (0..100)
    reserved:    Bits[1]   # Bit 15: Reserved

flags = DeviceFlags(powered_on=1, busy=0, mode=5, error_code=0, battery_pct=95, reserved=0)
raw = flags.to_bytes()
restored = DeviceFlags.from_bytes(raw)
assert restored.battery_pct == 95
```

#### Relative Offsets and Dynamic Offset Tables
Offsets can be relative to the start of the struct (`Base.SELF`) or offset field (`Base.FIELD`):
```python
from binary_master import (
    binary_struct, UInt16, UInt32, FixedArray, UInt8,
    Offset, OffsetTable, Base, read_struct
)

@binary_struct
class ChunkPayload:
    width: UInt16
    height: UInt16
    pixels: FixedArray[UInt8, 8]

@binary_struct
class FileContainer:
    magic: UInt32
    # Self-relative offset (stored value = payload_pos - struct_start_pos)
    primary_offset: Offset[ChunkPayload, UInt32, Base.SELF]
    # Self-relative offset with constant displacement (stored value = payload_pos - (struct_start + 0x20))
    aux_offset: Offset[ChunkPayload, UInt32, Base.SELF + 0x20]
    # Dynamic table of 2 pointers relative to struct start
    num_chunks: UInt16
    chunk_table: OffsetTable[2, UInt32, Base.SELF]

# Writing: write_struct automatically writes child structs at the end and patches offsets
c1 = ChunkPayload(width=10, height=20, pixels=b"12345678")
c2 = ChunkPayload(width=30, height=40, pixels=b"87654321")
container = FileContainer(
    magic=0x12345678,
    primary_offset=c1,
    aux_offset=c2,
    num_chunks=2,
    chunk_table=[c1, c2]
)
data = container.to_bytes()

# Reading: read_struct dereferences pointers automatically!
restored = FileContainer.from_bytes(data)
assert restored.primary_offset.width == 10
assert restored.aux_offset.width == 30
assert restored.chunk_table == [46, 58] # Offsets in table (relative to Base.SELF)
```

#### Polymorphic Tagged Union (`Variant`)
```python
from binary_master import binary_struct, UInt8, UInt16, FixedArray, Variant

@binary_struct
class TextPayload:
    text: FixedArray[UInt8, 16]

@binary_struct
class BinaryPayload:
    data: FixedArray[UInt8, 16]

@binary_struct
class DynamicPacket:
    type_id: UInt8  # Tag field MUST precede the Variant field
    payload: Variant["type_id", {
        1: TextPayload,
        2: BinaryPayload,
    }]

pkt = DynamicPacket(type_id=1, payload=TextPayload(text=b"HELLO\x00" + b"\x00"*10))
raw = pkt.to_bytes()
restored = DynamicPacket.from_bytes(raw)
assert isinstance(restored.payload, TextPayload)
```

---

## 4. Schema-First Builder Layer: `Builder` (`BinaryBuilder`)

### 4.0 Why Builder? (Builder vs Writer Core Rationale)
While `BinaryWriter` can generate specs and C headers directly from serialized data, `Builder` remains essential for three primary architectural reasons:
1. **Zero-Data Specification Authoring (Design Phase)**: Define protocol layouts, narrative chapters (`add_document`), and multi-language exports upfront *before* any serializing code or binary test data exists.
2. **Schema-Driven Automated Deserialization (`builder.read`)**: Parses arbitrary raw byte streams into structured Python objects by evaluating tags and conditions dynamically, eliminating the need to write custom procedural `Reader` loops.
3. **Compiler Intermediate Representation (IR)**: `Builder` serves as the internal AST/IR for all code generators (`c_header`, `code_gen/*`). Methods like `writer.to_c_header()` actually convert writer traces to a `Builder` via `writer.to_builder()` under the hood.

**Rule of Thumb**:
- Use `BinaryWriter` for daily binary generation and execution-trace documentation.
- Use `Builder` for specification-first design and automated incoming packet parsing.

### 4.1 Builder Methods Signature Table
| Method | Arguments | Description |
|---|---|---|
| `Builder(...)` | `title: str = "...", default_endian: str = "little", version: str = None, description: str = ""` | Initialize protocol schema |
| `add_document` | `title: str, content: str` | Add narrative chapter / overview text (Markdown) |
| `add_struct` | `struct_cls: type, name: str = None, desc: str = "", condition: str = None, condition_func: Callable = None, count: int\|str\|Callable = None` | Register sequential struct (supports conditions and repeated counts) |
| `add_choice` | `name: str, tag_field: str\|Callable, variants: dict\|list, desc: str = "", condition: str = None, condition_func: Callable = None` | Register polymorphic branch dispatched by `tag_field` |
| `add_field` | `name: str, type_name: str, size: int, desc: str = "", endian: str = None, condition: str = None` | Register ad-hoc primitive field without dedicated struct class |
| `set_caption`, `section`, `caption` | `title: str, desc: str = "", spec_count: int\|str = None` | Context manager to group elements: `with builder.set_caption(...):` |
| `write`, `write_markdown` | `path_or_file: str|Path|IO, diagram_direction: str = "TD", ...` | Generate and save complete Markdown specification with Mermaid diagrams |
| `to_markdown` | `diagram_direction: str = "TD", ... -> str` | Return generated Markdown specification string |
| `to_bytes`, `serialize` | `data: dict|Any, endian: str = None -> bytes` | Serialize structured data into binary bytes according to schema |
| `read` | `data: bytes|bytearray|Reader, trace: bool = False` | Automatically parse binary into a `BuilderReadResult` |
| `hexdump` | `data: bytes\|bytearray, width: int = 16, color: bool = False` | Output annotated hexdump correlated with schema fields |
| `dump` | `data: bytes\|bytearray, format: str = "table"` | Output decoded layout table |
| `write_c_header` | `path_or_file, guard: str = None, pack: bool = True` | Export C header (`.h`) |
| `write_rust` | `path_or_file` | Export Rust definitions (`.rs`) |
| `write_cpp` | `path_or_file` | Export Modern C++ header (`.hpp`) |
| `write_csharp` | `path_or_file, namespace: str = "BinaryProtocol"` | Export C# file (`.cs`) |
| `write_go` | `path_or_file, package_name: str = "protocol"` | Export Go package (`.go`) |
| `write_code` | `path_or_file, lang: str = None` | Export code, auto-detecting language from file extension |

### 4.2 Complete Builder Example: Schema, Docs, Multi-Lang & Read
```python
from pathlib import Path
from binary_master import (
    Builder, binary_struct, UInt8, UInt16, UInt32, Float32,
    FixedArray, BinaryWriter
)

@binary_struct(endian="little")
class Header:
    magic: UInt32      # 0x4D534750 ('MSGP')
    msg_type: UInt16   # 1 = Text, 2 = Sensor
    flags: UInt16      # Bit 0: Has Footer

@binary_struct
class TextMsg:
    text: FixedArray[UInt8, 16]

@binary_struct
class SensorMsg:
    temperature: Float32
    humidity: Float32

@binary_struct
class Footer:
    crc32: UInt32

# 1. Construct Schema
builder = Builder(
    title="Sensor Network Protocol",
    version="1.0.0",
    default_endian="little",
    description="Telemetry protocol with dynamic message payload."
)

builder.add_document(
    "Protocol Overview",
    "Packets start with `Header`. `msg_type` dictates the payload structure."
)

with builder.section("Header Section", "Identification block"):
    builder.add_struct(Header, name="header")

with builder.caption("Payload Section", "Polymorphic payload"):
    builder.add_choice(
        name="payload",
        tag_field="msg_type",
        variants={
            1: (TextMsg, "Text payload"),
            2: (SensorMsg, "Sensor payload"),
        }
    )

with builder.section("Footer Section", "Optional verification"):
    builder.add_struct(Footer, name="footer", condition="flags & 0x01 != 0")

# 2. Output Specification Manual & Code
builder.write("spec.md")
builder.write_code("protocol.h")
builder.write_code("protocol.rs")

# 3. Automated Deserialization (builder.read)
# Create raw packet: Header(msg_type=2, flags=1) + SensorMsg + Footer
writer = BinaryWriter()
writer.write_struct(Header(magic=0x4D534750, msg_type=2, flags=1))
writer.write_struct(SensorMsg(temperature=24.5, humidity=60.0))
writer.write_struct(Footer(crc32=0x12345678))
raw_bytes = writer.to_bytes()

# Parse automatically via schema!
result = builder.read(raw_bytes)

assert result.header.magic == 0x4D534750
assert isinstance(result.payload, SensorMsg)
assert result.payload.temperature == 24.5
assert "footer" in result
assert result.footer.crc32 == 0x12345678
# Supports dict access as well
assert result["header"]["msg_type"] == 2
```

---

## 5. Procedural Layer: `BinaryWriter` & `BinaryReader`

Use procedural classes when handling streaming I/O, custom packet packing, ad-hoc string formatting, or fine-grained buffer positioning.

### 5.1 `BinaryWriter` (`Writer`) Cheat Sheet
Methods return `self` for fluent chaining.
```python
from binary_master import BinaryWriter, Endian

writer = BinaryWriter(default_endian="little") # or BinaryWriter.to_file("out.bin")

# Primitives
writer.write_uint8(255, name="u8")
writer.write_uint16(65535, endian="big", name="u16_be") # endian override
writer.write_uint32(0xCAFEBABE, name="u32")
writer.write_uint64(0x1122334455667788, name="u64")
writer.write_int8(-1, name="i8")
writer.write_int16(-32000, name="i16")
writer.write_int32(-100000, name="i32")
writer.write_int64(-9999999999, name="i64")
writer.write_float32(3.14159, name="f32")
writer.write_float64(2.7182818284, name="f64")
writer.write_bool(True, name="flag")
writer.write_bytes(b"\x01\x02\x03\x04", name="raw")

# Strings
writer.write_cstring("Hello", encoding="utf-8") # Null-terminated
writer.write_prefixed_string("Prefixed", prefix_bytes=2, encoding="utf-8") # Pascal string
writer.write_fixed_string("Fixed", length=16, pad_byte=b"\x00") # Padded fixed string

# Alignment & Padding
writer.pad(count=4, pad_byte=b"\x00")
writer.align(boundary=4, pad_byte=b"\x00") # Pad to 4-byte multiple

# Struct Integration & Repetition
writer.write_struct(my_struct_instance)
writer.write_struct(chunk, repeat="chunk_count")  # Expression / variable name in spec
writer.write_struct(chunk, repeat=-1)             # Indefinite count: 不定回数 (0回以上 / 可変)
# Note: section is optional (default=""). When omitted, repeats automatically group under struct class name.

# Polymorphic Variants (Type validation & auto-registration for specs/code)
writer.write_variant(
    payload_instance,
    candidates={0x01: HeaderChunk, 0x02: TextChunk}, # dict or list of allowed struct classes
    tag_field="msg_type",                            # optional: checks preceding field value matches
    name="payload",
    desc="Dynamic payload",
)

# Specification Metadata & Scoped Captions (Centralized with set_caption)
with writer.set_caption("Chunks", desc="Indefinite stream of chunks", spec_count=-1):
    for c in chunks:
        writer.write_struct(c)

with writer.set_caption("offsets", desc="Table of chunk offsets", spec_count="num_chunks"):
    table_handle = writer.write_offset_table(count=2, offset_size=4, base_offset=0)

# Direct caption setup:
writer.set_caption("Body Section", desc="Payload contents")
writer.subcaption("Sub Section", desc="Details")

# Offset Tables with delayed patching
table_handle = writer.write_offset_table(count=2, offset_size=4, base_offset=0)
# Later...
table_handle.set_offset(0, target_offset=0x100) # manual offset
table_handle.write_target(1, child_struct)       # writes target at current pos & records offset

# One-Stop Specification & Multi-Language Code Generation (No Builder Required!)
writer.write_markdown("protocol_spec.md")
md_str = writer.to_markdown()
writer.write_c_header("protocol.h")
writer.write_rust("protocol.rs")
writer.write_cpp("protocol.hpp")
writer.write_csharp("protocol.cs", namespace="MyProtocol")
writer.write_go("protocol.go", package_name="protocol")
writer.write_code("output.rs") # Auto-detects language from file extension
builder = writer.to_builder(title="Generated Spec") # Convert to static Builder if needed

# Position Preservation & Direct Offset Patching
with writer.preserve_position():
    writer.seek(0)
    writer.write_uint32(0x12345678) # returns to original position on exit

with writer.at_offset(0x04):
    writer.write_uint32(1024)       # writes at offset 0x04 and returns on exit

# Inspection & Output
pos = writer.tell()
data = writer.to_bytes()
```

### 5.2 `BinaryReader` (`Reader`) Cheat Sheet
```python
from binary_master import BinaryReader

reader = BinaryReader(data, default_endian="little") # or BinaryReader.from_file("in.bin")

# Primitives
u8  = reader.read_uint8()
u16 = reader.read_uint16(endian="big") # endian override
u32 = reader.read_uint32()
u64 = reader.read_uint64()
i8  = reader.read_int8()
i16 = reader.read_int16()
i32 = reader.read_int32()
i64 = reader.read_int64()
f32 = reader.read_float32()
f64 = reader.read_float64()
b   = reader.read_bool()
raw = reader.read_bytes(4) # None reads until EOF

# Lookahead (Peek) without advancing cursor
byte_val = reader.peek()
raw_peek = reader.peek_bytes(4)
u16_peek = reader.peek_uint16()
u32_peek = reader.peek_uint32()

# Strings
s_null = reader.read_cstring(encoding="utf-8")
s_pref = reader.read_prefixed_string(prefix_bytes=2, encoding="utf-8")
s_fix  = reader.read_fixed_string(length=16, pad_byte=b"\x00", encoding="utf-8")

# Navigation & Positioning
pos = reader.tell()
reader.seek(0)
reader.skip(4)
reader.align(4)
rem = reader.remaining() # Number of bytes left
is_done = reader.is_eof  # Boolean property: True if remaining() == 0

# Position Preservation Context
with reader.preserve_position():
    reader.seek(0x20)
    sub_val = reader.read_uint32()
# automatically restores cursor on exit

# Struct Integration
obj = reader.read_struct(MyStructClass)
```

---

## 6. Multi-Language Code Generation

Export schemas or individual structs across 5 languages:

| Target Language | Single Struct Method | Builder Method | Writer Method | File Extension |
|---|---|---|---|---|
| **C (C99 / C11)** | `Cls.to_c()` | `builder.write_c_header("p.h")` | `writer.write_c_header("p.h")` | `.h`, `.c` |
| **Rust (2021+)** | `Cls.to_rust()` | `builder.write_rust("p.rs")` | `writer.write_rust("p.rs")` | `.rs` |
| **Modern C++ (C++17/20)** | `Cls.to_cpp()` | `builder.write_cpp("p.hpp")` | `writer.write_cpp("p.hpp")` | `.hpp`, `.cpp` |
| **C# (.NET 8+)** | `Cls.to_csharp(namespace="...")` | `builder.write_csharp("p.cs")` | `writer.write_csharp("p.cs")` | `.cs` |
| **Go (1.20+)** | `Cls.to_go(package_name="...")` | `builder.write_go("p.go")` | `writer.write_go("p.go")` | `.go` |

Unified caller: `write_code(builder_or_writer, "output.rs")` auto-detects language from extension.

---

## 7. Debugging, Inspection & Diffing

### 7.1 Visual Annotated Hexdump (`hexdump`)
Correlates binary bytes directly with written fields, showing offset, hex, ASCII, and field annotations:
```python
from binary_master import hexdump

# Accepts BinaryWriter, BinaryReader, @binary_struct instance, or raw bytes
print(hexdump(writer, width=16, color=True))
print(hexdump(reader)) # Highlights current reader cursor with --> CURSOR @ 0xXXXX
```

### 7.2 Structured Dumps (`dump_table`, `dump_json`, `dump_dict`)
```python
from binary_master import dump_table, dump_json

# Print clean monospace markdown table of all fields, offsets, sizes, types, and values
print(dump_table(writer))

# Export structured JSON for test assertions
json_str = dump_json(writer, indent=2)
```

### 7.3 Binary Diff Comparison (`diff_dump`)
Highlights differing bytes and shows which fields were changed:
```python
from binary_master import diff_dump

# Compare two writers, readers, or bytes
diff_text = diff_dump(writer1, writer2, color=True)
print(diff_text)
```

---

## 8. Specification & Manual Generation (`manual`)

```python
from binary_master import generate_manual

# 1. Direct from BinaryWriter (Preferred for data-driven pipelines):
writer.write_markdown("protocol_spec.md")
md_str = writer.to_markdown()

# 2. From Builder (For static schemas without dummy data):
builder.write("protocol_spec.md")

# 3. Direct low-level generation from writer entries:
md = generate_manual(
    writer.entries,
    title="Protocol Specification",
    default_endian="little",
    diagram_type="flowchart",       # "flowchart" | "packet"
    diagram_direction="TD",         # "TD" | "LR"
    bits_per_row=32,                # for packet diagram
    include_bitfield_diagram=True,  # generates detail packet diagrams for bitfields
)
```

---

## 9. Critical Rules, Constraints & Anti-Patterns (MUST READ FOR AI)

### ⚠️ RULE 1: `write_manual` is Replaced by `write_markdown` / `builder.write`
- **DO NOT** call `writer.write_manual(...)` or `builder.write_manual(...)` (deprecated / removed).
- **DO** call `writer.write_markdown("path.md")` (or `writer.to_markdown()`) for procedural writers.
- **DO** call `builder.write("path.md")` for schema-first builders.

### ⚠️ RULE 2: `Variant` Tag Field Placement
- In `@binary_struct`, the field referenced by `Variant["tag_name", ...]` **MUST be declared before** the `Variant` field itself in the class definition. Deserialization relies on previously unpacked kwargs.

### ⚠️ RULE 3: Bitfield Definition Constraints
- Classes using `Bits[N]` **MUST** specify total bits in the decorator: `@binary_struct(bits=16)`.
- The sum of all `Bits[N]` widths inside the class **MUST** match the total bits declared (e.g. 1 + 3 + 4 + 8 = 16).
- Standard types (e.g. `UInt16`, `FixedArray`) cannot be mixed inside a bitfield class; only `Bits[N]` is allowed.

### ⚠️ RULE 4: Static vs Dynamic Size Calculation
- `sizeof(Cls)` and `Cls.binary_size` work **statically** for classes with fixed-size types (`UInt*`, `Int*`, `Float*`, `FixedArray[T, N]`, `Offset[T, Size]`, `OffsetTable[N, Size]`, bitfields).
- If a class contains variable-length fields (`Array[T]`, `str`, `bytes`), `sizeof(Cls)` raises `ValueError`. Use `sizeof(instance)` or `len(instance)` on instantiated objects instead.

### ⚠️ RULE 5: Offset Bases & Arithmetic
- `Base.SELF` (synonym: `Base.STRUCT`) resolves to the start byte of the enclosing struct.
- `Base.FIELD` resolves to the byte position of the offset field itself.
- You can apply offsets using Python operators: `Base.SELF + 0x20` or `Base.FIELD - 4`.

### ⚠️ RULE 6: Python 3.14+ Type Annotations
- `binary-master` supports Python 3.14+ deferred annotations (`from __future__ import annotations`). All type hints in `@binary_struct` are lazily evaluated and normalized.

### ⚠️ RULE 7: `Array[T]` Consumes Stream to EOF (Tail Field Only)
- In `@binary_struct`, `Array[T]` (such as `Array[UInt8]`) has no explicit length prefix and consumes **all remaining bytes until EOF** during `read_struct` / `from_bytes`.
- Therefore, `Array[T]` **MUST be the last field** in a `@binary_struct`. Placing another field after `Array[T]` will trigger an `EOFError` on deserialization.
- For fixed-length slices, ALWAYS use `FixedArray[T, N]`. For dynamic payloads with trailing fields, use `Offset[Target]` or `Variant`.

### ⚠️ RULE 8: Choosing Between `Writer` and `Builder`
- **Use `BinaryWriter` (Code-First / Data-Driven)**: When writing real binaries or when structure depends on dynamic execution logic (loops, header branches). `writer.write_markdown()` and `writer.write_c_header()` produce specifications and headers directly from written data, with automatic repeat deduplication (`repeat=-1`, `repeat="expr"`).
- **Use `Builder` (Schema-First / Specification-Driven)**: When modeling protocols ahead of implementation, generating code definitions without real data, or using automated schema-driven deserialization (`builder.read(bytes)`). `Builder` also serves as the internal Intermediate Representation (IR) across all code generators.

### ⚠️ RULE 9: Direct Struct Export Over Manual Builder Wrappers
- When exporting specifications or multi-language code for a single `@binary_struct` class or instance, call `Cls.to_markdown()` or `Cls.to_code("rust")` directly (or `Cls.write_markdown("spec.md")` / `Cls.write_code("out.rs")`) instead of manually instantiating `Builder` or `BinaryWriter`.

---

## 10. Common Implementation Patterns

### Pattern A: Network Packet with Fixed Header and Variable Tail Payload
```python
from binary_master import (
    binary_struct, UInt8, UInt16, UInt32, Array, FixedArray,
    sizeof, read_struct
)

@binary_struct(endian="big")
class NetworkPacket:
    """Network frame with fixed header and trailing variable payload."""
    preamble: FixedArray[UInt8, 2] # 0xAA, 0x55
    msg_id: UInt16
    checksum: UInt32
    # Array[T] MUST be at the end of the struct as it consumes until EOF
    payload: Array[UInt8]

# Instantiate
pkt = NetworkPacket(
    preamble=b"\xAA\x55",
    msg_id=0x0102,
    checksum=0x12345678,
    payload=b"VARIABLE_LENGTH_PAYLOAD",
)
data = pkt.to_bytes()
restored = NetworkPacket.from_bytes(data)
assert bytes(restored.payload) == b"VARIABLE_LENGTH_PAYLOAD"
```

### Pattern B: Procedural Header with Pointers to Payloads
```python
from binary_master import BinaryWriter

writer = BinaryWriter(default_endian="little")

# 1. Header with table reserved
writer.write_uint32(0x46494C45, name="magic") # 'FILE'
writer.write_uint16(2, name="item_count")
table = writer.write_offset_table(count=2, offset_size=4, name="item_offsets")

# 2. Write payloads and patch offsets
table.write_target(0, b"First Payload Data")
table.write_target(1, b"Second Payload Data")

binary_data = writer.to_bytes()
```

---

## 11. v2.0 Advanced Features Reference (LLM Quick Reference)

### 11.1 CRC & Checksum Declarative Types
- **Types**: `CRC32` (4B, IEEE 802.3), `CRC16` / `CRC16_CCITT` (2B, poly 0x1021), `CRC16_ARC` (2B, poly 0xA001), `Checksum8` (1B, sum mod 256), `Checksum16` (2B, sum mod 65536), `Fletcher16` (2B), `Adler32` (4B).
- **Slice Range**: By default, covers `0` to the field position. Custom slice: `CRC32[4:20]`.
- **Automatic Behavior**:
  - `to_bytes()` calculates checksum over preceding bytes and packs it into the stream.
  - `from_bytes()` reads checksum and verifies against calculated value.
  - On mismatch, raises `ChecksumMismatchError(expected=..., actual=...)`.
- **Procedural**: `with writer.checksum("crc32"): ...`, `writer.write_checksum("crc32")`, `reader.verify_checksum("crc32")`.

### 11.2 Enums (`BinaryEnum` & `IntEnum`)
- **Base Class**: Subclass `BinaryEnum` (subclasses `enum.IntEnum`).
- **Explicit Sizing**: `MyEnum[UInt8]`, `MyEnum[UInt16]`, `MyEnum[UInt32]`, `MyEnum[UInt64]`.
- **Automatic Sizing**: Bare `MyEnum` or standard `enum.IntEnum` auto-selects 1 byte (<=255), 2 bytes (<=65535), or 4 bytes.
- **Deserialization**: `from_bytes` instantiates the Python `Enum` member directly.
- **Validation**: If stream integer is not in enum, raises `InvalidEnumError(enum_cls, raw_val)`.

### 11.3 Magic Numbers & Constant Constraints
- **Magic**: `Magic[b"PNG\r\n\x1a\n"]` or `Magic[0x12345678]`.
- **Constant**: `Constant[UInt16, 20]`.
- **Zero-Boilerplate Instantiation**: Fields typed as `Magic` or `Constant` do not require arguments in `__init__`.
- **Validation on Read**: `from_bytes` verifies against expected value, raising `InvalidMagicError` or `InvalidConstantError`.

### 11.4 JSON / Dict Interop
- `instance.to_dict(bytes_format="hex"|"base64"|"list")` -> `dict`
- `Cls.from_dict(d)` -> `Cls`
- `instance.to_json(indent=None, bytes_format="hex"|"base64"|"list")` -> `str`
- `Cls.from_json(json_str)` -> `Cls`
- Hex format prefixes `"0x..."`. `from_dict` automatically parses both `"0x..."` and raw hex strings.

### 11.5 Large File Streaming & Memory-Mapped Zero-Copy
- `reader.iter_struct(Cls)`: Generator yielding instances of `Cls` until EOF.
- `BinaryReader.from_mmap(path, default_endian="little")`: Context manager utilizing OS memory-mapping (`mmap`) for zero-copy slice reads without loading whole files into memory.

### 11.6 Variable-Length Integers (LEB128)
- **Types**: `VarUInt`, `VarInt`, `VarUInt32`, `VarInt32`, `VarUInt64`, `VarInt64`.
- **Procedural Writer**: `writer.write_varuint(val)`, `writer.write_varint(val)`.
- **Procedural Reader**: `reader.read_varuint()`, `reader.read_varint()`.
- **Declarative Struct**: Can be used as field types in `@binary_struct`.

### 11.7 Arbitrary Bitstream Manipulation
- `BitWriter(stream=None, msb_first=True)`: `write_bits(value, bit_count)`, `flush_bits(pad_bit=0)`, `to_bytes()`.
- `BitReader(data_or_stream, msb_first=True)`: `read_bits(bit_count)`, `peek_bits(bit_count)`, `align_to_byte()`.
- `writer.write_bits(val, count)` & `reader.read_bits(count)`: Integrated directly into `BinaryWriter` and `BinaryReader`. Non-bit write methods automatically flush unaligned bits.

### 11.8 CLI Binary Inspector
`pyproject.toml` script entry point: `binary-master`.
- `binary-master inspect <file>`: Formatted, annotated Hexdump.
- `binary-master diff <file1> <file2>`: Visual byte diff.
- `binary-master spec <module:Class> [-o output.md]`: Markdown protocol manual generation.
- `binary-master export <module:Class> --lang <rust|c|cpp|csharp|go> [-o output]`: Multi-language code generation (pass `-o -` for stdout).

### 11.9 Direct Struct Export & Descriptors
`@binary_struct` classes and instances support direct specification and multi-language code export without instantiating `Builder` or `BinaryWriter`:
- `Cls.to_markdown(title=None, **kwargs) -> str` / `inst.to_markdown(include_values=True, **kwargs) -> str`
- `Cls.write_markdown(path, **kwargs) -> str` / `inst.write_markdown(path, **kwargs) -> str`
- `Cls.to_code(lang="rust"|"c"|"cpp"|"csharp"|"go", **kwargs) -> str` / `inst.to_code(lang, **kwargs) -> str`
- `Cls.write_code(path, lang=None, **kwargs) -> str` / `inst.write_code(path, **kwargs) -> str` (infers language from file extension if `lang` is omitted)
- Individual language shortcuts: `Cls.to_c()`, `Cls.to_rust()`, `Cls.to_cpp()`, `Cls.to_csharp()`, `Cls.to_go()`.

