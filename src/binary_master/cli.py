"""CLI tool for binary-master: inspect, diff, spec, and export binary formats."""

from __future__ import annotations

import argparse
import importlib
import sys
from pathlib import Path
from typing import Any, Optional


def _load_struct_class(path_or_qualname: str) -> type:
    """Dynamically load a @binary_struct class by 'module.path:ClassName' or 'module.path.ClassName'."""
    if ":" in path_or_qualname:
        mod_name, cls_name = path_or_qualname.split(":", 1)
    else:
        parts = path_or_qualname.rsplit(".", 1)
        if len(parts) == 1:
            raise ValueError(f"Struct target must include module and class name, e.g. 'my_module:MyStruct', got '{path_or_qualname}'")
        mod_name, cls_name = parts[0], parts[1]

    # Ensure current working directory is in sys.path
    if "" not in sys.path and "." not in sys.path:
        sys.path.insert(0, "")

    module = importlib.import_module(mod_name)
    cls = getattr(module, cls_name, None)
    if cls is None:
        raise AttributeError(f"Module '{mod_name}' has no attribute '{cls_name}'")
    return cls


def cmd_inspect(args: argparse.Namespace) -> int:
    """Inspect binary file."""
    path = Path(args.file)
    if not path.exists():
        print(f"Error: File '{path}' does not exist", file=sys.stderr)
        return 1

    data = path.read_bytes()

    if args.struct:
        try:
            struct_cls = _load_struct_class(args.struct)
        except Exception as e:
            print(f"Error loading struct '{args.struct}': {e}", file=sys.stderr)
            return 1

        from binary_master.binary_struct import read_struct
        from binary_master.writer import BinaryWriter

        try:
            instance: Any = read_struct(struct_cls, data)
        except Exception as e:
            print(f"Error decoding binary with {struct_cls.__name__}: {e}", file=sys.stderr)
            return 1

        w = BinaryWriter()
        w.write_struct(instance)

        if args.format == "table":
            print(w.dump("table"))
        elif args.format == "json":
            print(w.dump("json"))
        else:
            print(w.hexdump(color=args.color, annotate=True))
    else:
        from binary_master.debug import hexdump
        print(hexdump(data, color=args.color, annotate=False))

    return 0


def cmd_diff(args: argparse.Namespace) -> int:
    """Compare two binary files."""
    p1 = Path(args.file1)
    p2 = Path(args.file2)
    if not p1.exists():
        print(f"Error: File '{p1}' does not exist", file=sys.stderr)
        return 1
    if not p2.exists():
        print(f"Error: File '{p2}' does not exist", file=sys.stderr)
        return 1

    d1 = p1.read_bytes()
    d2 = p2.read_bytes()

    from binary_master.debug import diff_dump
    print(diff_dump(d1, d2, color=args.color))
    return 0


def cmd_spec(args: argparse.Namespace) -> int:
    """Generate Markdown or HTML specification from a struct class."""
    try:
        struct_cls = _load_struct_class(args.struct)
    except Exception as e:
        print(f"Error loading struct '{args.struct}': {e}", file=sys.stderr)
        return 1

    from binary_master.builder import Builder
    builder = Builder(title=f"{struct_cls.__name__} Specification")
    builder.add_struct(struct_cls)

    is_html = getattr(args, "html", False) or getattr(args, "format", "markdown") == "html"
    if args.output and (args.output.endswith(".html") or args.output.endswith(".htm")):
        is_html = True

    if is_html:
        lang: Any = getattr(args, "lang", "auto")
        if args.output == "-":
            print(builder.to_html(lang=lang))
            return 0
        out_path = args.output or f"{struct_cls.__name__.lower()}_spec.html"
        builder.write_html(out_path, lang=lang)
        print(f"HTML specification written to {out_path}")
        return 0

    if args.output == "-":
        print(builder.to_markdown())
        return 0

    out_path = args.output or f"{struct_cls.__name__.lower()}_spec.md"
    builder.write_markdown(out_path)
    print(f"Specification written to {out_path}")
    return 0


def cmd_export(args: argparse.Namespace) -> int:
    """Export struct class to native code (c, rust, cpp, csharp, go)."""
    try:
        struct_cls = _load_struct_class(args.struct)
    except Exception as e:
        print(f"Error loading struct '{args.struct}': {e}", file=sys.stderr)
        return 1

    from binary_master.builder import Builder
    builder = Builder(title=f"{struct_cls.__name__} Code Export")
    builder.add_struct(struct_cls)

    lang = args.lang.lower()
    ext_map = {"c": ".h", "rust": ".rs", "cpp": ".hpp", "csharp": ".cs", "go": ".go"}

    if args.output == "-":
        if lang == "c":
            print(builder.to_c_header())
        elif lang == "rust":
            print(builder.to_rust())
        elif lang == "cpp":
            print(builder.to_cpp())
        elif lang == "csharp":
            print(builder.to_csharp())
        elif lang == "go":
            print(builder.to_go())
        else:
            print(f"Unknown language: {lang}. Choose from c, rust, cpp, csharp, go", file=sys.stderr)
            return 1
        return 0

    out_path = args.output or f"{struct_cls.__name__.lower()}{ext_map.get(lang, '.txt')}"

    if lang == "c":
        builder.write_c_header(out_path)
    elif lang == "rust":
        builder.write_rust(out_path)
    elif lang == "cpp":
        builder.write_cpp(out_path)
    elif lang == "csharp":
        builder.write_csharp(out_path)
    elif lang == "go":
        builder.write_go(out_path)
    else:
        print(f"Unknown language: {lang}. Choose from c, rust, cpp, csharp, go", file=sys.stderr)
        return 1

    print(f"Exported {lang.upper()} code written to {out_path}")
    return 0


def main(argv: Optional[list[str]] = None) -> int:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="binary-master",
        description="Binary Master CLI: inspect, diff, generate specs, and export binary formats.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # inspect
    p_inspect = subparsers.add_parser("inspect", help="Inspect and dump a binary file")
    p_inspect.add_argument("file", help="Path to binary file")
    p_inspect.add_argument("--struct", "-s", help="Qualified @binary_struct name, e.g. 'my_module:MyHeader'")
    p_inspect.add_argument("--format", "-f", choices=["hexdump", "table", "json"], default="hexdump", help="Output format")
    p_inspect.add_argument("--color", "-c", action="store_true", help="Enable terminal ANSI colors")

    # diff
    p_diff = subparsers.add_parser("diff", help="Visually diff two binary files")
    p_diff.add_argument("file1", help="Path to first binary file")
    p_diff.add_argument("file2", help="Path to second binary file")
    p_diff.add_argument("--color", "-c", action="store_true", help="Enable terminal ANSI colors")

    # spec / manual
    p_spec = subparsers.add_parser(
        "spec",
        aliases=["manual"],
        help="Generate Markdown or HTML specification manual for a struct",
    )
    p_spec.add_argument("struct", help="Qualified @binary_struct name, e.g. 'my_module:MyHeader'")
    p_spec.add_argument("--output", "-o", help="Output specification file path (.md or .html)")
    p_spec.add_argument("--format", "-f", choices=["markdown", "html"], default="markdown", help="Output format (markdown or html)")
    p_spec.add_argument("--html", action="store_true", help="Generate HTML specification instead of Markdown")
    p_spec.add_argument("--lang", choices=["auto", "en", "ja"], default="auto", help="Documentation language for HTML")

    # export
    p_export = subparsers.add_parser("export", help="Export struct to C, Rust, C++, C#, or Go code")
    p_export.add_argument("struct", help="Qualified @binary_struct name, e.g. 'my_module:MyHeader'")
    p_export.add_argument("--lang", "-l", choices=["c", "rust", "cpp", "csharp", "go"], required=True, help="Target language")
    p_export.add_argument("--output", "-o", help="Output source code file path")

    args = parser.parse_args(argv)

    if args.command == "inspect":
        return cmd_inspect(args)
    elif args.command == "diff":
        return cmd_diff(args)
    elif args.command in ("spec", "manual"):
        return cmd_spec(args)
    elif args.command == "export":
        return cmd_export(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
