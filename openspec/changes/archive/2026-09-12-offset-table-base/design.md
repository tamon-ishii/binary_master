# Design: Configurable Base Offset for Offset Tables

## Architecture

### 1. `BinaryWriter.write_offset_table`
Add `base_offset: int = 0` to signature:
```python
def write_offset_table(
    self,
    count: int,
    offset_size: int = 4,
    endian: EndianType = None,
    name: str = "offsets",
    desc: str = "Offset Table",
    base_offset: int = 0,
) -> OffsetTableHandle:
```
- Validate `base_offset >= 0`.
- Pass `base_offset` into `OffsetTableHandle`.

### 2. `OffsetTableHandle`
- Stores `self._base_offset = base_offset`.
- Provides property `base_offset`.
- Provides helper methods `get_target_offset(index)` and `get_stored_offset(index)`.
- In `set_offset(index, target_offset=None)`:
  - If `target_offset is None`, `target_offset = self._writer.tell()`.
  - Calculate `stored_value = target_offset - self._base_offset`.
  - If `stored_value < 0`, raise `ValueError`.
  - Pack and write `stored_value` into the slot.
  - Update `entry.value = stored_value` and `entry.target_offset = target_offset`.
  - Return `stored_value`.

### 3. `@binary_struct.OffsetTable`
Update `OffsetTable.__class_getitem__`:
```python
class OffsetTable(Generic[T]):
    def __class_getitem__(cls, args):
        if isinstance(args, tuple):
            count = args[0]
            offset_t = args[1] if len(args) > 1 else UInt32
            base_offset = args[2] if len(args) > 2 else 0
        else:
            count = args
            offset_t = UInt32
            base_offset = 0
        return cls, count, offset_t, base_offset
```
Update `write_struct` to extract `base_offset` and pass it to `writer.write_offset_table(...)`.

## Testing Strategy
- Test `base_offset=0` (default) backward compatibility.
- Test `base_offset > 0` with `set_offset`, `write_offset`, `write_target`.
- Test validation errors (`base_offset < 0`, `target_offset < base_offset`).
- Test manual generation reflecting `stored_value` and `target_offset`.
- Test `@binary_struct` with `OffsetTable[Count, Type, BaseOffset]`.
