"""Zero-copy and lazy binary parsing views."""

from __future__ import annotations

import mmap
import struct
from pathlib import Path
from typing import (
    Any,
    Dict,
    Generic,
    Optional,
    Type,
    TypeVar,
    Union,
)

from binary_master.enums import Endian, normalize_endian

T = TypeVar("T")


class ZeroCopyView(Generic[T]):
    """Zero-copy / lazy parsing view over a binary buffer.

    Provides attribute-based access directly against underlying bytes or memoryview
    without allocating Python struct instances or decoding unwanted fields.
    If the buffer is writable (e.g. bytearray), field attributes can be updated in-place.
    """

    __slots__ = (
        "_cls",
        "_buffer",
        "_offset",
        "_endian",
        "_plan",
        "_field_offsets",
        "_field_plans",
        "_total_size",
        "_mmap_obj",
    )

    def __init__(
        self,
        cls: Type[T],
        buffer: Union[bytes, bytearray, memoryview, mmap.mmap],
        offset: int = 0,
        endian: Optional[Union[str, Endian]] = None,
        mmap_obj: Optional[mmap.mmap] = None,
    ) -> None:
        object.__setattr__(self, "_cls", cls)
        if isinstance(buffer, memoryview):
            mv = buffer
        else:
            mv = memoryview(buffer)
        object.__setattr__(self, "_buffer", mv)
        object.__setattr__(self, "_offset", offset)
        object.__setattr__(self, "_mmap_obj", mmap_obj)

        from binary_master.binary_struct import get_struct_plan

        plan = get_struct_plan(cls)
        object.__setattr__(self, "_plan", plan)
        act_endian = normalize_endian(endian or plan.endian)
        object.__setattr__(self, "_endian", act_endian)

        # Precompute fixed field offsets
        field_offsets: Dict[str, int] = {}
        field_plans: Dict[str, Any] = {}
        curr_off = 0
        all_fixed = True

        for fp in plan.field_plans:
            field_plans[fp.name] = fp
            # Alignment check
            align = fp.align
            if (plan.align_setting is not None or plan.auto_align) and align > 1:
                req_align = min(align, plan.align_setting) if plan.align_setting else align
                if req_align > 1:
                    curr_off = ((curr_off + req_align - 1) // req_align) * req_align

            field_offsets[fp.name] = curr_off

            if fp.size > 0:
                curr_off += fp.size
            else:
                all_fixed = False

        object.__setattr__(self, "_field_offsets", field_offsets)
        object.__setattr__(self, "_field_plans", field_plans)

        if all_fixed:
            if plan.total_size is not None:
                tot = plan.total_size
            else:
                tot = curr_off
            object.__setattr__(self, "_total_size", tot)
        else:
            object.__setattr__(self, "_total_size", None)

    @property
    def byte_size(self) -> int:
        """Total size in bytes of the struct within the buffer."""
        tot = self._total_size
        if tot is not None:
            return tot
        # For variable-size structs, compute by decoding or measuring
        inst = self.to_struct()
        from binary_master.binary_struct import sizeof

        sz = sizeof(inst)
        object.__setattr__(self, "_total_size", sz)
        return sz

    def __len__(self) -> int:
        return self.byte_size

    def as_buffer(self) -> memoryview:
        """Return memoryview slice of this struct."""
        return self._buffer[self._offset : self._offset + self.byte_size]

    def to_struct(self) -> T:
        """Deserialize into a full @binary_struct instance."""
        from binary_master.binary_struct import read_struct

        return read_struct(self._cls, bytes(self._buffer[self._offset : self._offset + (self._total_size or len(self._buffer) - self._offset)]))

    def to_dict(self) -> Dict[str, Any]:
        """Read all fields into a dictionary."""
        return {fp.name: getattr(self, fp.name) for fp in self._plan.field_plans}

    def hexdump(
        self,
        width: int = 16,
        color: bool = False,
        annotate: bool = True,
        show_ascii: bool = True,
        show_header: bool = True,
    ) -> str:
        """Generate hexdump of this struct's bytes."""
        from binary_master.debug import hexdump

        return hexdump(
            bytes(self.as_buffer()),
            width=width,
            color=color,
            annotate=annotate,
            show_ascii=show_ascii,
            show_header=show_header,
        )

    def __getattr__(self, name: str) -> Any:
        field_plans = self._field_plans
        if name not in field_plans:
            raise AttributeError(f"'{self._cls.__name__}' zero-copy view has no field '{name}'")

        fp = field_plans[name]
        field_offset = self._field_offsets[name]
        abs_offset = self._offset + field_offset
        buffer = self._buffer
        endian_char = "<" if self._endian == Endian.LITTLE else ">"

        from binary_master.binary_struct import FieldKind

        kind = fp.kind
        if kind in (FieldKind.PRIMITIVE, FieldKind.CONSTANT, FieldKind.RANGE, FieldKind.LENGTH_OF, FieldKind.COUNT_OF):
            fmt = fp.fmt
            if not fmt.startswith(("<", ">", "@", "=", "!")):
                fmt = endian_char + fmt
            return struct.unpack_from(fmt, buffer, abs_offset)[0]

        if kind == FieldKind.MAGIC:
            if fp.is_bytes_magic:
                return bytes(buffer[abs_offset : abs_offset + fp.size])
            fmt = fp.fmt
            if not fmt.startswith(("<", ">", "@", "=", "!")):
                fmt = endian_char + fmt
            return struct.unpack_from(fmt, buffer, abs_offset)[0]

        if kind == FieldKind.BOOL:
            val = buffer[abs_offset]
            return bool(val)

        if kind == FieldKind.ENUM:
            fmt = fp.fmt
            if not fmt.startswith(("<", ">", "@", "=", "!")):
                fmt = endian_char + fmt
            raw_val = struct.unpack_from(fmt, buffer, abs_offset)[0]
            if fp.enum_cls:
                return fp.enum_cls(raw_val)
            return raw_val

        if kind == FieldKind.FIXED_STRING:
            raw = bytes(buffer[abs_offset : abs_offset + fp.size])
            return raw.rstrip(b"\x00").decode(fp.encoding or "utf-8", errors="replace")

        if kind == FieldKind.BYTES:
            return bytes(buffer[abs_offset : abs_offset + fp.size])

        if kind == FieldKind.NESTED_STRUCT:
            return ZeroCopyView(fp.nested_cls, buffer, offset=abs_offset, endian=self._endian)

        # Fallback to full struct property if specialized field kind
        inst = self.to_struct()
        return getattr(inst, name)

    def __setattr__(self, name: str, value: Any) -> None:
        if name in self.__slots__ or name.startswith("_"):
            object.__setattr__(self, name, value)
            return

        field_plans = object.__getattribute__(self, "_field_plans")
        if name not in field_plans:
            raise AttributeError(f"'{self._cls.__name__}' zero-copy view has no field '{name}'")

        buffer = object.__getattribute__(self, "_buffer")
        if buffer.readonly:
            raise TypeError("Cannot modify fields on a read-only buffer (use bytearray for in-place modifications)")

        fp = field_plans[name]
        field_offset = object.__getattribute__(self, "_field_offsets")[name]
        abs_offset = object.__getattribute__(self, "_offset") + field_offset
        endian = object.__getattribute__(self, "_endian")
        endian_char = "<" if endian == Endian.LITTLE else ">"

        from binary_master.binary_struct import FieldKind

        kind = fp.kind
        if kind in (FieldKind.PRIMITIVE, FieldKind.CONSTANT, FieldKind.RANGE, FieldKind.LENGTH_OF, FieldKind.COUNT_OF):
            fmt = fp.fmt
            if not fmt.startswith(("<", ">", "@", "=", "!")):
                fmt = endian_char + fmt
            struct.pack_into(fmt, buffer, abs_offset, value)
            return

        if kind == FieldKind.MAGIC:
            if fp.is_bytes_magic:
                b = bytes(value)
                buffer[abs_offset : abs_offset + len(b)] = b
            else:
                fmt = fp.fmt
                if not fmt.startswith(("<", ">", "@", "=", "!")):
                    fmt = endian_char + fmt
                struct.pack_into(fmt, buffer, abs_offset, value)
            return

        if kind == FieldKind.BOOL:
            buffer[abs_offset] = 1 if value else 0
            return

        if kind == FieldKind.ENUM:
            fmt = fp.fmt
            if not fmt.startswith(("<", ">", "@", "=", "!")):
                fmt = endian_char + fmt
            val = value.value if hasattr(value, "value") else int(value)
            struct.pack_into(fmt, buffer, abs_offset, val)
            return

        if kind == FieldKind.FIXED_STRING:
            encoded = str(value).encode(fp.encoding or "utf-8")
            if len(encoded) < fp.size:
                encoded = encoded.ljust(fp.size, b"\x00")
            elif len(encoded) > fp.size:
                encoded = encoded[: fp.size]
            buffer[abs_offset : abs_offset + fp.size] = encoded
            return

        if kind == FieldKind.BYTES:
            b = bytes(value)
            buffer[abs_offset : abs_offset + min(len(b), fp.size)] = b[: fp.size]
            return

        raise NotImplementedError(f"In-place modification of field kind {kind} is not supported directly in view")

    def __repr__(self) -> str:
        sz = self._total_size if self._total_size is not None else "?"
        return f"<ZeroCopyView({self._cls.__name__}) at offset=0x{self._offset:04x}, size={sz}>"

    def close(self) -> None:
        """Close memory-mapped file if opened via from_file."""
        buf = getattr(self, "_buffer", None)
        if buf is not None and isinstance(buf, memoryview):
            try:
                buf.release()
            except Exception:
                pass
        mmap_obj = getattr(self, "_mmap_obj", None)
        if mmap_obj is not None:
            try:
                mmap_obj.close()
            except Exception:
                pass
            object.__setattr__(self, "_mmap_obj", None)

    def __enter__(self) -> "ZeroCopyView[T]":
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()

    @classmethod
    def from_bytes(
        cls,
        struct_cls: Type[T],
        buffer: Union[bytes, bytearray, memoryview],
        offset: int = 0,
        endian: Optional[Union[str, Endian]] = None,
    ) -> "ZeroCopyView[T]":
        """Create a ZeroCopyView from an in-memory buffer."""
        return cls(struct_cls, buffer=buffer, offset=offset, endian=endian)

    @classmethod
    def from_file(
        cls,
        struct_cls: Type[T],
        path: Union[str, Path],
        offset: int = 0,
        endian: Optional[Union[str, Endian]] = None,
        writable: bool = False,
    ) -> "ZeroCopyView[T]":
        """Create a ZeroCopyView from a file using mmap for zero-overhead OS memory paging."""
        p = Path(path)
        mode = "r+b" if writable else "rb"
        access = mmap.ACCESS_WRITE if writable else mmap.ACCESS_READ
        f = open(p, mode)
        try:
            mm = mmap.mmap(f.fileno(), 0, access=access)
            f.close()
            return cls(struct_cls, buffer=mm, offset=offset, endian=endian, mmap_obj=mm)
        except Exception:
            f.close()
            raise


__all__ = ["ZeroCopyView"]
