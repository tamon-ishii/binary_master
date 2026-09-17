# Proposal: IDE Typing Support, PEP 561 Stubs, and Strict Type Checker Compatibility

## Why

Modern Python development heavily relies on IDEs (PyCharm, VSCode) and strict static type checkers (`ty`, `mypy`, `pyright`). Previously, binary structure type annotations like `Offset[Target, ...]` and `FixedArray[T, 4]` caused type checker errors (such as `invalid-type-form`, `invalid-assignment`, and argument type mismatches) and prevented IDEs from auto-completing target fields on deserialized objects (`restored.image_offset.width`).

Providing PEP 561 compliant type stubs and runtime unwrapping allows full IDE auto-completion and zero-diagnostic type checking while preserving runtime binary serialization behavior.

## What Changes

- Add PEP 561 marker file `py.typed` to `binary_master`.
- Add type stub files `binary_struct.pyi` and `__init__.pyi`.
- Map primitive binary types (`UInt8` through `UInt64`, `Int8` through `Int64`, `Float16` through `Float64`, `Bool`) to standard Python types (`int`, `float`, `bool`) in stubs so literals can be assigned without warnings.
- Map `Offset[Target, *Args]` to `Target | None` in stubs, enabling header-first assignment (`header.image_offset = payload`) and full IDE completion on attributes (`restored.image_offset.width`).
- Export `Literal` and concise alias `L` from `binary_master` to allow PEP 484/526 compliant array sizing (`FixedArray[UInt8, L[4]]`).
- Add runtime literal unwrapping (`_unwrap_literal_int`) in `FixedArray` and `OffsetTable` so `Literal[N]` and `L[N]` seamlessly unpack to integers at runtime.
- Update documentation and samples to illustrate typed workflows and IDE completion.

## Capabilities

### New Capabilities
- `ide-typing-and-stubs`: PEP 561 type stubs, IDE auto-completion for `Offset[Target]`, and `Literal`/`L` support for fixed-size array/table declarations.

### Modified Capabilities
<!-- None -->

## Impact

- Affected files: `src/binary_master/py.typed`, `src/binary_master/*.pyi`, `src/binary_master/__init__.py`, `src/binary_master/binary_struct.py`, `README.md`, `TUTORIAL.md`, `FOR_AI.md`.
- Fully backward-compatible: bare numbers (e.g. `FixedArray[UInt8, 4]`) continue to work seamlessly at runtime.
