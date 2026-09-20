from typing import (
    IO,
    Any,
    Optional,
    TypeVar,
    Union,
    dataclass_transform,
)

T = TypeVar("T")
T1 = TypeVar("T1")
T2 = TypeVar("T2")
T3 = TypeVar("T3")

# 1. Base Binary Types
class BinaryType:
    _fmt: str
    _size: int
    fmt: str
    size: int

# 2. Primitive types (Static checkers / IDEs see them as int / float / bool)
type UInt8 = int
type UInt16 = int
type UInt32 = int
type UInt64 = int
type u8 = int
type u16 = int
type u32 = int
type u64 = int
type Int8 = int
type Int16 = int
type Int32 = int
type Int64 = int
type i8 = int
type i16 = int
type i32 = int
type i64 = int
type s8 = int
type s16 = int
type s32 = int
type s64 = int
type Float16 = float
type Float32 = float
type Float64 = float
type f16 = float
type f32 = float
type f64 = float
type Bool = bool

# Dynamic types
type Bytes = bytes
type FixedString = str
type CString = str
type PrefixedString = str

# 3. Arrays & Offsets
type FixedArray[T, *Args] = bytes | list[T]
type Array[T] = list[T]
type Offset[Target, *Args] = Target | None
type OffsetTable[Count, *Args] = list[Any] | None
type Bits[Width] = int
type Variant[Tag, Mapping, *Args] = Any

# 4. Declarative Constraints and Annotations
type Magic[*Args] = Any
type Constant[T, *Args] = T
type Range[T, *Args] = T
type LengthOf[T, *Args] = T
type CountOf[T, *Args] = T
type Compressed[T, *Args] = T
type CompressedBytes[*Args] = bytes

class MagicBase:
    _value: Any
    _raw_val: Any
    _fmt: str

class ConstantBase:
    _type: Any
    _value: Any

class RangeBase:
    _type: Any
    _min: Any
    _max: Any

class LengthOfBase:
    _type: Any
    _target_field: str

class CountOfBase:
    _type: Any
    _target_field: str

class BinaryEnum: ...

# 5. Base Relative Origins
class Base:
    class SELF: ...
    STRUCT = SELF
    class FIELD: ...

class RelativeBase: ...

# 6. Decorator and Base Classes
class BinaryFlag: ...

@dataclass_transform()
def binary_struct[T](cls: T = ..., **kwargs: Any) -> T: ...

class BinaryStruct:
    def to_bytes(self, endian: Any = ...) -> bytes: ...
    @classmethod
    def from_bytes[T](cls: type[T], data: bytes, endian: Any = ...) -> T: ...
    def to_file(self, path_or_file: Union[str, Any, IO[bytes]], endian: Any = ...) -> int: ...
    @classmethod
    def from_file[T](cls: type[T], path_or_file: Union[str, Any, IO[bytes]], endian: Any = ...) -> T: ...
    @classmethod
    def from_stream[T](cls: type[T], stream: IO[bytes], endian: Any = ...) -> T: ...
    def to_dict(self) -> dict[str, Any]: ...
    def to_json(self, **kwargs: Any) -> str: ...
    def dump_table(self, **kwargs: Any) -> str: ...
    def hexdump(self, **kwargs: Any) -> str: ...
    @classmethod
    def to_markdown(cls, **kwargs: Any) -> str: ...
    @classmethod
    def write_markdown(cls, path_or_file: Union[str, Any, IO[str]], **kwargs: Any) -> str: ...
    @classmethod
    def to_html(cls, **kwargs: Any) -> str: ...
    @classmethod
    def write_html(cls, path_or_file: Union[str, Any, IO[str]], **kwargs: Any) -> str: ...
    @classmethod
    def to_code(cls, lang: str, **kwargs: Any) -> str: ...
    @classmethod
    def write_code(cls, path_or_file: Union[str, Any, IO[str]], lang: Optional[str] = ..., **kwargs: Any) -> str: ...
    @classmethod
    def to_c(cls, **kwargs: Any) -> str: ...
    @classmethod
    def write_c(cls, path_or_file: Union[str, Any, IO[str]], **kwargs: Any) -> str: ...
    @classmethod
    def to_rust(cls, **kwargs: Any) -> str: ...
    @classmethod
    def write_rust(cls, path_or_file: Union[str, Any, IO[str]], **kwargs: Any) -> str: ...
    @classmethod
    def to_cpp(cls, **kwargs: Any) -> str: ...
    @classmethod
    def write_cpp(cls, path_or_file: Union[str, Any, IO[str]], **kwargs: Any) -> str: ...
    @classmethod
    def to_csharp(cls, **kwargs: Any) -> str: ...
    @classmethod
    def write_csharp(cls, path_or_file: Union[str, Any, IO[str]], **kwargs: Any) -> str: ...
    @classmethod
    def to_go(cls, **kwargs: Any) -> str: ...
    @classmethod
    def write_go(cls, path_or_file: Union[str, Any, IO[str]], **kwargs: Any) -> str: ...
    @classmethod
    def to_wireshark(cls, **kwargs: Any) -> str: ...
    @classmethod
    def write_wireshark(cls, path_or_file: Union[str, Any, IO[str]], **kwargs: Any) -> str: ...
    @classmethod
    def to_hexpat(cls, **kwargs: Any) -> str: ...
    @classmethod
    def write_hexpat(cls, path_or_file: Union[str, Any, IO[str]], **kwargs: Any) -> str: ...
    @classmethod
    def view[T](cls: type[T], buffer: Any, offset: int = ..., endian: Any = ...) -> Any: ...
    @classmethod
    def view_from_bytes[T](cls: type[T], buffer: Any, offset: int = ..., endian: Any = ...) -> Any: ...
    @classmethod
    def view_from_file[T](cls: type[T], path: Any, offset: int = ..., endian: Any = ..., writable: bool = ...) -> Any: ...
    @classmethod
    def iter_packets[T](cls: type[T], source: Any, max_count: Optional[int] = ..., ignore_errors: bool = ..., endian: Any = ...) -> Any: ...
    @classmethod
    def iter_views[T](cls: type[T], source: Any, max_count: Optional[int] = ..., endian: Any = ...) -> Any: ...
    @classmethod
    def async_iter_packets[T](cls: type[T], source: Any, max_count: Optional[int] = ..., ignore_errors: bool = ..., endian: Any = ...) -> Any: ...
    @classmethod
    def dummy[T](cls: type[T], seed: Optional[int] = ..., **overrides: Any) -> T: ...
    async def to_async_stream(self, writer: Any, endian: Any = ..., drain: bool = ...) -> None: ...
    @classmethod
    async def from_async_stream[T](cls: type[T], reader: Any, endian: Any = ...) -> T: ...

def to_bytes(obj: Any, endian: Any = ...) -> bytes: ...
def from_bytes[T](cls: type[T], data: bytes, endian: Any = ...) -> T: ...
def to_file(obj: Any, path_or_file: Union[str, Any, IO[bytes]], endian: Any = ...) -> int: ...
def from_file[T](cls: type[T], path_or_file: Union[str, Any, IO[bytes]], endian: Any = ...) -> T: ...
def from_stream[T](cls: type[T], stream: IO[bytes], endian: Any = ...) -> T: ...
async def to_async_stream(obj: Any, writer: Any, endian: Any = ..., drain: bool = ...) -> None: ...
async def from_async_stream[T](cls: type[T], reader: Any, endian: Any = ...) -> T: ...
def write_struct(
    instance: Any,
    writer: Any = ...,
    endian: Any = ...,
    parent_field_name: str = ...,
    parent_struct_name: Optional[str] = ...,
    desc: str = ...,
    section: str = ...,
    spec_count: Any = ...,
    repeat: Any = ...,
    **kwargs: Any,
) -> Any: ...
def write_variant(
    data: Any,
    candidates: Any = ...,
    writer: Any = ...,
    tag_field: Optional[str] = ...,
    name: str = ...,
    desc: str = ...,
    condition: Optional[str] = ...,
    endian: Any = ...,
    section: str = ...,
    spec_count: Any = ...,
    repeat: Any = ...,
    **kwargs: Any,
) -> Any: ...

def read_struct[T](cls: type[T], data: bytes | Any = ..., reader: Any = ..., endian: Any = ...) -> T: ...
def sizeof(cls_or_obj: Any) -> int: ...
def offsetof(cls_or_obj: Any, field_name: str) -> int: ...
def bit_offsetof(cls_or_obj: Any, field_name: str) -> tuple[int, int]: ...
def _calculate_field_size(name: str, ftype: Any, val: Any = ..., is_cls: bool = ..., instance: Any = ...) -> int: ...
def _safe_issubclass(cls: Any, base: Any) -> bool: ...
def compile_struct_plan(cls: type) -> Any: ...
def get_struct_plan(cls: type) -> Any: ...

class FieldKind:
    PRIMITIVE: int
    BOOL: int
    MAGIC: int
    CONSTANT: int
    RANGE: int
    LENGTH_OF: int
    COUNT_OF: int
    CHECKSUM: int
    COMPRESSED: int
    VARINT: int
    ENUM: int
    NESTED_STRUCT: int
    FIXED_STRING: int
    BYTES: int
    C_STRING: int
    PREFIXED_STRING: int
    FIXED_ARRAY: int
    ARRAY: int
    OFFSET: int
    NAMED_OFFSET: int
    OFFSET_TABLE: int
    VARIANT: int
    PYTHON_PRIMITIVE: int

