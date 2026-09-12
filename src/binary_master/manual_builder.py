"""Schema-first ManualBuilder and automated binary reader."""

from __future__ import annotations

import inspect
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import (
    Any,
    Callable,
    Dict,
    IO,
    List,
    Optional,
    Sequence,
    Tuple,
    Type,
    Union,
)

from binary_master.manual import (
    LayoutEntry,
    generate_bitfield_packet_diagram,
    generate_packet_diagram,
    inspect_struct_layout,
)
from binary_master.reader import BinaryReader


@dataclass
class DocumentElement:
    """A freeform narrative documentation chapter or section."""

    title: str
    content: str


@dataclass
class StructElement:
    """A registered @binary_struct class in the specification."""

    struct_cls: type
    name: Optional[str] = None
    desc: str = ""
    condition: Optional[str] = None
    condition_func: Optional[Callable[[Any], bool]] = None
    count: Optional[Union[int, str, Callable[[Any], int]]] = None


@dataclass
class ChoiceElement:
    """A polymorphic choice or variant point dispatched by a tag field."""

    name: str
    tag_field: Union[str, Callable[[Any], Any]]
    variants: Any
    desc: str = ""
    condition: Optional[str] = None
    condition_func: Optional[Callable[[Any], bool]] = None


@dataclass
class SectionElement:
    """A logical section divider grouping elements."""

    title: str
    desc: str = ""


@dataclass
class FieldElement:
    """An ad-hoc individual field entry without a full struct class."""

    name: str
    type_name: str
    size: int
    desc: str = ""
    endian: Optional[str] = None
    condition: Optional[str] = None
    condition_func: Optional[Callable[[Any], bool]] = None


class BuilderReadResult(dict):
    """Container for deserialized objects returned by ManualBuilder.read().

    Supports both dictionary-style key access (`res['header']`) and
    attribute-style dot access (`res.header`), including shadowed method names.
    """

    def __getattribute__(self, name: str) -> Any:
        if not name.startswith("__") and name != "to_dict":
            try:
                return dict.__getitem__(self, name)
            except KeyError:
                pass
        return super().__getattribute__(name)

    def __setattr__(self, name: str, value: Any) -> None:
        self[name] = value

    def __delattr__(self, name: str) -> None:
        if name in self:
            del self[name]
        else:
            raise AttributeError(f"'BuilderReadResult' object has no attribute '{name}'")

    def to_dict(self) -> Dict[str, Any]:
        """Convert result to a plain dictionary recursively."""
        out = {}
        for k in dict.keys(self):
            v = dict.__getitem__(self, k)
            if isinstance(v, BuilderReadResult):
                out[k] = v.to_dict()
            elif isinstance(v, list):
                out[k] = [item.to_dict() if isinstance(item, BuilderReadResult) else item for item in v]
            else:
                out[k] = v
        return out



def _normalize_variants(variants: Any) -> List[Tuple[Any, type, str]]:
    """Normalize variants dictionary or sequence into a list of (tag, cls, desc)."""
    norm: List[Tuple[Any, type, str]] = []
    if isinstance(variants, dict):
        for k, v in variants.items():
            if isinstance(v, tuple):
                cls = v[0]
                desc = v[1] if len(v) > 1 else (getattr(cls, "__doc__", "") or "")
            else:
                cls = v
                desc = getattr(cls, "__doc__", "") or ""
            norm.append((k, cls, desc or ""))
    elif isinstance(variants, (list, tuple)):
        for item in variants:
            if isinstance(item, tuple):
                if len(item) == 3:
                    norm.append((item[0], item[1], item[2] or ""))
                elif len(item) == 2:
                    norm.append((item[0], item[1], getattr(item[1], "__doc__", "") or ""))
                elif len(item) == 1:
                    norm.append(("-", item[0], getattr(item[0], "__doc__", "") or ""))
            elif hasattr(item, "__binary__"):
                norm.append(("-", item, getattr(item, "__doc__", "") or ""))
    return norm


def _clean_mermaid_id(name: str) -> str:
    """Clean a string to be a safe Mermaid node ID."""
    clean = re.sub(r"[^a-zA-Z0-9_]", "_", name)
    clean = re.sub(r"_+", "_", clean).strip("_")
    return clean or "node"


class ManualBuilder:
    """Declarative specification builder and automated deserializer for binary protocols.

    Enables schema-first manual generation with conditional branches, polymorphic variants,
    narrative document chapters, and automated schema-driven reading.
    """

    def __init__(
        self,
        title: str = "Binary Specification Manual",
        default_endian: str = "little",
        version: Optional[str] = None,
        description: str = "",
    ) -> None:
        self.title = title
        self.default_endian = default_endian
        self.version = version
        self.description = description
        self.elements: List[
            Union[DocumentElement, StructElement, ChoiceElement, SectionElement, FieldElement]
        ] = []

    def add_document(self, title: str, content: str) -> ManualBuilder:
        """Add a narrative documentation chapter or explanatory markdown section.

        Args:
            title: Section or chapter title.
            content: Markdown formatted text.

        Returns:
            self for method chaining.
        """
        self.elements.append(DocumentElement(title=title, content=content.strip()))
        return self

    def add_struct(
        self,
        struct_cls: type,
        name: Optional[str] = None,
        desc: str = "",
        condition: Optional[str] = None,
        condition_func: Optional[Callable[[Any], bool]] = None,
        count: Optional[Union[int, str, Callable[[Any], int]]] = None,
    ) -> ManualBuilder:
        """Register a @binary_struct class in the specification layout.

        Args:
            struct_cls: The @binary_struct class.
            name: Optional display name for this struct instance/field.
            desc: Optional description overriding or supplementing the docstring.
            condition: Human-readable condition string (e.g. "flags & 0x01 != 0").
            condition_func: Optional callable returning bool given the read context.
            count: Optional count if repeated (int, field name str, or callable).

        Returns:
            self for method chaining.
        """
        if not hasattr(struct_cls, "__binary__"):
            raise TypeError(f"Class {getattr(struct_cls, '__name__', str(struct_cls))} is not a binary_struct")

        self.elements.append(
            StructElement(
                struct_cls=struct_cls,
                name=name,
                desc=desc,
                condition=condition,
                condition_func=condition_func,
                count=count,
            )
        )
        return self

    def add_choice(
        self,
        name: str,
        tag_field: Union[str, Callable[[Any], Any]],
        variants: Any,
        desc: str = "",
        condition: Optional[str] = None,
        condition_func: Optional[Callable[[Any], bool]] = None,
    ) -> ManualBuilder:
        """Register a polymorphic branch or choice point dispatched by a tag field.

        Args:
            name: Logical name of the choice field/block.
            tag_field: Name of the preceding field or callable that determines the tag.
            variants: Dictionary mapping tag -> struct_cls or (struct_cls, desc),
                      or list of (tag, struct_cls, desc) tuples.
            desc: Description of this choice branch.
            condition: Optional condition under which this choice appears.
            condition_func: Optional callable returning bool given the read context.

        Returns:
            self for method chaining.
        """
        self.elements.append(
            ChoiceElement(
                name=name,
                tag_field=tag_field,
                variants=variants,
                desc=desc,
                condition=condition,
                condition_func=condition_func,
            )
        )
        return self

    def add_section(self, title: str, desc: str = "") -> ManualBuilder:
        """Add a section divider grouping subsequent elements.

        Args:
            title: Section title.
            desc: Section description.

        Returns:
            self for method chaining.
        """
        self.elements.append(SectionElement(title=title, desc=desc))
        return self

    def add_field(
        self,
        name: str,
        type_name: str,
        size: int,
        desc: str = "",
        endian: Optional[str] = None,
        condition: Optional[str] = None,
        condition_func: Optional[Callable[[Any], bool]] = None,
    ) -> ManualBuilder:
        """Add an ad-hoc field entry without requiring a full struct class.

        Args:
            name: Field name.
            type_name: Data type name (e.g. 'UInt32', 'Bytes').
            size: Size in bytes.
            desc: Field description.
            endian: Optional endianness ('little' or 'big').
            condition: Optional condition string.
            condition_func: Optional callable returning bool given the read context.

        Returns:
            self for method chaining.
        """
        self.elements.append(
            FieldElement(
                name=name,
                type_name=type_name,
                size=size,
                desc=desc,
                endian=endian,
                condition=condition,
                condition_func=condition_func,
            )
        )
        return self


    def generate_flowchart(self, direction: str = "TD") -> str:
        """Generate a Mermaid flowchart visualizing the execution flow and choice branches."""
        lines = [f"```mermaid\nflowchart {direction}"]

        # Track previous nodes that should connect to the current step
        prev_nodes: List[str] = []

        for idx, elem in enumerate(self.elements):
            if isinstance(elem, DocumentElement) or isinstance(elem, SectionElement):
                continue

            elem_id = f"E{idx}_{_clean_mermaid_id(getattr(elem, 'name', '') or str(idx))}"

            if isinstance(elem, StructElement):
                cls_name = elem.struct_cls.__name__
                disp_name = elem.name or cls_name
                entries = inspect_struct_layout(elem.struct_cls)
                size_str = f", {sum(e.size for e in entries)}B" if entries else ""
                count_str = f" [x{elem.count}]" if elem.count is not None else ""

                node_id = elem_id
                if elem.condition:
                    cond_id = f"Cond_{elem_id}"
                    lines.append(f'    {cond_id}{{"{elem.condition}?"}}')
                    for p in prev_nodes:
                        lines.append(f"    {p} --> {cond_id}")
                    lines.append(f'    {node_id}["{disp_name} ({cls_name}{size_str}){count_str}"]')
                    lines.append(f"    {cond_id} -->|yes| {node_id}")
                    prev_nodes = [node_id, f"{cond_id} -- no -->"]
                else:
                    lines.append(f'    {node_id}["{disp_name} ({cls_name}{size_str}){count_str}"]')
                    for p in prev_nodes:
                        if p.endswith("-->"):
                            lines.append(f"    {p} {node_id}")
                        else:
                            lines.append(f"    {p} --> {node_id}")
                    prev_nodes = [node_id]

            elif isinstance(elem, ChoiceElement):
                choice_id = f"Choice_{elem_id}"
                tag_name = elem.tag_field if isinstance(elem.tag_field, str) else "tag"
                choice_label = f"Choice: {elem.name} ({tag_name}?)"
                lines.append(f'    {choice_id}{{"{choice_label}"}}')

                for p in prev_nodes:
                    if p.endswith("-->"):
                        lines.append(f"    {p} {choice_id}")
                    else:
                        lines.append(f"    {p} --> {choice_id}")

                norm_vars = _normalize_variants(elem.variants)
                out_nodes = []
                for v_idx, (tag, v_cls, v_desc) in enumerate(norm_vars):
                    v_cls_name = getattr(v_cls, "__name__", str(v_cls))
                    v_id = f"V_{elem_id}_{v_idx}"
                    tag_label = f"Tag 0x{tag:02X}" if isinstance(tag, int) else f"Tag {tag}"
                    v_entries = inspect_struct_layout(v_cls)
                    v_size = f", {sum(e.size for e in v_entries)}B" if v_entries else ""
                    lines.append(f'    {v_id}["{v_cls_name}{v_size}"]')
                    lines.append(f'    {choice_id} -->|"{tag_label}"| {v_id}')
                    out_nodes.append(v_id)

                prev_nodes = out_nodes if out_nodes else [choice_id]

            elif isinstance(elem, FieldElement):
                node_id = elem_id
                field_label = f"{elem.name} ({elem.type_name}, {elem.size}B)"
                lines.append(f'    {node_id}["{field_label}"]')
                for p in prev_nodes:
                    if p.endswith("-->"):
                        lines.append(f"    {p} {node_id}")
                    else:
                        lines.append(f"    {p} --> {node_id}")
                prev_nodes = [node_id]

        lines.append("```")
        return "\n".join(lines)

    def build(
        self,
        diagram_direction: str = "TD",
        diagram_type: str = "flowchart",
        bits_per_row: int = 32,
        include_bitfield_diagram: bool = True,
        expand_bitfields: bool = False,
        font_size: Optional[str] = None,
        bit_width: Optional[int] = None,
        section_packet_diagrams: bool = False,
    ) -> str:
        """Build and return the formatted Markdown specification manual.

        Args:
            diagram_direction: Direction for Mermaid flowchart ('TD' or 'LR').
            diagram_type: Diagram types to include ('flowchart', 'packet', 'both', or 'none').
            bits_per_row: Packet diagram width in bits.
            include_bitfield_diagram: Whether to render bitfield diagrams.
            expand_bitfields: Whether to expand bitfields in packet diagrams.
            font_size: Optional font size for diagrams.
            bit_width: Optional bit width for packet diagrams.
            section_packet_diagrams: Whether to include packet diagrams per struct.

        Returns:
            The complete Markdown document as a string.
        """
        sections: List[str] = []
        sections.append(f"# {self.title}\n")

        # Overview
        sections.append("## Overview\n")
        if self.description:
            sections.append(f"{self.description.strip()}\n")
        if self.version:
            sections.append(f"- **Version**: `{self.version}`")
        sections.append(f"- **Default Endianness**: {self.default_endian.capitalize()}")

        struct_count = sum(1 for e in self.elements if isinstance(e, StructElement))
        choice_count = sum(1 for e in self.elements if isinstance(e, ChoiceElement))
        sections.append(f"- **Defined Structures**: {struct_count}")
        if choice_count > 0:
            sections.append(f"- **Choice / Branch Points**: {choice_count}")
        sections.append("")

        # Document elements registered at the top before any structs
        elem_idx = 0
        while elem_idx < len(self.elements) and isinstance(self.elements[elem_idx], DocumentElement):
            doc = self.elements[elem_idx]
            sections.append(f"## {doc.title}\n")
            sections.append(f"{doc.content}\n")
            elem_idx += 1

        # Structure Diagram
        if any(not isinstance(e, DocumentElement) for e in self.elements):
            if diagram_type in ("flowchart", "both"):
                sections.append("## Structure Diagram (Flowchart)\n")
                sections.append(self.generate_flowchart(direction=diagram_direction))
                sections.append("")

        # Memory Layout & Structure Specifications
        sections.append("## Data Structures & Layout\n")

        all_bitfields: List[LayoutEntry] = []

        while elem_idx < len(self.elements):
            elem = self.elements[elem_idx]
            elem_idx += 1

            if isinstance(elem, DocumentElement):
                sections.append(f"## {elem.title}\n")
                sections.append(f"{elem.content}\n")

            elif isinstance(elem, SectionElement):
                sections.append(f"### Section: {elem.title}\n")
                if elem.desc:
                    sections.append(f"{elem.desc}\n")

            elif isinstance(elem, StructElement):
                cls_name = elem.struct_cls.__name__
                disp_name = elem.name or cls_name
                entries = inspect_struct_layout(elem.struct_cls)
                total_size = sum(e.size for e in entries)

                sections.append(f"### Struct `{disp_name}` ({cls_name})\n")
                if elem.condition:
                    sections.append(f"> [!NOTE]\n> **Condition**: `{elem.condition}`\n")
                if elem.count is not None:
                    sections.append(f"> [!NOTE]\n> **Repetition Count**: `{elem.count}`\n")

                doc = elem.desc or getattr(elem.struct_cls, "__doc__", "") or ""
                if doc:
                    sections.append(f"{inspect.cleandoc(doc)}\n")

                sections.append(f"- **Total Size**: {total_size} bytes (`0x{total_size:04X}`)\n")

                for e in entries:
                    if e.subfields:
                        all_bitfields.append(e)

                if section_packet_diagrams and entries:
                    p_diag = generate_packet_diagram(
                        entries,
                        title=f"{disp_name} Layout",
                        bits_per_row=bits_per_row,
                        expand_bitfields=expand_bitfields,
                        font_size=font_size,
                        bit_width=bit_width,
                        relative_offset=True,
                    )
                    if p_diag:
                        sections.append(p_diag)
                        sections.append("")

                self._render_struct_table(entries, sections)

            elif isinstance(elem, ChoiceElement):
                sections.append(f"### Choice Branch: `{elem.name}`\n")
                tag_name = elem.tag_field if isinstance(elem.tag_field, str) else "tag_field"
                sections.append(f"Dispatched by field: `{tag_name}`\n")
                if elem.condition:
                    sections.append(f"> [!NOTE]\n> **Condition**: `{elem.condition}`\n")
                if elem.desc:
                    sections.append(f"{elem.desc}\n")

                sections.append("Depending on the tag value, one of the following variant structures is used:\n")
                norm_vars = _normalize_variants(elem.variants)

                for tag, v_cls, v_desc in norm_vars:
                    v_cls_name = getattr(v_cls, "__name__", str(v_cls))
                    tag_str = f"Tag `0x{tag:02X}`" if isinstance(tag, int) else (f"Tag `{tag}`" if tag != "-" else "")
                    header = f"#### [Variant] {tag_str + ': ' if tag_str else ''}`{v_cls_name}`\n"
                    sections.append(header)

                    doc_text = v_desc or getattr(v_cls, "__doc__", "") or ""
                    if doc_text:
                        sections.append(f"{inspect.cleandoc(doc_text)}\n")

                    v_entries = inspect_struct_layout(v_cls)
                    for e in v_entries:
                        if e.subfields:
                            all_bitfields.append(e)

                    if v_entries:
                        v_total = sum(e.size for e in v_entries)
                        sections.append(f"- **Variant Size**: {v_total} bytes (`0x{v_total:04X}`)\n")
                        if section_packet_diagrams:
                            v_diag = generate_packet_diagram(
                                v_entries,
                                title=f"{v_cls_name} Layout",
                                bits_per_row=bits_per_row,
                                expand_bitfields=expand_bitfields,
                                font_size=font_size,
                                bit_width=bit_width,
                                relative_offset=True,
                            )
                            if v_diag:
                                sections.append(v_diag)
                                sections.append("")
                        self._render_struct_table(v_entries, sections)

            elif isinstance(elem, FieldElement):
                sections.append(f"### Field `{elem.name}`\n")
                if elem.condition:
                    sections.append(f"> [!NOTE]\n> **Condition**: `{elem.condition}`\n")
                if elem.desc:
                    sections.append(f"{elem.desc}\n")
                sections.append(f"- **Type**: `{elem.type_name}`")
                sections.append(f"- **Size**: {elem.size} bytes")
                if elem.endian:
                    sections.append(f"- **Endianness**: {elem.endian}")
                sections.append("")

        # Aggregated Bitfield Details if any exist
        if include_bitfield_diagram and all_bitfields:
            sections.append("## Bitfield Details\n")
            seen_bitfields = set()
            for bf in all_bitfields:
                bf_name = bf.name or bf.type_name
                if bf_name in seen_bitfields:
                    continue
                seen_bitfields.add(bf_name)

                sections.append(f"### `{bf_name}` (Size: {bf.size}B)\n")
                if bf.struct_doc:
                    sections.append(f"{bf.struct_doc}\n")

                diag = generate_bitfield_packet_diagram(bf)
                if diag:
                    sections.append(diag)
                    sections.append("")

                sections.append("| Bit Range | Field Name | Width | Description |")
                sections.append("|---|---|---|---|")
                for sub in (bf.subfields or []):
                    bit_range = f"`[{sub.get('bit_start', 0)}:{sub.get('bit_end', 0)}]`"
                    sub_name = f"`{sub.get('name', '-')}`"
                    width_str = f"{sub.get('width', 1)} bit(s)"
                    sub_desc = sub.get("description") or "-"
                    sections.append(f"| {bit_range} | {sub_name} | {width_str} | {sub_desc} |")
                sections.append("")

        return "\n".join(sections)

    def _render_struct_table(self, entries: List[LayoutEntry], sec_list: List[str]) -> None:
        """Render a layout table for struct fields with relative offsets."""
        sec_list.append("| Relative Offset | Size (B) | Field Name | Type | Endian | Description |")
        sec_list.append("|---|---|---|---|---|---|")
        for entry in entries:
            rel_off = f"`+0x{entry.offset:02X}`"
            size_str = str(entry.size)
            name_str = f"`{entry.name}`" if entry.name else "-"
            type_str = f"`{entry.type_name}`"
            endian_str = entry.endian or "-"
            desc_str = entry.description or "-"
            if entry.target_offset is not None:
                target_marker = f"`-> 0x{entry.target_offset:04X}`"
                desc_str = f"{desc_str} ({target_marker})" if desc_str != "-" else target_marker
            sec_list.append(f"| {rel_off} | {size_str} | {name_str} | {type_str} | {endian_str} | {desc_str} |")
        sec_list.append("")

    def to_markdown(self, **kwargs) -> str:
        """Alias for build()."""
        return self.build(**kwargs)

    def write(
        self,
        path_or_file: Optional[Union[str, Path, IO[str]]] = None,
        **kwargs,
    ) -> str:
        """Generate specification markdown and optionally write it to a file or stream.

        Args:
            path_or_file: File path string, Path object, or writable text stream.
            **kwargs: Options forwarded to build().

        Returns:
            The complete Markdown document as a string.
        """
        content = self.build(**kwargs)
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

    def write_manual(
        self,
        path_or_file: Optional[Union[str, Path, IO[str]]] = None,
        **kwargs,
    ) -> str:
        """Alias for write() matching BinaryWriter naming."""
        return self.write(path_or_file, **kwargs)

    def to_c_header(self, guard: Optional[str] = None, pack: bool = True) -> str:
        """Generate a complete C99/C11 header file from this specification schema.

        Args:
            guard: Optional custom include guard name (e.g. 'MY_PROTOCOL_H').
            pack: Whether to wrap structs with #pragma pack(push, 1) and #pragma pack(pop).

        Returns:
            The generated C header code as a string.
        """
        from binary_master.c_header import generate_c_header

        return generate_c_header(self, guard=guard, pack=pack)

    def write_c_header(
        self,
        path_or_file: Optional[Union[str, Path, IO[str]]] = None,
        guard: Optional[str] = None,
        pack: bool = True,
    ) -> str:
        """Generate C header code and optionally save it to a file or writable stream.

        Args:
            path_or_file: Target file path, Path object, or writable text stream.
            guard: Optional custom include guard name.
            pack: Whether to wrap structs with #pragma pack(push, 1) and #pragma pack(pop).

        Returns:
            The generated C header code as a string.
        """
        from binary_master.c_header import write_c_header

        return write_c_header(self, path_or_file=path_or_file, guard=guard, pack=pack)

    def to_rust(self) -> str:
        """Generate Rust type definitions and packed structs from this schema."""
        from binary_master.code_gen.rust import generate_rust_code

        return generate_rust_code(self)

    def write_rust(
        self,
        path_or_file: Optional[Union[str, Path, IO[str]]] = None,
    ) -> str:
        """Generate Rust code and optionally save it to a file or stream."""
        from binary_master.code_gen.rust import write_rust

        return write_rust(self, path_or_file=path_or_file)

    def to_cpp(self) -> str:
        """Generate modern C++17/20 header with packed structs and std::variant."""
        from binary_master.code_gen.cpp import generate_cpp_code

        return generate_cpp_code(self)

    def write_cpp(
        self,
        path_or_file: Optional[Union[str, Path, IO[str]]] = None,
    ) -> str:
        """Generate modern C++ header and optionally save it to a file or stream."""
        from binary_master.code_gen.cpp import write_cpp

        return write_cpp(self, path_or_file=path_or_file)

    def to_csharp(self, namespace: str = "BinaryProtocol") -> str:
        """Generate C# type definitions with sequential structs and explicit unions."""
        from binary_master.code_gen.csharp import generate_csharp_code

        return generate_csharp_code(self, namespace=namespace)

    def write_csharp(
        self,
        path_or_file: Optional[Union[str, Path, IO[str]]] = None,
        namespace: str = "BinaryProtocol",
    ) -> str:
        """Generate C# code and optionally save it to a file or stream."""
        from binary_master.code_gen.csharp import write_csharp

        return write_csharp(self, path_or_file=path_or_file, namespace=namespace)

    def to_go(self, package_name: str = "protocol") -> str:
        """Generate Go structs, const tags, and interfaces from this schema."""
        from binary_master.code_gen.go import generate_go_code

        return generate_go_code(self, package_name=package_name)

    def write_go(
        self,
        path_or_file: Optional[Union[str, Path, IO[str]]] = None,
        package_name: str = "protocol",
    ) -> str:
        """Generate Go code and optionally save it to a file or stream."""
        from binary_master.code_gen.go import write_go

        return write_go(self, path_or_file=path_or_file, package_name=package_name)

    def to_code(self, lang: str, **kwargs) -> str:
        """Generate source code in the specified language ('c', 'rust', 'cpp', 'csharp', 'go')."""
        from binary_master.code_gen import generate_code

        return generate_code(self, lang=lang, **kwargs)

    def write_code(
        self,
        path_or_file: Union[str, Path, IO[str]],
        lang: Optional[str] = None,
        **kwargs,
    ) -> str:
        """Generate source code and save to file, automatically inferring language if omitted."""
        from binary_master.code_gen import write_code

        return write_code(self, path_or_file=path_or_file, lang=lang, **kwargs)


    def read(
        self,
        reader_or_bytes: Union[bytes, bytearray, BinaryReader, IO[bytes]],
        endian: Optional[str] = None,
    ) -> BuilderReadResult:
        """Automatically deserialize binary data according to the registered schema.

        Args:
            reader_or_bytes: Binary data as bytes/bytearray, BinaryReader instance, or stream.
            endian: Optional endianness override.

        Returns:
            A BuilderReadResult object containing deserialized struct instances and fields.
        """
        if isinstance(reader_or_bytes, BinaryReader):
            reader = reader_or_bytes
        elif isinstance(reader_or_bytes, (bytes, bytearray)):
            reader = BinaryReader(reader_or_bytes, default_endian=endian or self.default_endian)
        elif hasattr(reader_or_bytes, "read"):
            data = reader_or_bytes.read()
            reader = BinaryReader(data, default_endian=endian or self.default_endian)
        else:
            raise TypeError(f"Unsupported reader_or_bytes type: {type(reader_or_bytes).__name__}")

        result = BuilderReadResult()

        for elem in self.elements:
            if isinstance(elem, (DocumentElement, SectionElement)):
                continue

            # Evaluate condition
            cond_func = getattr(elem, "condition_func", None)
            if cond_func is not None:
                if not cond_func(result):
                    continue
            elif getattr(elem, "condition", None) is not None:
                if not self._eval_condition(elem.condition, result):
                    continue


            if isinstance(elem, StructElement):
                key = elem.name or elem.struct_cls.__name__
                if elem.count is not None:
                    # Repeated struct
                    n_count = self._resolve_count(elem.count, result)
                    items = [
                        reader.read_struct(elem.struct_cls, endian=endian or self.default_endian)
                        for _ in range(n_count)
                    ]
                    result[key] = items
                else:
                    obj = reader.read_struct(elem.struct_cls, endian=endian or self.default_endian)
                    result[key] = obj

            elif isinstance(elem, ChoiceElement):
                # Resolve tag value
                tag_val = self._resolve_tag_value(elem.tag_field, result)
                variant_cls = self._match_variant(elem.variants, tag_val)
                if variant_cls is None:
                    raise ValueError(f"Tag value {tag_val!r} did not match any variant for choice '{elem.name}'")
                variant_obj = reader.read_struct(variant_cls, endian=endian or self.default_endian)
                result[elem.name] = variant_obj

            elif isinstance(elem, FieldElement):
                val = self._read_primitive_field(reader, elem, endian=endian or self.default_endian)
                result[elem.name] = val

        return result

    def _eval_condition(self, condition: str, result: BuilderReadResult) -> bool:
        """Safely evaluate a condition string against current read context."""
        ctx = dict(result)
        for v in result.values():
            if hasattr(v, "__dict__"):
                ctx.update(v.__dict__)
            elif hasattr(v, "__binary__"):
                for k in getattr(v, "__binary__", {}).get("fields", {}):
                    if hasattr(v, k):
                        ctx[k] = getattr(v, k)
        try:
            return bool(eval(condition, {"__builtins__": {}}, ctx))
        except Exception:
            return True

    def _resolve_count(
        self,
        count: Union[int, str, Callable[[Any], int]],
        result: BuilderReadResult,
    ) -> int:
        """Resolve count parameter to an integer."""
        if isinstance(count, int):
            return count
        if callable(count):
            return int(count(result))
        if isinstance(count, str):
            if count in result:
                return int(result[count])
            for v in result.values():
                if hasattr(v, count):
                    return int(getattr(v, count))
            raise ValueError(f"Count field '{count}' not found in read context")
        return int(count)

    def _resolve_tag_value(
        self,
        tag_field: Union[str, Callable[[Any], Any]],
        result: BuilderReadResult,
    ) -> Any:
        """Resolve the tag value from context or previous struct attributes."""
        if callable(tag_field):
            return tag_field(result)

        if tag_field in result:
            return result[tag_field]

        for v in result.values():
            if hasattr(v, tag_field):
                return getattr(v, tag_field)

        raise ValueError(f"Tag field '{tag_field}' not found in read context to resolve choice")

    def _match_variant(self, variants: Any, tag_val: Any) -> Optional[type]:
        """Match a tag value against registered variants."""
        norm_vars = _normalize_variants(variants)
        for tag, cls, _ in norm_vars:
            if tag == tag_val:
                return cls
            try:
                if int(tag) == int(tag_val):
                    return cls
            except (ValueError, TypeError):
                pass
        return None

    def _read_primitive_field(
        self,
        reader: BinaryReader,
        elem: FieldElement,
        endian: str,
    ) -> Any:
        """Read an ad-hoc primitive field."""
        t = elem.type_name.lower()
        if "uint8" in t:
            return reader.read_uint8()
        if "uint16" in t:
            return reader.read_uint16(endian=endian)
        if "uint32" in t:
            return reader.read_uint32(endian=endian)
        if "uint64" in t:
            return reader.read_uint64(endian=endian)
        if "int8" in t:
            return reader.read_int8()
        if "int16" in t:
            return reader.read_int16(endian=endian)
        if "int32" in t:
            return reader.read_int32(endian=endian)
        if "int64" in t:
            return reader.read_int64(endian=endian)
        if "float32" in t:
            return reader.read_float32(endian=endian)
        if "float64" in t:
            return reader.read_float64(endian=endian)
        return reader.read_bytes(elem.size)
