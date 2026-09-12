# Design: Binary Size Inspection for @binary_struct

## Size Calculation Logic (`sizeof`)

```python
def sizeof(target: Any) -> int:
    """Calculate the binary size in bytes of a @binary_struct class, instance, or BinaryType."""
    if isinstance(target, type) and issubclass(target, BinaryType):
        return target._size

    # Handle instance
    if not isinstance(target, type):
        if hasattr(target, "__binary__"):
            return len(target.to_bytes())
        raise TypeError(f"Object {target!r} of type {type(target).__name__} is not a binary_struct")

    # Handle class
    meta = getattr(target, "__binary__", None)
    if meta is None:
        raise TypeError(f"Class {target.__name__} is not a binary_struct")

    total_bits = meta.get("bits")
    if total_bits is not None:
        raw_bytes = (total_bits + 7) // 8
        align = meta.get("align")
        if align:
            raw_bytes = ((raw_bytes + align - 1) // align) * align
        return raw_bytes

    fields = meta.get("fields", {})
    align_setting = meta.get("align")
    auto_align = meta.get("auto_align", False)

    current_offset = 0
    for name, ftype in fields.items():
        if get_origin(ftype) is Annotated:
            ftype = get_args(ftype)[0]

        # Check alignment padding before field
        if align_setting is not None or auto_align:
            field_align = _get_field_alignment(ftype, None)
            req_align = min(field_align, align_setting) if align_setting else field_align
            if req_align > 1:
                rem = current_offset % req_align
                if rem != 0:
                    current_offset += (req_align - rem)

        # Field size calculation
        if (isinstance(ftype, tuple) and len(ftype) >= 1 and ftype[0] is Offset) or get_origin(ftype) is Offset:
            offset_t = ftype[2] if isinstance(ftype, tuple) and len(ftype) >= 3 else UInt32
            _, size, _ = _normalize_offset_type(offset_t)
            current_offset += size
        elif (isinstance(ftype, tuple) and len(ftype) >= 1 and ftype[0] is OffsetTable) or get_origin(ftype) is OffsetTable:
            count = ftype[1] if isinstance(ftype, tuple) else get_args(ftype)[0]
            offset_t = ftype[2] if isinstance(ftype, tuple) and len(ftype) >= 3 else UInt32
            _, size, _ = _normalize_offset_type(offset_t)
            current_offset += count * size
        elif (isinstance(ftype, tuple) and len(ftype) >= 1 and ftype[0] is FixedArray) or get_origin(ftype) is FixedArray:
            elem_t = ftype[1] if isinstance(ftype, tuple) else get_args(ftype)[0]
            count = ftype[2] if isinstance(ftype, tuple) else get_args(ftype)[1]
            elem_size = sizeof(elem_t) if (hasattr(elem_t, "__binary__") or (isinstance(elem_t, type) and issubclass(elem_t, BinaryType))) else 1
            current_offset += count * elem_size
        elif hasattr(ftype, "__binary__"):
            current_offset += sizeof(ftype)
        elif isinstance(ftype, type) and issubclass(ftype, BinaryType):
            current_offset += ftype._size
        elif ftype in (int, float):
            current_offset += 4
        elif ftype is bool:
            current_offset += 1
        else:
            raise ValueError(f"Cannot determine static binary size for field '{name}' with type {ftype}; use sizeof(instance) instead")

    # Struct size alignment padding
    if align_setting is not None or auto_align:
        field_aligns = [_get_field_alignment(ft, None) for fn, ft in fields.items()]
        max_field_align = max(field_aligns, default=1)
        struct_boundary = align_setting if align_setting else max_field_align
        if struct_boundary > 1:
            rem = current_offset % struct_boundary
            if rem != 0:
                current_offset += (struct_boundary - rem)

    return current_offset

binary_size = sizeof
```

## Descriptor for Class & Instance `binary_size`

```python
class _BinarySizeDescriptor:
    def __get__(self, instance, owner=None):
        if instance is not None:
            return sizeof(instance)
        return sizeof(owner)
```

In `binary_struct`:
```python
target_cls.binary_size = _BinarySizeDescriptor()
target_cls.__len__ = lambda self: sizeof(self)
```
