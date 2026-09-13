
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
    read_struct,         # Procedural struct deserializer
    sizeof,              # Binary size in bytes (alias: binary_size)
    binary_size,         # Alias for sizeof
    offsetof,            # Byte offset of a field (supports dot notation)
    bit_offsetof,        # (byte_offset, bit_offset) tuple

    # Primitive Binary Types
    BinaryType,          # Base type for all primitives
    UInt8, UInt16, UInt32, UInt64,
    Int8,  Int16,  Int32,  Int64,
    Float32, Float64,

    # Generic & Advanced Type Annotations
    Bits,                # Bits[N]: Bitfield slice (used with @binary_struct(bits=N))
    Offset,              # Offset[Target, OffsetType=UInt32, BaseOffset=0]
    OffsetTable,         # OffsetTable[Count, OffsetType=UInt32, BaseOffset=0]
    Variant,             # Variant[tag_field_name, {tag_val: StructCls, ...}]
    Array,               # Array[T]: Dynamic length sequence
    FixedArray,          # FixedArray[T, N]: Static N-element array
    Base,                # Base.SELF, Base.STRUCT, Base.FIELD origin markers
    RelativeBase,        # Result of Base + delta arithmetic

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
| `bool` | 1 byte | `bool` | `0x00` = False, non-zero = True |
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

Use `Builder` when you want to define the overall protocol layout once, generate human-readable Markdown specifications with Mermaid diagrams, export headers for other languages, and perform schema-driven automated deserialization (`builder.read`).

### 4.1 Builder Methods Signature Table
| Method | Arguments | Description |
|---|---|---|
| `Builder(...)` | `title: str = "...", default_endian: str = "little", version: str = None, description: str = ""` | Initialize protocol schema |
| `add_document` | `title: str, content: str` | Add narrative chapter / overview text (Markdown) |
| `add_struct` | `struct_cls: type, name: str = None, desc: str = "", condition: str = None, condition_func: Callable = None, count: int\|str\|Callable = None` | Register sequential struct (supports conditions and repeated counts) |
| `add_choice` | `name: str, tag_field: str\|Callable, variants: dict\|list, desc: str = "", condition: str = None, condition_func: Callable = None` | Register polymorphic branch dispatched by `tag_field` |
| `add_field` | `name: str, type_name: str, size: int, desc: str = "", endian: str = None, condition: str = None` | Register ad-hoc primitive field without dedicated struct class |
| `section`, `caption` | `title: str, desc: str = ""` | Context manager to group elements: `with builder.section(...):` |
| `write` | `path_or_file: str\|Path\|IO, diagram_direction: str = "TD", ...` | Generate and save complete Markdown specification with Mermaid diagrams |
| `read` | `data: bytes\|bytearray\|Reader, trace: bool = False` | Automatically parse binary into a `BuilderReadResult` |
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

# Struct Integration
writer.write_struct(my_struct_instance)

# Captions (for Manual & Trace Table)
writer.caption("Body Section", "Payload contents")
writer.subcaption("Sub Section", "Details")

# Offset Tables with delayed patching
table_handle = writer.write_offset_table(count=2, offset_size=4, base_offset=0)
# Later...
table_handle.set_offset(0, target_offset=0x100) # manual offset
table_handle.write_target(1, child_struct)       # writes target at current pos & records offset

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

# Struct Integration
obj = reader.read_struct(MyStructClass)
```

---

## 6. Multi-Language Code Generation

Export schemas or individual structs across 5 languages:

| Target Language | Single Struct Method | Builder Method | File Extension |
|---|---|---|---|
| **C (C99 / C11)** | `Cls.to_c()` | `builder.write_c_header("p.h")` | `.h`, `.c` |
| **Rust (2021+)** | `Cls.to_rust()` | `builder.write_rust("p.rs")` | `.rs` |
| **Modern C++ (C++17/20)** | `Cls.to_cpp()` | `builder.write_cpp("p.hpp")` | `.hpp`, `.cpp` |
| **C# (.NET 8+)** | `Cls.to_csharp(namespace="...")` | `builder.write_csharp("p.cs")` | `.cs` |
| **Go (1.20+)** | `Cls.to_go(package_name="...")` | `builder.write_go("p.go")` | `.go` |

Unified caller: `write_code(builder, "output.rs")` auto-detects language from extension.

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

# Direct manual generation from writer entries:
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

### ⚠️ RULE 1: `write_manual` is REMOVED
- **DO NOT** call `writer.write_manual(...)` or `builder.write_manual(...)` or `binary_master.write_manual(...)`. They have been permanently removed.
- **DO** call `builder.write("path.md")` for schema specifications, or `generate_manual(writer.entries)` for procedural writer entries.

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
