"""C/C++ header file generator for binary_master schemas and structs."""

from __future__ import annotations

import inspect
import re
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
)


def to_snake_case(name: str) -> str:
    """Convert PascalCase or camelCase name to snake_case."""
    s1 = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", name)
    s2 = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s1)
    return s2.lower()


def to_screaming_snake_case(name: str) -> str:
    """Convert PascalCase, camelCase, or snake_case to SCREAMING_SNAKE_CASE."""
    return to_snake_case(name).upper()


def to_pascal_case(name: str) -> str:
    """Convert snake_case or identifier to PascalCase."""
    snake = to_snake_case(name)
    parts = re.split(r"[^a-zA-Z0-9]+", snake)
    return "".join(p.capitalize() for p in parts if p)


def c_type_of(field_type: Any) -> Tuple[str, Optional[int], Optional[str]]:
    """Determine the C type, array count, and optional inline comment for a binary field type.

    Returns:
        (c_type_name, array_size_or_None, comment_annotation_or_None)
    """
    if get_origin(field_type) is Annotated:
        args = get_args(field_type)
        base_t = args[0]
        c_name, arr_sz, _ = c_type_of(base_t)
        ann_desc = str(args[1]) if len(args) > 1 else None
        return c_name, arr_sz, ann_desc

    # Primitives
    if field_type is UInt8:
        return "uint8_t", None, None
    if field_type is UInt16:
        return "uint16_t", None, None
    if field_type is UInt32:
        return "uint32_t", None, None
    if field_type is UInt64:
        return "uint64_t", None, None
    if field_type is Int8:
        return "int8_t", None, None
    if field_type is Int16:
        return "int16_t", None, None
    if field_type is Int32:
        return "int32_t", None, None
    if field_type is Int64:
        return "int64_t", None, None
    if field_type is Float32:
        return "float", None, None
    if field_type is Float64:
        return "double", None, None
    if field_type is bool:
        return "bool", None, None

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
        elem_c, _, _ = c_type_of(elem_t)
        return elem_c, cnt, None

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

        c_name, _, _ = c_type_of(offset_t)
        return c_name, None, f"Offset to {target_name}"

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
        c_name, _, _ = c_type_of(offset_t)
        return c_name, count, "Offset table"

    # Nested binary_struct
    if hasattr(field_type, "__binary__"):
        return field_type.__name__, None, None

    # Fallback
    return "uint8_t", None, None


def _get_type_name(type_obj: Any) -> str:
    """Safely obtain a type's name without raising type-to-string inspection warnings."""
    name = getattr(type_obj, "__name__", None)
    if isinstance(name, str):
        return name
    return type_obj.__class__.__name__


def generate_c_struct(
    struct_cls: type,
    name: Optional[str] = None,
    desc: str = "",
    condition: Optional[str] = None,
) -> str:
    """Generate a C typedef struct definition for a @binary_struct class."""
    if not hasattr(struct_cls, "__binary__"):
        raise TypeError(f"Class {_get_type_name(struct_cls)} is not a binary_struct")

    meta: dict[str, Any] = getattr(struct_cls, "__binary__", {})
    cls_name = struct_cls.__name__ if struct_cls else (name or "Struct")
    field_alias = name if (name and name != cls_name) else None
    doc_text = desc or getattr(struct_cls, "__doc__", "") or meta.get("doc", "")

    # Doxygen docstring header
    lines: List[str] = ["/**"]
    if field_alias:
        lines.append(f" * @brief Logical Name: `{field_alias}`")
    if doc_text:
        for d_line in inspect.cleandoc(doc_text).splitlines():
            lines.append(f" * {d_line}")
    elif not field_alias:
        lines.append(f" * @brief {cls_name} structure.")

    if condition:
        lines.append(f" * @note Condition: {condition}")
    lines.append(" */")

    total_bits = meta.get("bits")
    if isinstance(total_bits, int):
        # Bitfield struct
        if total_bits <= 8:
            base_type = "uint8_t"
        elif total_bits <= 16:
            base_type = "uint16_t"
        elif total_bits <= 32:
            base_type = "uint32_t"
        else:
            base_type = "uint64_t"

        lines.append(f"typedef struct {cls_name} {{")
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
        lines.append(f"}} {cls_name};")
    else:
        # Regular struct
        lines.append(f"typedef struct {cls_name} {{")
        fields = meta.get("fields", {})
        descriptions = meta.get("descriptions", {})

        for field_name, field_type in fields.items():
            c_name, arr_cnt, note = c_type_of(field_type)
            field_desc = descriptions.get(field_name, "") or note or ""
            comment = f" /**< {field_desc} */" if field_desc else ""

            if arr_cnt is not None:
                lines.append(f"    {c_name} {field_name}[{arr_cnt}];{comment}")
            else:
                lines.append(f"    {c_name} {field_name};{comment}")

        lines.append(f"}} {cls_name};")

    return "\n".join(lines)


def generate_c_choice(
    choice_name: str,
    tag_field: Union[str, Any],
    variants: Any,
    desc: str = "",
    condition: Optional[str] = None,
    emitted_structs: Optional[Set[str]] = None,
) -> str:
    """Generate C enum tag constants, variant structs, and union definition for a choice."""
    from binary_master.builder import _normalize_variants

    if emitted_structs is None:
        emitted_structs = set()

    norm_vars = _normalize_variants(variants)
    tag_field_name = tag_field if isinstance(tag_field, str) else "tag"

    # 1. Tag Enum definition
    enum_name = f"{to_pascal_case(choice_name)}Tag"
    lines: List[str] = [
        "/**",
        f" * @brief Tag values for choice `{choice_name}` (dispatched by `{tag_field_name}`).",
    ]
    if desc:
        lines.append(f" * {desc}")
    if condition:
        lines.append(f" * @note Condition: {condition}")
    lines.append(" */")
    lines.append(f"typedef enum {enum_name} {{")

    prefix = to_screaming_snake_case(choice_name)
    for tag, v_cls, v_desc in norm_vars:
        v_cls_name = _get_type_name(v_cls)
        tag_val_str = f"0x{tag:02X}" if isinstance(tag, int) else f"{tag}"
        tag_enum_id = f"{prefix}_TAG_{to_screaming_snake_case(v_cls_name)}"
        comment = f" /**< Tag {tag_val_str}: {v_desc or v_cls_name} */"
        lines.append(f"    {tag_enum_id} = {tag_val_str},{comment}")
    lines.append(f"}} {enum_name};\n")

    # 2. Emit each variant struct if not already emitted
    for tag, v_cls, v_desc in norm_vars:
        v_cls_name = _get_type_name(v_cls)
        if v_cls_name not in emitted_structs:
            lines.append(generate_c_struct(v_cls, desc=v_desc))
            lines.append("")
            emitted_structs.add(v_cls_name)

    # 3. Emit Union definition
    union_name = f"{to_pascal_case(choice_name)}Union"
    lines.append("/**")
    lines.append(f" * @brief Polymorphic union for choice `{choice_name}`.")
    lines.append(" */")
    lines.append(f"typedef union {union_name} {{")
    for tag, v_cls, v_desc in norm_vars:
        v_cls_name = _get_type_name(v_cls)
        member_name = to_snake_case(v_cls_name)
        lines.append(f"    {v_cls_name} {member_name};")
    lines.append(f"}} {union_name};")

    return "\n".join(lines)


def generate_c_header(
    builder: Any,
    guard: Optional[str] = None,
    pack: bool = True,
) -> str:
    """Generate a complete C99/C11 header file from a BinaryBuilder instance."""
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

    if guard is None:
        clean_title = re.sub(r"[^a-zA-Z0-9_]", "_", title).strip("_").upper()
        guard = f"{clean_title}_H"

    # Include Guard
    lines: List[str] = [
        f"#ifndef {guard}",
        f"#define {guard}\n",
        "/**",
        " * @file",
        f" * @brief {title}",
    ]
    if version:
        lines.append(f" * @version {version}")
    if getattr(builder, "description", ""):
        for d in builder.description.strip().splitlines():
            lines.append(f" * {d}")
    lines.append(" *")
    lines.append(" * Automatically generated by binary_master.")
    lines.append(" */\n")

    # Standard C Includes
    lines.append("#include <stdint.h>")
    lines.append("#include <stdbool.h>\n")

    # C++ extern "C" guard
    lines.append("#ifdef __cplusplus")
    lines.append('extern "C" {')
    lines.append("#endif\n")

    # Packing Pragma
    if pack:
        lines.append("/* Force 1-byte struct alignment for exact binary wire format */")
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
                s_code = generate_c_struct(
                    elem.struct_cls,
                    name=elem.name,
                    desc=elem.desc,
                    condition=elem.condition,
                )
                lines.append(s_code)
                lines.append("")
                emitted_structs.add(s_name)

        elif isinstance(elem, ChoiceElement):
            c_code = generate_c_choice(
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
            c_type, arr_cnt, _ = c_type_of(elem.type_name)
            desc_str = f" /**< {elem.desc} */" if elem.desc else ""
            lines.append(f"/* Ad-hoc field: {elem.name} ({elem.type_name}, {elem.size}B){desc_str} */\n")

    # Restore Packing Pragma
    if pack:
        lines.append("#if defined(_MSC_VER) || defined(__GNUC__) || defined(__clang__)")
        lines.append("#pragma pack(pop)")
        lines.append("#endif\n")

    # Close C++ extern "C" guard
    lines.append("#ifdef __cplusplus")
    lines.append("}")
    lines.append("#endif\n")

    # Close Include Guard
    lines.append(f"#endif /* {guard} */\n")

    return "\n".join(lines)


to_c_header = generate_c_header


def write_c_header(
    builder: Any,
    path_or_file: Optional[Union[str, Path, IO[str]]] = None,
    guard: Optional[str] = None,
    pack: bool = True,
) -> str:
    """Generate C header code from a BinaryBuilder and optionally save to file."""
    content = generate_c_header(builder, guard=guard, pack=pack)
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


def to_c_struct(struct_cls: type, name: Optional[str] = None, desc: str = "") -> str:
    """Convenience helper to generate a C struct definition from a single @binary_struct class."""
    return generate_c_struct(struct_cls, name=name, desc=desc)
