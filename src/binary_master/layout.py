"""Layout model representing binary layout entries."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, List, Optional, Union


@dataclass
class LayoutEntry:
    """Represents a serialized field or binary chunk in the output layout."""

    offset: int
    size: int
    type_name: str
    value: Any = None
    name: str = ""
    endian: Optional[str] = None
    description: str = ""
    struct_name: Optional[str] = None
    target_offset: Optional[int] = None
    subfields: Optional[List[dict]] = None
    caption: Optional[str] = None
    struct_doc: Optional[str] = None
    caption_desc: Optional[str] = None
    subcaption: Optional[str] = None
    subcaption_desc: Optional[str] = None
    caption_variants: Optional[list] = None
    caption_spec_count: Optional[Union[int, str, bool]] = None
    caption_repeat: Optional[Union[int, str, bool]] = None

    def __post_init__(self):
        if self.caption_spec_count is None and self.caption_repeat is not None:
            self.caption_spec_count = self.caption_repeat
        elif self.caption_repeat is None and self.caption_spec_count is not None:
            self.caption_repeat = self.caption_spec_count


__all__ = ["LayoutEntry"]
