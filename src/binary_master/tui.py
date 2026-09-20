"""Interactive terminal TUI inspector using curses."""

from __future__ import annotations

import curses
import sys
from typing import Any, List, Optional, Tuple


def _format_ascii(chunk: bytes) -> str:
    return "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)


def run_interactive_inspector(
    data: bytes,
    struct_cls: Optional[type] = None,
    filename: str = "binary",
) -> int:
    """Launch interactive curses TUI for binary inspection.

    Args:
        data: Raw binary bytes to inspect.
        struct_cls: Optional @binary_struct class to decode and highlight fields.
        filename: Display filename in header.

    Returns:
        Exit code (0 on normal exit).
    """
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        from binary_master.debug import hexdump

        print(hexdump(data, color=True))
        return 0

    # If struct provided, decode fields
    field_info: List[Tuple[str, str, int, int, Any]] = []  # name, type, offset, size, val
    if struct_cls is not None:
        try:
            from binary_master.binary_struct import get_struct_plan, read_struct

            instance: Any = read_struct(struct_cls, data)
            plan = get_struct_plan(struct_cls)
            curr_off = 0
            for fp in plan.field_plans:
                align = fp.align
                if plan.align_setting:
                    align = min(align, plan.align_setting)
                if align > 1:
                    curr_off = ((curr_off + align - 1) // align) * align
                val = getattr(instance, fp.name, "")
                f_size = fp.size if fp.size > 0 else len(bytes(val)) if isinstance(val, (bytes, bytearray)) else 1
                field_info.append((fp.name, getattr(fp.target_type, "__name__", str(fp.fmt)), curr_off, f_size, val))
                curr_off += f_size
        except Exception:
            pass

    def _tui_main(stdscr: curses.window) -> int:
        curses.curs_set(0)
        curses.use_default_colors()

        # Color pairs
        if curses.has_colors():
            curses.init_pair(1, curses.COLOR_CYAN, -1)     # Address
            curses.init_pair(2, curses.COLOR_GREEN, -1)    # Values
            curses.init_pair(3, curses.COLOR_YELLOW, -1)   # Highlight
            curses.init_pair(4, curses.COLOR_BLACK, curses.COLOR_CYAN) # Header / Footer
            curses.init_pair(5, curses.COLOR_WHITE, curses.COLOR_BLUE) # Selected field

        scroll_line = 0
        selected_field_idx = 0 if field_info else -1
        total_lines = (len(data) + 15) // 16

        while True:
            stdscr.clear()
            max_y, max_x = stdscr.getmaxyx()

            if max_y < 8 or max_x < 40:
                try:
                    stdscr.addstr(0, 0, "Terminal too small!")
                    stdscr.refresh()
                except curses.error:
                    pass
                ch = stdscr.getch()
                if ch in (ord("q"), ord("Q"), 27):
                    break
                continue

            # Header
            header = f" Binary Master TUI | {filename} ({len(data)} bytes, 0x{len(data):X}) "
            header = header.ljust(max_x)[:max_x]
            try:
                stdscr.attron(curses.color_pair(4) | curses.A_BOLD)
                stdscr.addstr(0, 0, header)
                stdscr.attroff(curses.color_pair(4) | curses.A_BOLD)
            except curses.error:
                pass

            # Highlight range from selected field
            hl_start, hl_end = -1, -1
            if 0 <= selected_field_idx < len(field_info):
                _, _, f_off, f_sz, _ = field_info[selected_field_idx]
                hl_start = f_off
                hl_end = f_off + f_sz

            # Hexdump pane lines
            dump_height = max_y - 2
            split_x = max_x if not field_info else max(40, max_x * 6 // 10)

            for i in range(dump_height):
                line_idx = scroll_line + i
                if line_idx >= total_lines:
                    break

                off = line_idx * 16
                chunk = data[off : off + 16]

                # Render address
                addr_str = f"{off:08x}: "
                try:
                    stdscr.attron(curses.color_pair(1))
                    stdscr.addstr(1 + i, 0, addr_str)
                    stdscr.attroff(curses.color_pair(1))
                except curses.error:
                    pass

                # Render hex bytes
                hex_col = 10
                for b_idx in range(16):
                    byte_pos = off + b_idx
                    if byte_pos < len(data):
                        b = data[byte_pos]
                        b_str = f"{b:02x} "
                        is_hl = hl_start <= byte_pos < hl_end
                        try:
                            if is_hl:
                                stdscr.attron(curses.color_pair(3) | curses.A_REVERSE)
                            stdscr.addstr(1 + i, hex_col, b_str)
                            if is_hl:
                                stdscr.attroff(curses.color_pair(3) | curses.A_REVERSE)
                        except curses.error:
                            pass
                    else:
                        try:
                            stdscr.addstr(1 + i, hex_col, "   ")
                        except curses.error:
                            pass
                    hex_col += 3
                    if b_idx == 7:
                        hex_col += 1  # space between 8-byte groups

                # Render ASCII
                ascii_col = hex_col + 1
                try:
                    stdscr.addstr(1 + i, ascii_col, "|")
                    ascii_str = _format_ascii(chunk)
                    for c_idx, ch_char in enumerate(ascii_str):
                        byte_pos = off + c_idx
                        is_hl = hl_start <= byte_pos < hl_end
                        if is_hl:
                            stdscr.attron(curses.color_pair(3) | curses.A_REVERSE)
                        stdscr.addstr(1 + i, ascii_col + 1 + c_idx, ch_char)
                        if is_hl:
                            stdscr.attroff(curses.color_pair(3) | curses.A_REVERSE)
                    stdscr.addstr(1 + i, ascii_col + 1 + len(ascii_str), "|")
                except curses.error:
                    pass

            # Struct Field Pane (right side)
            if field_info and split_x < max_x - 10:
                field_pane_x = split_x + 1
                try:
                    for r in range(1, max_y - 1):
                        stdscr.addstr(r, split_x, "│")
                    f_header = " Field (Type) [Offset] = Value "
                    stdscr.attron(curses.color_pair(2) | curses.A_BOLD)
                    stdscr.addstr(1, field_pane_x, f_header[: max_x - field_pane_x])
                    stdscr.attroff(curses.color_pair(2) | curses.A_BOLD)

                    for f_idx, (fname, ftype, foff, fsz, fval) in enumerate(field_info):
                        if 2 + f_idx >= max_y - 1:
                            break
                        is_sel = f_idx == selected_field_idx
                        val_repr = str(fval)
                        if len(val_repr) > 15:
                            val_repr = val_repr[:12] + "..."
                        row_str = f" {fname}: {val_repr} (0x{foff:X}+{fsz}) "
                        row_str = row_str.ljust(max_x - field_pane_x)[: max_x - field_pane_x]

                        if is_sel:
                            stdscr.attron(curses.color_pair(5) | curses.A_BOLD)
                        stdscr.addstr(2 + f_idx, field_pane_x, row_str)
                        if is_sel:
                            stdscr.attroff(curses.color_pair(5) | curses.A_BOLD)
                except curses.error:
                    pass

            # Footer
            footer = " [↑/↓] Scroll | [Tab/Shift+Tab] Select Field | [q] Quit "
            footer = footer.ljust(max_x)[:max_x]
            try:
                stdscr.attron(curses.color_pair(4))
                stdscr.addstr(max_y - 1, 0, footer)
                stdscr.attroff(curses.color_pair(4))
            except curses.error:
                pass

            stdscr.refresh()
            key = stdscr.getch()

            if key in (ord("q"), ord("Q"), 27):  # ESC or q
                break
            elif key in (curses.KEY_UP, ord("k")):
                scroll_line = max(0, scroll_line - 1)
            elif key in (curses.KEY_DOWN, ord("j")):
                scroll_line = min(total_lines - 1, scroll_line + 1)
            elif key in (curses.KEY_PPAGE, ord("b")):
                scroll_line = max(0, scroll_line - max(1, dump_height))
            elif key in (curses.KEY_NPAGE, ord("f"), ord(" ")):
                scroll_line = min(total_lines - 1, scroll_line + max(1, dump_height))
            elif key in (curses.KEY_HOME, ord("g")):
                scroll_line = 0
            elif key in (curses.KEY_END, ord("G")):
                scroll_line = max(0, total_lines - dump_height)
            elif key in (ord("\t"), curses.KEY_RIGHT):
                if field_info:
                    selected_field_idx = (selected_field_idx + 1) % len(field_info)
                    # Automatically scroll into view
                    f_off = field_info[selected_field_idx][2]
                    target_line = f_off // 16
                    if target_line < scroll_line or target_line >= scroll_line + dump_height:
                        scroll_line = max(0, target_line - 2)
            elif key in (curses.KEY_BTAB, curses.KEY_LEFT):
                if field_info:
                    selected_field_idx = (selected_field_idx - 1) % len(field_info)
                    f_off = field_info[selected_field_idx][2]
                    target_line = f_off // 16
                    if target_line < scroll_line or target_line >= scroll_line + dump_height:
                        scroll_line = max(0, target_line - 2)

        return 0

    return curses.wrapper(_tui_main)


__all__ = ["run_interactive_inspector"]
