
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
    BinaryStruct,        # Base class providing static typing for IDEs/ty/mypy/pyright (alias: Struct)
    Struct,              # Alias for BinaryStruct
    to_bytes,            # Standalone struct serializer to bytes: to_bytes(struct_instance)
    from_bytes,          # Standalone struct deserializer from bytes: from_bytes(StructCls, data)
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
    Float16, Float32, Float64,
    Float, Double,  # Convenient aliases: Float = Float32, Double = Float64

    # Generic & Advanced Type Annotations
    Bits,                # Bits[N]: Bitfield slice (used with @binary_struct(bits=N))
    Bytes,               # Bytes[N]: Static raw byte sequence (bytes)
    FixedString,         # FixedString[N]: Static fixed-length string (str)
    CString,             # CString: Null-terminated string (str)
    PrefixedString,      # PrefixedString[N]: Length-prefixed string (str)
    Offset,              # Offset[Target, OffsetType=UInt32, BaseOffset=0]
    NamedOffset,         # NamedOffset["key", OffsetType=UInt32, BaseOffset=0]
    OffsetTable,         # OffsetTable[Count, OffsetType=UInt32, BaseOffset=0]
    Variant,             # Variant[tag_field_name, {tag_val: StructCls, ...}]
    Array,               # Array[T]: Dynamic length sequence
    FixedArray,          # FixedArray[T, N]: Static N-element array
    Literal,             # typing.Literal re-export for PEP-compliant type parameters
    L,                   # Short alias for Literal: FixedArray[UInt8, L[4]]
    Base,                # Base.SELF, Base.STRUCT, Base.FIELD origin markers
    RelativeBase,        # Result of Base + delta arithmetic


    # v0.2.0 & v0.3.0 Declarative Types & Constraints
    BinaryEnum,          # IntEnum with explicit sizing: MyEnum[UInt8]
    Magic,               # Magic[b"PNG..."] or Magic[0x1234]: signature constraint
    Constant,            # Constant[Type, Value]: fixed-value constant field
    Range,               # Range[Type, min, max]: bounded value range with validation
    LengthOf,            # LengthOf[Type, "target_field"]: automatic byte length calculation & linked deserialization
    CountOf,             # CountOf[Type, "target_field"]: automatic array element count calculation & linked deserialization
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
    RangeValidationError,
    TotalSizeExceededError,

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

    # Manual, HTML & Mermaid Generation
    generate_manual,
    generate_html,
    write_html,
    generate_mermaid_diagram,
    generate_packet_diagram,
    generate_bitfield_packet_diagram,
    inspect_struct_layout,
    resolve_language,
    LayoutEntry,
)

```

---

## 2. Type System Reference

| Type Annotation | Binary Size | Python Input/Output | Notes & Examples |
|---|---|---|---|
| `UInt8`, `UInt16`, `UInt32`, `UInt64` | 1, 2, 4, 8 bytes | `int` | Unsigned standard integers |
| `Int8`, `Int16`, `Int32`, `Int64` | 1, 2, 4, 8 bytes | `int` | Signed 2's complement integers |
| `Float16`, `Float32` (`Float`), `Float64` (`Double`) | 2, 4, 8 bytes | `float` | IEEE 754 half / single / double precision (`Float` = `Float32`, `Double` = `Float64`) |
| `Bool` / `bool` | 1 byte (or `Bool[N]` bytes) | `bool` | `0x00` = False, non-zero = True (supports `Bool[1]`, `Bool[2]`, `Bool[4]`) |
| `Bytes[N]` | `N` bytes | `bytes` | Static raw bytes buffer. Example: `Bytes[16]` |
| `FixedString[N]` | `N` bytes | `str` | Static fixed-length string (null/space-padded). Example: `FixedString[8]` |
| `CString` | Variable (`len + 1` bytes) | `str` | Null-terminated C string (`\0`) |
| `PrefixedString[N]` | Variable (`N + len` bytes) | `str` | Length-prefixed string with N-byte length prefix (1, 2, 4) |
| `FixedArray[T, N]` | `N * sizeof(T)` | `bytes` (if T is UInt8) or `list[T]` | Static fixed element buffer. Example: `FixedArray[UInt8, 16]` |
| `Array[T]` | Dynamic (`len * sizeof(T)`) | `bytes` (if T is UInt8) or `list[T]` | Dynamic sequence. Consumes remaining bytes on read unless bounded. |
| `Range[Type, min, max]` | `sizeof(Type)` | `int` or `float` | Bounded numeric field validated on serialization and deserialization. |
| `LengthOf[Type, target]` | `sizeof(Type)` | `int` | Auto-calculates target byte length on write; bounds target read on deserialization. |
| `CountOf[Type, target]` | `sizeof(Type)` | `int` | Auto-calculates target element count on write; bounds target array read on deserialization. |
| `Bits[N]` | `N` bits | `int` | Bitfield slice. Must be within struct decorated with `@binary_struct(bits=Total)`. |
| `Offset[Target, Type, Base]` | 1, 2, 4, or 8 bytes | Instance of `Target` or `int` | Pointer offset. Backpatched automatically on write; auto-dereferenced on read. Default: `UInt32`, Base `0`. |
| `NamedOffset[Key, Type, Base]` | 1, 2, 4, or 8 bytes | `int` | Named placeholder offset resolved via `writer.write_named_offset("key")`. |
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
    total_size=None,      # Fixed total byte size of struct. Automatically pads with pad_byte up to total_size
    pad_byte=b"\x00",     # Byte used for total_size padding (default b"\x00")
)
class MyStruct:
    ...
```

### 3.1.1 Default Values Anywhere & Automatic Zero-Initialization
- Fields can define explicit default values (`field: Type = default_val` or `field(default=...)`).
- **No ordering restriction**: Unlike standard `@dataclass`, fields with defaults can appear **anywhere** (e.g. at the beginning of a header) without raising `TypeError: non-default argument follows default argument`.
- **Automatic Zero-Initialization**: Fields without explicit defaults automatically default to zero (or type-appropriate zero values: `0`, `0.0`, `False`, `b"\x00"*N`, `[]`, `None`). All fields can be omitted during instantiation (e.g. `MyStruct()` or `MyStruct(magic=0x1234)`).
- When instantiating, omitted fields automatically take their explicit default or zero value.


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

# Writing: declare container header first, then set payloads
container = FileContainer(magic=0x12345678)
container.primary_offset = ChunkPayload(width=10, height=20, pixels=b"12345678")
container.aux_offset = ChunkPayload(width=30, height=40, pixels=b"87654321")
container.chunk_table = [
    ChunkPayload(width=10, height=20, pixels=b"12345678"),
    ChunkPayload(width=30, height=40, pixels=b"87654321"),
]
data = container.to_bytes()

# Reading: read_struct dereferences pointers automatically!
restored = FileContainer.from_bytes(data)
assert restored.primary_offset.width == 10
assert restored.aux_offset.width == 30
assert restored.chunk_table == [46, 58] # Offsets in table (relative to Base.SELF)

#### Direct Offset to OffsetTable (`Offset[OffsetTable[...]]`)
No wrapper struct needed. Passing a python list of structs automatically calculates count, writes table and elements at the end, and backpatches:
```python
@binary_struct
class DirectTableContainer:
    magic: UInt32
    num_items: UInt16
    table_offset: Offset[OffsetTable["num_items", UInt32, Base.SELF], Base.SELF]

# Declare header first, assign list afterwards (num_items=2 derived automatically):
container = DirectTableContainer(magic=0x524F4F54)
container.table_offset = [
    ChunkPayload(width=1, height=2, pixels=b"A"*8),
    ChunkPayload(width=3, height=4, pixels=b"B"*8),
]
raw = container.to_bytes()
```

#### NamedOffset for Arbitrary Positioning (`NamedOffset["key"]`)
When header is written first, arbitrary data/padding is streamed, and target offset is determined later:
```python
from binary_master import BinaryWriter, NamedOffset, DuplicateNamedOffsetError, NamedOffsetNotFoundError

@binary_struct
class Header:
    magic: UInt16
    payload_offset: NamedOffset["my_payload"]

writer = BinaryWriter()
writer.write_struct(Header(magic=0x1234))
writer.write_string("variable length padding or metadata...")
# Backpatch "my_payload" offset to current position (or write target struct):
writer.write_named_offset("my_payload") 
# Multiple offsets can share the same key (e.g. multiple pointers referencing the same payload); all will be backpatched.
# Calling write_named_offset more than once on the same key raises DuplicateNamedOffsetError (use rewrite_named_offset to re-patch).
# Calling write_named_offset or rewrite_named_offset with unknown key raises NamedOffsetNotFoundError.
```

##### Scoped Namespaces for NamedOffset (`with writer.namespace(...)`)
Avoid key collisions across repeated chunks/sections without altering struct definitions:
```python
with writer.namespace("chunk_0"):
    writer.write_struct(Header(magic=0x1111))
    writer.write_named_offset("my_payload")  # Qualified as "chunk_0/my_payload"

with writer.namespace("chunk_1"):
    writer.write_struct(Header(magic=0x2222))
    writer.write_named_offset("my_payload")  # Qualified as "chunk_1/my_payload" (no collision)

# Supports nesting: with writer.namespace("sec"): with writer.namespace("sub"): ...
# Root escape with leading slash: NamedOffset["/global_footer"] bypasses active namespace.
# Auto-incrementing IDs: with writer.namespace("chunk", auto_id=True): (generates chunk_0, chunk_1...)
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
writer.write_float16(1.5, name="f16")
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
f16 = reader.read_float16()
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
from binary_master import generate_manual, generate_html, write_html

# 1. Direct from BinaryWriter (Preferred for data-driven pipelines):
# Generates both flowchart & packet diagram by default; lang="auto" resolves by OS locale
writer.write_markdown("protocol_spec.md")
writer.write_html("protocol_spec.html")
md_str = writer.to_markdown(lang="ja")          # Explicit Japanese
html_str = writer.to_html(theme="dark")         # Interactive Hex Inspector

# 2. From Builder (For static schemas without dummy data):
builder.write("protocol_spec.md")
builder.write_html("protocol_spec.html")

# 3. Direct low-level generation from writer entries or @binary_struct:
md = generate_manual(
    writer.entries,
    title="Protocol Specification",
    default_endian="little",
    diagram_type="both",            # "both" (default) | "flowchart" | "packet" | "none"
    diagram_direction="TD",         # "TD" | "LR"
    bits_per_row=32,                # for packet diagram
    include_bitfield_diagram=True,  # generates detail packet diagrams for bitfields
    lang="auto",                    # "auto" (default: OS locale) | "en" | "ja"
    include_section_offsets=False,  # False (default): omit addresses in section titles; True: append (0x0000 - 0x0010, 16B)
    large_data_threshold=64,        # 64 (default): auto-summarizes raw Bytes/arrays >=64B in packet diagrams
)
```


---

## 9. Critical Rules, Constraints & Anti-Patterns (MUST READ FOR AI)

### ⚠️ RULE 1: `write_manual` is Replaced by `write_markdown` / `builder.write` / `write_html`
- **DO NOT** call `writer.write_manual(...)` or `builder.write_manual(...)` (deprecated / removed).
- **DO** call `writer.write_markdown("path.md")` (or `writer.to_markdown()`) for Markdown specifications.
- **DO** call `writer.write_html("path.html")` (or `writer.to_html()`) for interactive HTML manuals with Hex Inspector.
- **DO** call `builder.write("path.md")` (or `builder.write_html("path.html")`) for schema-first builders.
- **DO** use `lang="auto"` (default, auto-detects OS locale: Japanese in `ja_JP`, English otherwise) or pass `lang="ja"` / `lang="en"` explicitly.
- **DO** leverage `include_section_offsets=False` (default) for clean reusable specs, and `large_data_threshold=64` (default) for summarizing large byte buffers/arrays in packet diagrams. Intermediate entries of `OffsetTable` and repeated structures are automatically omitted with `...`.


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

### ⚠️ RULE 6: Python 3.14+ Type Annotations, PEP 561 & IDE Completion
- `binary-master` ships with PEP 561 compliant type stubs (`py.typed`, `.pyi`).
- **`Offset[Target]` Completion**: Statically resolves to `Target | None`. Setting `field: Offset[Target] = None` allows clean header-first assignment (`header.field = payload`) without type warnings, and deserialized access (`restored.field.attr`) provides full IDE auto-completion.
- **FixedArray Size Parameter (`L[N]` / `Literal[N]`)**: Standard Python typing specifications forbid bare numeric literals (like `FixedArray[UInt8, 4]`) in type expressions. Use `FixedArray[UInt8, L[4]]` or `FixedArray[UInt8, Literal[4]]` for strict 0-diagnostic type checking in `ty`, PyCharm, and `mypy`. `L` is exported directly from `binary_master`. (Bare numbers are still accepted and automatically unwrapped at runtime for backward compatibility).


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

## 10. AI Decision Guide: Recommended Approaches ("こういうときはこれを使う")

AI（LLM）がユーザー要件やプロトコル仕様からコードを生成する際、最適な型・機能を選択するための判断指針。

### 10.1 Feature Selection Matrix (要件・ユースケース別 選択表)

| 要件・ユースケース | 推奨機能 / 型アノテーション | 避けるべきアンチパターン | 選定理由・メリット |
|---|---|---|---|
| **固定ヘッダー + 可変長ボディ + フッター/CRC** | `LengthOf[UInt16, "payload"]` + `payload: Bytes` | `payload: Array[UInt8]` を中間に配置 | `Array` は EOF まで貪欲に読み込むため、後続のフッターや CRC が読めなくなる。`LengthOf` なら読み込みバイト数が自動制限され、後続フィールドも正しく復元される。 |
| **可変個数の子構造体リスト** | `CountOf[UInt16, "items"]` + `items: Array[ItemCls]` | 手動で `len(items)` を計算してヘッダーに詰める | シリアライズ時に要素数が自動計算され、デシリアライズ時にも指定個数分だけ正確に復元される。 |
| **ファイルシグネチャ・パケット開始識別子** | `magic: Magic[b"PKT\x01"]` または `Magic[0x12345678]` | `magic: Bytes[4]` に初期値を与えて自前で `if` 比較 | コンストラクタ引数から除外され（引数不要）、`from_bytes` 時に自動検証されて不整合なら即座に `InvalidMagicError` が送出される。 |
| **プロトコルバージョン等の固定定数** | `version: Constant[UInt8, 1]` | `version: UInt8 = 1` | 固定値として強制され、読み込み時にバージョン違いを `InvalidConstantError` として厳格に検知。 |
| **エラー検知・完全性検証 (CRC/チェックサム)** | `checksum: CRC32` または `CRC16`, `Adler32` | 自前で `zlib.crc32` を呼んで手動バックパッチ | シリアライズ時に直前バイトまでを自動計算して書き込み、デシリアライズ時に自動検証（不一致で `ChecksumMismatchError`）。 |
| **固定長フレーム（通信規格・セクタサイズ合わせ）** | `@binary_struct(total_size=512, pad_byte=b"\x00")` | 自前で `b"\x00" * (512 - len(data))` を末尾追加 | サイズ不足を自動パディング。万が一フィールド合計が 512B を超えた場合は `TotalSizeExceededError` で即検知。多言語出力時もパディング配列が自動生成される。 |
| **構造体先頭相対のポインタ・データ参照** | `offset: Offset[TargetCls, UInt32, Base.SELF]` | 手続き的にオフセットを手動計算して書き込む | シリアライズ時に対象構造体を末尾に配置しオフセットを自動バックパッチ。デシリアライズ時に対象クラスを自動インスタンス化。 |
| **離れた場所への遅延バックパッチ** | `NamedOffset["target_key"]` + `writer.write_named_offset(...)` | グローバル変数や `seek()` の手動計算 | 文字列キーで直感的に遅延解決。同一キーの多重登録で複数箇所の一括バックパッチも可能。 |
| **反復ブロック内でのキー衝突防止** | `with writer.namespace("block", auto_id=True):` | キー名を手動で `"block_0_payload"` のように結合 | コンテキストマネージャでスコープ化され、構造体定義を変更せずにキー衝突を完全に回避。 |
| **種別タグに応じた構造体の切り替え** | `Variant["tag_field", {1: ClsA, 2: ClsB}]` | パケットごとに `if type == 1:` と分岐パーサーを手書き | 宣言的なタグ付き共用体。`Variant` より前に必ず `tag_field` を宣言する。 |
| **状態・コマンドなどの限定値** | `state: MyEnum[UInt8]` (subclass of `BinaryEnum`) | 生の `UInt8` で定義して自前バリデーション | Python の `Enum` オブジェクトとして直接読み書きされ、未定義値は `InvalidEnumError` で弾かれる。 |
| **センサー値や範囲制限のある数値** | `temp: Range[Int16, -40, 125]` | 読み込み後に自前で `if not (-40 <= temp <= 125):` | 宣言的な境界検証（違反時は `RangeValidationError`）。仕様書や多言語コード（C/Rust等）にも範囲コメントが反映される。 |
| **大容量ファイル・連続ログの解析** | `BinaryReader.from_mmap(path)` + `reader.iter_struct(Cls)` | ファイル全体を `read()` してメモリに載せる | OS のメモリマッピングを活用し、メモリ消費ほぼゼロ・高速ゼロコピーで構造体を 1 件ずつストリーミング復元。 |
| **ビット単位のフラグ・制御レジスタ** | `@binary_struct(bits=16)` + `Bits[N]` | ビットシフト演算（`<<`, `>>`, `&`, `|`）を自前で実装 | ビット幅の合計チェックと型安全なパッキング・アンパッキングを自動化。通常構造体へのネストも可能。 |
| **仕様書・多言語コードのエクスポート** | `Cls.write_html("spec.html")` / `Cls.to_code("rust")` | `Builder` や `BinaryWriter` を手動インスタンス化 | 構造体クラスから直接ワンライナーで出力可能。 |

### 10.2 Do's and Don'ts for LLMs (AIが守るべきコーディング規約)

#### ✅ DO (推奨される書き方)
1. **可変長フィールドの前には `LengthOf` または `CountOf` を置く**:
   可変長バイト列なら `LengthOf[UInt16, "payload"]` + `payload: Bytes`、可変長配列なら `CountOf[UInt16, "items"]` + `items: Array[Item]` を使用する。
2. **`Magic` / `Constant` / `CRC*` は引数なしでインスタンス化する**:
   `pkt = Packet(data=b"...")` のように、自動計算されるフィールドは `__init__` 引数に渡さない。
3. **`Variant` のタグフィールドは必ず手前に宣言する**:
   タグフィールドは `Variant` よりも先にクラス定義内に現れなければならない。
4. **大容量データの読み込みには `from_mmap` + `iter_struct` を推奨する**:
   ギガバイト級のバイナリや通信ログを解析するコードでは、常にメモリ効率の良いストリーミングコードを生成する。
5. **多言語コードや仕様書の出力にはクラス直接メソッドを使う**:
   `Cls.to_c()`, `Cls.to_rust()`, `Cls.write_html("spec.html")` を使用する。

#### ❌ DON'T (避けるべきアンチパターン)
1. **`Array[T]` を構造体の途中や先頭に置かない**:
   `Array[T]` は EOF まで貪欲に読み込むため、後ろにフィールドがあるとデシリアライズ時に `EOFError` が発生する。途中に置く場合は必ず `CountOf` または `FixedArray` を使う。
2. **自前でチェックサムや長さを計算して手動代入しない**:
   `len(payload)` や `zlib.crc32(...)` を手動で計算して構造体に代入するコードは生成しない。`LengthOf` や `CRC32` を使えばライブラリが完全に自動処理する。
3. **ビットフィールドクラスに通常プリミティブ（`UInt16` 等）を混在させない**:
   `@binary_struct(bits=N)` で修飾されたクラス内には `Bits[K]` のみを定義し、全ビット幅の合計を `N` と完全に一致させる。
4. **廃止された API を呼ばない**:
   `write_manual`（廃止）は使用せず、`write_markdown` または `write_html` を使用する。

---

## 11. "How-To" Practical Recipes & Production Patterns ("こういうときはこうする！実践事例集")

AIが実際のプロジェクトで即座に活用できる、本番水準の実践レシピ集。

### Recipe 1: 通信パケット（Magic + LengthOf + Range + CRC32 + Footer）
**【課題】**  
可変長データを含むセンサーパケットで、ヘッダーの開始シグネチャ、温度などの値域チェック、データ長、フッター、そしてデータ破損を検知する CRC32 を安全に実装したい。

```python
from binary_master import (
    binary_struct, Magic, Range, LengthOf, Bytes, CRC32,
    UInt16, Int16, UInt8, ChecksumMismatchError
)

@binary_struct(endian="big")
class TelemetryFrame:
    """センサー通信フレーム（自動検証・CRC32自動計算付き）"""
    magic: Magic[b"TLM\x01"]                       # 4B シグネチャ（自動付与・検証）
    device_id: UInt16                             # 2B 端末ID
    temp_celsius: Range[Int16, -40, 85]           # 2B 動作保証温度 (-40℃ 〜 85℃)
    status_flags: Range[UInt8, 0, 15]             # 1B ステータスコード
    payload_len: LengthOf[UInt16, "payload"]      # 2B ペイロード長（自動計算 & デシリアライズ制限）
    payload: Bytes                                # 可変長ペイロード
    footer: Magic[0xAA55]                         # 2B 終端識別子
    checksum: CRC32                               # 4B 先頭〜フッターまでの CRC32 自動計算 & 検証

# 1. 送信側（シリアライズ）: magic, payload_len, footer, checksum は完全自動！
tx_frame = TelemetryFrame(
    device_id=1001,
    temp_celsius=25,
    status_flags=1,
    payload=b"PRESSURE=1013hPa;HUMIDITY=45%"
)
data = tx_frame.to_bytes()  # payload_len や checksum が自動計算されてバイナリ化

# 2. 受信側（デシリアライズ）: 整合性が自動検証される
rx_frame = TelemetryFrame.from_bytes(data)
assert rx_frame.device_id == 1001
assert rx_frame.temp_celsius == 25
assert rx_frame.payload == b"PRESSURE=1013hPa;HUMIDITY=45%"

# 3. 破損データの自動検知（1バイト改ざん）
corrupted_data = bytearray(data)
corrupted_data[8] ^= 0xFF  # 温度フィールドを破壊
try:
    TelemetryFrame.from_bytes(bytes(corrupted_data))
except ChecksumMismatchError as e:
    print(f"破損データを正しく検知: {e}")
```

### Recipe 2: アーカイブ/コンテナ形式（CountOf + OffsetTable + 構造体）
**【課題】**  
ファイル先頭に目次（ファイル数とオフセット配列）があり、後方に各ファイル実体が配置されるアーカイブコンテナを構築・復元したい。

```python
from binary_master import (
    binary_struct, Magic, CountOf, FixedString, UInt32, UInt16,
    Offset, OffsetTable, Base
)

@binary_struct
class FileContent:
    """実ファイルデータブロック"""
    content_id: UInt32
    data_size: UInt32
    data: FixedString[16]

@binary_struct
class ArchiveContainer:
    """先頭にメタデータとオフセット配列を持つコンテナ"""
    magic: Magic[b"ARCH"]
    # 子エントリの数を自動算出
    num_files: UInt16
    # 構造体先頭（Base.SELF）からのオフセット配列
    file_offsets: OffsetTable[2, UInt32, Base.SELF]
    # 直後のファイル参照（Offset を使って自動バックパッチ）
    primary_file: Offset[FileContent, UInt32, Base.SELF]

f1 = FileContent(content_id=1, data_size=16, data="FILE_DATA_ALPHA_")
f2 = FileContent(content_id=2, data_size=16, data="FILE_DATA_BETA__")

# 書き込み: Offset / OffsetTable にオブジェクトを渡すだけで自動配置 & アドレス計算
container = ArchiveContainer(
    num_files=2,
    file_offsets=[f1, f2],
    primary_file=f1
)
archive_bytes = container.to_bytes()

# 読み込み: ポインタ参照先が自動的に FileContent インスタンスとして復元される
restored = ArchiveContainer.from_bytes(archive_bytes)
assert restored.primary_file.content_id == 1
assert restored.primary_file.data == "FILE_DATA_ALPHA_"
```

### Recipe 3: 階層化名前空間と同一オフセットの多重参照（NamedOffset + namespace）
**【課題】**  
複雑なフォーマットやループ処理で複数のチャンクを書き出す際、キー名の衝突を防ぎ、さらに「同じオフセット位置を複数のポインタから参照」させたい。

```python
from binary_master import BinaryWriter, NamedOffset, binary_struct, UInt16

@binary_struct
class BlockHeader:
    block_id: UInt16
    # 同一のキー "body" を2つのポインタが参照（同一キーの多重登録）
    primary_body_offset: NamedOffset["body"]
    mirror_body_offset: NamedOffset["body"]

writer = BinaryWriter(default_endian="little")

# ループ内で同じキー名 "body" を使っても、namespace スコープで衝突しない！
for i in range(3):
    # auto_id=True により "block_0", "block_1", "block_2" が自動生成される
    with writer.namespace("block", auto_id=True):
        writer.write_struct(BlockHeader(block_id=i))
        writer.write_string(f"Metadata padding for block {i}...")
        
        # 1回の write_named_offset で primary と mirror の両方が一括バックパッチされる！
        writer.write_named_offset("body")
        writer.write_string(f"Actual Body Content {i}")

final_bytes = writer.to_bytes()
```

### Recipe 4: コマンドIDによる多態メッセージディスパッチ（Variant / Tagged Union）
**【課題】**  
単一の通信コネクション上で、メッセージ種別IDに応じて異なる構造体（Ping, LoginRequest, ChatMessage 等）を透過的に送受信したい。

```python
from binary_master import binary_struct, UInt8, UInt16, UInt32, FixedString, Variant

# 各種別ごとのペイロード構造体
@binary_struct
class PingPayload:
    sequence: UInt32

@binary_struct
class LoginRequest:
    user_id: UInt16
    username: FixedString[12]

@binary_struct
class ChatMessage:
    channel: UInt8
    text: FixedString[32]

# 外側のエンベロープ構造体
@binary_struct
class MessageEnvelope:
    # ⚠️ 重要: タグフィールドは必ず Variant より前に宣言する！
    msg_type: UInt8
    payload: Variant["msg_type", {
        0x01: PingPayload,
        0x02: LoginRequest,
        0x03: ChatMessage,
    }]

# 1. 送信: メッセージ種別に応じたインスタンスをそのまま渡す
msg = MessageEnvelope(msg_type=0x02, payload=LoginRequest(user_id=42, username="Alice"))
data = msg.to_bytes()

# 2. 受信: msg_type の値に基づいて自動的に LoginRequest としてデシリアライズされる
restored = MessageEnvelope.from_bytes(data)
assert restored.msg_type == 0x02
assert isinstance(restored.payload, LoginRequest)
assert restored.payload.user_id == 42
assert restored.payload.username.strip() == "Alice"
```

### Recipe 5: 大容量バイナリのメモリマップド・ゼロコピー走査（mmap + iter_struct + peek）
**【課題】**  
GB単位の巨大なログファイルやキャプチャファイルから、メモリを枯渇させることなく、高速にレコードを 1 件ずつ走査・抽出したい。

```python
from binary_master import binary_struct, BinaryReader, UInt32, Float32, FixedString

@binary_struct
class LogRecord:
    timestamp: UInt32
    metric_value: Float32
    tag: FixedString[8]

def scan_large_log(file_path: str, target_tag: str):
    """OS メモリマップを活用してメモリ消費ほぼゼロで走査"""
    with BinaryReader.from_mmap(file_path) as reader:
        # 先読みでシグネチャを検査（カーソルは進まない）
        if reader.peek(4) != b"LOG\x00":
            # 先頭にヘッダーがある場合はスキップ等の処理が可能
            reader.skip(4)
            
        # iter_struct で EOF まで 1 レコードずつ省メモリに逐次デシリアライズ
        for record in reader.iter_struct(LogRecord):
            if record.tag.strip() == target_tag:
                yield record

# 使用例:
# for match in scan_large_log("huge_production.log", "ERROR_1"):
#     print(match.timestamp, match.metric_value)
```

### Recipe 6: ビットフィールドによるハードウェアレジスタ・制御フラグ（Bits + @binary_struct(bits=N)）
**【課題】**  
組込み通信や制御レジスタの 16bit / 32bit のビットフラグを、シフト演算やマスク演算を手書きせず型安全に定義・埋め込みたい。

```python
from binary_master import binary_struct, Bits, UInt8, UInt16

# 1. 16bit のレジスタフラグ（Bits の合計幅が 16 になること）
@binary_struct(bits=16)
class ControlRegister:
    rx_enable: Bits[1]     # bit 0: 受信有効
    tx_enable: Bits[1]     # bit 1: 送信有効
    mode: Bits[3]          # bit 2-4: 動作モード (0-7)
    channel: Bits[4]       # bit 5-8: 通信チャネル (0-15)
    reserved: Bits[7]      # bit 9-15: 予約領域 (計 1 + 1 + 3 + 4 + 7 = 16 bits)

# 2. 通常の構造体にビットフィールドを自然に埋め込む
@binary_struct
class DeviceCommand:
    command_id: UInt8
    ctrl: ControlRegister
    param: UInt16

# 直感的なフィールド操作
cmd = DeviceCommand(
    command_id=0x10,
    ctrl=ControlRegister(rx_enable=1, tx_enable=1, mode=2, channel=5, reserved=0),
    param=1200
)
raw_bytes = cmd.to_bytes()

# 復元時も各ビットフィールドに直接アクセス可能
restored = DeviceCommand.from_bytes(raw_bytes)
assert restored.ctrl.rx_enable == 1
assert restored.ctrl.mode == 2
assert restored.ctrl.channel == 5
```

### Recipe 7: 単一定義からの多言語コード生成 & インタラクティブ仕様書出力ワークフロー
**【課題】**  
Python で定義したバイナリ仕様から、組み込み C ヘッダー、Rust 構造体、およびブラウザで検証できる HTML 仕様書をワンライナーで出力したい。

```python
from binary_master import binary_struct, Magic, UInt16, Float32, CString, CRC32

@binary_struct(endian="little")
class SensorReport:
    """IoT エッジデバイスからの定期センサー報告パケット"""
    magic: Magic[b"SENS"]
    node_id: UInt16
    temp: Float32
    location_name: CString
    checksum: CRC32

# 1. ブラウザで開けるインタラクティブ HTML 仕様書（Hex Inspector付き）
SensorReport.write_html("sensor_spec.html", title="IoT センサーパケット仕様書")

# 2. 組込み C 言語用ヘッダーファイルの自動生成
c_code = SensorReport.to_c()
# SensorReport.write_c("sensor_packet.h") で直接ファイル保存も可能

# 3. Rust 構造体 & ゼロコピー実装コードの自動生成
rust_code = SensorReport.to_rust()
# SensorReport.write_code("sensor_packet.rs") で保存可能（言語は拡張子から自動推論）
```

### Recipe 8: TLV (Type-Length-Value) 形式の可変長ストリーム
**【課題】**  
Bluetooth LE、暗号通信、拡張ヘッダー等で頻出する「種別タグ・データ長・可変長バイト列」の TLV 要素を安全に構築・走査したい。

**【ポイント】**  
- `length` フィールドを `LengthOf[UInt16, "value"]` として宣言することで、書き込み時の長さ計算と、読み込み時のバッファ切り出しが完全自動化される。
- `read_struct` や `BinaryReader` と組み合わせることで、任意の数の TLV レコードを順次パース可能。

```python
from binary_master import binary_struct, UInt8, UInt16, LengthOf, Bytes, BinaryReader, BinaryWriter

@binary_struct
class TLVRecord:
    tag: UInt8
    length: LengthOf[UInt16, "value"]
    value: Bytes

# 1. 複数の TLV レコードを書き込み
writer = BinaryWriter()
writer.write_struct(TLVRecord(tag=0x01, value=b"DeviceName"))
writer.write_struct(TLVRecord(tag=0x02, value=b"\x12\x34\x56\x78"))
stream_bytes = writer.to_bytes()

# 2. ストリームから順次読み出し
reader = BinaryReader(stream_bytes)
records = []
while not reader.is_eof:
    record = reader.read_struct(TLVRecord)
    records.append(record)

assert records[0].tag == 0x01
assert records[0].value == b"DeviceName"
assert records[1].tag == 0x02
assert records[1].value == b"\x12\x34\x56\x78"
```

### Recipe 9: 階層化ネスト構造体（ネットワークパケット: Ethernet + IPv4 + ペイロード）
**【課題】**  
Ethernet フレームの中に IPv4 ヘッダーがあり、その中にペイロードがあるような、階層的なプロトコルスタックを型安全にモデル化したい。

**【ポイント】**  
- `@binary_struct` を修飾したクラスは、他の `@binary_struct` のフィールド型としてそのまま使用できる。
- エンディアン（`endian="big"`）は外側の構造体および内側のネスト構造体で一貫して適用される。

```python
from binary_master import binary_struct, UInt8, UInt16, FixedArray, LengthOf, Bytes

@binary_struct(endian="big")
class MacHeader:
    dst_mac: FixedArray[UInt8, 6]
    src_mac: FixedArray[UInt8, 6]
    ethertype: UInt16  # 0x0800 = IPv4

@binary_struct(endian="big")
class Ipv4Header:
    version_ihl: UInt8
    tos: UInt8
    total_len: UInt16
    packet_id: UInt16
    flags_frag: UInt16
    ttl: UInt8
    protocol: UInt8    # 6 = TCP, 17 = UDP
    checksum: UInt16
    src_ip: FixedArray[UInt8, 4]
    dst_ip: FixedArray[UInt8, 4]

@binary_struct(endian="big")
class PacketFrame:
    mac: MacHeader
    ip: Ipv4Header
    payload_len: LengthOf[UInt16, "payload"]
    payload: Bytes

frame = PacketFrame(
    mac=MacHeader(dst_mac=b"\xFF"*6, src_mac=b"\x00\x11\x22\x33\x44\x55", ethertype=0x0800),
    ip=Ipv4Header(
        version_ihl=0x45, tos=0, total_len=40, packet_id=1, flags_frag=0,
        ttl=64, protocol=6, checksum=0, src_ip=b"\xC0\xA8\x00\x01", dst_ip=b"\xC0\xA8\x00\x02"
    ),
    payload=b"TCP_PAYLOAD_DATA"
)
raw = frame.to_bytes()

# 復元後、ネストしたメンバーへ直感的にアクセス可能
restored = PacketFrame.from_bytes(raw)
assert restored.mac.ethertype == 0x0800
assert bytes(restored.ip.src_ip) == b"\xC0\xA8\x00\x01"
assert restored.payload == b"TCP_PAYLOAD_DATA"
```

### Recipe 10: 文字列プール（String Table / String Pool）形式の構築
**【課題】**  
ゲームのアセットファイルやコンパイル済みバイナリで一般的な、ヘッダー部に文字列へのオフセット一覧を持ち、ファイル末尾に可変長文字列（Null終端等）を集約配置する形式を作りたい。

**【ポイント】**  
- `writer.write_offset_table(count, offset_size)` でヘッダー内にオフセット領域を予約。
- 文字列実体を書き込む際に `table.write_target(index, string_bytes)` を呼ぶと、予約位置へ正確なオフセットが自動バックパッチされる。

```python
from binary_master import BinaryWriter

writer = BinaryWriter(default_endian="little")

# 1. ヘッダー情報の書き込み
writer.write_uint32(0x53545247, name="magic")  # 'STRG'
names = ["HeroCharacter", "FireSword", "HealthPotion"]
writer.write_uint16(len(names), name="string_count")

# 2. オフセットテーブルの予約（3件分の4バイトオフセット）
table = writer.write_offset_table(count=len(names), offset_size=4, name="offsets")

# 3. ファイル末尾の文字列プールに書き込み & オフセット解決
for idx, name in enumerate(names):
    # write_target で現在の書き込み位置が table[idx] に自動バックパッチされる
    table.write_target(idx, name.encode("utf-8") + b"\x00")

binary_data = writer.to_bytes()
```

### Recipe 11: 固定セクタ長パディング & JSON 相互変換（ゲームセーブデータ / ステータス連携）
**【課題】**  
ゲームセーブスロットなどの固定長（例: 256バイト）セクタ領域にデータを保存し、かつ Web API やデバッグ用に JSON 形式とも相互変換したい。

**【ポイント】**  
- `@binary_struct(total_size=256, pad_byte=b"\x00")` で固定セクタ長を保証。データが短ければ自動パディング、超過すれば `TotalSizeExceededError`。
- `instance.to_dict()` / `to_json()` および `Cls.from_dict()` / `from_json()` で完全な双方向シリアライズが可能。

```python
from binary_master import binary_struct, Magic, Range, UInt8, UInt16, UInt32, FixedString

@binary_struct(total_size=256, pad_byte=b"\x00")
class SaveSlot:
    magic: Magic[b"SAVE"]
    slot_id: UInt8
    level: Range[UInt16, 1, 99]
    hp: UInt32
    gold: UInt32
    player_name: FixedString[16]

# 1. データの作成とバイナリ化（自動でちょうど256バイトになる）
save = SaveSlot(slot_id=1, level=45, hp=4500, gold=99999, player_name="Warrior")
binary_data = save.to_bytes()
assert len(binary_data) == 256

# 2. Web API 連携用の JSON 変換
json_string = save.to_json(indent=2)
# {
#   "magic": "0x53415645",
#   "slot_id": 1,
#   "level": 45,
#   "hp": 4500,
#   "gold": 99999,
#   "player_name": "Warrior"
# }

# 3. JSON からの構造体インスタンス復元
restored_from_json = SaveSlot.from_json(json_string)
assert restored_from_json.hp == 4500
assert restored_from_json.to_bytes() == binary_data
```

### Recipe 12: 任意ビット幅ストリームの直列パッキング（BitWriter / BitReader）
**【課題】**  
音声・映像コーデック、圧縮アルゴリズム、または超高密度パケットで、バイト境界に揃わない任意ビット数（3bit, 5bit, 12bit 等）を連続して詰め込み・復元したい。

**【ポイント】**  
- `BitWriter(msb_first=True)` でバイト境界を気にせず `write_bits(val, count)` を呼び出し、最後に `flush_bits()` でバイト境界に切り上げる。
- `BitReader` で指定ビット数ずつ順次取り出し。

```python
from binary_master import BitWriter, BitReader

# 1. ビットストリームの書き込み
bw = BitWriter(msb_first=True)
bw.write_bits(0b101, 3)     # 3 bits
bw.write_bits(0b11001, 5)   # 5 bits (合計 8 bits = 1 byte 完了)
bw.write_bits(0b1010, 4)    # 4 bits
bw.write_bits(0b01, 2)      # 2 bits
bw.flush_bits(pad_bit=0)    # 残り 2 bits を 0 で埋めてバイトアライメント
stream = bw.to_bytes()
assert len(stream) == 2

# 2. ビットストリームの読み込み
br = BitReader(stream, msb_first=True)
assert br.read_bits(3) == 0b101
assert br.read_bits(5) == 0b11001
assert br.read_bits(4) == 0b1010
assert br.read_bits(2) == 0b01
```

### Recipe 13: スキーマ先行プロトコル設計（Builder）による条件分岐フローチャート生成
**【課題】**  
バイナリ実データを書き出す前のプロトコル設計段階で、条件分岐や多態バリアントを含めた仕様書（Markdown + Mermaid）や多言語ヘッダーを出力したい。

**【ポイント】**  
- `Builder` を使用し、構造体登録、説明文、条件分岐ノード（`condition`）を宣言的に構築。
- `builder.write("protocol_spec.md")` で Mermaid フローチャート付き仕様書をワンライナー生成。

```python
from binary_master import Builder, UInt16, UInt32, FixedString, binary_struct

@binary_struct
class Header:
    magic: UInt32
    version: UInt16

@binary_struct
class AuthRequest:
    token: FixedString[32]

@binary_struct
class DataRequest:
    query_id: UInt32

# スキーマファーストでプロトコル仕様を定義
builder = Builder(title="クライアント・サーバー間プロトコル仕様書")
builder.add_struct(Header, desc="共通通信ヘッダー")

# 仕様書に条件分岐ノードを追加
builder.condition(
    "version == 1",
    then_fn=lambda b: b.add_struct(AuthRequest, desc="認証リクエスト（v1）"),
    else_fn=lambda b: b.add_struct(DataRequest, desc="データ問い合わせリクエスト（v2）"),
)

# Markdown 仕様書（Mermaid フローチャート付き）および C ヘッダーを出力
builder.write("protocol_spec.md")
builder.write_c("protocol_types.h")
```

---

## 12. Advanced Features Reference (LLM Quick Reference)

### 12.1 CRC & Checksum Declarative Types
- **Types**: `CRC32` (4B, IEEE 802.3), `CRC16` / `CRC16_CCITT` (2B, poly 0x1021), `CRC16_ARC` (2B, poly 0xA001), `Checksum8` (1B, sum mod 256), `Checksum16` (2B, sum mod 65536), `Fletcher16` (2B), `Adler32` (4B).
- **Slice Range**: By default, covers `0` to the field position. Custom slice: `CRC32[4:20]`.
- **Automatic Behavior**:
  - `to_bytes()` calculates checksum over preceding bytes and packs it into the stream.
  - `from_bytes()` reads checksum and verifies against calculated value.
  - On mismatch, raises `ChecksumMismatchError(expected=..., actual=...)`.
- **Procedural**: `with writer.checksum("crc32"): ...`, `writer.write_checksum("crc32")`, `reader.verify_checksum("crc32")`.

### 12.2 Enums (`BinaryEnum` & `IntEnum`)
- **Base Class**: Subclass `BinaryEnum` (subclasses `enum.IntEnum`).
- **Explicit Sizing**: `MyEnum[UInt8]`, `MyEnum[UInt16]`, `MyEnum[UInt32]`, `MyEnum[UInt64]`.
- **Automatic Sizing**: Bare `MyEnum` or standard `enum.IntEnum` auto-selects 1 byte (<=255), 2 bytes (<=65535), or 4 bytes.
- **Deserialization**: `from_bytes` instantiates the Python `Enum` member directly.
- **Validation**: If stream integer is not in enum, raises `InvalidEnumError(enum_cls, raw_val)`.

### 12.3 Magic Numbers & Constant Constraints
- **Magic**: `Magic[b"PNG\r\n\x1a\n"]` or `Magic[0x12345678]`.
- **Constant**: `Constant[UInt16, 20]`.
- **Zero-Boilerplate Instantiation**: Fields typed as `Magic` or `Constant` do not require arguments in `__init__`.
- **Validation on Read**: `from_bytes` verifies against expected value, raising `InvalidMagicError` or `InvalidConstantError`.

### 12.4 JSON / Dict Interop
- `instance.to_dict(bytes_format="hex"|"base64"|"list")` -> `dict`
- `Cls.from_dict(d)` -> `Cls`
- `instance.to_json(indent=None, bytes_format="hex"|"base64"|"list")` -> `str`
- `Cls.from_json(json_str)` -> `Cls`
- Hex format prefixes `"0x..."`. `from_dict` automatically parses both `"0x..."` and raw hex strings.

### 12.5 Large File Streaming & Memory-Mapped Zero-Copy
- `reader.iter_struct(Cls)`: Generator yielding instances of `Cls` until EOF.
- `BinaryReader.from_mmap(path, default_endian="little")`: Context manager utilizing OS memory-mapping (`mmap`) for zero-copy slice reads without loading whole files into memory.

### 12.6 Variable-Length Integers (LEB128)
- **Types**: `VarUInt`, `VarInt`, `VarUInt32`, `VarInt32`, `VarUInt64`, `VarInt64`.
- **Procedural Writer**: `writer.write_varuint(val)`, `writer.write_varint(val)`.
- **Procedural Reader**: `reader.read_varuint()`, `reader.read_varint()`.
- **Declarative Struct**: Can be used as field types in `@binary_struct`.

### 12.7 Arbitrary Bitstream Manipulation
- `BitWriter(stream=None, msb_first=True)`: `write_bits(value, bit_count)`, `flush_bits(pad_bit=0)`, `to_bytes()`.
- `BitReader(data_or_stream, msb_first=True)`: `read_bits(bit_count)`, `peek_bits(bit_count)`, `align_to_byte()`.
- `writer.write_bits(val, count)` & `reader.read_bits(count)`: Integrated directly into `BinaryWriter` and `BinaryReader`. Non-bit write methods automatically flush unaligned bits.

### 12.8 CLI Binary Inspector
`pyproject.toml` script entry point: `binary-master`.
- `binary-master inspect <file>`: Formatted, annotated Hexdump.
- `binary-master diff <file1> <file2>`: Visual byte diff.
- `binary-master spec <module:Class> [-o output.md]`: Markdown protocol manual generation.
- `binary-master export <module:Class> --lang <rust|c|cpp|csharp|go> [-o output]`: Multi-language code generation (pass `-o -` for stdout).

### 12.9 Direct Struct Export & Descriptors
`@binary_struct` classes and instances support direct specification and multi-language code export without instantiating `Builder` or `BinaryWriter`:
- `Cls.to_markdown(title=None, **kwargs) -> str` / `inst.to_markdown(include_values=True, **kwargs) -> str`
- `Cls.write_markdown(path, **kwargs) -> str` / `inst.write_markdown(path, **kwargs) -> str`
- `Cls.to_html(title=None, **kwargs) -> str` / `inst.to_html(**kwargs) -> str`
- `Cls.write_html(path, **kwargs) -> str` / `inst.write_html(path, **kwargs) -> str`
- `Cls.to_code(lang="rust"|"c"|"cpp"|"csharp"|"go", **kwargs) -> str` / `inst.to_code(lang, **kwargs) -> str`
- `Cls.write_code(path, lang=None, **kwargs) -> str` / `inst.write_code(path, **kwargs) -> str` (infers language from file extension if `lang` is omitted)
- Individual language shortcuts: `Cls.to_c()`, `Cls.to_rust()`, `Cls.to_cpp()`, `Cls.to_csharp()`, `Cls.to_go()`.

### 12.10 LengthOf & CountOf (Automatic Calculation & Bound Deserialization)
- **Declarative Syntax**: `LengthOf[Type, "target_field", delta=0]` and `CountOf[Type, "target_field", delta=0]`. (Also accepts `["target_field", Type]`).
- **Serialization**: When writing, if the field value is `0` or omitted, it is automatically computed from the target field's byte length (`LengthOf`) or item count (`CountOf`).
- **Deserialization**: When reading, `LengthOf` and `CountOf` values dynamically bind the number of bytes read by downstream `Bytes` / `Array[T]`, eliminating greedy buffer overconsumption.
```python
@binary_struct
class Packet:
    payload_len: LengthOf[UInt16, "payload"]
    payload: Bytes
    footer: UInt8

p = Packet(payload=b"hello", footer=0xFF)
data = p.to_bytes()  # payload_len auto-computed as 5!
recovered = Packet.from_bytes(data)
assert recovered.payload == b"hello"
assert recovered.footer == 0xFF
```

### 12.11 Value Range Validation (`Range[Type, min, max]`)
- **Declarative Syntax**: `Range[Type, min_val, max_val]`. Supports integer and floating-point types (`UInt8`, `Int32`, `Float32`, etc.).
- **Validation**:
  - `to_bytes()` / `write_struct`: Validates that `min <= val <= max`. Raises `RangeValidationError(field_name, value, min, max)` if violated.
  - `from_bytes()` / `read_struct`: Validates read value against `[min, max]`, raising `RangeValidationError` on invalid data.
- **Multi-Language Export**: Emitted in C, C++, Rust, C#, and Go with inline comment `/**< Range: [min, max] */`.
```python
@binary_struct
class SensorPacket:
    temp: Range[Int16, -40, 125]
    humidity: Range[UInt8, 0, 100]
```

### 12.12 Struct Fixed Size & Writer Padding (`total_size`, `pad_to`)
- **Struct-Level Total Size**: `@binary_struct(total_size=64, pad_byte=b"\x00")`.
  - Serializes fields and automatically appends `pad_byte` until the struct reaches `total_size` bytes.
  - If field data exceeds `total_size`, raises `TotalSizeExceededError`.
  - `sizeof(Struct)` returns `total_size`.
  - Multi-language export automatically emits a padding buffer field (e.g. `uint8_t _padding[N]`).
- **Procedural Pad To**: `writer.pad_to(target_offset, pad_byte=b"\x00")`.
  - Pads stream with `pad_byte` until `writer.tell() == target_offset`.
  - Raises `ValueError` if current stream offset is already past `target_offset`.

### 12.13 Interactive Standalone HTML Documentation (`to_html()`, `write_html()`)
- **Single-File Output**: Generates self-contained HTML specification manuals with responsive CSS, light/dark theme toggle, embedded Mermaid diagrams, and bitfield tables.
- **Interactive Hex Inspector**:
  - Displays a 16-byte side-by-side hex dump and ASCII preview.
  - Bidirectional hover inspection: Hovering any row in the specification table highlights its exact byte range in the hex dump. Hovering any hex byte highlights the corresponding field in the table and updates a floating inspection bar.
- **API Availability**:
  - `Cls.to_html(title=None, **kwargs) -> str` / `Cls.write_html(path, **kwargs) -> str`
  - `instance.to_html(**kwargs) -> str` / `instance.write_html(path, **kwargs) -> str`
  - `writer.to_html(**kwargs) -> str` / `writer.write_html(path, **kwargs) -> str`
  - `builder.to_html(**kwargs) -> str` / `builder.write_html(path, **kwargs) -> str`
  - `generate_html(entries, sample_data=None, **kwargs) -> str` / `write_html(entries, path, **kwargs) -> str`

### 12.14 Specification Diagrams & Manual Generation Options
- **`diagram_type`**: `"both"` (default), `"flowchart"`, `"packet"`, `"none"`.
  - When `diagram_type="both"`: If multiple structures or sections exist, the top overview renders a clean `## 構造図` (`## Structure Diagram`) flowchart, and redundant overall packet diagrams are omitted from the top. Instead, per-struct detailed packet diagrams (`packet-beta`) are automatically rendered under each struct section (`### StructName`).
  - `full_packet_diagram=True`: Forces the overall packet diagram at the top even when multiple sections/structs exist. Default is `False`.
- **`large_data_threshold`** (default `64`): Summarizes large byte arrays or unallocated padding blocks in packet diagrams (e.g. `payload (10000B)` or `padding (128B)`).
- **`include_section_offsets`** (default `False`): Appends `(0xXXXX - 0xYYYY, ZZB)` byte ranges to section headings and flowchart subgraphs.
- **Offset Table & Repetition Aggregation**:
  - `OffsetTable[N, T]` is rendered as a single aggregated node in flowcharts and a single slice in packet diagrams, eliminating repetitive `...` noise.
  - Arrays and repeated structs are summarized as `StructName 🔁 xN (TotalBytes)`.



