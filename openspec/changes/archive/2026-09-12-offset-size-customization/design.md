# Design: Configurable Offset Size for Offset[T]

## Type Parsing & Representation

### `Offset` Class Definition
```python
class Offset(Generic[T]):
    """シリアライズ時に自動計算されるオフセット"""

    def __init__(self, target: Any = None, offset: Optional[int] = None):
        self.target = target
        self.offset = offset

    def __class_getitem__(cls, args):
        if isinstance(args, tuple):
            target_t = args[0]
            offset_t = args[1] if len(args) > 1 else UInt32
            base_offset = args[2] if len(args) > 2 else 0
        else:
            target_t = args
            offset_t = UInt32
            base_offset = 0
        return cls, target_t, offset_t, base_offset
```

### Type Normalization Helper
Helper function to normalize `offset_t` (e.g. `UInt16` or `2`) into format char and byte size:
```python
def _normalize_offset_type(offset_t: Any) -> tuple[str, int, str]:
    """Returns (fmt_char, size_in_bytes, type_label)"""
    size_map = {1: ("B", 1, "UInt8"), 2: ("H", 2, "UInt16"), 4: ("I", 4, "UInt32"), 8: ("Q", 8, "UInt64")}
    if isinstance(offset_t, int):
        if offset_t not in size_map:
            raise ValueError(f"Offset byte size must be 1, 2, 4, or 8, got {offset_t}")
        return size_map[offset_t]
    if hasattr(offset_t, "_size") and hasattr(offset_t, "_fmt"):
        fmt = offset_t._fmt
        size = offset_t._size
        return fmt, size, offset_t.__name__
    return ("I", 4, "UInt32")
```

## Field Alignment
In `_get_field_alignment`:
```python
if (isinstance(ftype, tuple) and len(ftype) >= 1 and ftype[0] is Offset) or get_origin(ftype) is Offset:
    offset_t = ftype[2] if isinstance(ftype, tuple) and len(ftype) >= 3 else UInt32
    _, size, _ = _normalize_offset_type(offset_t)
    return size
```

## Serialization (`write_struct`)
- Extract `target_t`, `offset_t`, `base_offset`.
- Compute `fmt_char, offset_size, type_name = _normalize_offset_type(offset_t)`.
- Write placeholder using `_pack_write(fmt_char, 0, ...)`.
- Add to `deferred_offsets`:
  `(offset_placeholder_idx, placeholder_pos, target, active_endian, fmt_char, base_offset)`.
- When resolving target:
  - `stored_offset = target_pos - base_offset`.
  - Validate bounds for `fmt_char`.
  - Pack and write `stored_offset` using `fmt_char`.
  - Update `writer._entries` with `value = stored_offset` and `target_offset = target_pos`.

## Deserialization (`read_struct`)
- Read offset using `reader._unpack_read(fmt_char, offset_size, endian=active_endian)`.
- Absolute target pos is `stored_offset + base_offset`.
- If target struct exists and `stored_offset > 0`:
  - Seek to target pos, deserialize struct, return to saved pos.
