"""ImHex Pattern Language (.hexpat) code generator."""

from __future__ import annotations

import inspect
from pathlib import Path
from typing import IO, Any, List, Optional, Set, Union

from binary_master.code_gen.c import to_pascal_case, to_snake_case
from binary_master.enums import Endian, EndianType, normalize_endian


def _field_plan_to_hexpat(fp: Any) -> str:
    """Map a FieldPlan to ImHex Pattern Language type string."""
    from binary_master.binary_struct import FieldKind

    if fp.enum_cls is not None:
        return to_pascal_case(fp.enum_cls.__name__)

    if fp.kind == FieldKind.NESTED_STRUCT and fp.nested_cls is not None:
        return to_pascal_case(getattr(fp.nested_cls, "__name__", "SubStruct"))

    if fp.kind == FieldKind.FIXED_STRING:
        return f"char[{fp.size}]"

    if fp.kind == FieldKind.MAGIC:
        if fp.is_bytes_magic:
            return f"char[{fp.size}]"
        fmt = fp.fmt.lstrip("<>!=@")
        fmt_map = {
            "B": "u8",
            "H": "u16",
            "I": "u32",
            "Q": "u64",
            "b": "s8",
            "h": "s16",
            "i": "s32",
            "q": "s64",
        }
        return fmt_map.get(fmt, "u32")

    if fp.kind == FieldKind.FIXED_ARRAY:
        elem_t_str = "u8"
        if fp.elem_is_bool:
            elem_t_str = "bool"
        elif fp.elem_is_uint8:
            elem_t_str = "u8"
        elif fp.elem_is_int8:
            elem_t_str = "s8"
        elif fp.elem_is_struct and fp.elem_type:
            elem_t_str = to_pascal_case(getattr(fp.elem_type, "__name__", "SubStruct"))
        elif fp.elem_fmt:
            elem_fmt = fp.elem_fmt.lstrip("<>!=@")
            fmt_map = {
                "B": "u8",
                "H": "u16",
                "I": "u32",
                "Q": "u64",
                "b": "s8",
                "h": "s16",
                "i": "s32",
                "q": "s64",
                "f": "float",
                "d": "double",
            }
            elem_t_str = fmt_map.get(elem_fmt, "u8")
        return f"{elem_t_str}[{fp.count}]"

    if fp.kind == FieldKind.BYTES:
        return f"u8[{fp.size}]"

    if fp.kind == FieldKind.BOOL:
        return "bool"

    if fp.kind in (FieldKind.C_STRING, FieldKind.PREFIXED_STRING):
        return "char[]"

    fmt = fp.fmt.lstrip("<>!=@") if fp.fmt else ""
    fmt_map = {
        "B": "u8",
        "b": "s8",
        "H": "u16",
        "h": "s16",
        "I": "u32",
        "i": "s32",
        "Q": "u64",
        "q": "s64",
        "e": "u16",
        "f": "float",
        "d": "double",
        "?": "bool",
    }
    return fmt_map.get(fmt, "u8")


def generate_imhex_pattern(
    target: Any,
    root_name: Optional[str] = None,
    endian: Optional[EndianType] = None,
) -> str:
    """Generate an ImHex Pattern Language (.hexpat) script.

    Args:
        target: A @binary_struct class, instance, or Builder.
        root_name: Variable name for the root pattern placement (default: lowercased struct name).
        endian: Byte order override (Endian.LITTLE or Endian.BIG).

    Returns:
        Complete .hexpat script as a string.
    """
    from binary_master.binary_struct import get_struct_plan
    from binary_master.builder import Builder, StructElement

    active_endian = Endian.LITTLE
    target_classes: List[type] = []
    cls_name = "Root"

    if isinstance(target, Builder):
        cls_name = target.title.replace(" ", "") if target.title else "Root"
        for elem in target.elements:
            if isinstance(elem, StructElement) and elem.struct_cls:
                target_classes.append(elem.struct_cls)
    elif hasattr(target, "__binary__") or inspect.isclass(target):
        cls = target if inspect.isclass(target) else target.__class__
        cls_name = getattr(cls, "__name__", "Root")
        target_classes.append(cls)
        meta = getattr(cls, "__binary__", {})
        if isinstance(meta, dict):
            active_endian = normalize_endian(meta.get("endian", Endian.LITTLE))

    if endian is not None:
        active_endian = normalize_endian(endian)

    endian_str = "big" if active_endian == Endian.BIG else "little"

    lines: List[str] = [
        "// ImHex Pattern Script",
        f"// Generated automatically by Binary Master for {cls_name}",
        "#include <std/mem.pat>",
        "",
        f"#pragma endian {endian_str}",
        "",
    ]

    emitted: Set[str] = set()

    def emit_struct(struct_cls: type) -> None:
        s_name = to_pascal_case(getattr(struct_cls, "__name__", "Struct"))
        if s_name in emitted:
            return

        plan = get_struct_plan(struct_cls)
        meta = getattr(struct_cls, "__binary__", {})

        # Emit bitfield if bits set
        if plan.is_bitfield:
            lines.append(f"bitfield {s_name} {{")
            fields = meta.get("fields", {})
            for fname, ftype in fields.items():
                bit_width = 1
                if isinstance(ftype, tuple) and len(ftype) > 1:
                    bit_width = ftype[1]
                lines.append(f"    {fname} : {bit_width};")
            lines.append("};\n")
            emitted.add(s_name)
            return

        from binary_master.binary_struct import FieldKind

        # Pre-emit any nested structs or enums
        for fp in plan.field_plans:
            if fp.enum_cls is not None:
                enum_name = to_pascal_case(fp.enum_cls.__name__)
                if enum_name not in emitted:
                    lines.append(f"enum {enum_name} : u32 {{")
                    for m in fp.enum_cls:
                        lines.append(f"    {m.name} = {m.value},")
                    lines.append("};\n")
                    emitted.add(enum_name)
            elif fp.kind == FieldKind.NESTED_STRUCT and fp.nested_cls is not None:
                emit_struct(fp.nested_cls)
            elif fp.kind == FieldKind.FIXED_ARRAY and fp.elem_is_struct and fp.elem_type:
                emit_struct(fp.elem_type)

        lines.append(f"struct {s_name} {{")
        for fp in plan.field_plans:
            type_str = _field_plan_to_hexpat(fp)
            if "[" in type_str and type_str.endswith("]"):
                base_t, arr_part = type_str.split("[", 1)
                lines.append(f"    {base_t} {fp.name}[{arr_part};")
            else:
                lines.append(f"    {type_str} {fp.name};")
        lines.append("};\n")
        emitted.add(s_name)

    for s_cls in target_classes:
        emit_struct(s_cls)

    # Root placement
    root_var = to_snake_case(root_name or cls_name)
    lines.append(f"{to_pascal_case(cls_name)} {root_var} @ 0x00;\n")

    return "\n".join(lines)


def write_imhex_pattern(
    target: Any,
    path_or_file: Union[str, Path, IO[str]],
    root_name: Optional[str] = None,
    endian: Optional[EndianType] = None,
) -> str:
    """Generate and write an ImHex Pattern Language (.hexpat) file.

    Args:
        target: A @binary_struct class, instance, or Builder.
        path_or_file: File path or writable stream.
        root_name: Variable name for root placement.
        endian: Byte order override.

    Returns:
        Generated pattern content.
    """
    content = generate_imhex_pattern(target, root_name=root_name, endian=endian)

    if hasattr(path_or_file, "write"):
        path_or_file.write(content)
    else:
        path = Path(path_or_file)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    return content
