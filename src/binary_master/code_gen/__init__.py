"""Multi-language code generator package for binary_master."""

from __future__ import annotations

from pathlib import Path
from typing import IO, Any, Optional, Union

from binary_master.code_gen.c import (
    generate_c_choice,
    generate_c_header,
    generate_c_struct,
    write_c_header,
)
from binary_master.code_gen.cpp import (
    generate_cpp_choice,
    generate_cpp_code,
    generate_cpp_struct,
    write_cpp,
)
from binary_master.code_gen.csharp import (
    generate_csharp_choice,
    generate_csharp_code,
    generate_csharp_struct,
    write_csharp,
)
from binary_master.code_gen.go import (
    generate_go_choice,
    generate_go_code,
    generate_go_struct,
    write_go,
)
from binary_master.code_gen.rust import (
    generate_rust_choice,
    generate_rust_code,
    generate_rust_struct,
    write_rust,
)

EXTENSION_MAP = {
    ".h": "c",
    ".c": "c",
    ".rs": "rust",
    ".hpp": "cpp",
    ".cpp": "cpp",
    ".cc": "cpp",
    ".cxx": "cpp",
    ".cs": "csharp",
    ".go": "go",
}


def normalize_lang(lang: str) -> str:
    """Normalize language identifier."""
    norm = lang.strip().lower()
    if norm in ("c",):
        return "c"
    if norm in ("rust", "rs"):
        return "rust"
    if norm in ("cpp", "c++", "hpp", "cc", "cxx"):
        return "cpp"
    if norm in ("csharp", "cs", "c#"):
        return "csharp"
    if norm in ("go", "golang"):
        return "go"
    raise ValueError(
        f"Unsupported language: {lang!r}. Supported languages: 'c', 'rust', 'cpp', 'csharp', 'go'"
    )


def generate_code(builder: Any, lang: str, **kwargs) -> str:
    """Generate source code in the requested language from a BinaryBuilder, BinaryWriter, or @binary_struct."""
    if hasattr(builder, "__binary__"):
        from binary_master.builder import Builder
        cls = builder if isinstance(builder, type) else builder.__class__
        b = Builder(title=getattr(cls, "__name__", "Schema"))
        b.add_struct(cls)
        builder = b
    elif hasattr(builder, "to_builder"):
        builder = builder.to_builder()
    norm = normalize_lang(lang)
    if norm == "c":
        return generate_c_header(builder, **kwargs)
    if norm == "rust":
        return generate_rust_code(builder)
    if norm == "cpp":
        return generate_cpp_code(builder)
    if norm == "csharp":
        return generate_csharp_code(builder, **kwargs)
    if norm == "go":
        return generate_go_code(builder, **kwargs)
    raise ValueError(f"Unhandled language: {norm}")


def write_code(
    builder: Any,
    path_or_file: Union[str, Path, IO[str]],
    lang: Optional[str] = None,
    **kwargs,
) -> str:
    """Generate source code in the target language and write to file."""
    if hasattr(builder, "__binary__"):
        from binary_master.builder import Builder
        cls = builder if isinstance(builder, type) else builder.__class__
        b = Builder(title=getattr(cls, "__name__", "Schema"))
        b.add_struct(cls)
        builder = b
    elif hasattr(builder, "to_builder"):
        builder = builder.to_builder()
    if lang is None:
        p_str = str(path_or_file) if not hasattr(path_or_file, "name") else str(getattr(path_or_file, "name"))
        ext = Path(p_str).suffix.lower()
        if ext in EXTENSION_MAP:
            lang = EXTENSION_MAP[ext]
        else:
            raise ValueError(
                f"Cannot infer language from file extension '{ext}'. Please specify 'lang' explicitly."
            )

    norm = normalize_lang(lang)
    if norm == "c":
        return write_c_header(builder, path_or_file, **kwargs)
    if norm == "rust":
        return write_rust(builder, path_or_file)
    if norm == "cpp":
        return write_cpp(builder, path_or_file)
    if norm == "csharp":
        return write_csharp(builder, path_or_file, **kwargs)
    if norm == "go":
        return write_go(builder, path_or_file, **kwargs)
    raise ValueError(f"Unhandled language: {norm}")


__all__ = [
    "generate_c_header",
    "write_c_header",
    "generate_c_struct",
    "generate_c_choice",
    "generate_rust_code",
    "write_rust",
    "generate_rust_struct",
    "generate_rust_choice",
    "generate_cpp_code",
    "write_cpp",
    "generate_cpp_struct",
    "generate_cpp_choice",
    "generate_csharp_code",
    "write_csharp",
    "generate_csharp_struct",
    "generate_csharp_choice",
    "generate_go_code",
    "write_go",
    "generate_go_struct",
    "generate_go_choice",
    "generate_code",
    "write_code",
    "normalize_lang",
]
