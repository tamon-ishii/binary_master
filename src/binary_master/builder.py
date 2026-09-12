"""Binary protocol and specification builder.

Provides BinaryBuilder, Builder, and ManualBuilder (backward compatibility alias).
"""

from __future__ import annotations

from binary_master.manual_builder import (
    BinaryBuilder,
    Builder,
    BuilderReadResult,
    ChoiceElement,
    DocumentElement,
    FieldElement,
    ManualBuilder,
    SectionElement,
    StructElement,
)

__all__ = [
    "BinaryBuilder",
    "Builder",
    "ManualBuilder",
    "BuilderReadResult",
    "DocumentElement",
    "StructElement",
    "ChoiceElement",
    "SectionElement",
    "FieldElement",
]
