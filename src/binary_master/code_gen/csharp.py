"""C# (.NET / Unity) code generator for binary_master schemas and structs."""

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
    Float16,
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
from binary_master.code_gen.c import to_pascal_case


def csharp_type_of(field_type: Any) -> Tuple[str, Optional[int], Optional[str]]:
    """Determine the C# type, array length, and optional comment note."""
    if get_origin(field_type) is Annotated:
        args = get_args(field_type)
        return csharp_type_of(args[0])

    if field_type is UInt8:
        return "byte", None, None
    if field_type is UInt16:
        return "ushort", None, None
    if field_type is UInt32:
        return "uint", None, None
    if field_type is UInt64:
        return "ulong", None, None
    if field_type is Int8:
        return "sbyte", None, None
    if field_type is Int16:
        return "short", None, None
    if field_type is Int32:
        return "int", None, None
    if field_type is Int64:
        return "long", None, None
    if field_type is Float16 or field_type == "Float16":
        return "Half", None, None
    if field_type is Float32:
        return "float", None, None
    if field_type is Float64:
        return "double", None, None
    if field_type is bool or field_type is Bool or (isinstance(field_type, type) and issubclass(field_type, Bool)):
        size = getattr(field_type, "_size", 1) if field_type is not bool else 1
        if size == 1:
            return "bool", None, None
        elif size == 2:
            return "ushort", None, "2-byte boolean"
        elif size == 4:
            return "uint", None, "4-byte boolean"
        elif size == 8:
            return "ulong", None, "8-byte boolean"
        else:
            return "byte", size, f"{size}-byte boolean"

    from binary_master.binary_struct import (
        Bytes,
        FixedString,
        CString,
        PrefixedString,
        MagicBase,
        ConstantBase,
        RangeBase,
        LengthOfBase,
        CountOfBase,
    )
    from binary_master.checksum import ChecksumBase
    from binary_master.varint import VarIntTypeMeta
    import enum

    if isinstance(field_type, type) and issubclass(field_type, RangeBase):
        cs_name, arr_cnt, _ = csharp_type_of(field_type._type)
        return cs_name, arr_cnt, f"Range: [{field_type._min}, {field_type._max}]"

    if isinstance(field_type, type) and issubclass(field_type, LengthOfBase):
        cs_name, arr_cnt, _ = csharp_type_of(field_type._type)
        return cs_name, arr_cnt, f"Length of '{field_type._target_field}'"

    if isinstance(field_type, type) and issubclass(field_type, CountOfBase):
        cs_name, arr_cnt, _ = csharp_type_of(field_type._type)
        return cs_name, arr_cnt, f"Count of '{field_type._target_field}'"

    if isinstance(field_type, type) and issubclass(field_type, MagicBase):
        expected = getattr(field_type, "_value", None)
        if isinstance(expected, bytes):
            return "byte[]", len(expected), f"Magic: {expected!r}"
        else:
            fmt = getattr(field_type, "_fmt", "I")
            cs_map = {"B": "byte", "H": "ushort", "I": "uint", "Q": "ulong"}
            return cs_map.get(fmt, "uint"), None, f"Magic: {getattr(field_type, '_raw_val', '')!r}"

    if isinstance(field_type, type) and issubclass(field_type, ConstantBase):
        t = getattr(field_type, "_type", UInt32)
        val = getattr(field_type, "_value", None)
        cs_name, _, _ = csharp_type_of(t)
        return cs_name, None, f"Constant: {val!r}"

    if isinstance(field_type, type) and issubclass(field_type, ChecksumBase):
        sz = getattr(field_type, "_size", 4)
        cs_map = {1: "byte", 2: "ushort", 4: "uint", 8: "ulong"}
        return cs_map.get(sz, "uint"), None, f"{getattr(field_type, '_algorithm', 'checksum').upper()} Checksum"

    if isinstance(field_type, VarIntTypeMeta):
        return "long" if field_type.is_signed else "ulong", None, "Variable-length integer (LEB128)"

    if isinstance(field_type, tuple) and len(field_type) >= 2 and isinstance(field_type[0], type) and issubclass(field_type[0], enum.Enum):
        cs_name, _, _ = csharp_type_of(field_type[1])
        return cs_name, None, f"Enum: {field_type[0].__name__}"

    if isinstance(field_type, type) and issubclass(field_type, enum.Enum):
        max_v = max([abs(m.value) for m in field_type], default=0)
        cs_name = "byte" if max_v <= 255 else ("ushort" if max_v <= 65535 else "uint")
        return cs_name, None, f"Enum: {field_type.__name__}"

    if isinstance(field_type, type) and issubclass(field_type, Bytes):
        return "byte[]", field_type._size, "raw bytes"
    if isinstance(field_type, type) and issubclass(field_type, FixedString):
        return "string", field_type._size, "fixed-length string"
    if field_type is CString or (isinstance(field_type, type) and issubclass(field_type, CString)):
        return "string", None, "null-terminated string"
    if field_type is PrefixedString or (isinstance(field_type, type) and issubclass(field_type, PrefixedString)):
        p_bytes = getattr(field_type, "prefix_bytes", 1)
        return "string", None, f"prefixed string ({p_bytes}-byte length prefix)"

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
        elem_cs, _, _ = csharp_type_of(elem_t)
        return f"{elem_cs}[]", cnt, None

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

        cs_name, _, _ = csharp_type_of(offset_t)
        return cs_name, None, f"Offset to {target_name}"

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
        cs_name, _, _ = csharp_type_of(offset_t)
        return f"{cs_name}[]", count, "Offset table"

    # Nested binary_struct
    if hasattr(field_type, "__binary__"):
        return field_type.__name__, None, None

    return "byte", None, None


def _get_type_name(type_obj: Any) -> str:
    """Safely obtain a type's name without raising type-to-string inspection warnings."""
    name = getattr(type_obj, "__name__", None)
    if isinstance(name, str):
        return name
    return type_obj.__class__.__name__


def generate_csharp_struct(
    struct_cls: type,
    name: Optional[str] = None,
    desc: str = "",
    condition: Optional[str] = None,
) -> str:
    """Generate C# struct definition for a @binary_struct class."""
    if not hasattr(struct_cls, "__binary__"):
        raise TypeError(f"Class {_get_type_name(struct_cls)} is not a binary_struct")

    meta: dict[str, Any] = getattr(struct_cls, "__binary__", {})
    cls_name = struct_cls.__name__ if struct_cls else (name or "Struct")
    field_alias = name if (name and name != cls_name) else None
    doc_text = desc or getattr(struct_cls, "__doc__", "") or meta.get("doc", "")

    lines: List[str] = ["/// <summary>"]
    if field_alias:
        lines.append(f"/// Logical Name: {field_alias}")
    if doc_text:
        for d_line in inspect.cleandoc(doc_text).splitlines():
            lines.append(f"/// {d_line}")
    elif not field_alias:
        lines.append(f"/// {cls_name} binary structure.")
    if condition:
        lines.append(f"/// Condition: {condition}")
    lines.append("/// </summary>")

    total_bits = meta.get("bits")
    if isinstance(total_bits, int):
        if total_bits <= 8:
            base_type = "byte"
        elif total_bits <= 16:
            base_type = "ushort"
        elif total_bits <= 32:
            base_type = "uint"
        else:
            base_type = "ulong"

        lines.append("[StructLayout(LayoutKind.Sequential, Pack = 1)]")
        lines.append(f"public struct {cls_name} {{")
        lines.append(f"    public {base_type} Raw;")

        fields = meta.get("fields", {})
        descriptions = meta.get("descriptions", {})
        shift = 0
        for field_name, field_type in fields.items():
            width = field_type[1] if isinstance(field_type, tuple) and len(field_type) >= 2 else 1
            field_desc = descriptions.get(field_name, "")
            mask = (1 << width) - 1
            prop_name = to_pascal_case(field_name)
            doc = f"    /// <summary>Bits [{shift}:{shift + width - 1}]{': ' + field_desc if field_desc else ''}</summary>"
            lines.append(doc)
            lines.append(f"    public {base_type} {prop_name} => ({base_type})((Raw >> {shift}) & 0x{mask:X});")
            shift += width

        lines.append("}")
    else:
        lines.append("[StructLayout(LayoutKind.Sequential, Pack = 1)]")
        lines.append(f"public struct {cls_name} {{")
        fields = meta.get("fields", {})
        descriptions = meta.get("descriptions", {})

        for field_name, field_type in fields.items():
            cs_type, arr_cnt, note = csharp_type_of(field_type)
            field_desc = descriptions.get(field_name, "") or note or ""
            prop_name = to_pascal_case(field_name)

            if field_desc:
                lines.append(f"    /// <summary>{field_desc}</summary>")

            if arr_cnt is not None:
                lines.append(f"    [MarshalAs(UnmanagedType.ByValArray, SizeConst = {arr_cnt})]")
                lines.append(f"    public {cs_type} {prop_name};")
            else:
                lines.append(f"    public {cs_type} {prop_name};")

        total_size = meta.get("total_size")
        if total_size is not None:
            try:
                from binary_master.binary_struct import _calculate_field_size
                curr_size = sum(_calculate_field_size(fn, ft, is_cls=True) for fn, ft in fields.items())
                if curr_size < total_size:
                    pad_len = total_size - curr_size
                    lines.append(f"    /// <summary>Struct padding to total size {total_size}</summary>")
                    lines.append(f"    [MarshalAs(UnmanagedType.ByValArray, SizeConst = {pad_len})]")
                    lines.append(f"    public byte[] _Padding;")
            except Exception:
                pass

        lines.append("}")

    return "\n".join(lines)


def generate_csharp_choice(
    choice_name: str,
    tag_field: Union[str, Any],
    variants: Any,
    desc: str = "",
    condition: Optional[str] = None,
    emitted_structs: Optional[Set[str]] = None,
) -> str:
    """Generate C# enum tag and explicit union for a choice."""
    from binary_master.builder import _normalize_variants

    if emitted_structs is None:
        emitted_structs = set()

    norm_vars = _normalize_variants(variants)
    tag_field_name = tag_field if isinstance(tag_field, str) else "tag"

    # 1. Tag Enum definition
    enum_name = f"{to_pascal_case(choice_name)}Tag"
    lines: List[str] = [
        "/// <summary>",
        f"/// Tag values for choice `{choice_name}` (dispatched by `{tag_field_name}`).",
    ]
    if desc:
        lines.append(f"/// {desc}")
    if condition:
        lines.append(f"/// Condition: {condition}")
    lines.append("/// </summary>")
    lines.append(f"public enum {enum_name} : ushort {{")

    for tag, v_cls, v_desc in norm_vars:
        v_cls_name = _get_type_name(v_cls)
        tag_val_str = f"0x{tag:02X}" if isinstance(tag, int) else f"{tag}"
        variant_tag_name = to_pascal_case(v_cls_name)
        if v_desc:
            lines.append(f"    /// <summary>{v_desc}</summary>")
        lines.append(f"    {variant_tag_name} = {tag_val_str},")
    lines.append("}\n")

    # 2. Emit each variant struct if not already emitted
    for tag, v_cls, v_desc in norm_vars:
        v_cls_name = _get_type_name(v_cls)
        if v_cls_name not in emitted_structs:
            lines.append(generate_csharp_struct(v_cls, desc=v_desc))
            lines.append("")
            emitted_structs.add(v_cls_name)

    # 3. Emit C# Explicit Layout Union
    union_name = f"{to_pascal_case(choice_name)}Union"
    lines.append("/// <summary>")
    lines.append(f"/// Polymorphic union container for choice `{choice_name}`.")
    lines.append("/// </summary>")
    lines.append("[StructLayout(LayoutKind.Explicit, Pack = 1)]")
    lines.append(f"public struct {union_name} {{")
    for tag, v_cls, v_desc in norm_vars:
        v_cls_name = _get_type_name(v_cls)
        prop_name = to_pascal_case(v_cls_name)
        lines.append(f"    [FieldOffset(0)] public {v_cls_name} {prop_name};")
    lines.append("}")

    return "\n".join(lines)


def generate_csharp_code(builder: Any, namespace: str = "BinaryProtocol") -> str:
    """Generate complete C# source file from a BinaryBuilder instance."""
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
        "// " + "=" * 76,
        f"// {title}",
    ]
    if version:
        lines.append(f"// Version: {version}")
    if getattr(builder, "description", ""):
        for d in builder.description.strip().splitlines():
            lines.append(f"// {d}")
    lines.append("// Automatically generated by binary_master.")
    lines.append("// " + "=" * 76 + "\n")

    lines.append("using System;")
    lines.append("using System.Runtime.InteropServices;\n")

    lines.append(f"namespace {namespace} {{")

    emitted_structs: Set[str] = set()

    for elem in elements:
        if isinstance(elem, DocumentElement):
            lines.append("    // " + "=" * 72)
            lines.append(f"    // {elem.title}")
            lines.append("    // " + "=" * 72)
            for c_line in elem.content.splitlines():
                lines.append(f"    // {c_line}" if c_line else "    //")
            lines.append("")

        elif isinstance(elem, SectionElement):
            lines.append("    // " + "-" * 72)
            lines.append(f"    // Section: {elem.title}")
            if elem.desc:
                lines.append(f"    // {elem.desc}")
            lines.append("    // " + "-" * 72 + "\n")

        elif isinstance(elem, StructElement):
            s_name = elem.struct_cls.__name__
            if s_name not in emitted_structs:
                s_code = generate_csharp_struct(
                    elem.struct_cls,
                    name=elem.name,
                    desc=elem.desc,
                    condition=elem.condition,
                )
                for sc_line in s_code.splitlines():
                    lines.append(f"    {sc_line}" if sc_line else "")
                lines.append("")
                emitted_structs.add(s_name)

        elif isinstance(elem, ChoiceElement):
            c_code = generate_csharp_choice(
                choice_name=elem.name,
                tag_field=elem.tag_field,
                variants=elem.variants,
                desc=elem.desc,
                condition=elem.condition,
                emitted_structs=emitted_structs,
            )
            for cc_line in c_code.splitlines():
                lines.append(f"    {cc_line}" if cc_line else "")
            lines.append("")

        elif isinstance(elem, FieldElement):
            cs_t, _, _ = csharp_type_of(elem.type_name)
            desc_str = f" // {elem.desc}" if elem.desc else ""
            lines.append(f"    // Ad-hoc field: {elem.name} ({elem.type_name}, {elem.size}B){desc_str}\n")

    lines.append("}")

    return "\n".join(lines)


def write_csharp(
    builder: Any,
    path_or_file: Optional[Union[str, Path, IO[str]]] = None,
    namespace: str = "BinaryProtocol",
) -> str:
    """Generate C# code from a BinaryBuilder and optionally save to file."""
    content = generate_csharp_code(builder, namespace=namespace)
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
