"""Modern C++ (C++17/C++20) code generator for binary_master schemas and structs."""

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
from binary_master.code_gen.c import to_pascal_case


def cpp_type_of(field_type: Any) -> Tuple[str, Optional[str]]:
    """Determine the modern C++ type and optional comment note."""
    if get_origin(field_type) is Annotated:
        args = get_args(field_type)
        return cpp_type_of(args[0])

    if field_type is UInt8:
        return "uint8_t", None
    if field_type is UInt16:
        return "uint16_t", None
    if field_type is UInt32:
        return "uint32_t", None
    if field_type is UInt64:
        return "uint64_t", None
    if field_type is Int8:
        return "int8_t", None
    if field_type is Int16:
        return "int16_t", None
    if field_type is Int32:
        return "int32_t", None
    if field_type is Int64:
        return "int64_t", None
    if field_type is Float32:
        return "float", None
    if field_type is Float64:
        return "double", None
    if field_type is bool or field_type is Bool or (isinstance(field_type, type) and issubclass(field_type, Bool)):
        size = getattr(field_type, "_size", 1) if field_type is not bool else 1
        if size == 1:
            return "bool", None
        elif size == 2:
            return "uint16_t", "2-byte boolean"
        elif size == 4:
            return "uint32_t", "4-byte boolean"
        elif size == 8:
            return "uint64_t", "8-byte boolean"
        else:
            return f"std::array<uint8_t, {size}>", f"{size}-byte boolean"

    from binary_master.binary_struct import (
        Bytes,
        FixedString,
        CString,
        PrefixedString,
        MagicBase,
        ConstantBase,
    )
    from binary_master.checksum import ChecksumBase
    from binary_master.varint import VarIntTypeMeta
    import enum

    if isinstance(field_type, type) and issubclass(field_type, MagicBase):
        expected = getattr(field_type, "_value", None)
        if isinstance(expected, bytes):
            return f"std::array<uint8_t, {len(expected)}>", f"Magic: {expected!r}"
        else:
            fmt = getattr(field_type, "_fmt", "I")
            cpp_map = {"B": "uint8_t", "H": "uint16_t", "I": "uint32_t", "Q": "uint64_t"}
            return cpp_map.get(fmt, "uint32_t"), f"Magic: {getattr(field_type, '_raw_val', '')!r}"

    if isinstance(field_type, type) and issubclass(field_type, ConstantBase):
        t = getattr(field_type, "_type", UInt32)
        val = getattr(field_type, "_value", None)
        cpp_name, _ = cpp_type_of(t)
        return cpp_name, f"Constant: {val!r}"

    if isinstance(field_type, type) and issubclass(field_type, ChecksumBase):
        sz = getattr(field_type, "_size", 4)
        cpp_map = {1: "uint8_t", 2: "uint16_t", 4: "uint32_t", 8: "uint64_t"}
        return cpp_map.get(sz, "uint32_t"), f"{getattr(field_type, '_algorithm', 'checksum').upper()} Checksum"

    if isinstance(field_type, VarIntTypeMeta):
        return "int64_t" if field_type.is_signed else "uint64_t", "Variable-length integer (LEB128)"

    if isinstance(field_type, tuple) and len(field_type) >= 2 and isinstance(field_type[0], type) and issubclass(field_type[0], enum.Enum):
        cpp_name, _ = cpp_type_of(field_type[1])
        return cpp_name, f"Enum: {field_type[0].__name__}"

    if isinstance(field_type, type) and issubclass(field_type, enum.Enum):
        max_v = max([abs(m.value) for m in field_type], default=0)
        cpp_name = "uint8_t" if max_v <= 255 else ("uint16_t" if max_v <= 65535 else "uint32_t")
        return cpp_name, f"Enum: {field_type.__name__}"

    if isinstance(field_type, type) and issubclass(field_type, Bytes):
        return f"std::array<uint8_t, {field_type._size}>", "raw bytes"
    if isinstance(field_type, type) and issubclass(field_type, FixedString):
        return f"std::array<char, {field_type._size}>", "fixed-length string"
    if field_type is CString or (isinstance(field_type, type) and issubclass(field_type, CString)):
        return "const char*", "null-terminated string"
    if field_type is PrefixedString or (isinstance(field_type, type) and issubclass(field_type, PrefixedString)):
        p_bytes = getattr(field_type, "prefix_bytes", 1)
        return "const char*", f"prefixed string ({p_bytes}-byte length prefix)"

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
        elem_cpp, _ = cpp_type_of(elem_t)
        return f"std::array<{elem_cpp}, {cnt}>", None

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

        cpp_name, _ = cpp_type_of(offset_t)
        return cpp_name, f"Offset to {target_name}"

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
        cpp_name, _ = cpp_type_of(offset_t)
        return f"std::array<{cpp_name}, {count}>", "Offset table"

    # Nested binary_struct
    if hasattr(field_type, "__binary__"):
        return field_type.__name__, None

    return "uint8_t", None


def _get_type_name(type_obj: Any) -> str:
    """Safely obtain a type's name without raising type-to-string inspection warnings."""
    name = getattr(type_obj, "__name__", None)
    if isinstance(name, str):
        return name
    return type_obj.__class__.__name__


def generate_cpp_struct(
    struct_cls: type,
    name: Optional[str] = None,
    desc: str = "",
    condition: Optional[str] = None,
) -> str:
    """Generate modern C++ struct definition for a @binary_struct class."""
    if not hasattr(struct_cls, "__binary__"):
        raise TypeError(f"Class {_get_type_name(struct_cls)} is not a binary_struct")

    meta: dict[str, Any] = getattr(struct_cls, "__binary__", {})
    cls_name = struct_cls.__name__ if struct_cls else (name or "Struct")
    field_alias = name if (name and name != cls_name) else None
    doc_text = desc or getattr(struct_cls, "__doc__", "") or meta.get("doc", "")

    lines: List[str] = ["/**"]
    if field_alias:
        lines.append(f" * @brief Logical Name: `{field_alias}`")
    if doc_text:
        for d_line in inspect.cleandoc(doc_text).splitlines():
            lines.append(f" * {d_line}")
    elif not field_alias:
        lines.append(f" * @brief {cls_name} binary structure.")
    if condition:
        lines.append(f" * @note Condition: {condition}")
    lines.append(" */")

    total_bits = meta.get("bits")
    if isinstance(total_bits, int):
        if total_bits <= 8:
            base_type = "uint8_t"
        elif total_bits <= 16:
            base_type = "uint16_t"
        elif total_bits <= 32:
            base_type = "uint32_t"
        else:
            base_type = "uint64_t"

        lines.append(f"struct {cls_name} {{")
        fields = meta.get("fields", {})
        descriptions = meta.get("descriptions", {})
        shift = 0
        for field_name, field_type in fields.items():
            width = field_type[1] if isinstance(field_type, tuple) and len(field_type) >= 2 else 1
            field_desc = descriptions.get(field_name, "")
            bit_end = shift + width - 1
            bit_range = f"[{shift}:{bit_end}]" if width > 1 else f"[{shift}]"
            comment = f" /**< Bit {bit_range}{': ' + field_desc if field_desc else ''} */"
            lines.append(f"    {base_type} {field_name} : {width};{comment}")
            shift += width
        lines.append("};")
    else:
        lines.append(f"struct {cls_name} {{")
        fields = meta.get("fields", {})
        descriptions = meta.get("descriptions", {})

        for field_name, field_type in fields.items():
            cpp_type, note = cpp_type_of(field_type)
            field_desc = descriptions.get(field_name, "") or note or ""
            comment = f" /**< {field_desc} */" if field_desc else ""
            lines.append(f"    {cpp_type} {field_name};{comment}")

        lines.append("};")

    return "\n".join(lines)


def generate_cpp_choice(
    choice_name: str,
    tag_field: Union[str, Any],
    variants: Any,
    desc: str = "",
    condition: Optional[str] = None,
    emitted_structs: Optional[Set[str]] = None,
) -> str:
    """Generate C++ enum class, variant structs, and std::variant alias for a choice."""
    from binary_master.builder import _normalize_variants

    if emitted_structs is None:
        emitted_structs = set()

    norm_vars = _normalize_variants(variants)
    tag_field_name = tag_field if isinstance(tag_field, str) else "tag"

    enum_name = f"{to_pascal_case(choice_name)}Tag"
    lines: List[str] = [
        "/**",
        f" * @brief Strongly-typed tag values for choice `{choice_name}` (dispatched by `{tag_field_name}`).",
    ]
    if desc:
        lines.append(f" * {desc}")
    if condition:
        lines.append(f" * @note Condition: {condition}")
    lines.append(" */")
    lines.append(f"enum class {enum_name} : uint16_t {{")

    for tag, v_cls, v_desc in norm_vars:
        v_cls_name = _get_type_name(v_cls)
        tag_val_str = f"0x{tag:02X}" if isinstance(tag, int) else f"{tag}"
        variant_tag_name = to_pascal_case(v_cls_name)
        comment = f" /**< Tag {tag_val_str}: {v_desc or v_cls_name} */"
        lines.append(f"    {variant_tag_name} = {tag_val_str},{comment}")
    lines.append("};\n")

    # 2. Emit each variant struct if not already emitted
    for tag, v_cls, v_desc in norm_vars:
        v_cls_name = _get_type_name(v_cls)
        if v_cls_name not in emitted_structs:
            lines.append(generate_cpp_struct(v_cls, desc=v_desc))
            lines.append("")
            emitted_structs.add(v_cls_name)

    # 3. Emit std::variant alias
    variant_alias = f"{to_pascal_case(choice_name)}Variant"
    variant_types = ", ".join(_get_type_name(v_cls) for _, v_cls, _ in norm_vars)
    lines.append("/**")
    lines.append(f" * @brief Type-safe variant container for choice `{choice_name}`.")
    lines.append(" */")
    lines.append(f"using {variant_alias} = std::variant<{variant_types}>;")

    return "\n".join(lines)


def generate_cpp_code(builder: Any) -> str:
    """Generate complete C++17 header from a BinaryBuilder instance."""
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

    lines: List[str] = ["#pragma once\n", "/**", " * @file", f" * @brief {title}"]

    if version:
        lines.append(f" * @version {version}")
    if getattr(builder, "description", ""):
        for d in builder.description.strip().splitlines():
            lines.append(f" * {d}")
    lines.append(" *")
    lines.append(" * Automatically generated by binary_master.")
    lines.append(" */\n")

    lines.append("#include <cstdint>")  # noinspection SpellCheckingInspection
    lines.append("#include <cstddef>")  # noinspection SpellCheckingInspection
    lines.append("#include <array>")
    lines.append("#include <variant>\n")

    lines.append("/* Force 1-byte struct alignment */")
    lines.append("#if defined(_MSC_VER)")
    lines.append("#pragma pack(push, 1)")
    lines.append("#elif defined(__GNUC__) || defined(__clang__)")
    lines.append("#pragma pack(push, 1)")
    lines.append("#endif\n")

    emitted_structs: Set[str] = set()

    for elem in elements:
        if isinstance(elem, DocumentElement):
            lines.append("/*")
            lines.append(" * " + "=" * 76)
            lines.append(f" * {elem.title}")
            lines.append(" * " + "=" * 76)
            for c_line in elem.content.splitlines():
                lines.append(f" * {c_line}" if c_line else " *")
            lines.append(" */\n")

        elif isinstance(elem, SectionElement):
            lines.append("/* " + "-" * 76)
            lines.append(f" * Section: {elem.title}")
            if elem.desc:
                lines.append(f" * {elem.desc}")
            lines.append(" * " + "-" * 76 + " */\n")

        elif isinstance(elem, StructElement):
            s_name = elem.struct_cls.__name__
            if s_name not in emitted_structs:
                s_code = generate_cpp_struct(
                    elem.struct_cls,
                    name=elem.name,
                    desc=elem.desc,
                    condition=elem.condition,
                )
                lines.append(s_code)
                lines.append("")
                emitted_structs.add(s_name)

        elif isinstance(elem, ChoiceElement):
            c_code = generate_cpp_choice(
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
            cpp_t, _ = cpp_type_of(elem.type_name)
            desc_str = f" /**< {elem.desc} */" if elem.desc else ""
            lines.append(f"/* Ad-hoc field: {elem.name} ({elem.type_name}, {elem.size}B){desc_str} */\n")

    lines.append("#if defined(_MSC_VER) || defined(__GNUC__) || defined(__clang__)")
    lines.append("#pragma pack(pop)")
    lines.append("#endif\n")

    return "\n".join(lines)


def write_cpp(
    builder: Any,
    path_or_file: Optional[Union[str, Path, IO[str]]] = None,
) -> str:
    """Generate C++ code from a BinaryBuilder and optionally save to file."""
    content = generate_cpp_code(builder)
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
