## Context

Binary Master uses rich type annotations (`UInt32`, `Offset[Target]`, `FixedArray[T, N]`) as a domain-specific language (DSL) for declarative binary serialization. However, Python type checkers (PEP 484/526/695) enforce strict rules on type expressions. In particular:
- Bare integer literals (`FixedArray[UInt8, 4]`) violate type expression rules (`invalid-type-form`).
- Custom metaclass types (`UInt32`) trigger type mismatch errors when passed standard `int` literals.
- `Offset[Target]` as a custom generic class hides the attribute interface of `Target` from IDE autocompletion.

## Goals / Non-Goals

**Goals:**
- Provide zero-diagnostic type checking in strict type checkers (`ty`, `mypy`, `pyright`) on user struct definitions and serialized/deserialized code.
- Provide seamless IDE autocompletion for `restored.offset_field.attribute` without requiring `if TYPE_CHECKING:` guards in user code.
- Export `Literal` and `L` directly from `binary_master` for ergonomic array size annotations.
- Automatically unwrap `Literal` instances to integers at runtime for complete backward compatibility.

**Non-Goals:**
- Completely rewriting internal binary packing logic into native Python types.
- Disallowing bare numeric arguments at runtime.

## Decisions

1. **Use PEP 561 Type Stubs (`.pyi`) over runtime type aliases**:
   - *Rationale*: Type stub files are prioritized by all modern IDEs (PyCharm, VSCode) and type checkers (`ty`, `mypy`), while leaving the runtime `.py` files completely untouched in their bytecode generation, serialization routines, and performance characteristics.
   - *Alternatives considered*: In-file `if TYPE_CHECKING:` blocks across all modules (creates maintenance overhead and clutters runtime logic).

2. **Map `Offset[Target, *Args]` to `Target | None` in stubs**:
   - *Rationale*: Statically, the field behaves as an instance of `Target` (or `None` when omitted in header-first instantiation). This enables IDE dot-completion and allows assigning `header.field = payload` without warnings.
   - *Alternatives considered*: Generic proxy class with `__getattr__` stub (IDEs cannot reliably infer dynamic attributes from generic type arguments).

3. **Provide `_unwrap_literal_int` helper**:
   - *Rationale*: When users write `FixedArray[UInt8, Literal[4]]` or `FixedArray[UInt8, L[4]]`, `get_origin(arg)` is `Literal`. Unwrapping this to `4` inside `__class_getitem__` ensures that downstream packing, code generation, and manual generation receive clean integers without modifications.

## Risks / Trade-offs

- [Typing difference between static analysis and runtime reflection] → Static type checkers see `Target | None`, whereas `__annotations__` at runtime still preserves `Offset[Target, ...]`. This is the intended behavior of PEP 561 stubs and is fully validated by our test suite.
