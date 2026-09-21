"""Manual and documentation generator with Mermaid diagrams for BinaryWriter."""

from __future__ import annotations

from binary_master.layout import LayoutEntry
from binary_master.manual.diagrams import (
    generate_bitfield_packet_diagram,
    generate_mermaid_diagram,
    generate_packet_diagram,
)
from binary_master.manual.helpers import (
    create_dummy_instance,
    format_value_preview,
    inspect_struct_layout,
)
from binary_master.manual.html import generate_html, write_html
from binary_master.manual.i18n import resolve_language
from binary_master.manual.markdown import generate_manual

__all__ = [
    "LayoutEntry",
    "resolve_language",
    "create_dummy_instance",
    "inspect_struct_layout",
    "format_value_preview",
    "generate_mermaid_diagram",
    "generate_packet_diagram",
    "generate_bitfield_packet_diagram",
    "generate_manual",
    "generate_html",
    "write_html",
]
