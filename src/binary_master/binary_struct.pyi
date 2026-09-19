from typing import (
    Any,
    Callable,
    Generic,
    Literal,
    Optional,
    TypeVar,
    Union,
    dataclass_transform,
    overload,
)

T = TypeVar("T")
T1 = TypeVar("T1")
T2 = TypeVar("T2")
T3 = TypeVar("T3")

# 1. Primitive types (Static checkers / IDEs see them as int / float / bool)
type UInt8 = int
type UInt16 = int
type UInt32 = int
type UInt64 = int
type Int8 = int
type Int16 = int
type Int32 = int
type Int64 = int
type Float16 = float
type Float32 = float
type Float64 = float
type Float = float
type Double = float
type Bool = bool

# Dynamic types
type Bytes = bytes
type FixedString = str
type CString = str
type PrefixedString = str

# 2. Arrays & Offsets
L = Literal
type FixedArray[T, *Args] = bytes | list[T]
type Array[T] = list[T]
type Offset[Target, *Args] = Target | None
type NamedOffset[Key, Target = Any, *Args] = Target | None
type OffsetTable[Count, *Args] = list[Any] | None
type Bits[Width] = int
type Variant[Tag, Mapping, *Args] = Any

# 3. Base Relative Origins
class Base:
    class SELF: ...
    STRUCT = SELF
    class FIELD: ...


class RelativeBase: ...

# 4. Decorator and Base Classes
@dataclass_transform()
def binary_struct[T](cls: T) -> T: ...

class BinaryStruct:
    def to_bytes(self, endian: Any = ...) -> bytes: ...
    @classmethod
    def from_bytes[T](cls: type[T], data: bytes, endian: Any = ...) -> T: ...

Struct = BinaryStruct

def to_bytes(obj: Any, endian: Any = ...) -> bytes: ...
def from_bytes[T](cls: type[T], data: bytes, endian: Any = ...) -> T: ...
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


def binary_size(cls_or_obj: Any) -> int: ...
def offsetof(cls_or_obj: Any, field_name: str) -> int: ...
def bit_offsetof(cls_or_obj: Any, field_name: str) -> int: ...

def Magic(val: Any) -> Any: ...
def Constant(val: Any) -> Any: ...
def Range(min_val: Any, max_val: Any) -> Any: ...
def LengthOf(target: str) -> Any: ...
def CountOf(target: str) -> Any: ...
