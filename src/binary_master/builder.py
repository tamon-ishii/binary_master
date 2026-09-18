"""Schema-first BinaryBuilder / Builder and automated binary reader."""

from __future__ import annotations

import inspect
import re
from dataclasses import dataclass
from pathlib import Path
from typing import (
    Any,
    Callable,
    Dict,
    IO,
    List,
    Literal,
    Mapping,
    Optional,
    Tuple,
    Union,
    cast,
)

from binary_master.manual import (
    LayoutEntry,
    generate_bitfield_packet_diagram,
    generate_packet_diagram,
    inspect_struct_layout,
    resolve_language,
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
    is_end: bool = False
    spec_count: Optional[Union[int, str, bool]] = None


class _SectionContext:
    """Context manager and chaining proxy for section and caption grouping."""

    def __init__(
        self,
        builder: Any,
        title: str,
        desc: str = "",
        spec_count: Optional[Union[int, str, bool]] = None,
        repeat: Optional[Union[int, str, bool]] = None,
    ) -> None:
        self._builder = builder
        self._title = title
        self._desc = desc
        self._spec_count = spec_count if spec_count is not None else repeat
        self._in_context = False
        self._elem = SectionElement(title=title, desc=desc, spec_count=self._spec_count)
        self._builder.elements.append(self._elem)

    def __enter__(self) -> Any:
        self._in_context = True
        return self._builder

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if self._in_context:
            self._builder.elements.append(
                SectionElement(
                    title=self._title,
                    desc=self._desc,
                    is_end=True,
                    spec_count=self._spec_count,
                )
            )

    def __getattr__(self, name: str) -> Any:
        return getattr(self._builder, name)


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
    """Container for deserialized objects returned by BinaryBuilder.read() / Builder.read().

    Supports both dictionary-style key access (`res['header']`) and
    attribute-style dot access (`res.header`), including shadowed method names.
    Also supports hexdump() and dump() when read with trace=True.
    """

    def __getattribute__(self, name: str) -> Any:
        if not name.startswith("__") and name not in ("to_dict", "hexdump", "dump", "_writer"):
            try:
                return dict.__getitem__(self, name)
            except KeyError:
                pass
        return super().__getattribute__(name)

    def __setattr__(self, name: str, value: Any) -> None:
        if name == "_writer":
            self.__dict__["_writer"] = value
            return
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

    def hexdump(
        self,
        *,
        width: int = 16,
        color: bool = False,
        annotate: bool = True,
        show_ascii: bool = True,
        show_header: bool = True,
        cursor: Optional[int] = None,
        max_bytes: Optional[int] = None,
    ) -> str:
        """Generate annotated hexdump for this read result (requires trace=True)."""
        writer = self.__dict__.get("_writer")
        if writer is not None:
            from binary_master.debug import hexdump as _hexdump

            return _hexdump(
                writer,
                width=width,
                color=color,
                annotate=annotate,
                show_ascii=show_ascii,
                show_header=show_header,
                cursor=cursor,
                max_bytes=max_bytes,
            )
        raise RuntimeError(
            "hexdump() is only available on BuilderReadResult when read(..., trace=True) is used, "
            "or by calling builder.hexdump(data) directly."
        )

    def dump(
        self,
        format: str = "table",
        *,
        color: bool = False,
        **kwargs: Any,
    ) -> Any:
        """Dump decoded fields in table, json, or dict format (requires trace=True)."""
        writer = self.__dict__.get("_writer")
        if writer is not None:
            return writer.dump(format=format, color=color, **kwargs)
        raise RuntimeError(
            "dump() is only available on BuilderReadResult when read(..., trace=True) is used, "
            "or by calling builder.dump(data, format=...) directly."
        )



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


class BinaryBuilder:
    """Declarative specification builder, multi-language code generator, and automated deserializer.

    Enables schema-first manual generation with conditional branches, polymorphic variants,
    narrative document chapters, multi-language code export (C, Rust, C++, C#, Go),
    and automated schema-driven reading.
    """

    def __init__(
        self,
        title: str = "Binary Specification Manual",
        default_endian: str = "little",
        version: Optional[str] = None,
        description: str = "",
        lang: Literal["auto", "en", "ja"] = "auto",
    ) -> None:
        self.title = title
        self.default_endian = default_endian
        self.version = version
        self.description = description
        self.lang = lang

        self.elements: List[
            Union[DocumentElement, StructElement, ChoiceElement, SectionElement, FieldElement]
        ] = []

    def add_document(self, title: str, content: str) -> BinaryBuilder:
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
    ) -> BinaryBuilder:
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
    ) -> BinaryBuilder:
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

    def set_caption(
        self,
        title: str,
        desc: str = "",
        spec_count: Optional[Union[int, str, bool]] = None,
        repeat: Optional[Union[int, str, bool]] = None,
    ) -> _SectionContext:
        """Set active section caption/description/spec_count for subsequent builder elements.

        Can be called directly or used as a context manager:
            with builder.set_caption("offsets", desc="Table of chunk offsets", spec_count="num_chunk"):
                ...

        Args:
            title: Section/caption title.
            desc: Optional section/caption description.
            spec_count: Optional specification count metadata (e.g. 'num_chunk', 5, -1).
            repeat: Alias for spec_count.

        Returns:
            _SectionContext context manager and proxy.
        """
        eff_spec = spec_count if spec_count is not None else repeat
        return _SectionContext(self, title=title, desc=desc, spec_count=eff_spec)

    def caption(
        self,
        title: str,
        desc: str = "",
        spec_count: Optional[Union[int, str, bool]] = None,
        repeat: Optional[Union[int, str, bool]] = None,
    ) -> _SectionContext:
        """Concise alias for set_caption()."""
        return self.set_caption(title=title, desc=desc, spec_count=spec_count, repeat=repeat)

    def section(
        self,
        title: str,
        desc: str = "",
        spec_count: Optional[Union[int, str, bool]] = None,
        repeat: Optional[Union[int, str, bool]] = None,
    ) -> _SectionContext:
        """Alias for set_caption()."""
        return self.set_caption(title=title, desc=desc, spec_count=spec_count, repeat=repeat)

    def add_section(
        self,
        title: str,
        desc: str = "",
        spec_count: Optional[Union[int, str, bool]] = None,
        repeat: Optional[Union[int, str, bool]] = None,
    ) -> _SectionContext:
        """Alias for set_caption()."""
        return self.set_caption(title=title, desc=desc, spec_count=spec_count, repeat=repeat)

    def add_caption(
        self,
        title: str,
        desc: str = "",
        spec_count: Optional[Union[int, str, bool]] = None,
        repeat: Optional[Union[int, str, bool]] = None,
    ) -> _SectionContext:
        """Alias for set_caption()."""
        return self.set_caption(title=title, desc=desc, spec_count=spec_count, repeat=repeat)

    def add_field(
        self,
        name: str,
        type_name: str,
        size: int,
        desc: str = "",
        endian: Optional[str] = None,
        condition: Optional[str] = None,
        condition_func: Optional[Callable[[Any], bool]] = None,
    ) -> BinaryBuilder:
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

    def import_writer(
        self,
        writer: Any,
        *,
        include_fields: bool = True,
    ) -> BinaryBuilder:
        """Import section captions and layout fields recorded by a BinaryWriter.

        Enables seamless transition from procedural binary writing to declarative schema
        specification, diagramming, multi-language code export, and automated reading.

        Args:
            writer: BinaryWriter or any object with recorded `entries`.
            include_fields: If True, imports both section captions and fields.
                            If False, imports only unique section captions.

        Returns:
            self for method chaining.
        """
        entries = getattr(writer, "entries", None)
        if entries is None:
            raise TypeError(f"Expected a BinaryWriter or object with 'entries', got {type(writer).__name__}")

        current_caption: Optional[str] = None
        seen_captions = set()

        for entry in entries:
            cap = getattr(entry, "caption", None)
            cap_desc = getattr(entry, "caption_desc", "") or ""

            if cap != current_caption:
                current_caption = cap
                if current_caption and (include_fields or current_caption not in seen_captions):
                    seen_captions.add(current_caption)
                    self.add_section(current_caption, desc=cap_desc)

            if include_fields:
                fname = getattr(entry, "name", "") or f"field_0x{getattr(entry, 'offset', 0):04X}"
                ftype = getattr(entry, "type_name", "Bytes")
                fsize = getattr(entry, "size", 0)
                fdesc = getattr(entry, "description", "") or ""
                fendian = getattr(entry, "endian", None)

                self.add_field(
                    name=fname,
                    type_name=ftype,
                    size=fsize,
                    desc=fdesc,
                    endian=fendian,
                )

        return self

    def import_captions(self, writer: Any) -> BinaryBuilder:
        """Import unique section captions from a BinaryWriter into the builder.

        Args:
            writer: BinaryWriter with recorded layout entries.

        Returns:
            self for method chaining.
        """
        return self.import_writer(writer, include_fields=False)

    @classmethod
    def from_writer(
        cls,
        writer: Any,
        title: str = "Binary Specification Manual",
        default_endian: Optional[str] = None,
        version: Optional[str] = None,
        description: str = "",
    ) -> BinaryBuilder:
        """Construct a new Builder schema from a populated BinaryWriter instance.

        Args:
            writer: Populated BinaryWriter instance.
            title: Title for the specification document.
            default_endian: Default endianness (auto-detected from writer if omitted).
            version: Optional protocol version.
            description: Optional protocol description.

        Returns:
            A new BinaryBuilder configured with sections and fields from writer.
        """
        if hasattr(writer, "to_builder"):
            return writer.to_builder(
                title=title,
                default_endian=default_endian,
                version=version,
                description=description,
            )

        w_endian = getattr(writer, "default_endian", None)
        norm_endian = str(w_endian).lower() if w_endian else "little"
        if "big" in norm_endian:
            resolved_endian = "big"
        else:
            resolved_endian = "little"

        builder = cls(
            title=title,
            default_endian=default_endian or resolved_endian,
            version=version,
            description=description,
        )
        builder.import_writer(writer, include_fields=True)
        return builder


    def generate_flowchart(self, direction: str = "TD") -> str:
        """Generate a Mermaid flowchart visualizing the execution flow and choice branches."""
        lines = [f"```mermaid\nflowchart {direction}"]

        has_sections = any(
            isinstance(e, SectionElement) and not getattr(e, "is_end", False)
            for e in self.elements
        )

        prev_nodes: List[str] = []
        active_subgraph: Optional[str] = None

        def indent(level: int = 1) -> str:
            extra = 1 if (has_sections and active_subgraph is not None) else 0
            return "    " * (level + extra)

        for idx, elem in enumerate(self.elements):
            if isinstance(elem, DocumentElement):
                continue

            if isinstance(elem, SectionElement):
                if not has_sections:
                    continue
                if getattr(elem, "is_end", False):
                    if active_subgraph is not None:
                        lines.append("    end")
                        active_subgraph = None
                else:
                    if active_subgraph is not None:
                        lines.append("    end")
                    sg_id = f"SG_{idx}_{_clean_mermaid_id(elem.title)}"
                    sg_label = elem.title + (f" - {elem.desc}" if elem.desc else "")
                    lines.append(f'    subgraph {sg_id} ["{sg_label}"]')
                    active_subgraph = sg_id
                continue

            elem_id = f"E{idx}_{_clean_mermaid_id(getattr(elem, 'name', '') or str(idx))}"
            pfx = indent(1)

            if isinstance(elem, StructElement):
                cls_name = elem.struct_cls.__name__
                disp_name = elem.name or cls_name
                entries = inspect_struct_layout(elem.struct_cls)
                size_str = f", {sum(e.size for e in entries)}B" if entries else ""
                count_str = f" [x{elem.count}]" if elem.count is not None else ""

                node_id = elem_id
                if elem.condition:
                    cond_id = f"Cond_{elem_id}"
                    lines.append(f'{pfx}{cond_id}{{"{elem.condition}?"}}')
                    for p in prev_nodes:
                        lines.append(f"{pfx}{p} --> {cond_id}")
                    lines.append(f'{pfx}{node_id}["{disp_name} ({cls_name}{size_str}){count_str}"]')
                    lines.append(f"{pfx}{cond_id} -->|yes| {node_id}")
                    prev_nodes = [node_id, f"{cond_id} -- no -->"]
                else:
                    lines.append(f'{pfx}{node_id}["{disp_name} ({cls_name}{size_str}){count_str}"]')
                    for p in prev_nodes:
                        if p.endswith("-->"):
                            lines.append(f"{pfx}{p} {node_id}")
                        else:
                            lines.append(f"{pfx}{p} --> {node_id}")
                    prev_nodes = [node_id]

            elif isinstance(elem, ChoiceElement):
                choice_id = f"Choice_{elem_id}"
                tag_name = elem.tag_field if isinstance(elem.tag_field, str) else "tag"
                choice_label = f"Choice: {elem.name} ({tag_name}?)"
                lines.append(f'{pfx}{choice_id}{{"{choice_label}"}}')

                for p in prev_nodes:
                    if p.endswith("-->"):
                        lines.append(f"{pfx}{p} {choice_id}")
                    else:
                        lines.append(f"{pfx}{p} --> {choice_id}")

                norm_vars = _normalize_variants(elem.variants)
                out_nodes = []
                for v_idx, (tag, v_cls, v_desc) in enumerate(norm_vars):
                    v_cls_name = getattr(v_cls, "__name__", str(v_cls))
                    v_id = f"V_{elem_id}_{v_idx}"
                    tag_label = f"Tag 0x{tag:02X}" if isinstance(tag, int) else f"Tag {tag}"
                    v_entries = inspect_struct_layout(v_cls)
                    v_size = f", {sum(e.size for e in v_entries)}B" if v_entries else ""
                    lines.append(f'{pfx}{v_id}["{v_cls_name}{v_size}"]')
                    lines.append(f'{pfx}{choice_id} -->|"{tag_label}"| {v_id}')
                    out_nodes.append(v_id)

                prev_nodes = out_nodes if out_nodes else [choice_id]

            elif isinstance(elem, FieldElement):
                node_id = elem_id
                field_label = f"{elem.name} ({elem.type_name}, {elem.size}B)"
                lines.append(f'{pfx}{node_id}["{field_label}"]')
                for p in prev_nodes:
                    if p.endswith("-->"):
                        lines.append(f"{pfx}{p} {node_id}")
                    else:
                        lines.append(f"{pfx}{p} --> {node_id}")
                prev_nodes = [node_id]

        if active_subgraph is not None:
            lines.append("    end")

        lines.append("```")
        return "\n".join(lines)

    def build(
        self,
        diagram_direction: Literal["TD", "LR"] = "TD",
        diagram_type: Literal["both", "flowchart", "packet", "none"] = "both",
        bits_per_row: int = 32,
        include_bitfield_diagram: bool = True,
        expand_bitfields: bool = False,
        font_size: Optional[str] = None,
        bit_width: Optional[int] = None,
        section_packet_diagrams: bool = False,
        lang: Optional[Literal["auto", "en", "ja"]] = None,
        large_data_threshold: int = 64,
        **kwargs: Any,
    ) -> str:
        """Build and return the formatted Markdown specification manual.

        Args:
            diagram_direction: Direction for Mermaid flowchart ('TD' or 'LR'). Default is 'TD'.
            diagram_type: Diagram types to include ('both', 'flowchart', 'packet', or 'none'). Default is 'both'.
            bits_per_row: Packet diagram width in bits.
            include_bitfield_diagram: Whether to render bitfield diagrams.
            expand_bitfields: Whether to expand bitfields in packet diagrams.
            font_size: Optional font size for diagrams.
            bit_width: Optional bit width for packet diagrams.
            section_packet_diagrams: Whether to include packet diagrams per struct.
            lang: Output language ('auto', 'en', or 'ja'). Defaults to builder's lang setting (default 'auto').
            large_data_threshold: Threshold in bytes to summarize large data blocks in packet diagrams (default 64).
            **kwargs: Extra options forwarded to internal renderers.

        Returns:
            The complete Markdown document as a string.
        """
        is_ja = resolve_language(lang or getattr(self, "lang", "auto")) == "ja"

        sections: List[str] = []
        sections.append(f"# {self.title}\n")


        # Overview
        if is_ja:
            sections.append("## 概要\n")
            if self.description:
                sections.append(f"{self.description.strip()}\n")
            if self.version:
                sections.append(f"- **バージョン**: `{self.version}`")
            endian_disp = "リトルエンディアン (Little)" if self.default_endian.lower() == "little" else "ビッグエンディアン (Big)"
            sections.append(f"- **デフォルトエンディアン**: {endian_disp}")

            struct_count = sum(1 for e in self.elements if isinstance(e, StructElement))
            choice_count = sum(1 for e in self.elements if isinstance(e, ChoiceElement))
            sections.append(f"- **定義された構造体数**: {struct_count}")
            if choice_count > 0:
                sections.append(f"- **条件分岐数**: {choice_count}")
            sections.append("")
        else:
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
        while elem_idx < len(self.elements):
            doc = self.elements[elem_idx]
            if not isinstance(doc, DocumentElement):
                break
            sections.append(f"## {doc.title}\n")
            sections.append(f"{doc.content}\n")
            elem_idx += 1

        # Structure Diagram
        if any(not isinstance(e, DocumentElement) for e in self.elements):
            if diagram_type in ("flowchart", "both"):
                sections.append("## 構造図 (フローチャート)\n" if is_ja else "## Structure Diagram (Flowchart)\n")
                sections.append(self.generate_flowchart(direction=diagram_direction))
                sections.append("")

        # Memory Layout & Structure Specifications
        sections.append("## データ構造とレイアウト\n" if is_ja else "## Data Structures & Layout\n")

        all_bitfields: List[LayoutEntry] = []

        while elem_idx < len(self.elements):
            elem = self.elements[elem_idx]
            elem_idx += 1

            if isinstance(elem, DocumentElement):
                sections.append(f"## {elem.title}\n")
                sections.append(f"{elem.content}\n")

            elif isinstance(elem, SectionElement):
                if getattr(elem, "is_end", False):
                    continue
                sec_lbl = "セクション" if is_ja else "Section"
                sections.append(f"### {sec_lbl}: {elem.title}\n")
                if elem.desc:
                    sections.append(f"{elem.desc}\n")

            elif isinstance(elem, StructElement):
                cls_name = elem.struct_cls.__name__
                disp_name = elem.name or cls_name
                entries = inspect_struct_layout(elem.struct_cls)
                total_size = sum(e.size for e in entries)

                st_lbl = "構造体" if is_ja else "Struct"
                sections.append(f"### {st_lbl} `{disp_name}` ({cls_name})\n")
                if elem.condition:
                    cond_lbl = "適用条件" if is_ja else "Condition"
                    sections.append(f"> [!NOTE]\n> **{cond_lbl}**: `{elem.condition}`\n")
                if elem.count is not None:
                    rep_lbl = "繰り返し回数" if is_ja else "Repetition Count"
                    sections.append(f"> [!NOTE]\n> **{rep_lbl}**: `{elem.count}`\n")

                doc = elem.desc or getattr(elem.struct_cls, "__doc__", "") or ""
                if doc:
                    sections.append(f"{inspect.cleandoc(doc)}\n")

                if is_ja:
                    sections.append(f"- **合計サイズ**: {total_size} バイト (`0x{total_size:04X}`)\n")
                else:
                    sections.append(f"- **Total Size**: {total_size} bytes (`0x{total_size:04X}`)\n")

                for e in entries:
                    if e.subfields:
                        all_bitfields.append(e)

                if (section_packet_diagrams or diagram_type in ("packet", "both")) and entries:
                    p_diag = generate_packet_diagram(
                        entries,
                        title=f"{disp_name} レイアウト" if is_ja else f"{disp_name} Layout",
                        bits_per_row=bits_per_row,
                        expand_bitfields=expand_bitfields,
                        font_size=font_size,
                        bit_width=bit_width,
                        relative_offset=True,
                        large_data_threshold=large_data_threshold,
                    )
                    if p_diag:
                        sections.append(p_diag)
                        sections.append("")

                self._render_struct_table(entries, sections, is_ja=is_ja)

            elif isinstance(elem, ChoiceElement):
                ch_lbl = "条件分岐" if is_ja else "Choice Branch"
                sections.append(f"### {ch_lbl}: `{elem.name}`\n")
                tag_name = elem.tag_field if isinstance(elem.tag_field, str) else "tag_field"
                if is_ja:
                    sections.append(f"判定フィールド: `{tag_name}`\n")
                else:
                    sections.append(f"Dispatched by field: `{tag_name}`\n")
                if elem.condition:
                    cond_lbl = "適用条件" if is_ja else "Condition"
                    sections.append(f"> [!NOTE]\n> **{cond_lbl}**: `{elem.condition}`\n")
                if elem.desc:
                    sections.append(f"{elem.desc}\n")

                if is_ja:
                    sections.append("タグ値に応じて、以下のいずれかの構造体が使用されます:\n")
                else:
                    sections.append("Depending on the tag value, one of the following variant structures is used:\n")
                norm_vars = _normalize_variants(elem.variants)

                for tag, v_cls, v_desc in norm_vars:
                    v_cls_name = getattr(v_cls, "__name__", str(v_cls))
                    tag_str = f"Tag `0x{tag:02X}`" if isinstance(tag, int) else (f"Tag `{tag}`" if tag != "-" else "")
                    var_prefix = "#### [バリアント]" if is_ja else "#### [Variant]"
                    header = f"{var_prefix} {tag_str + ': ' if tag_str else ''}`{v_cls_name}`\n"
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
                        if is_ja:
                            sections.append(f"- **バリアントサイズ**: {v_total} バイト (`0x{v_total:04X}`)\n")
                        else:
                            sections.append(f"- **Variant Size**: {v_total} bytes (`0x{v_total:04X}`)\n")
                        if section_packet_diagrams or diagram_type in ("packet", "both"):
                            v_diag = generate_packet_diagram(
                                v_entries,
                                title=f"{v_cls_name} レイアウト" if is_ja else f"{v_cls_name} Layout",
                                bits_per_row=bits_per_row,
                                expand_bitfields=expand_bitfields,
                                font_size=font_size,
                                bit_width=bit_width,
                                relative_offset=True,
                            )
                            if v_diag:
                                sections.append(v_diag)
                                sections.append("")
                        self._render_struct_table(v_entries, sections, is_ja=is_ja)

            elif isinstance(elem, FieldElement):
                f_lbl = "フィールド" if is_ja else "Field"
                sections.append(f"### {f_lbl} `{elem.name}`\n")
                if elem.condition:
                    cond_lbl = "適用条件" if is_ja else "Condition"
                    sections.append(f"> [!NOTE]\n> **{cond_lbl}**: `{elem.condition}`\n")
                if elem.desc:
                    sections.append(f"{elem.desc}\n")
                if is_ja:
                    sections.append(f"- **型**: `{elem.type_name}`")
                    sections.append(f"- **サイズ**: {elem.size} バイト")
                    if elem.endian:
                        sections.append(f"- **エンディアン**: {elem.endian}")
                else:
                    sections.append(f"- **Type**: `{elem.type_name}`")
                    sections.append(f"- **Size**: {elem.size} bytes")
                    if elem.endian:
                        sections.append(f"- **Endianness**: {elem.endian}")
                sections.append("")

        # Aggregated Bitfield Details if any exist
        if include_bitfield_diagram and all_bitfields:
            sections.append("## ビットフィールド詳細\n" if is_ja else "## Bitfield Details\n")
            seen_bitfields = set()
            for bf in all_bitfields:
                bf_name = bf.name or bf.type_name
                if bf_name in seen_bitfields:
                    continue
                seen_bitfields.add(bf_name)

                sz_lbl = "サイズ:" if is_ja else "Size:"
                sections.append(f"### `{bf_name}` ({sz_lbl} {bf.size}B)\n")
                if bf.struct_doc:
                    sections.append(f"{bf.struct_doc}\n")

                diag = generate_bitfield_packet_diagram(bf)
                if diag:
                    sections.append(diag)
                    sections.append("")

                if is_ja:
                    sections.append("| ビット範囲 | フィールド名 | ビット幅 | 説明 |")
                    sections.append("|---|---|---|---|")
                else:
                    sections.append("| Bit Range | Field Name | Width | Description |")
                    sections.append("|---|---|---|---|")
                for sub in (bf.subfields or []):
                    bit_range = f"`[{sub.get('bit_start', 0)}:{sub.get('bit_end', 0)}]`"
                    sub_name = f"`{sub.get('name', '-')}`"
                    width_str = f"{sub.get('width', 1)} bit" if is_ja else f"{sub.get('width', 1)} bit(s)"
                    sub_desc = sub.get("description") or "-"
                    sections.append(f"| {bit_range} | {sub_name} | {width_str} | {sub_desc} |")
                sections.append("")

        return "\n".join(sections)

    def _render_struct_table(self, entries: List[LayoutEntry], sec_list: List[str], is_ja: bool = False) -> None:
        """Render a layout table for struct fields with relative offsets."""
        if is_ja:
            sec_list.append("| 相対オフセット | サイズ (B) | フィールド名 | 型 | エンディアン | 説明 |")
            sec_list.append("|---|---|---|---|---|---|")
        else:
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

    def to_markdown(
        self,
        diagram_direction: Literal["TD", "LR"] = "TD",
        diagram_type: Literal["both", "flowchart", "packet", "none"] = "both",
        bits_per_row: int = 32,
        include_bitfield_diagram: bool = True,
        expand_bitfields: bool = False,
        font_size: Optional[str] = None,
        bit_width: Optional[int] = None,
        section_packet_diagrams: bool = False,
        lang: Optional[Literal["auto", "en", "ja"]] = None,
        large_data_threshold: int = 64,
        **kwargs: Any,
    ) -> str:
        """Alias for build().

        Args:
            diagram_direction: Direction for Mermaid flowchart ('TD' or 'LR'). Default is 'TD'.
            diagram_type: Diagram types to include ('both', 'flowchart', 'packet', or 'none'). Default is 'both'.
            bits_per_row: Packet diagram width in bits. Default is 32.
            include_bitfield_diagram: Whether to render bitfield diagrams. Default is True.
            expand_bitfields: Whether to expand bitfields in packet diagrams. Default is False.
            font_size: Optional CSS font size for diagrams.
            bit_width: Optional pixel width per bit in packet diagrams.
            section_packet_diagrams: Whether to include packet diagrams per struct. Default is False.
            lang: Output language ('auto', 'en', or 'ja'). Defaults to builder's lang setting (default 'auto').
            large_data_threshold: Threshold in bytes to summarize large data blocks in packet diagrams (default 64).
            **kwargs: Extra options forwarded to build().

        Returns:
            The complete Markdown document as a string.
        """
        return self.build(
            diagram_direction=diagram_direction,
            diagram_type=diagram_type,
            bits_per_row=bits_per_row,
            include_bitfield_diagram=include_bitfield_diagram,
            expand_bitfields=expand_bitfields,
            font_size=font_size,
            bit_width=bit_width,
            section_packet_diagrams=section_packet_diagrams,
            lang=lang,
            large_data_threshold=large_data_threshold,
            **kwargs,
        )

    def write(
        self,
        path_or_file: Optional[Union[str, Path, IO[str]]] = None,
        diagram_direction: Literal["TD", "LR"] = "TD",
        diagram_type: Literal["both", "flowchart", "packet", "none"] = "both",
        bits_per_row: int = 32,
        include_bitfield_diagram: bool = True,
        expand_bitfields: bool = False,
        font_size: Optional[str] = None,
        bit_width: Optional[int] = None,
        section_packet_diagrams: bool = False,
        lang: Optional[Literal["auto", "en", "ja"]] = None,
        large_data_threshold: int = 64,
        **kwargs: Any,
    ) -> str:
        """Generate specification markdown and optionally write it to a file or stream.

        Args:
            path_or_file: File path string, Path object, or writable text stream.
            diagram_direction: Direction for Mermaid flowchart ('TD' or 'LR'). Default is 'TD'.
            diagram_type: Diagram types to include ('both', 'flowchart', 'packet', or 'none'). Default is 'both'.
            bits_per_row: Packet diagram width in bits. Default is 32.
            include_bitfield_diagram: Whether to render bitfield diagrams. Default is True.
            expand_bitfields: Whether to expand bitfields in packet diagrams. Default is False.
            font_size: Optional CSS font size for diagrams.
            bit_width: Optional pixel width per bit in packet diagrams.
            section_packet_diagrams: Whether to include packet diagrams per struct. Default is False.
            lang: Output language ('auto', 'en', or 'ja'). Defaults to builder's lang setting (default 'auto').
            large_data_threshold: Threshold in bytes to summarize large data blocks in packet diagrams (default 64).
            **kwargs: Options forwarded to build().


        Returns:
            The complete Markdown document as a string.
        """
        content = self.build(
            diagram_direction=diagram_direction,
            diagram_type=diagram_type,
            bits_per_row=bits_per_row,
            include_bitfield_diagram=include_bitfield_diagram,
            expand_bitfields=expand_bitfields,
            font_size=font_size,
            bit_width=bit_width,
            section_packet_diagrams=section_packet_diagrams,
            lang=lang,
            large_data_threshold=large_data_threshold,
            **kwargs,
        )
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

    def write_markdown(
        self,
        path_or_file: Union[str, Path, IO[str]],
        diagram_direction: Literal["TD", "LR"] = "TD",
        diagram_type: Literal["both", "flowchart", "packet", "none"] = "both",
        bits_per_row: int = 32,
        include_bitfield_diagram: bool = True,
        expand_bitfields: bool = False,
        font_size: Optional[str] = None,
        bit_width: Optional[int] = None,
        section_packet_diagrams: bool = False,
        lang: Optional[Literal["auto", "en", "ja"]] = None,
        large_data_threshold: int = 64,
        **kwargs: Any,
    ) -> str:
        """Generate specification markdown and write it to a file or stream.

        Args:
            path_or_file: File path string, Path object, or writable text stream.
            diagram_direction: Direction for Mermaid flowchart ('TD' or 'LR'). Default is 'TD'.
            diagram_type: Diagram types to include ('both', 'flowchart', 'packet', or 'none'). Default is 'both'.
            bits_per_row: Packet diagram width in bits. Default is 32.
            include_bitfield_diagram: Whether to render bitfield diagrams. Default is True.
            expand_bitfields: Whether to expand bitfields in packet diagrams. Default is False.
            font_size: Optional CSS font size for diagrams.
            bit_width: Optional pixel width per bit in packet diagrams.
            section_packet_diagrams: Whether to include packet diagrams per struct. Default is False.
            lang: Output language ('auto', 'en', or 'ja'). Defaults to builder's lang setting (default 'auto').
            large_data_threshold: Threshold in bytes to summarize large data blocks in packet diagrams (default 64).
            **kwargs: Options forwarded to write().

        Returns:
            The complete Markdown document as a string.
        """
        return self.write(
            path_or_file=path_or_file,
            diagram_direction=diagram_direction,
            diagram_type=diagram_type,
            bits_per_row=bits_per_row,
            include_bitfield_diagram=include_bitfield_diagram,
            expand_bitfields=expand_bitfields,
            font_size=font_size,
            bit_width=bit_width,
            section_packet_diagrams=section_packet_diagrams,
            lang=lang,
            large_data_threshold=large_data_threshold,
            **kwargs,
        )

    @property
    def entries(self) -> List[LayoutEntry]:
        """Aggregate layout entries from all registered StructElements."""
        from binary_master.manual import inspect_struct_layout
        all_entries: List[LayoutEntry] = []
        for elem in self.elements:
            if isinstance(elem, StructElement):
                all_entries.extend(inspect_struct_layout(elem.struct_cls))
        return all_entries

    def to_html(self, lang: Optional[Literal["auto", "en", "ja"]] = None, **kwargs: Any) -> str:
        """Generate a complete standalone HTML specification manual."""
        from binary_master.manual import generate_html
        kwargs.setdefault("title", self.title)
        kwargs.setdefault("default_endian", self.default_endian)
        target_lang = lang or getattr(self, "lang", "auto") or "auto"
        kwargs["lang"] = target_lang
        return generate_html(self.entries, **kwargs)

    def write_html(
        self,
        path_or_file: Union[str, Path, IO[str]],
        lang: Optional[Literal["auto", "en", "ja"]] = None,
        **kwargs: Any,
    ) -> str:
        """Generate specification HTML and write it to a file or stream."""
        content = self.to_html(lang=lang, **kwargs)
        if isinstance(path_or_file, (str, Path)):
            p = Path(path_or_file)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")
        elif hasattr(path_or_file, "write"):
            path_or_file.write(content)
        else:
            raise TypeError(f"Invalid path_or_file: {type(path_or_file).__name__}")
        return content

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

    def serialize(
        self,
        data: Union[dict[str, Any], BuilderReadResult, list[Any], tuple[Any, ...], Any],
        writer: Optional[Any] = None,
        endian: Optional[str] = None,
    ) -> Any:
        """Serialize data structures and fields into binary according to this schema.

        Args:
            data: Dictionary, BuilderReadResult, or sequence mapping element names to instances or values.
            writer: Optional BinaryWriter instance to write into (creates in-memory writer if None).
            endian: Optional endianness override.

        Returns:
            The BinaryWriter instance containing serialized binary data and layout metadata.
        """
        from binary_master.writer import BinaryWriter

        if writer is None:
            writer = BinaryWriter(default_endian=endian or self.default_endian)

        # Normalize data into mapping
        if isinstance(data, dict):
            data_dict = dict(data)
        elif isinstance(data, (list, tuple)):
            data_dict = {}
            for item in data:
                if hasattr(item, "__class__"):
                    data_dict[item.__class__.__name__] = item
        elif hasattr(data, "__dict__"):
            data_dict = dict(data.__dict__)
        else:
            data_dict = {}

        current_caption: Optional[str] = None
        current_caption_desc: str = ""
        current_spec_count: Optional[Union[int, str, bool]] = None

        for elem in self.elements:
            if isinstance(elem, DocumentElement):
                continue

            if isinstance(elem, SectionElement):
                if getattr(elem, "is_end", False):
                    current_caption = None
                    current_caption_desc = ""
                    current_spec_count = None
                else:
                    current_caption = elem.title
                    current_caption_desc = elem.desc
                    current_spec_count = getattr(elem, "spec_count", None)
                writer.set_caption(current_caption, desc=current_caption_desc, spec_count=current_spec_count)
                continue

            # Evaluate condition
            cond_func = getattr(elem, "condition_func", None)
            cond_str = getattr(elem, "condition", None)
            if cond_func is not None:
                if not cond_func(data_dict):
                    continue
            elif cond_str is not None:
                if not self._eval_condition(cond_str, data_dict):
                    continue

            writer.set_caption(current_caption, desc=current_caption_desc, spec_count=current_spec_count)

            if isinstance(elem, StructElement):
                key = elem.name or elem.struct_cls.__name__
                val = data_dict.get(key)
                if val is None:
                    val = data_dict.get(elem.struct_cls.__name__)
                if val is None:
                    val = data_dict.get(elem.struct_cls)
                if val is None and elem.name:
                    val = data_dict.get(elem.name.lower())
                if val is None:
                    val = data_dict.get(elem.struct_cls.__name__.lower())
                if val is None:
                    for k, v in data_dict.items():
                        if isinstance(v, elem.struct_cls):
                            val = v
                            break
                        elif isinstance(v, (list, tuple)) and v and isinstance(v[0], elem.struct_cls):
                            val = v
                            break

                if val is not None:
                    if elem.count is not None or isinstance(val, (list, tuple)):
                        item_list = val if isinstance(val, (list, tuple)) else [val]
                        sp_cnt = elem.count if isinstance(elem.count, (int, str, bool)) else None
                        writer.write_repeated(
                            item_list,
                            title=elem.name or elem.struct_cls.__name__,
                            spec_count=sp_cnt,
                            desc=elem.desc,
                            endian=endian or self.default_endian,
                        )
                    else:
                        writer.write_struct(val, endian=endian or self.default_endian)

            elif isinstance(elem, ChoiceElement):
                val = data_dict.get(elem.name)
                if val is None:
                    norm_vars = _normalize_variants(elem.variants)
                    candidate_classes = tuple(v[1] for v in norm_vars)
                    for k, v in data_dict.items():
                        if isinstance(v, candidate_classes):
                            val = v
                            break

                if val is not None:
                    tag_str = elem.tag_field if isinstance(elem.tag_field, str) else None
                    writer.write_variant(
                        val,
                        candidates=elem.variants,
                        tag_field=tag_str,
                        name=elem.name,
                        desc=elem.desc,
                        endian=endian or self.default_endian,
                    )

            elif isinstance(elem, FieldElement):
                val = data_dict.get(elem.name)
                if val is not None:
                    self._write_primitive_field(writer, elem, val, endian=endian or self.default_endian)

        return writer

    def to_bytes(
        self,
        data: Union[dict[str, Any], BuilderReadResult, list[Any], tuple[Any, ...], Any],
        endian: Optional[str] = None,
    ) -> bytes:
        """Serialize data according to the registered schema and return raw bytes.

        Args:
            data: Dictionary, BuilderReadResult, or sequence containing struct instances and values.
            endian: Optional endianness override.

        Returns:
            The serialized bytes.
        """
        writer = self.serialize(data, endian=endian)
        return writer.to_bytes()

    def read(
        self,
        reader_or_bytes: Union[bytes, bytearray, BinaryReader, IO[bytes]],
        endian: Optional[str] = None,
        trace: bool = False,
    ) -> BuilderReadResult:
        """Automatically deserialize binary data according to the registered schema.

        Args:
            reader_or_bytes: Binary data as bytes/bytearray, BinaryReader instance, or stream.
            endian: Optional endianness override.
            trace: If True, tracks layout entries for debug inspection (res.hexdump(), res.dump()).

        Returns:
            A BuilderReadResult object containing deserialized struct instances and fields.
        """
        if trace:
            res, _ = self._parse_and_trace(reader_or_bytes, endian=endian)
            return res

        if isinstance(reader_or_bytes, BinaryReader):
            reader = reader_or_bytes
        elif isinstance(reader_or_bytes, (bytes, bytearray, memoryview)):
            reader = BinaryReader(bytes(reader_or_bytes), default_endian=endian or self.default_endian)
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
            cond_str = getattr(elem, "condition", None)
            if cond_func is not None:
                if not cond_func(result):
                    continue
            elif cond_str is not None:
                if not self._eval_condition(cond_str, result):
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

    def _parse_and_trace(
        self,
        reader_or_bytes: Union[bytes, bytearray, BinaryReader, IO[bytes]],
        endian: Optional[str] = None,
    ) -> Tuple[BuilderReadResult, Any]:
        """Deserialize binary data while recording layout entries via BinaryWriter."""
        from binary_master.writer import BinaryWriter

        if isinstance(reader_or_bytes, BinaryReader):
            reader = reader_or_bytes
        elif isinstance(reader_or_bytes, (bytes, bytearray, memoryview)):
            reader = BinaryReader(bytes(reader_or_bytes), default_endian=endian or self.default_endian)
        elif hasattr(reader_or_bytes, "read"):
            data = reader_or_bytes.read()
            reader = BinaryReader(data, default_endian=endian or self.default_endian)
        else:
            raise TypeError(f"Unsupported reader_or_bytes type: {type(reader_or_bytes).__name__}")

        writer = BinaryWriter(default_endian=endian or self.default_endian)
        result = BuilderReadResult()
        current_caption: Optional[str] = None
        current_caption_desc: str = ""
        current_spec_count: Optional[Union[int, str, bool]] = None

        for elem in self.elements:
            if isinstance(elem, DocumentElement):
                continue

            if isinstance(elem, SectionElement):
                if getattr(elem, "is_end", False):
                    current_caption = None
                    current_caption_desc = ""
                    current_spec_count = None
                else:
                    current_caption = elem.title
                    current_caption_desc = elem.desc
                    current_spec_count = getattr(elem, "spec_count", None)
                writer.set_caption(current_caption, desc=current_caption_desc, spec_count=current_spec_count)
                continue

            # Evaluate condition
            cond_func = getattr(elem, "condition_func", None)
            cond_str = getattr(elem, "condition", None)
            if cond_func is not None:
                if not cond_func(result):
                    continue
            elif cond_str is not None:
                if not self._eval_condition(cond_str, result):
                    continue

            writer.set_caption(current_caption, desc=current_caption_desc, spec_count=current_spec_count)

            if isinstance(elem, StructElement):
                key = elem.name or elem.struct_cls.__name__
                if elem.count is not None:
                    n_count = self._resolve_count(elem.count, result)
                    items = []
                    for _ in range(n_count):
                        obj = reader.read_struct(elem.struct_cls, endian=endian or self.default_endian)
                        writer.write_struct(obj)
                        items.append(obj)
                    result[key] = items
                else:
                    obj = reader.read_struct(elem.struct_cls, endian=endian or self.default_endian)
                    writer.write_struct(obj)
                    result[key] = obj

            elif isinstance(elem, ChoiceElement):
                tag_val = self._resolve_tag_value(elem.tag_field, result)
                variant_cls = self._match_variant(elem.variants, tag_val)
                if variant_cls is None:
                    raise ValueError(f"Tag value {tag_val!r} did not match any variant for choice '{elem.name}'")
                variant_obj = reader.read_struct(variant_cls, endian=endian or self.default_endian)
                writer.write_struct(variant_obj)
                result[elem.name] = variant_obj

            elif isinstance(elem, FieldElement):
                val = self._read_primitive_field(reader, elem, endian=endian or self.default_endian)
                result[elem.name] = val
                self._write_primitive_field_to_writer(writer, elem, val, endian=endian or self.default_endian)

        result._writer = writer
        return result, writer

    def _write_primitive_field_to_writer(
        self,
        writer: Any,
        elem: FieldElement,
        val: Any,
        endian: str,
    ) -> None:
        """Write an ad-hoc primitive field into the trace writer."""
        t = elem.type_name.lower()
        if "uint8" in t:
            writer.write_uint8(val, name=elem.name, desc=elem.desc)
        elif "uint16" in t:
            writer.write_uint16(val, endian=endian, name=elem.name, desc=elem.desc)
        elif "uint32" in t:
            writer.write_uint32(val, endian=endian, name=elem.name, desc=elem.desc)
        elif "uint64" in t:
            writer.write_uint64(val, endian=endian, name=elem.name, desc=elem.desc)
        elif "int8" in t:
            writer.write_int8(val, name=elem.name, desc=elem.desc)
        elif "int16" in t:
            writer.write_int16(val, endian=endian, name=elem.name, desc=elem.desc)
        elif "int32" in t:
            writer.write_int32(val, endian=endian, name=elem.name, desc=elem.desc)
        elif "int64" in t:
            writer.write_int64(val, endian=endian, name=elem.name, desc=elem.desc)
        elif "float16" in t:
            writer.write_float16(val, endian=endian, name=elem.name, desc=elem.desc)
        elif "float32" in t or t == "float":
            writer.write_float32(val, endian=endian, name=elem.name, desc=elem.desc)
        elif "float64" in t or "double" in t:
            writer.write_float64(val, endian=endian, name=elem.name, desc=elem.desc)
        elif "bool" in t:
            writer.write_bool(bool(val), size=elem.size or 1, endian=endian, name=elem.name, desc=elem.desc)
        else:
            raw = val if isinstance(val, (bytes, bytearray)) else bytes(val)
            writer.write_bytes(raw, name=elem.name, desc=elem.desc)

    def hexdump(
        self,
        data: Union[bytes, bytearray, BinaryReader, IO[bytes]],
        *,
        width: int = 16,
        color: bool = False,
        annotate: bool = True,
        show_ascii: bool = True,
        show_header: bool = True,
        cursor: Optional[int] = None,
        max_bytes: Optional[int] = None,
        endian: Optional[str] = None,
    ) -> str:
        """Generate an annotated hexdump of binary data decoded according to this schema.

        Correlates byte offsets to struct field names, types, values, and section captions.

        Args:
            data: Binary bytes or reader to decode and format.
            width: Bytes displayed per row (default 16).
            color: Whether to use ANSI terminal colors.
            annotate: Whether to show correlated field annotations.
            show_ascii: Whether to show ASCII preview column.
            show_header: Whether to show offset header.
            cursor: Optional explicit cursor offset.
            max_bytes: Optional limit on displayed bytes.
            endian: Optional endianness override.

        Returns:
            Formatted hexdump string.
        """
        _, writer = self._parse_and_trace(data, endian=endian)
        from binary_master.debug import hexdump as _hexdump

        return _hexdump(
            writer,
            width=width,
            color=color,
            annotate=annotate,
            show_ascii=show_ascii,
            show_header=show_header,
            cursor=cursor,
            max_bytes=max_bytes,
        )

    def dump(
        self,
        data: Union[bytes, bytearray, BinaryReader, IO[bytes]],
        format: str = "table",
        *,
        color: bool = False,
        endian: Optional[str] = None,
        **kwargs: Any,
    ) -> Any:
        """Dump decoded fields of binary data in table, json, or dict format.

        Args:
            data: Binary bytes or reader to decode and format.
            format: Output format: 'table', 'json', or 'dict'.
            color: Whether to use ANSI terminal colors for table format.
            endian: Optional endianness override.
            **kwargs: Extra arguments passed to debug_dump.

        Returns:
            Formatted table string, or JSON string, or dictionary structure.
        """
        _, writer = self._parse_and_trace(data, endian=endian)
        return writer.dump(format=format, color=color, **kwargs)

    def _eval_condition(self, condition: str, result: Union[BuilderReadResult, Mapping[str, Any], dict[str, Any]]) -> bool:
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
            count_fn = cast(Callable[[Any], Any], count)
            return int(count_fn(result))
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
            tag_fn = cast(Callable[[Any], Any], tag_field)
            return tag_fn(result)

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
        if "float16" in t:
            return reader.read_float16(endian=endian)
        if "float32" in t or t == "float":
            return reader.read_float32(endian=endian)
        if "float64" in t or "double" in t:
            return reader.read_float64(endian=endian)
        if "bool" in t:
            return reader.read_bool(size=elem.size or 1, endian=endian)
        return reader.read_bytes(elem.size)

    def _write_primitive_field(
        self,
        writer: Any,
        elem: FieldElement,
        val: Any,
        endian: str,
    ) -> None:
        """Write an ad-hoc primitive field."""
        t = elem.type_name.lower()
        order = elem.endian or endian
        if "uint8" in t:
            writer.write_uint8(int(val), name=elem.name, desc=elem.desc)
        elif "uint16" in t:
            writer.write_uint16(int(val), endian=order, name=elem.name, desc=elem.desc)
        elif "uint32" in t:
            writer.write_uint32(int(val), endian=order, name=elem.name, desc=elem.desc)
        elif "uint64" in t:
            writer.write_uint64(int(val), endian=order, name=elem.name, desc=elem.desc)
        elif "int8" in t:
            writer.write_int8(int(val), name=elem.name, desc=elem.desc)
        elif "int16" in t:
            writer.write_int16(int(val), endian=order, name=elem.name, desc=elem.desc)
        elif "int32" in t:
            writer.write_int32(int(val), endian=order, name=elem.name, desc=elem.desc)
        elif "int64" in t:
            writer.write_int64(int(val), endian=order, name=elem.name, desc=elem.desc)
        elif "float16" in t:
            writer.write_float16(float(val), endian=order, name=elem.name, desc=elem.desc)
        elif "float32" in t or t == "float":
            writer.write_float32(float(val), endian=order, name=elem.name, desc=elem.desc)
        elif "float64" in t or "double" in t:
            writer.write_float64(float(val), endian=order, name=elem.name, desc=elem.desc)
        elif "bool" in t:
            writer.write_bool(bool(val), size=elem.size or 1, endian=order, name=elem.name, desc=elem.desc)
        elif "cstring" in t:
            writer.write_cstring(str(val), name=elem.name, desc=elem.desc)
        elif "fixedstring" in t:
            writer.write_fixed_string(str(val), length=elem.size, name=elem.name, desc=elem.desc)
        elif isinstance(val, (bytes, bytearray, memoryview)):
            writer.write_bytes(bytes(val), name=elem.name, desc=elem.desc)
        else:
            writer.write_bytes(bytes(val), name=elem.name, desc=elem.desc)


# Canonical aliases
Builder = BinaryBuilder

__all__ = [
    "BinaryBuilder",
    "Builder",
    "BuilderReadResult",
    "DocumentElement",
    "StructElement",
    "ChoiceElement",
    "SectionElement",
    "FieldElement",
    "_normalize_variants",
]
