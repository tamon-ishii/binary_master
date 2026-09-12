# Design: Relative Offset Base via Base.SELF

## 1. RelativeBase & Base Classes

```python
class RelativeBase:
    """Represents a relative origin base for offsets."""
    def __init__(self, target: str = "self", delta: int = 0):
        self.target = target  # "self", "struct", "field"
        self.delta = delta

    def __add__(self, other: int) -> "RelativeBase":
        if not isinstance(other, int):
            return NotImplemented
        return RelativeBase(self.target, self.delta + other)

    def __sub__(self, other: int) -> "RelativeBase":
        if not isinstance(other, int):
            return NotImplemented
        return RelativeBase(self.target, self.delta - other)

    def resolve(self, struct_start: int, field_pos: int = 0) -> int:
        origin = struct_start if self.target in ("self", "struct") else field_pos
        return origin + self.delta

    def __repr__(self) -> str:
        name = f"Base.{self.target.upper()}"
        if self.delta > 0:
            return f"{name}+{hex(self.delta)}" if self.delta > 9 else f"{name}+{self.delta}"
        elif self.delta < 0:
            return f"{name}-{hex(-self.delta)}" if -self.delta > 9 else f"{name}-{(-self.delta)}"
        return name


class Base:
    SELF = RelativeBase("self", 0)
    STRUCT = SELF
    FIELD = RelativeBase("field", 0)
```

## 2. Offset & OffsetTable Subscript Parsing

In `Offset.__class_getitem__`:
```python
    def __class_getitem__(cls, args):
        if isinstance(args, tuple):
            target_t = args[0]
            if len(args) == 2:
                if isinstance(args[1], (RelativeBase, int)) and not (isinstance(args[1], type) and issubclass(args[1], BinaryType)):
                    # args[1] is base_offset, e.g. Offset[Target, Base.SELF + 0x20]
                    offset_t = UInt32
                    base_offset = args[1]
                else:
                    offset_t = args[1]
                    base_offset = 0
            elif len(args) > 2:
                offset_t = args[1]
                base_offset = args[2]
            else:
                offset_t = UInt32
                base_offset = 0
        else:
            target_t = args
            offset_t = UInt32
            base_offset = 0
        return cls, target_t, offset_t, base_offset
```

In `OffsetTable.__class_getitem__`:
```python
    def __class_getitem__(cls, args):
        if isinstance(args, tuple):
            count = args[0]
            if len(args) == 2:
                if isinstance(args[1], (RelativeBase, int)) and not (isinstance(args[1], type) and issubclass(args[1], BinaryType)):
                    offset_t = UInt32
                    base_offset = args[1]
                else:
                    offset_t = args[1]
                    base_offset = 0
            elif len(args) > 2:
                offset_t = args[1]
                base_offset = args[2]
            else:
                offset_t = UInt32
                base_offset = 0
        else:
            count = args
            offset_t = UInt32
            base_offset = 0
        return cls, count, offset_t, base_offset
```

## 3. Serialization (`write_struct`)
- At start of `write_struct`:
  `struct_start_pos = writer.tell()`
- For `Offset`:
  `placeholder_pos = writer.tell()`
  `actual_base = base_offset.resolve(struct_start_pos, placeholder_pos) if isinstance(base_offset, RelativeBase) else int(base_offset)`
  Record `actual_base` in `deferred_offsets`.
  When resolving deferred offset:
  `stored_val = target_pos - actual_base`
  If `stored_val < 0`:
  raise `ValueError` (or handle signed types).
- For `OffsetTable`:
  `placeholder_pos = writer.tell()`
  `actual_base = base_offset.resolve(struct_start_pos, placeholder_pos) if isinstance(base_offset, RelativeBase) else int(base_offset)`
  Pass `base_offset=actual_base` to `writer.write_offset_table(...)`.

## 4. Deserialization (`read_struct`)
- At start of `read_struct`:
  `struct_start_pos = reader.tell()`
- For `Offset`:
  `placeholder_pos = reader.tell()`
  `actual_base = base_offset.resolve(struct_start_pos, placeholder_pos) if isinstance(base_offset, RelativeBase) else int(base_offset)`
  `stored_offset = reader._unpack_read(...)`
  `target_offset = stored_offset + actual_base`
  If `target_type` is a binary struct, seek to `target_offset`, deserialize, restore position.
