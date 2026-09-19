"""Wireshark Lua Dissector generator for binary_master schemas and structs."""

from __future__ import annotations

import inspect
from pathlib import Path
from typing import IO, Any, List, Optional, Tuple, Union

from binary_master.code_gen.c import to_pascal_case, to_snake_case


def _wireshark_field_for(
    field_name: str,
    field_type: Any,
    proto_id: str,
) -> Tuple[str, str, int]:
    """Return (proto_field_def, dissect_code, static_size).
    static_size is > 0 for fixed-width fields, or 0 for variable length (e.g. CString).
    """
    snake = to_snake_case(field_name)
    var_name = f"f_{snake}"
    label = snake.replace("_", " ").title()
    filter_name = f"{proto_id}.{snake}"

    type_str = str(field_type)
    type_name = getattr(field_type, "__name__", type_str)

    # 1. Integers
    if type_name in ("UInt8", "int") and getattr(field_type, "_size", 0) == 1:
        defn = f'local {var_name} = ProtoField.uint8("{filter_name}", "{label}", base.DEC)'
        code = f'subtree:add({var_name}, buffer(offset, 1))\noffset = offset + 1'
        return defn, code, 1
    if type_name == "UInt16" or getattr(field_type, "_size", 0) == 2:
        defn = f'local {var_name} = ProtoField.uint16("{filter_name}", "{label}", base.DEC)'
        code = f'subtree:add_le({var_name}, buffer(offset, 2))\noffset = offset + 2'
        return defn, code, 2
    if type_name == "UInt32" or getattr(field_type, "_size", 0) == 4:
        is_hex = "crc" in snake.lower() or "magic" in snake.lower()
        base_fmt = "base.HEX" if is_hex else "base.DEC"
        defn = f'local {var_name} = ProtoField.uint32("{filter_name}", "{label}", {base_fmt})'
        code = f'subtree:add_le({var_name}, buffer(offset, 4))\noffset = offset + 4'
        return defn, code, 4
    if type_name == "UInt64" or getattr(field_type, "_size", 0) == 8:
        defn = f'local {var_name} = ProtoField.uint64("{filter_name}", "{label}", base.DEC)'
        code = f'subtree:add_le({var_name}, buffer(offset, 8))\noffset = offset + 8'
        return defn, code, 8
    if type_name == "Int8":
        defn = f'local {var_name} = ProtoField.int8("{filter_name}", "{label}", base.DEC)'
        code = f'subtree:add({var_name}, buffer(offset, 1))\noffset = offset + 1'
        return defn, code, 1
    if type_name == "Int16":
        defn = f'local {var_name} = ProtoField.int16("{filter_name}", "{label}", base.DEC)'
        code = f'subtree:add_le({var_name}, buffer(offset, 2))\noffset = offset + 2'
        return defn, code, 2
    if type_name == "Int32":
        defn = f'local {var_name} = ProtoField.int32("{filter_name}", "{label}", base.DEC)'
        code = f'subtree:add_le({var_name}, buffer(offset, 4))\noffset = offset + 4'
        return defn, code, 4
    if type_name == "Int64":
        defn = f'local {var_name} = ProtoField.int64("{filter_name}", "{label}", base.DEC)'
        code = f'subtree:add_le({var_name}, buffer(offset, 8))\noffset = offset + 8'
        return defn, code, 8

    # 2. Floats
    if type_name in ("Float32", "Float64", "Float16", "float"):
        sz = getattr(field_type, "_size", 4)
        fn = "float" if sz <= 4 else "double"
        defn = f'local {var_name} = ProtoField.{fn}("{filter_name}", "{label}")'
        code = f'subtree:add_le({var_name}, buffer(offset, {sz}))\noffset = offset + {sz}'
        return defn, code, sz

    # 3. Bool
    if type_name in ("Bool", "bool"):
        defn = f'local {var_name} = ProtoField.bool("{filter_name}", "{label}")'
        code = f'subtree:add({var_name}, buffer(offset, 1))\noffset = offset + 1'
        return defn, code, 1

    # 4. Strings
    if "CString" in type_str:
        defn = f'local {var_name} = ProtoField.stringz("{filter_name}", "{label}")'
        code = (
            f"local len_{snake} = 0\n"
            f"while offset + len_{snake} < length and buffer(offset + len_{snake}, 1):uint() ~= 0 do\n"
            f"    len_{snake} = len_{snake} + 1\n"
            f"end\n"
            f"subtree:add({var_name}, buffer(offset, len_{snake} + 1))\n"
            f"offset = offset + len_{snake} + 1"
        )
        return defn, code, 0

    if "FixedString" in type_str:
        sz = getattr(field_type, "_size", 16)
        defn = f'local {var_name} = ProtoField.string("{filter_name}", "{label}")'
        code = f'subtree:add({var_name}, buffer(offset, {sz}))\noffset = offset + {sz}'
        return defn, code, sz

    # 5. Checksum & Magic
    if "CRC32" in type_str:
        defn = f'local {var_name} = ProtoField.uint32("{filter_name}", "{label}", base.HEX)'
        code = f'subtree:add_le({var_name}, buffer(offset, 4))\noffset = offset + 4'
        return defn, code, 4
    if "Magic" in type_str:
        sz = getattr(field_type, "_size", 4)
        defn = f'local {var_name} = ProtoField.bytes("{filter_name}", "{label}")'
        code = f'subtree:add({var_name}, buffer(offset, {sz}))\noffset = offset + {sz}'
        return defn, code, sz

    # Fallback to bytes
    sz = getattr(field_type, "_size", 4)
    sz = sz if sz > 0 else 4
    defn = f'local {var_name} = ProtoField.bytes("{filter_name}", "{label}")'
    code = f'subtree:add({var_name}, buffer(offset, {sz}))\noffset = offset + {sz}'
    return defn, code, sz


def generate_wireshark_dissector(
    target: Any,
    protocol_name: Optional[str] = None,
    description: Optional[str] = None,
    port: Optional[int] = None,
) -> str:
    """Generate Wireshark Lua Dissector script for a @binary_struct or Builder schema.

    Args:
        target: A @binary_struct class, instance, or Builder.
        protocol_name: Short identifier for the protocol (e.g. 'my_proto').
        description: User-friendly description for packet list view.
        port: Optional TCP/UDP port to automatically register dissector.

    Returns:
        Complete Lua script as string.
    """
    # Extract fields from target
    from binary_master.builder import Builder

    fields_info: List[Tuple[str, Any]] = []
    cls_name = "Protocol"

    if isinstance(target, Builder):
        from binary_master.builder import FieldElement, StructElement

        cls_name = target.title.replace(" ", "") if target.title else "Protocol"
        # Collect fields from builder
        for elem in target.elements:
            if isinstance(elem, StructElement):
                s_cls = elem.struct_cls
                if s_cls:
                    cls_name = str(elem.name or getattr(s_cls, "__name__", cls_name))
                    hints = getattr(s_cls, "__annotations__", {})
                    for fname, ftype in hints.items():
                        fields_info.append((fname, ftype))
            elif isinstance(elem, FieldElement):
                fields_info.append((elem.name, elem.type_name))
            elif isinstance(elem, dict):
                elem_type = elem.get("type")
                if elem_type == "struct":
                    dict_s_cls = elem.get("class")
                    if dict_s_cls and hasattr(dict_s_cls, "__annotations__"):
                        for fname, ftype in dict_s_cls.__annotations__.items():
                            fields_info.append((fname, ftype))
                elif elem_type == "field":
                    fields_info.append((elem.get("name", "field"), elem.get("type_name", "UInt32")))
    elif hasattr(target, "__binary__") or inspect.isclass(target):
        target_cls: type = target if inspect.isclass(target) else type(target)
        cls_name = getattr(target_cls, "__name__", "Packet")
        hints = getattr(target_cls, "__annotations__", {})
        for fname, ftype in hints.items():
            fields_info.append((fname, ftype))
    else:
        raise TypeError(f"Cannot generate Wireshark dissector for unsupported target: {type(target).__name__}")

    proto_id = to_snake_case(protocol_name or cls_name)
    proto_title = description or f"{to_pascal_case(cls_name)} Protocol"

    lines: List[str] = [
        f"-- Wireshark Lua Dissector for {proto_title}",
        "-- Generated automatically by Binary Master",
        "",
        f'local proto = Proto("{proto_id}", "{proto_title}")',
        "",
        "-- Field definitions",
    ]

    field_defs: List[str] = []
    dissect_codes: List[str] = []
    field_vars: List[str] = []

    for fname, ftype in fields_info:
        f_defn, f_code, _ = _wireshark_field_for(fname, ftype, proto_id)
        field_defs.append(f_defn)
        dissect_codes.append(f_code)
        field_vars.append(f"f_{to_snake_case(fname)}")

    lines.extend(field_defs)
    lines.append("")
    lines.append(f"proto.fields = {{ {', '.join(field_vars)} }}")
    lines.append("")
    lines.append("-- Dissector function")
    lines.append("function proto.dissector(buffer, pinfo, tree)")
    lines.append("    local length = buffer:len()")
    lines.append("    if length == 0 then return end")
    lines.append("")
    lines.append("    pinfo.cols.protocol = proto.name")
    lines.append(f'    local subtree = tree:add(proto, buffer(), "{proto_title} Data")')
    lines.append("    local offset = 0")
    lines.append("")

    for code in dissect_codes:
        for cl in code.split("\n"):
            lines.append(f"    {cl}")
        lines.append("")

    lines.append("end")

    if port is not None:
        lines.append("")
        lines.append(f"-- Port registration (Port {port})")
        lines.append('local udp_table = DissectorTable.get("udp.port")')
        lines.append(f'udp_table:add({port}, proto)')
        lines.append('local tcp_table = DissectorTable.get("tcp.port")')
        lines.append(f'tcp_table:add({port}, proto)')

    lines.append("")
    return "\n".join(lines)


def write_wireshark(
    target: Any,
    path_or_file: Optional[Union[str, Path, IO[str]]] = None,
    protocol_name: Optional[str] = None,
    description: Optional[str] = None,
    port: Optional[int] = None,
) -> str:
    """Generate Wireshark Lua Dissector and optionally save to file or stream."""
    script = generate_wireshark_dissector(
        target,
        protocol_name=protocol_name,
        description=description,
        port=port,
    )
    if path_or_file is not None:
        if isinstance(path_or_file, (str, Path)):
            p = Path(path_or_file)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(script, encoding="utf-8")
        else:
            path_or_file.write(script)
    return script
