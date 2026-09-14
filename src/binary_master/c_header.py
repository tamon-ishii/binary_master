"""C/C++ header file generator for binary_master schemas and structs.

This module re-exports C header generator functions from `binary_master.code_gen.c`.
"""

from __future__ import annotations

from binary_master.code_gen.c import (
    c_type_of,
    generate_c_choice,
    generate_c_header,
    generate_c_struct,
    to_c_header,
    to_c_struct,
    to_pascal_case,
    to_screaming_snake_case,
    to_snake_case,
    write_c_header,
)

__all__ = [
    "c_type_of",
    "generate_c_choice",
    "generate_c_header",
    "generate_c_struct",
    "to_c_header",
    "to_c_struct",
    "to_pascal_case",
    "to_screaming_snake_case",
    "to_snake_case",
    "write_c_header",
]
