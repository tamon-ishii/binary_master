"""BinaryWriter: Core sequential binary writer implementation."""

from __future__ import annotations

import io
from pathlib import Path
import struct
from typing import Any, IO, Iterable, Optional, Union

from binary_master.enums import Endian, EndianType, normalize_endian

# Integer boundary constants
INT8_MIN, INT8_MAX = -128, 127
UINT8_MIN, UINT8_MAX = 0, 255
INT16_MIN, INT16_MAX = -32768, 32767
UINT16_MIN, UINT16_MAX = 0, 65535
INT32_MIN, INT32_MAX = -2147483648, 2147483647
UINT32_MIN, UINT32_MAX = 0, 4294967295
INT64_MIN, INT64_MAX = -9223372036854775808, 9223372036854775807
UINT64_MIN, UINT64_MAX = 0, 18446744073709551615

_FMT_TO_TYPE_NAME = {
    "B": "UInt8",
    "b": "Int8",
    "H": "UInt16",
    "h": "Int16",
    "I": "UInt32",
    "i": "Int32",
    "Q": "UInt64",
    "q": "Int64",
    "f": "Float32",
    "d": "Float64",
    "?": "Bool",
}


def _check_int_bounds(name: str, value: int, min_val: int, max_val: int) -> None:
    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError(f"{name} requires an integer, got {type(value).__name__}")
    if not (min_val <= value <= max_val):
        raise ValueError(
            f"Value {value} out of range for {name} (expected {min_val} to {max_val})"
        )


class _RepeatContext:
    """Context manager for scoping a repeated section in BinaryWriter."""

    def __init__(
        self,
        writer: BinaryWriter,
        section: str = "",
        count: Optional[Union[int, str, bool]] = None,
        desc: str = "",
    ) -> None:
        self.writer = writer
        self.section = section
        self.count = count
        self.desc = desc
        self._prev_caption: Optional[str] = None
        self._prev_desc: str = ""
        self._prev_repeat: Optional[Union[int, str, bool]] = None
        self._prev_variants: Optional[list] = None

    def __enter__(self) -> BinaryWriter:
        self._prev_caption = self.writer._current_caption
        self._prev_desc = self.writer._current_caption_desc
        self._prev_repeat = self.writer._current_caption_repeat
        self._prev_variants = self.writer._current_caption_variants
        title = self.section or self._prev_caption or "Repeat"
        self.writer.caption(title=title, desc=self.desc, repeat=self.count)
        return self.writer

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.writer._current_caption = self._prev_caption
        self.writer._current_caption_desc = self._prev_desc
        self.writer._current_caption_repeat = self._prev_repeat
        self.writer._current_caption_variants = self._prev_variants


class _CaptionContext:
    """Context manager and proxy for scoped section caption and specification metadata."""

    def __init__(
        self,
        writer: BinaryWriter,
        title: Optional[str] = None,
        desc: str = "",
        spec_count: Optional[Union[int, str, bool]] = None,
        variants: Optional[list] = None,
    ) -> None:
        self.writer = writer
        self.title = title if title else None
        self.desc = desc
        self.spec_count = spec_count
        self.variants = variants

        self._prev_caption = writer._current_caption
        self._prev_desc = writer._current_caption_desc
        self._prev_repeat = writer._current_caption_repeat
        self._prev_variants = writer._current_caption_variants
        self._prev_subcaption = writer._current_subcaption
        self._prev_subcaption_desc = writer._current_subcaption_desc

        writer._apply_caption(
            title=self.title,
            desc=self.desc,
            spec_count=self.spec_count,
            variants=self.variants,
        )

    def __enter__(self) -> BinaryWriter:
        return self.writer

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.writer._current_caption = self._prev_caption
        self.writer._current_caption_desc = self._prev_desc
        self.writer._current_caption_repeat = self._prev_repeat
        self.writer._current_caption_variants = self._prev_variants
        self.writer._current_subcaption = self._prev_subcaption
        self.writer._current_subcaption_desc = self._prev_subcaption_desc

    def __getattr__(self, name: str) -> Any:
        return getattr(self.writer, name)

    def __bytes__(self) -> bytes:
        return bytes(self.writer)

    def __len__(self) -> int:
        return len(self.writer)

    def __repr__(self) -> str:
        return repr(self.writer)

    def __str__(self) -> str:
        return str(self.writer)


class BinaryWriter:
    """A sequential binary writer supporting in-memory buffers and stream/file targets."""

    def __init__(
        self,
        stream: Optional[IO[bytes]] = None,
        default_endian: EndianType = Endian.LITTLE,
        auto_close: Optional[bool] = None,
    ) -> None:
        """Initialize a BinaryWriter.

        Args:
            stream: A writable binary stream (e.g. io.BytesIO or open binary file).
                    If None, an in-memory io.BytesIO is created.
            default_endian: The default byte order (Endian.LITTLE, Endian.BIG, or string alias).
            auto_close: Whether closing this writer should close the underlying stream.
                        Defaults to True if a file path was opened, False if stream was provided.
        """
        self._default_endian = normalize_endian(default_endian)
        self._entries: list[Any] = []
        self._struct_classes: list[type] = []
        self._variants: list[dict[str, Any]] = []
        self._expected_variant: Optional[dict[str, Any]] = None
        self._elements_log: list[tuple[str, Any]] = []
        self._current_caption: Optional[str] = None
        self._current_caption_desc: str = ""
        self._current_caption_variants: Optional[list] = None
        self._current_caption_repeat: Optional[Union[int, str, bool]] = None
        self._current_subcaption: Optional[str] = None
        self._current_subcaption_desc: str = ""
        if stream is None:
            self._stream = io.BytesIO()
            self._close_stream = auto_close if auto_close is not None else False
            self._is_memory = True
        else:
            self._stream = stream
            self._close_stream = auto_close if auto_close is not None else False
            self._is_memory = isinstance(stream, io.BytesIO)

    @property
    def struct_classes(self) -> list[type]:
        """Get the struct classes recorded during serialization."""
        return self._struct_classes

    @property
    def variants(self) -> list[dict[str, Any]]:
        """Get the variant choice definitions recorded on this writer."""
        return self._variants

    def _apply_caption(
        self,
        title: Optional[str] = None,
        desc: str = "",
        spec_count: Optional[Union[int, str, bool]] = None,
        variants: Optional[list] = None,
    ) -> None:
        self._current_caption = title if title else None
        self._current_caption_desc = desc
        self._current_caption_variants = variants
        self._current_caption_repeat = spec_count
        self._current_subcaption = None
        self._current_subcaption_desc = ""
        if title:
            self._elements_log.append(("section", title, desc, spec_count))

    def set_caption(
        self,
        title: Optional[str] = None,
        desc: str = "",
        spec_count: Optional[Union[int, str, bool]] = None,
        variants: Optional[list] = None,
        repeat: Optional[Union[int, str, bool]] = None,
    ) -> _CaptionContext:
        """Set active section caption/description/spec_count for subsequent writes.

        Can be called directly or used as a context manager:
            # Context manager (automatically resets caption upon exiting block):
            with writer.set_caption("offsets", desc="Table of chunk offsets", spec_count="num_chunk"):
                table = writer.write_offset_table(count=10)

            # Direct method call:
            writer.set_caption("File Header", desc="Main container header")

        Args:
            title: The caption or title string. Pass None or empty string to clear.
            desc: Optional description for this section/caption.
            spec_count: Optional specification count metadata, e.g. 'num_chunk', count, or -1.
            variants: Optional list or dict of candidate variant structures.
            repeat: Backward-compatible alias for spec_count.

        Returns:
            _CaptionContext supporting both context manager (`with`) and direct chaining.
        """
        rep_val = spec_count if spec_count is not None else repeat
        return _CaptionContext(
            writer=self,
            title=title,
            desc=desc,
            spec_count=rep_val,
            variants=variants,
        )

    def caption(
        self,
        title: Optional[str] = None,
        desc: str = "",
        variants: Optional[list] = None,
        repeat: Optional[Union[int, str, bool]] = None,
        spec_count: Optional[Union[int, str, bool]] = None,
    ) -> _CaptionContext:
        """Alias for set_caption."""
        return self.set_caption(
            title=title,
            desc=desc,
            spec_count=spec_count,
            variants=variants,
            repeat=repeat,
        )

    def subcaption(self, title: Optional[str] = None, desc: str = "") -> BinaryWriter:
        """Set an active subcaption under the current section caption.

        Args:
            title: The subcaption title string.
            desc: Optional description for this subcaption.

        Returns:
            self for method chaining.
        """
        self._current_subcaption = title if title else None
        self._current_subcaption_desc = desc
        return self

    def repeat(
        self,
        section: str = "",
        count: Optional[Union[int, str, bool]] = None,
        desc: str = "",
        spec_count: Optional[Union[int, str, bool]] = None,
    ) -> _CaptionContext:
        """Context manager to write a repeating section of binary data (convenience alias for set_caption).

        Example:
            with writer.repeat("DataChunks", count="chunk_count"):
                for chunk in chunks:
                    writer.write_struct(chunk)

        Args:
            section: Section name / title for the repeating block (default: "").
            count: Repetition count, loop variable name (e.g. 'chunk_count'), or True.
            desc: Optional description of this repeating section.
            spec_count: Optional specification count metadata (alias for count).
        """
        rep_val = spec_count if spec_count is not None else count
        return self.set_caption(title=section, desc=desc, spec_count=rep_val)

    def write_repeated(
        self,
        items: Iterable[Any],
        section: str = "",
        count: Optional[Union[int, str, bool]] = None,
        desc: str = "",
        endian: EndianType = None,
        spec_count: Optional[Union[int, str, bool]] = None,
    ) -> BinaryWriter:
        """Write an iterable of items (e.g. structs) as a repeated section.

        Args:
            items: Iterable of @binary_struct instances or items to write.
            section: Section name (default: "").
            count: Repetition count or variable name (defaults to len(items) if items has len).
            desc: Optional description for the section.
            endian: Optional endianness override.
            spec_count: Optional specification count metadata.

        Returns:
            self for method chaining.
        """
        item_list = list(items) if not isinstance(items, (list, tuple)) else items
        rep_val = spec_count if spec_count is not None else count
        effective_count = rep_val if rep_val is not None else len(item_list)
        with self.set_caption(title=section, desc=desc, spec_count=effective_count):
            for item in item_list:
                if hasattr(item, "__binary__"):
                    self.write_struct(item, endian=endian)
                elif callable(item):
                    item(self)
                else:
                    raise TypeError(f"Cannot write repeated item of type {type(item).__name__}")
        return self

    @property
    def current_caption_spec_count(self) -> Optional[Union[int, str, bool]]:
        """Active specification repetition count for the current caption."""
        return self._current_caption_repeat

    @property
    def current_caption(self) -> Optional[str]:
        """Get the currently active section caption."""
        return self._current_caption

    @property
    def current_caption_desc(self) -> str:
        """Get the description of the currently active section caption."""
        return self._current_caption_desc

    @property
    def current_caption_repeat(self) -> Optional[Union[int, str, bool]]:
        """Get the repetition metadata of the currently active section caption."""
        return self._current_caption_repeat

    @property
    def current_caption_variants(self) -> Optional[list]:
        """Get the candidate variants of the currently active section caption."""
        return self._current_caption_variants

    @property
    def current_subcaption(self) -> Optional[str]:
        """Get the currently active subcaption."""
        return self._current_subcaption

    @property
    def current_subcaption_desc(self) -> str:
        """Get the description of the currently active subcaption."""
        return self._current_subcaption_desc

    @classmethod
    def to_memory(cls, default_endian: EndianType = Endian.LITTLE) -> BinaryWriter:
        """Create a BinaryWriter writing to an in-memory buffer."""
        return cls(stream=None, default_endian=default_endian, auto_close=False)

    @classmethod
    def to_file(
        cls,
        path_or_file: Union[str, Path, IO[bytes]],
        default_endian: EndianType = Endian.LITTLE,
        mode: str = "wb",
    ) -> BinaryWriter:
        """Create a BinaryWriter targeting a file path or file stream.

        Args:
            path_or_file: A file path string, pathlib.Path, or open binary file-like object.
            default_endian: Default byte order.
            mode: File open mode when a path is supplied (default 'wb').
        """
        if isinstance(path_or_file, (str, Path)):
            file_stream = open(path_or_file, mode)
            return cls(stream=file_stream, default_endian=default_endian, auto_close=True)
        return cls(stream=path_or_file, default_endian=default_endian, auto_close=False)

    @property
    def default_endian(self) -> Endian:
        """Get the default endianness."""
        return self._default_endian

    @default_endian.setter
    def default_endian(self, endian: EndianType) -> None:
        """Set the default endianness."""
        self._default_endian = normalize_endian(endian)

    @property
    def stream(self) -> IO[bytes]:
        """Get the underlying binary stream."""
        return self._stream

    @property
    def closed(self) -> bool:
        """Check if the underlying stream is closed."""
        return self._stream.closed

    def flush(self) -> None:
        """Flush the underlying stream."""
        self._stream.flush()

    def close(self) -> None:
        """Close the writer and the underlying stream if auto_close is enabled."""
        self.flush()
        if self._close_stream and not self._stream.closed:
            self._stream.close()

    def to_bytes(self) -> bytes:
        """Return the accumulated binary data as immutable bytes (in-memory writers only).

        Raises:
            TypeError: If the writer is not writing to an in-memory BytesIO buffer.
        """
        if isinstance(self._stream, io.BytesIO):
            return self._stream.getvalue()
        raise TypeError("to_bytes() is only available for in-memory buffer writers")

    def to_bytearray(self) -> bytearray:
        """Return the accumulated binary data as a mutable bytearray (in-memory writers only)."""
        return bytearray(self.to_bytes())

    def __enter__(self) -> BinaryWriter:
        return self

    def __exit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        self.close()

    @property
    def entries(self) -> list[Any]:
        """Get the recorded layout entries."""
        return self._entries

    def hexdump(
        self,
        *,
        width: int = 16,
        color: bool = False,
        annotate: bool = True,
        show_ascii: bool = True,
        show_header: bool = True,
        max_bytes: Optional[int] = None,
    ) -> str:
        """Generate an annotated hexdump correlating bytes to written fields."""
        from binary_master.debug import hexdump as _hexdump

        return _hexdump(
            self,
            width=width,
            color=color,
            annotate=annotate,
            show_ascii=show_ascii,
            show_header=show_header,
            max_bytes=max_bytes,
        )

    def dump(
        self,
        format: str = "hexdump",
        **kwargs: Any,
    ) -> Union[str, list[dict[str, Any]]]:
        """Generate a debug dump of the written binary buffer and fields.

        Formats: 'hexdump' (default), 'table', 'json', 'dict'.
        """
        from binary_master.debug import debug_dump as _debug_dump

        return _debug_dump(self, format=format, **kwargs)

    def diff(
        self,
        other: Any,
        *,
        name_left: str = "Self",
        name_right: str = "Other",
        color: bool = False,
    ) -> str:
        """Compare this writer's buffer and fields against another buffer or writer."""
        from binary_master.debug import diff_dump as _diff_dump

        return _diff_dump(self, other, name_left=name_left, name_right=name_right, color=color)

    def verify(
        self,
        expected: Any,
        *,
        name_expected: str = "Expected",
        name_actual: str = "Actual",
        color: bool = False,
        raise_error: bool = True,
    ) -> bool:
        """Verify that this writer's binary content matches expected data.

        Args:
            expected: Expected bytes, BinaryWriter, or @binary_struct.
            name_expected: Label for expected data in diff output.
            name_actual: Label for actual data in diff output.
            color: Whether to colorize diff output.
            raise_error: If True, raises AssertionError on mismatch (default: True).

        Returns:
            True if identical, False if mismatched and raise_error is False.

        Raises:
            AssertionError: If contents do not match and raise_error is True.
        """
        from binary_master.debug import verify as _verify

        return _verify(
            actual=self,
            expected=expected,
            name_actual=name_actual,
            name_expected=name_expected,
            color=color,
            raise_error=raise_error,
        )

    def _record_entry(
        self,
        offset: int,
        size: int,
        type_name: str,
        value: Any = None,
        name: str = "",
        endian: Optional[str] = None,
        description: str = "",
        struct_name: Optional[str] = None,
        target_offset: Optional[int] = None,
        subfields: Optional[list] = None,
        caption: Optional[str] = None,
        struct_doc: Optional[str] = None,
        caption_desc: Optional[str] = None,
        subcaption: Optional[str] = None,
        subcaption_desc: Optional[str] = None,
        caption_variants: Optional[list] = None,
        caption_repeat: Optional[Union[int, str, bool]] = None,
    ) -> None:
        from binary_master.manual import LayoutEntry

        active_caption = caption if caption is not None else self._current_caption
        active_caption_desc = caption_desc if caption_desc is not None else self._current_caption_desc
        active_subcaption = subcaption if subcaption is not None else self._current_subcaption
        active_subcaption_desc = subcaption_desc if subcaption_desc is not None else self._current_subcaption_desc
        active_variants = caption_variants if caption_variants is not None else self._current_caption_variants
        active_repeat = caption_repeat if caption_repeat is not None else self._current_caption_repeat
        self._entries.append(
            LayoutEntry(
                offset=offset,
                size=size,
                type_name=type_name,
                value=value,
                name=name,
                endian=endian,
                description=description,
                struct_name=struct_name,
                target_offset=target_offset,
                subfields=subfields,
                caption=active_caption,
                struct_doc=struct_doc,
                caption_desc=active_caption_desc,
                subcaption=active_subcaption,
                subcaption_desc=active_subcaption_desc,
                caption_variants=active_variants,
                caption_repeat=active_repeat,
            )
        )

    # --- Internal Packing Helper ---

    def _pack_write(
        self,
        fmt_char: str,
        value: object,
        endian: EndianType = None,
        name: str = "",
        desc: str = "",
        struct_name: Optional[str] = None,
        struct_doc: Optional[str] = None,
    ) -> BinaryWriter:
        order = normalize_endian(endian, self._default_endian)
        data = struct.pack(f"{order.value}{fmt_char}", value)
        offset = self.tell()
        self._stream.write(data)
        self._record_entry(
            offset=offset,
            size=len(data),
            type_name=_FMT_TO_TYPE_NAME.get(fmt_char, fmt_char),
            value=value,
            name=name,
            endian=order.name.capitalize(),
            description=desc,
            struct_name=struct_name,
            struct_doc=struct_doc,
        )
        return self

    # --- Integer Methods ---

    def write_uint8(self, value: int, name: str = "", desc: str = "") -> BinaryWriter:
        """Write an unsigned 8-bit integer (0 to 255)."""
        _check_int_bounds("uint8", value, UINT8_MIN, UINT8_MAX)
        return self._pack_write("B", value, Endian.NATIVE, name=name, desc=desc)

    def write_int8(self, value: int, name: str = "", desc: str = "") -> BinaryWriter:
        """Write a signed 8-bit integer (-128 to 127)."""
        _check_int_bounds("int8", value, INT8_MIN, INT8_MAX)
        return self._pack_write("b", value, Endian.NATIVE, name=name, desc=desc)

    def write_uint16(self, value: int, endian: EndianType = None, name: str = "", desc: str = "") -> BinaryWriter:
        """Write an unsigned 16-bit integer (0 to 65535)."""
        _check_int_bounds("uint16", value, UINT16_MIN, UINT16_MAX)
        return self._pack_write("H", value, endian, name=name, desc=desc)

    def write_int16(self, value: int, endian: EndianType = None, name: str = "", desc: str = "") -> BinaryWriter:
        """Write a signed 16-bit integer (-32768 to 32767)."""
        _check_int_bounds("int16", value, INT16_MIN, INT16_MAX)
        return self._pack_write("h", value, endian, name=name, desc=desc)

    def write_uint32(self, value: int, endian: EndianType = None, name: str = "", desc: str = "") -> BinaryWriter:
        """Write an unsigned 32-bit integer (0 to 4294967295)."""
        _check_int_bounds("uint32", value, UINT32_MIN, UINT32_MAX)
        return self._pack_write("I", value, endian, name=name, desc=desc)

    def write_int32(self, value: int, endian: EndianType = None, name: str = "", desc: str = "") -> BinaryWriter:
        """Write a signed 32-bit integer (-2147483648 to 2147483647)."""
        _check_int_bounds("int32", value, INT32_MIN, INT32_MAX)
        return self._pack_write("i", value, endian, name=name, desc=desc)

    def write_uint64(self, value: int, endian: EndianType = None, name: str = "", desc: str = "") -> BinaryWriter:
        """Write an unsigned 64-bit integer (0 to 18446744073709551615)."""
        _check_int_bounds("uint64", value, UINT64_MIN, UINT64_MAX)
        return self._pack_write("Q", value, endian, name=name, desc=desc)

    def write_int64(self, value: int, endian: EndianType = None, name: str = "", desc: str = "") -> BinaryWriter:
        """Write a signed 64-bit integer (-9223372036854775808 to 9223372036854775807)."""
        _check_int_bounds("int64", value, INT64_MIN, INT64_MAX)
        return self._pack_write("q", value, endian, name=name, desc=desc)

    # --- Floating Point, Boolean, and Raw Bytes Methods ---

    def write_float32(self, value: float, endian: EndianType = None, name: str = "", desc: str = "") -> BinaryWriter:
        """Write a 32-bit single-precision IEEE 754 floating point number."""
        if not isinstance(value, (float, int)):
            raise TypeError(f"write_float32 requires a float or int, got {type(value).__name__}")
        return self._pack_write("f", float(value), endian, name=name, desc=desc)

    def write_float64(self, value: float, endian: EndianType = None, name: str = "", desc: str = "") -> BinaryWriter:
        """Write a 64-bit double-precision IEEE 754 floating point number."""
        if not isinstance(value, (float, int)):
            raise TypeError(f"write_float64 requires a float or int, got {type(value).__name__}")
        return self._pack_write("d", float(value), endian, name=name, desc=desc)

    def write_bool(
        self,
        value: bool,
        size: int = 1,
        endian: EndianType = None,
        name: str = "",
        desc: str = "",
        struct_name: Optional[str] = None,
        struct_doc: Optional[str] = None,
    ) -> BinaryWriter:
        """Write a boolean value with configurable byte size (default 1 byte)."""
        if not isinstance(size, int) or size <= 0:
            raise ValueError(f"Bool size must be a positive integer, got {size}")
        order = normalize_endian(endian, self._default_endian)
        offset = self.tell()
        bool_int = 1 if value else 0
        if size == 1:
            data = b"\x01" if value else b"\x00"
        elif size == 2:
            data = struct.pack(f"{order.value}H", bool_int)
        elif size == 4:
            data = struct.pack(f"{order.value}I", bool_int)
        elif size == 8:
            data = struct.pack(f"{order.value}Q", bool_int)
        else:
            byteorder = "little" if order == Endian.LITTLE else "big"
            data = bool_int.to_bytes(size, byteorder=byteorder)
        self._stream.write(data)
        type_str = "Bool" if size == 1 else f"Bool[{size}]"
        self._record_entry(
            offset=offset,
            size=size,
            type_name=type_str,
            value=bool(value),
            name=name,
            endian=order.name.capitalize() if size > 1 else "-",
            description=desc,
            struct_name=struct_name,
            struct_doc=struct_doc,
        )
        return self

    def write_bytes(self, data: Union[bytes, bytearray, memoryview], name: str = "", desc: str = "") -> BinaryWriter:
        """Write a sequence of raw bytes directly to the stream."""
        if not isinstance(data, (bytes, bytearray, memoryview)):
            raise TypeError(f"write_bytes requires bytes-like object, got {type(data).__name__}")
        raw = bytes(data)
        offset = self.tell()
        self._stream.write(raw)
        self._record_entry(
            offset=offset,
            size=len(raw),
            type_name=f"Bytes[{len(raw)}]",
            value=raw,
            name=name,
            endian="-",
            description=desc,
        )
        return self

    # --- String Serialization Methods ---

    def write_cstring(self, text: str, encoding: str = "utf-8", name: str = "", desc: str = "") -> BinaryWriter:
        """Write a null-terminated string (C-string).
        Args:
            text: The string to write.
            encoding: Character encoding (default 'utf-8').
            name: Optional field label for manual generation.
            desc: Optional description for manual generation.
        """
        if not isinstance(text, str):
            raise TypeError(f"write_cstring requires str, got {type(text).__name__}")
        encoded = text.encode(encoding) + b"\x00"
        offset = self.tell()
        self._stream.write(encoded)
        self._record_entry(
            offset=offset,
            size=len(encoded),
            type_name="CString",
            value=text,
            name=name,
            endian="-",
            description=desc,
        )
        return self

    def write_prefixed_string(
        self,
        text: str,
        prefix_bytes: int = 2,
        encoding: str = "utf-8",
        endian: EndianType = None,
        name: str = "",
        desc: str = "",
    ) -> BinaryWriter:
        """Write a length-prefixed string (Pascal-style).

        Args:
            text: The string to write.
            prefix_bytes: Number of bytes for length prefix (1, 2, 4, or 8).
            encoding: Character encoding (default 'utf-8').
            endian: Endianness for multi-byte length prefix.
            name: Optional field label for manual.
            desc: Optional description for manual.
        """
        if not isinstance(text, str):
            raise TypeError(f"write_prefixed_string requires str, got {type(text).__name__}")
        encoded = text.encode(encoding)
        length = len(encoded)
        offset = self.tell()

        if prefix_bytes == 1:
            self._stream.write(struct.pack("B", length))
        elif prefix_bytes == 2:
            order = normalize_endian(endian, self._default_endian)
            self._stream.write(struct.pack(f"{order.value}H", length))
        elif prefix_bytes == 4:
            order = normalize_endian(endian, self._default_endian)
            self._stream.write(struct.pack(f"{order.value}I", length))
        elif prefix_bytes == 8:
            order = normalize_endian(endian, self._default_endian)
            self._stream.write(struct.pack(f"{order.value}Q", length))
        else:
            raise ValueError(f"Unsupported prefix_bytes: {prefix_bytes}. Expected 1, 2, 4, or 8")

        self._stream.write(encoded)
        order = normalize_endian(endian, self._default_endian)
        self._record_entry(
            offset=offset,
            size=prefix_bytes + length,
            type_name=f"PrefixedString[{prefix_bytes}]",
            value=text,
            name=name,
            endian=order.name.capitalize(),
            description=desc,
        )
        return self

    def write_fixed_string(
        self,
        text: str,
        length: int,
        encoding: str = "utf-8",
        pad_byte: bytes = b"\x00",
        truncate: bool = False,
        name: str = "",
        desc: str = "",
    ) -> BinaryWriter:
        """Write a string into a fixed-length byte buffer, padding or truncating as needed."""
        if not isinstance(text, str):
            raise TypeError(f"write_fixed_string requires str, got {type(text).__name__}")
        if not isinstance(pad_byte, (bytes, bytearray)) or len(pad_byte) != 1:
            raise ValueError("pad_byte must be a single byte (e.g. b'\\x00' or b' ')")
        if length < 0:
            raise ValueError(f"length must be non-negative, got {length}")

        encoded = text.encode(encoding)
        if len(encoded) > length:
            if truncate:
                encoded = encoded[:length]
            else:
                raise ValueError(
                    f"Encoded string length ({len(encoded)} bytes) exceeds fixed length ({length} bytes)"
                )

        padding = bytes(pad_byte) * (length - len(encoded))
        offset = self.tell()
        self._stream.write(encoded + padding)
        self._record_entry(
            offset=offset,
            size=length,
            type_name=f"FixedString[{length}]",
            value=text,
            name=name,
            endian="-",
            description=desc,
        )
        return self

    def write_string(
        self,
        text: str,
        encoding: str = "utf-8",
        strategy: str = "null_terminated",
        prefix_bytes: int = 2,
        length: Optional[int] = None,
        pad_byte: bytes = b"\x00",
        endian: EndianType = None,
        name: str = "",
        desc: str = "",
    ) -> BinaryWriter:
        """Convenience method to write strings with various strategies."""
        norm_strategy = strategy.lower().replace("-", "_")
        if norm_strategy in ("null_terminated", "cstring", "c_string"):
            return self.write_cstring(text, encoding=encoding, name=name, desc=desc)
        if norm_strategy in ("prefixed", "pascal", "length_prefixed"):
            return self.write_prefixed_string(
                text, prefix_bytes=prefix_bytes, encoding=encoding, endian=endian, name=name, desc=desc
            )
        if norm_strategy in ("fixed", "fixed_length"):
            if length is None:
                raise ValueError("length is required when strategy is 'fixed'")
            return self.write_fixed_string(
                text, length=length, encoding=encoding, pad_byte=pad_byte, name=name, desc=desc
            )
        raise ValueError(f"Unknown string strategy: {strategy!r}")

    # --- Cursor Positioning, Seeking, and Alignment ---

    def tell(self) -> int:
        """Get the current cursor position in bytes.

        Raises:
            io.UnsupportedOperation: If the underlying stream does not support tell.
        """
        return self._stream.tell()

    def seek(self, offset: int, whence: int = io.SEEK_SET) -> int:
        """Seek to a byte offset in the stream.

        Args:
            offset: The byte offset to seek to.
            whence: io.SEEK_SET (0), io.SEEK_CUR (1), or io.SEEK_END (2).

        Returns:
            The new absolute cursor position.

        Raises:
            io.UnsupportedOperation: If the underlying stream is not seekable.
        """
        if hasattr(self._stream, "seekable") and not self._stream.seekable():
            raise io.UnsupportedOperation("Underlying stream is not seekable")
        return self._stream.seek(offset, whence)

    def pad(self, count: int, pad_byte: bytes = b"\x00", name: str = "padding", desc: str = "") -> BinaryWriter:
        """Write a number of padding bytes."""
        if not isinstance(count, int) or count < 0:
            raise ValueError(f"pad count must be a non-negative integer, got {count}")
        if not isinstance(pad_byte, (bytes, bytearray)) or len(pad_byte) != 1:
            raise ValueError("pad_byte must be a single byte (e.g. b'\\x00')")
        if count > 0:
            offset = self.tell()
            self._stream.write(bytes(pad_byte) * count)
            self._record_entry(
                offset=offset,
                size=count,
                type_name=f"Padding[{count}]",
                value=bytes(pad_byte) * count,
                name=name,
                endian="-",
                description=desc,
            )
        return self

    def align(self, boundary: int, pad_byte: bytes = b"\x00", name: str = "align", desc: str = "") -> BinaryWriter:
        """Align cursor position to a byte boundary by writing padding bytes if needed."""
        if not isinstance(boundary, int) or boundary <= 0:
            raise ValueError(f"boundary must be a positive integer, got {boundary}")

        pos = self.tell()
        rem = pos % boundary
        if rem != 0:
            padding_needed = boundary - rem
            self.pad(padding_needed, pad_byte=pad_byte, name=name, desc=desc or f"Align to {boundary}B boundary")
        return self

    def write_offset_table(
        self,
        count: int,
        offset_size: int = 4,
        endian: EndianType = None,
        name: str = "offsets",
        desc: str = "Offset Table",
        base_offset: Union[int, Any] = 0,
        repeat: Optional[Union[int, str, bool]] = None,
        spec_count: Optional[Union[int, str, bool]] = None,
    ) -> OffsetTableHandle:
        """Reserve an offset table for `count` entries of `offset_size` bytes each.

        Returns an OffsetTableHandle whose methods (write_offset, set_offset, write_target)
        can be used to fill in target offsets later.

        Args:
            count: Number of offset entries in the table.
            offset_size: Byte size of each offset (1, 2, 4, or 8 bytes, default: 4).
            endian: Endianness for offset values (default: writer's default endian).
            name: Base name for the table entries (e.g. 'file_offsets').
            desc: Description of the offset table.
            base_offset: The base origin (in bytes) subtracted from recorded target offsets
                         (default: 0, file/stream beginning).
            repeat: Backward-compatible alias for `spec_count`.
            spec_count: Optional specification count metadata, e.g. 'num_chunk', count, or -1.
                        When specified, manual generation aggregates the table slots into a template.

        Returns:
            OffsetTableHandle for recording/writing target offsets.
        """
        if count < 0:
            raise ValueError(f"count must be non-negative, got {count}")
        if offset_size not in (1, 2, 4, 8):
            raise ValueError(f"offset_size must be 1, 2, 4, or 8, got {offset_size}")
        resolve_fn = getattr(base_offset, "resolve", None)
        if callable(resolve_fn):
            base_offset = resolve_fn(self.tell(), self.tell())
        if base_offset < 0:
            raise ValueError(f"base_offset must be non-negative, got {base_offset}")

        spec_rep = spec_count if spec_count is not None else repeat
        if spec_rep is None and self._current_caption_repeat is not None:
            spec_rep = self._current_caption_repeat

        order = normalize_endian(endian, self._default_endian)
        start_pos = self.tell()
        fmt_map = {1: "UInt8", 2: "UInt16", 4: "UInt32", 8: "UInt64"}
        type_name = f"Offset[{fmt_map.get(offset_size, f'UInt{offset_size*8}')}]"

        entry_indices: list[int] = []
        for i in range(count):
            slot_pos = self.tell()
            self._stream.write(b"\x00" * offset_size)
            idx = len(self._entries)
            self._record_entry(
                offset=slot_pos,
                size=offset_size,
                type_name=type_name,
                value=0,
                name=f"{name}[{i}]",
                endian=order.name.capitalize(),
                description=f"{desc} [#{i}]" if desc else f"Offset entry {i}",
            )
            if spec_rep is not None:
                self._entries[idx].caption_repeat = spec_rep
                if not self._entries[idx].caption:
                    self._entries[idx].caption = name
                    self._entries[idx].caption_desc = desc
            entry_indices.append(idx)

        return OffsetTableHandle(
            writer=self,
            start_offset=start_pos,
            count=count,
            offset_size=offset_size,
            endian=order,
            entry_indices=entry_indices,
            name=name,
            base_offset=base_offset,
        )

    def _normalize_candidates(self, candidates: Union[list, dict, tuple]) -> list[tuple[Any, type, str]]:
        """Normalize candidate structs into [(tag, struct_cls, description), ...]."""
        norm_variants: list[tuple[Any, type, str]] = []
        if isinstance(candidates, dict):
            for k, v in candidates.items():
                if isinstance(v, tuple) and len(v) >= 2:
                    norm_variants.append((k, v[0], str(v[1])))
                elif isinstance(v, type):
                    norm_variants.append((k, v, getattr(v, "__doc__", "") or ""))
                else:
                    raise TypeError(f"Invalid candidate type in candidates dict: {v!r}")
        elif isinstance(candidates, (list, tuple)):
            for i, item in enumerate(candidates):
                if isinstance(item, tuple) and len(item) == 3:
                    norm_variants.append(item)
                elif isinstance(item, tuple) and len(item) == 2:
                    norm_variants.append((item[0], item[1], getattr(item[1], "__doc__", "") or ""))
                elif isinstance(item, type):
                    norm_variants.append((i, item, getattr(item, "__doc__", "") or ""))
                else:
                    raise TypeError(f"Invalid candidate entry in candidates: {item!r}")
        else:
            raise TypeError(f"candidates must be a list, dict, or tuple, got {type(candidates).__name__}")
        return norm_variants

    def write_struct(
        self,
        instance: object,
        endian: EndianType = None,
        section: str = "",
        repeat: Optional[Union[int, str, bool]] = None,
        desc: str = "",
        spec_count: Optional[Union[int, str, bool]] = None,
    ) -> BinaryWriter:
        """Write a @binary_struct instance to this writer's stream.

        Args:
            instance: An instance of a class decorated with @binary_struct.
            endian: Optional endianness override for this struct write.
            section: Optional section name (default: "").
            repeat: Optional repetition count or specifier (e.g. 5, "chunk_count", True).
            desc: Optional section description if section is provided.
            spec_count: Optional specification count metadata (alias for repeat).
        """
        rep_val = spec_count if spec_count is not None else repeat
        if section:
            if (
                self._current_caption != section
                or self._current_caption_repeat != rep_val
                or (desc and self._current_caption_desc != desc)
            ):
                self.caption(title=section, desc=desc, repeat=rep_val)
        elif rep_val is not None:
            if self._current_caption is None:
                self.caption(title=instance.__class__.__name__, desc=desc, repeat=rep_val)
            else:
                self._current_caption_repeat = rep_val

        if self._expected_variant is not None:
            expected = self._expected_variant
            allowed_classes = tuple(c[1] for c in expected["variants"])
            target_obj = getattr(instance, "value", instance) if hasattr(instance, "value") and type(instance).__name__ == "Variant" else instance
            if not isinstance(target_obj, allowed_classes):
                names = [c.__name__ for c in allowed_classes]
                raise TypeError(
                    f"Value '{target_obj}' of type '{type(target_obj).__name__}' is not in expected variant candidates: {names}"
                )
            tag_field = expected.get("tag_field")
            orig_candidates = expected.get("candidates_input")
            if tag_field and (isinstance(orig_candidates, dict) or (isinstance(orig_candidates, (list, tuple)) and orig_candidates and isinstance(orig_candidates[0], tuple))):
                matching_tag = None
                for tag, cls, _ in expected["variants"]:
                    if isinstance(target_obj, cls):
                        matching_tag = tag
                        break
                if matching_tag is not None:
                    for entry in reversed(self._entries):
                        if getattr(entry, "name", None) == tag_field:
                            if entry.value != matching_tag:
                                raise ValueError(
                                    f"Tag mismatch for variant '{expected.get('name')}': "
                                    f"field '{tag_field}' has value {entry.value}, but candidate "
                                    f"'{type(target_obj).__name__}' expects tag {matching_tag}"
                                    )
                            break
            self._expected_variant = None

        s_cls = instance.__class__
        if s_cls not in self._struct_classes:
            self._struct_classes.append(s_cls)
        self._elements_log.append(("struct", s_cls))

        from binary_master.binary_struct import write_struct
        write_struct(instance, writer=self, endian=endian)
        return self

    def write_variant(
        self,
        data: Any,
        candidates: Union[list, dict, tuple],
        tag_field: Optional[str] = None,
        name: str = "",
        desc: str = "",
        condition: Optional[str] = None,
        endian: EndianType = None,
        section: str = "",
        repeat: Optional[Union[int, str, bool]] = None,
    ) -> BinaryWriter:
        """Write a polymorphic variant struct to the stream while validating against candidate types.

        Registers the complete set of candidate variant structures for specification
        documentation and multi-language C/C++/C#/Go/Rust code export.

        Args:
            data: The struct instance to write.
            candidates: Allowed candidate struct types. Supported formats:
                        - list of struct classes: [StatusPayload, SensorPayload]
                        - dict of {tag: struct_class}: {0x01: StatusPayload, 0x02: SensorPayload}
                        - dict of {tag: (struct_class, desc)}
                        - list of tuples: [(0x01, StatusPayload, "desc"), ...]
            tag_field: Optional name of the tag/discriminator field preceding this variant.
            name: Logical name of this variant field/slot (e.g. 'payload').
            desc: Optional description for this variant field.
            condition: Optional condition string for the variant branch.
            endian: Optional endianness override.
            section: Optional section name (default: "").
            repeat: Optional repetition count or specifier (e.g. 5, "chunk_count", True).

        Returns:
            self for method chaining.

        Raises:
            TypeError: If data is not an instance of one of the allowed candidate classes.
            ValueError: If tag_field is provided, candidates specifies tags, and a previously
                        written field with name tag_field does not match data's expected tag.
        """
        if section:
            if (
                self._current_caption != section
                or self._current_caption_repeat != repeat
                or (desc and self._current_caption_desc != desc)
            ):
                self.caption(title=section, desc=desc, repeat=repeat)
        elif repeat is not None:
            target_cls = getattr(data, "__class__", None)
            c_name = target_cls.__name__ if target_cls else "Variant"
            if self._current_caption is None:
                self.caption(title=c_name, desc=desc, repeat=repeat)
            else:
                self._current_caption_repeat = repeat

        norm_variants = self._normalize_candidates(candidates)
        allowed_classes = tuple(c[1] for c in norm_variants)
        target_obj = getattr(data, "value", data) if hasattr(data, "value") and type(data).__name__ == "Variant" else data

        if not isinstance(target_obj, allowed_classes):
            names = [c.__name__ for c in allowed_classes]
            raise TypeError(
                f"Value '{target_obj}' of type '{type(target_obj).__name__}' is not in variant candidates: {names}"
            )

        if tag_field and (isinstance(candidates, dict) or (isinstance(candidates, (list, tuple)) and candidates and isinstance(candidates[0], tuple))):
            matching_tag = None
            for tag, cls, _ in norm_variants:
                if isinstance(target_obj, cls):
                    matching_tag = tag
                    break
            if matching_tag is not None:
                for entry in reversed(self._entries):
                    if getattr(entry, "name", None) == tag_field:
                        if entry.value != matching_tag:
                            raise ValueError(
                                f"Tag mismatch for variant '{name or type(target_obj).__name__}': "
                                f"field '{tag_field}' has value {entry.value}, but candidate "
                                f"'{type(target_obj).__name__}' expects tag {matching_tag}"
                            )
                        break

        variant_name = name or f"{type(target_obj).__name__}Variant"
        if self._current_caption is None:
            self.caption(variant_name, desc=desc, variants=norm_variants, repeat=repeat)
        else:
            self._current_caption_variants = norm_variants
            if repeat is not None:
                self._current_caption_repeat = repeat

        v_info = {
            "name": variant_name,
            "tag_field": tag_field or "tag",
            "variants": norm_variants,
            "desc": desc,
            "condition": condition,
        }
        self._variants.append(v_info)
        self._elements_log.append(("choice", v_info))
        for _, cls, _ in norm_variants:
            if cls not in self._struct_classes:
                self._struct_classes.append(cls)

        from binary_master.binary_struct import write_struct
        write_struct(target_obj, writer=self, endian=endian, desc=desc, parent_field_name=name)
        return self

    def variant(
        self,
        candidates: Union[list, dict, tuple],
        tag_field: Optional[str] = None,
        name: str = "",
        desc: str = "",
        condition: Optional[str] = None,
    ) -> BinaryWriter:
        """Register expected candidate variant structures for upcoming writes and documentation.

        If set, the next call to write_struct will validate that the struct is one of the candidates.

        Args:
            candidates: Allowed candidate struct types (list, dict, or list of tuples).
            tag_field: Optional name of the tag/discriminator field preceding this variant.
            name: Logical name of this variant field/slot (e.g. 'payload').
            desc: Optional description for this variant field.
            condition: Optional condition string.

        Returns:
            self for method chaining.
        """
        norm_variants = self._normalize_candidates(candidates)
        variant_name = name or "VariantChoice"
        if self._current_caption is None:
            self.caption(variant_name, desc=desc, variants=norm_variants)
        else:
            self._current_caption_variants = norm_variants

        self._expected_variant = {
            "name": variant_name,
            "tag_field": tag_field or "tag",
            "variants": norm_variants,
            "desc": desc,
            "condition": condition,
            "candidates_input": candidates,
        }
        self._variants.append(self._expected_variant)
        self._elements_log.append(("choice", self._expected_variant))
        for _, cls, _ in norm_variants:
            if cls not in self._struct_classes:
                self._struct_classes.append(cls)
        return self

    expect = variant

    def to_builder(
        self,
        title: str = "Binary Protocol",
        default_endian: Optional[str] = None,
        version: Optional[str] = None,
        description: str = "",
    ) -> Any:
        """Convert this BinaryWriter and its recorded layout/variants into a BinaryBuilder schema."""
        from binary_master.builder import Builder
        resolved_endian = default_endian or (
            "little" if self.default_endian == Endian.LITTLE else "big"
        )
        builder = Builder(
            title=title,
            default_endian=resolved_endian,
            version=version,
            description=description,
        )

        if not self._struct_classes and not self._variants:
            builder.import_writer(self, include_fields=True)
            return builder

        seen_sections: set[str] = set()
        seen_structs: set[type] = set()
        seen_choices: set[str] = set()

        choice_variants: set[type] = set()
        for v in self._variants:
            for _, v_cls, _ in v.get("variants", []):
                choice_variants.add(v_cls)

        for item in self._elements_log:
            kind = item[0]
            if kind == "section":
                sec_title, s_desc = item[1], item[2]
                sec_repeat = item[3] if len(item) > 3 else None
                if sec_title not in seen_sections:
                    seen_sections.add(sec_title)
                    builder.add_section(sec_title, desc=s_desc, repeat=sec_repeat)
            elif kind == "struct":
                s_cls = item[1]
                if s_cls not in seen_structs and s_cls not in choice_variants:
                    seen_structs.add(s_cls)
                    builder.add_struct(s_cls)
            elif kind == "choice":
                v_info = item[1]
                v_name = v_info.get("name") or "PayloadChoice"
                if v_name not in seen_choices:
                    seen_choices.add(v_name)
                    builder.add_choice(
                        name=v_name,
                        tag_field=v_info.get("tag_field") or "tag",
                        variants=v_info.get("variants", []),
                        desc=v_info.get("desc", ""),
                        condition=v_info.get("condition"),
                    )

        return builder

    def to_markdown(self, **kwargs: Any) -> str:
        """Generate a complete Markdown specification manual from this writer."""
        from binary_master.manual import generate_manual
        return generate_manual(self, **kwargs)

    def write_markdown(self, path_or_file: Union[str, Path, IO[str]], **kwargs: Any) -> str:
        """Generate specification markdown and write it to a file or stream."""
        content = self.to_markdown(**kwargs)
        if isinstance(path_or_file, (str, Path)):
            Path(path_or_file).write_text(content, encoding="utf-8")
        elif hasattr(path_or_file, "write"):
            path_or_file.write(content)
        else:
            raise TypeError(f"Invalid path_or_file: {type(path_or_file).__name__}")
        return content

    def to_c_header(self, guard: Optional[str] = None, pack: bool = True) -> str:
        """Generate a C99/C11 header file from this writer's recorded structures and variants."""
        return self.to_builder().to_c_header(guard=guard, pack=pack)

    def write_c_header(
        self,
        path_or_file: Optional[Union[str, Path, IO[str]]] = None,
        guard: Optional[str] = None,
        pack: bool = True,
    ) -> str:
        """Generate C header and write it to a file or stream."""
        return self.to_builder().write_c_header(path_or_file=path_or_file, guard=guard, pack=pack)

    def to_rust(self) -> str:
        """Generate Rust code from this writer's recorded structures and variants."""
        return self.to_builder().to_rust()

    def write_rust(self, path_or_file: Optional[Union[str, Path, IO[str]]] = None) -> str:
        """Generate Rust code and write to file."""
        return self.to_builder().write_rust(path_or_file=path_or_file)

    def to_cpp(self) -> str:
        """Generate C++ code from this writer's recorded structures and variants."""
        return self.to_builder().to_cpp()

    def write_cpp(self, path_or_file: Optional[Union[str, Path, IO[str]]] = None) -> str:
        """Generate C++ code and write to file."""
        return self.to_builder().write_cpp(path_or_file=path_or_file)

    def to_csharp(self, namespace: str = "BinaryProtocol") -> str:
        """Generate C# code from this writer's recorded structures and variants."""
        return self.to_builder().to_csharp(namespace=namespace)

    def write_csharp(
        self,
        path_or_file: Optional[Union[str, Path, IO[str]]] = None,
        namespace: str = "BinaryProtocol",
    ) -> str:
        """Generate C# code and write to file."""
        return self.to_builder().write_csharp(path_or_file=path_or_file, namespace=namespace)

    def to_go(self, package_name: str = "protocol") -> str:
        """Generate Go code from this writer's recorded structures and variants."""
        return self.to_builder().to_go(package_name=package_name)

    def write_go(
        self,
        path_or_file: Optional[Union[str, Path, IO[str]]] = None,
        package_name: str = "protocol",
    ) -> str:
        """Generate Go code and write to file."""
        return self.to_builder().write_go(path_or_file=path_or_file, package_name=package_name)

    def to_code(self, lang: str, **kwargs: Any) -> str:
        """Generate code in the specified language ('c', 'rust', 'cpp', 'csharp', 'go')."""
        return self.to_builder().to_code(lang=lang, **kwargs)

    def write_code(
        self,
        path_or_file: Union[str, Path, IO[str]],
        lang: Optional[str] = None,
        **kwargs: Any,
    ) -> str:
        """Generate code in the target language and write to file."""
        return self.to_builder().write_code(path_or_file=path_or_file, lang=lang, **kwargs)


class OffsetTableHandle:
    """Handle returned by BinaryWriter.write_offset_table.

    Allows setting or writing target offsets into the reserved offset table slots.
    """

    def __init__(
        self,
        writer: BinaryWriter,
        start_offset: int,
        count: int,
        offset_size: int,
        endian: Endian,
        entry_indices: list[int],
        name: str = "offsets",
        base_offset: int = 0,
    ):
        self._writer = writer
        self._start_offset = start_offset
        self._count = count
        self._offset_size = offset_size
        self._endian = endian
        self._entry_indices = entry_indices
        self._name = name
        self._base_offset = base_offset
        self._offsets: list[Optional[int]] = [None] * count
        self._targets: list[Any] = []

    @property
    def count(self) -> int:
        return self._count

    @property
    def offset_size(self) -> int:
        return self._offset_size

    @property
    def base_offset(self) -> int:
        """The base offset (origin) from which target offsets are calculated."""
        return self._base_offset

    def get_target_offset(self, index: int) -> Optional[int]:
        """Get the absolute target offset recorded for slot `index`."""
        if index < 0 or index >= self._count:
            raise IndexError(f"OffsetTable index {index} out of range (count={self._count})")
        return self._offsets[index]

    def get_stored_offset(self, index: int) -> Optional[int]:
        """Get the stored relative offset value (target - base) for slot `index`."""
        target = self.get_target_offset(index)
        if target is None:
            return None
        return target - self._base_offset

    def __len__(self) -> int:
        return self._count

    def __getitem__(self, index: int) -> Optional[int]:
        if index < 0 or index >= self._count:
            raise IndexError(f"OffsetTable index {index} out of range (count={self._count})")
        return self._offsets[index]

    def __setitem__(self, index: int, target_offset: int) -> None:
        self.set_offset(index, target_offset)

    def set_offset(self, index: int, target_offset: Optional[int] = None) -> int:
        """Set the target offset at slot `index`.

        If target_offset is None, automatically sets it to the current stream position (writer.tell()).
        Writes the value (target_offset - base_offset) into the binary stream placeholder and updates
        the manual layout entry.

        Returns:
            The stored relative offset value (target_offset - base_offset).
        """
        if index < 0 or index >= self._count:
            raise IndexError(f"OffsetTable index {index} out of range (count={self._count})")

        if target_offset is None:
            target_offset = self._writer.tell()

        stored_value = target_offset - self._base_offset
        if stored_value < 0:
            raise ValueError(
                f"Calculated offset {stored_value} is negative (target={target_offset}, base={self._base_offset})"
            )

        self._offsets[index] = target_offset
        slot_pos = self._start_offset + index * self._offset_size

        fmt_map = {1: "B", 2: "H", 4: "I", 8: "Q"}
        fmt_char = fmt_map.get(self._offset_size)
        if not fmt_char:
            raise ValueError(f"Unsupported offset_size: {self._offset_size}. Must be 1, 2, 4, or 8.")

        packed = struct.pack(f"{self._endian.value}{fmt_char}", stored_value)
        cur_pos = self._writer.tell()
        self._writer.seek(slot_pos)
        self._writer._stream.write(packed)
        self._writer.seek(cur_pos)

        if hasattr(self._writer, "_entries") and index < len(self._entry_indices):
            entry_idx = self._entry_indices[index]
            if 0 <= entry_idx < len(self._writer._entries):
                entry = self._writer._entries[entry_idx]
                entry.value = stored_value
                entry.target_offset = target_offset

        return stored_value

    def write_offset(self, index: int, target_offset: Optional[int] = None) -> int:
        """Write the offset into slot `index` (synonym for set_offset)."""
        return self.set_offset(index, target_offset)

    def write_target(self, index: int, target: Any) -> Any:
        """Record current offset into slot `index`, then serialize and write `target`."""
        pos = self._writer.tell()
        self.set_offset(index, pos)
        if hasattr(target, "__binary__"):
            self._writer.write_struct(target)
        elif isinstance(target, (bytes, bytearray)):
            self._writer.write_bytes(target)
        elif callable(target):
            target(self._writer)
        else:
            raise TypeError(f"Cannot write target of type {type(target).__name__}")
        return pos


Writer = BinaryWriter

