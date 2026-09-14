"""Rust code generator for binary_master schemas and structs."""

from __future__ import annotations

import inspect
from pathlib import Path
from typing import (
    Any,
    IO,
    List,
    Optional,
    Set,
    Tuple,
    Union,
    get_args,
    get_origin,
    Annotated,
)

from binary_master.binary_struct import (
    FixedArray,
    Float32,
    Float64,
    Int8,
    Int16,
    Int32,
    Int64,
    Offset,
    OffsetTable,
    UInt8,
    UInt16,
    UInt32,
    UInt64,
    Bool,
)
from binary_master.code_gen.c import to_pascal_case, to_snake_case


def rust_type_of(field_type: Any) -> Tuple[str, Optional[str]]:
    """Determine the Rust type and optional documentation note."""
    if get_origin(field_type) is Annotated:
        args = get_args(field_type)
        return rust_type_of(args[0])

    if field_type is UInt8:
        return "u8", None
    if field_type is UInt16:
        return "u16", None
    if field_type is UInt32:
        return "u32", None
    if field_type is UInt64:
        return "u64", None
    if field_type is Int8:
        return "i8", None
    if field_type is Int16:
        return "i16", None
    if field_type is Int32:
        return "i32", None
    if field_type is Int64:
        return "i64", None
    if field_type is Float32:
        return "f32", None
    if field_type is Float64:
        return "f64", None
    if field_type is bool or field_type is Bool or (isinstance(field_type, type) and issubclass(field_type, Bool)):
        size = getattr(field_type, "_size", 1) if field_type is not bool else 1
        if size == 1:
            return "bool", None
        elif size == 2:
            return "u16", "2-byte boolean"
        elif size == 4:
            return "u32", "4-byte boolean"
        elif size == 8:
            return "u64", "8-byte boolean"
        else:
            return f"[u8; {size}]", f"{size}-byte boolean"

    from binary_master.binary_struct import Bytes, FixedString, CString, PrefixedString
    if isinstance(field_type, type) and issubclass(field_type, Bytes):
        return f"[u8; {field_type._size}]", "raw bytes"
    if isinstance(field_type, type) and issubclass(field_type, FixedString):
        return f"[u8; {field_type._size}]", "fixed-length string"
    if field_type is CString or (isinstance(field_type, type) and issubclass(field_type, CString)):
        return "*const std::os::raw::c_char", "null-terminated string"
    if field_type is PrefixedString or (isinstance(field_type, type) and issubclass(field_type, PrefixedString)):
        p_bytes = getattr(field_type, "prefix_bytes", 1)
        return "*const std::os::raw::c_char", f"prefixed string ({p_bytes}-byte length prefix)"

    # FixedArray[Elem, Count]
    is_fixed = (isinstance(field_type, tuple) and len(field_type) >= 3 and field_type[0] is FixedArray) or (
        get_origin(field_type) is FixedArray
    )
    if is_fixed:
        if isinstance(field_type, tuple):
            elem_t = field_type[1]
            cnt = field_type[2]
        else:
            args = get_args(field_type)
            elem_t = args[0]
            cnt = args[1]
        elem_rs, _ = rust_type_of(elem_t)
        return f"[{elem_rs}; {cnt}]", None

    # Offset[Target, Size, Base]
    is_offset = (isinstance(field_type, tuple) and len(field_type) >= 1 and field_type[0] is Offset) or (
        get_origin(field_type) is Offset
    )
    if is_offset:
        target_name = "Target"
        offset_t = UInt32
        if isinstance(field_type, tuple):
            if len(field_type) >= 2:
                target_name = getattr(field_type[1], "__name__", str(field_type[1]))
            if len(field_type) >= 3:
                offset_t = field_type[2]
        else:
            args = get_args(field_type)
            if len(args) >= 1:
                target_name = getattr(args[0], "__name__", str(args[0]))
            if len(args) >= 2 and args[1] in (UInt8, UInt16, UInt32, UInt64):
                offset_t = args[1]

        rs_name, _ = rust_type_of(offset_t)
        return rs_name, f"Offset to {target_name}"

    # OffsetTable[Count, Type, Base]
    is_offset_tbl = (isinstance(field_type, tuple) and len(field_type) >= 1 and field_type[0] is OffsetTable) or (
        get_origin(field_type) is OffsetTable
    )
    if is_offset_tbl:
        count = 0
        offset_t = UInt32
        if isinstance(field_type, tuple):
            if len(field_type) >= 2:
                count = field_type[1]
            if len(field_type) >= 3:
                offset_t = field_type[2]
        else:
            args = get_args(field_type)
            if len(args) >= 1:
                count = args[0]
            if len(args) >= 2:
                offset_t = args[1]
        rs_name, _ = rust_type_of(offset_t)
        return f"[{rs_name}; {count}]", "Offset table"

    # Nested binary_struct
    if hasattr(field_type, "__binary__"):
        return field_type.__name__, None

    return "u8", None


def _get_type_name(type_obj: Any) -> str:
    """Safely obtain a type's name without raising type-to-string inspection warnings."""
    name = getattr(type_obj, "__name__", None)
    if isinstance(name, str):
        return name
    return type_obj.__class__.__name__


def generate_rust_struct(
    struct_cls: type,
    name: Optional[str] = None,
    desc: str = "",
    condition: Optional[str] = None,
) -> str:
    """Generate Rust struct definition for a @binary_struct class."""
    if not hasattr(struct_cls, "__binary__"):
        raise TypeError(f"Class {_get_type_name(struct_cls)} is not a binary_struct")

    meta: dict[str, Any] = getattr(struct_cls, "__binary__", {})
    cls_name = struct_cls.__name__ if struct_cls else (name or "Struct")
    field_alias = name if (name and name != cls_name) else None
    doc_text = desc or getattr(struct_cls, "__doc__", "") or meta.get("doc", "")

    lines: List[str] = []

    # Rustdoc comments
    if field_alias:
        lines.append(f"/// Logical Name: `{field_alias}`")
    if doc_text:
        for d_line in inspect.cleandoc(doc_text).splitlines():
            lines.append(f"/// {d_line}")
    elif not field_alias:
        lines.append(f"/// `{cls_name}` binary structure.")
    if condition:
        lines.append(f"///\n/// **Condition**: `{condition}`")

    total_bits = meta.get("bits")
    if isinstance(total_bits, int):
        # Bitfield packed container
        if total_bits <= 8:
            base_type = "u8"
        elif total_bits <= 16:
            base_type = "u16"
        elif total_bits <= 32:
            base_type = "u32"
        else:
            base_type = "u64"

        lines.append("#[repr(C, packed)]")
        lines.append("#[derive(Debug, Clone, Copy, PartialEq, Eq, Default)]")
        lines.append(f"pub struct {cls_name} {{")
        lines.append(f"    pub raw: {base_type},")
        lines.append("}")

        # Methods for bitfields
        lines.append(f"\nimpl {cls_name} {{")
        fields = meta.get("fields", {})
        descriptions = meta.get("descriptions", {})
        shift = 0
        for field_name, field_type in fields.items():
            width = field_type[1] if isinstance(field_type, tuple) and len(field_type) >= 2 else 1
            field_desc = descriptions.get(field_name, "")
            mask = (1 << width) - 1
            method_name = to_snake_case(field_name)
            doc_comment = f"    /// Bits [{shift}:{shift + width - 1}]{': ' + field_desc if field_desc else ''}"
            lines.append(doc_comment)
            lines.append(f"    pub fn {method_name}(&self) -> {base_type} {{")
            lines.append(f"        (self.raw >> {shift}) & 0x{mask:X}")
            lines.append("    }")
            shift += width
        lines.append("}")
    else:
        # Regular packed struct
        lines.append("#[repr(C, packed)]")
        lines.append("#[derive(Debug, Clone, Copy, PartialEq)]")
        lines.append(f"pub struct {cls_name} {{")
        fields = meta.get("fields", {})
        descriptions = meta.get("descriptions", {})

        for field_name, field_type in fields.items():
            rs_type, note = rust_type_of(field_type)
            field_desc = descriptions.get(field_name, "") or note or ""
            f_snake = to_snake_case(field_name)
            if field_desc:
                lines.append(f"    /// {field_desc}")
            lines.append(f"    pub {f_snake}: {rs_type},")

        lines.append("}")

    return "\n".join(lines)


def generate_rust_choice(
    choice_name: str,
    tag_field: Union[str, Any],
    variants: Any,
    desc: str = "",
    condition: Optional[str] = None,
    emitted_structs: Optional[Set[str]] = None,
) -> str:
    """Generate Rust enum tag constants, variant structs, and tagged union for a choice."""
    from binary_master.builder import _normalize_variants

    if emitted_structs is None:
        emitted_structs = set()

    norm_vars = _normalize_variants(variants)
    tag_field_name = tag_field if isinstance(tag_field, str) else "tag"

    # 1. Tag Enum definition
    enum_name = f"{to_pascal_case(choice_name)}Tag"
    lines: List[str] = [
        f"/// Tag values for choice `{choice_name}` (dispatched by `{tag_field_name}`).",
    ]
    if desc:
        lines.append(f"/// {desc}")
    if condition:
        lines.append(f"///\n/// **Condition**: `{condition}`")
    lines.append("#[repr(u16)]")
    lines.append("#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]")
    lines.append(f"pub enum {enum_name} {{")

    for tag, v_cls, v_desc in norm_vars:
        v_cls_name = _get_type_name(v_cls)
        tag_val_str = f"0x{tag:02X}" if isinstance(tag, int) else f"{tag}"
        variant_tag_name = to_pascal_case(v_cls_name)
        if v_desc:
            lines.append(f"    /// {v_desc}")
        lines.append(f"    {variant_tag_name} = {tag_val_str},")
    lines.append("}\n")

    # 2. Emit each variant struct if not already emitted
    for tag, v_cls, v_desc in norm_vars:
        v_cls_name = _get_type_name(v_cls)
        if v_cls_name not in emitted_structs:
            lines.append(generate_rust_struct(v_cls, desc=v_desc))
            lines.append("")
            emitted_structs.add(v_cls_name)

    # 3. Emit Rust Tagged Union Enum
    union_name = f"{to_pascal_case(choice_name)}Union"
    lines.append(f"/// Polymorphic container for choice `{choice_name}`.")
    lines.append("#[derive(Debug, Clone, Copy, PartialEq)]")
    lines.append(f"pub enum {union_name} {{")
    for tag, v_cls, v_desc in norm_vars:
        v_cls_name = _get_type_name(v_cls)
        variant_member = to_pascal_case(v_cls_name)
        lines.append(f"    {variant_member}({v_cls_name}),")
    lines.append("}")

    return "\n".join(lines)


def generate_rust_code(builder: Any) -> str:
    """Generate complete Rust code from a BinaryBuilder instance."""
    from binary_master.builder import (
        ChoiceElement,
        DocumentElement,
        FieldElement,
        SectionElement,
        StructElement,
    )

    title = getattr(builder, "title", "Binary Protocol")
    version = getattr(builder, "version", None)
    elements = getattr(builder, "elements", [])

    lines: List[str] = [
        "//! " + "=" * 76,
        f"//! {title}",
    ]
    if version:
        lines.append(f"//! Version: {version}")
    if getattr(builder, "description", ""):
        for d in builder.description.strip().splitlines():
            lines.append(f"//! {d}")
    lines.append("//! Automatically generated by binary_master.")
    lines.append("//! " + "=" * 76 + "\n")

    lines.append("#![allow(dead_code, non_camel_case_types, non_snake_case)]\n")

    emitted_structs: Set[str] = set()

    for elem in elements:
        if isinstance(elem, DocumentElement):
            lines.append("// " + "=" * 76)
            lines.append(f"// {elem.title}")
            lines.append("// " + "=" * 76)
            for c_line in elem.content.splitlines():
                lines.append(f"// {c_line}" if c_line else "//")
            lines.append("")

        elif isinstance(elem, SectionElement):
            lines.append("// " + "-" * 76)
            lines.append(f"// Section: {elem.title}")
            if elem.desc:
                lines.append(f"// {elem.desc}")
            lines.append("// " + "-" * 76 + "\n")

        elif isinstance(elem, StructElement):
            s_name = elem.struct_cls.__name__
            if s_name not in emitted_structs:
                s_code = generate_rust_struct(
                    elem.struct_cls,
                    name=elem.name,
                    desc=elem.desc,
                    condition=elem.condition,
                )
                lines.append(s_code)
                lines.append("")
                emitted_structs.add(s_name)

        elif isinstance(elem, ChoiceElement):
            c_code = generate_rust_choice(
                choice_name=elem.name,
                tag_field=elem.tag_field,
                variants=elem.variants,
                desc=elem.desc,
                condition=elem.condition,
                emitted_structs=emitted_structs,
            )
            lines.append(c_code)
            lines.append("")

        elif isinstance(elem, FieldElement):
            rs_type, _ = rust_type_of(elem.type_name)
            desc_str = f" // {elem.desc}" if elem.desc else ""
            lines.append(f"// Ad-hoc field: {elem.name} ({elem.type_name}, {elem.size}B){desc_str}\n")

    return "\n".join(lines)


def write_rust(
    builder: Any,
    path_or_file: Optional[Union[str, Path, IO[str]]] = None,
) -> str:
    """Generate Rust code from a BinaryBuilder and optionally save to file."""
    content = generate_rust_code(builder)
    if path_or_file is not None:
        if isinstance(path_or_file, (str, Path)):
            p = Path(path_or_file)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")
        elif hasattr(path_or_file, "write"):
            path_or_file.write(content)
        else:
            raise TypeError(f"Invalid path_or_file: {type(path_or_file).__name__}")
    return content
