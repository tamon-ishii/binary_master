## Context

`BinaryWriter` maintains `self._named_offset_slots: dict[str, list[dict[str, Any]]]`. See `proposal.md` for motivation to partition generic key names across independent sections.

## Goals / Non-Goals

**Goals:**
- Provide `namespace(name: str = "", *, auto_id: bool = False)` context manager on `BinaryWriter`.
- Expose `@property def current_namespace(self) -> str`.
- Automatically prefix relative keys with active namespace hierarchy (`"segment1/segment2/key"`).
- Treat keys prefixed with `/` as root-level absolute paths.
- Support `auto_id=True` using per-prefix sequence counters (`_namespace_counters`).

**Non-Goals:**
- Modifying struct type annotations (structs continue to declare generic keys like `NamedOffset["data"]`).

## Decisions

1. **Path-Based Namespace Separator (`/`)**:
   - *Choice*: Use `/` as the hierarchy delimiter (e.g. `section/table/entry`).
   - *Rationale*: Intuitive, matches filesystem path semantics, and makes absolute paths (`/global_key`) naturally expressive.

2. **Unified Key Qualification via `_qualify_name`**:
   - *Choice*: Implement `_qualify_name(name: str) -> str` that checks `if name.startswith("/")` -> `name[1:]`, else `"/".join(stack) + "/" + name` if stack else `name`.
   - *Rationale*: Centralizes resolution logic so `reserve_named_offset`, `write_named_offset`, `rewrite_named_offset`, and `_register_named_offset_slot` require minimal localized changes.

3. **Auto-Increment Counter Management**:
   - *Choice*: Maintain `_namespace_counters: dict[str, int]` on writer instance.
   - *Rationale*: Counters reset with each writer instance and increment predictably across iterations.

## Risks / Trade-offs

- **[Risk] Nested resolution of absolute keys**:
  - *Mitigation*: Leading `/` strips cleanly and maps to root namespace directly without ambiguity.
