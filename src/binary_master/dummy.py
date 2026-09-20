"""Dummy and mock binary struct generation."""

from __future__ import annotations

import random
import string
from typing import Any, Dict, Optional, Type, TypeVar

from binary_master.binary_struct import Bool, FieldKind, get_struct_plan

T = TypeVar("T")


def generate_dummy(
    cls: Type[T],
    seed: Optional[int] = None,
    **overrides: Any,
) -> T:
    """Generate a valid dummy/mock instance of a @binary_struct class.

    Respects Magic, Constant, Range, Enum, FixedString, and nested structures.
    Any keyword argument in `overrides` will override the generated field value.

    Args:
        cls: The @binary_struct class to instantiate.
        seed: Optional random seed for reproducible dummy data.
        **overrides: Explicit field values to use instead of random dummy values.

    Returns:
        Instantiated @binary_struct object populated with dummy data.
    """
    rng = random.Random(seed)
    return _generate_dummy_internal(cls, rng, overrides)


def _generate_dummy_internal(
    cls: Type[T],
    rng: random.Random,
    overrides: Dict[str, Any],
) -> T:
    plan = get_struct_plan(cls)
    meta = getattr(cls, "__binary__", {})

    # Bitfield handling
    if plan.is_bitfield:
        kwargs: Dict[str, Any] = {}
        fields = meta.get("fields", {})
        for name, ftype in fields.items():
            if name in overrides:
                kwargs[name] = overrides[name]
                continue
            base_t = ftype[0] if isinstance(ftype, tuple) and len(ftype) >= 2 else ftype
            width = ftype[1] if isinstance(ftype, tuple) and len(ftype) >= 2 else 1
            if base_t in (Bool, bool) or getattr(base_t, "_fmt", None) == "?":
                kwargs[name] = rng.choice([True, False])
            else:
                max_val = (1 << width) - 1
                kwargs[name] = rng.randint(0, max_val)
        return cls(**kwargs)

    kwargs = {}
    deferred_length_fields: list[Any] = []

    for fp in plan.field_plans:
        name = fp.name
        if name in overrides:
            kwargs[name] = overrides[name]
            continue

        kind = fp.kind
        if kind == FieldKind.MAGIC:
            kwargs[name] = fp.expected if fp.expected is not None else fp.raw_val

        elif kind == FieldKind.CONSTANT:
            kwargs[name] = fp.expected

        elif kind == FieldKind.RANGE:
            min_v = fp.min_val if fp.min_val is not None else 0
            max_v = fp.max_val if fp.max_val is not None else 100
            kwargs[name] = rng.randint(min_v, max_v)

        elif kind == FieldKind.BOOL:
            kwargs[name] = rng.choice([True, False])

        elif kind == FieldKind.ENUM:
            if fp.enum_cls:
                members = list(fp.enum_cls)
                kwargs[name] = rng.choice(members) if members else 0
            else:
                kwargs[name] = 0

        elif kind == FieldKind.FIXED_STRING:
            str_len = max(1, fp.size)
            letters = "".join(rng.choices(string.ascii_letters + string.digits, k=min(8, str_len)))
            kwargs[name] = letters

        elif kind == FieldKind.BYTES:
            kwargs[name] = bytes(rng.randint(0, 255) for _ in range(fp.size))

        elif kind in (FieldKind.C_STRING, FieldKind.PREFIXED_STRING):
            kwargs[name] = "dummy_str"

        elif kind == FieldKind.NESTED_STRUCT:
            kwargs[name] = _generate_dummy_internal(fp.nested_cls, rng, {})

        elif kind == FieldKind.FIXED_ARRAY:
            count = fp.count if isinstance(fp.count, int) and fp.count > 0 else 3
            elem_list: list[Any] = []
            for _ in range(count):
                if fp.elem_is_bool:
                    elem_list.append(rng.choice([True, False]))
                elif fp.elem_is_uint8:
                    elem_list.append(rng.randint(0, 255))
                elif fp.elem_is_int8:
                    elem_list.append(rng.randint(-128, 127))
                elif fp.elem_is_struct and fp.elem_type:
                    elem_list.append(_generate_dummy_internal(fp.elem_type, rng, {}))
                elif fp.elem_fmt in ("H", "I", "Q"):
                    elem_list.append(rng.randint(1, 1000))
                else:
                    elem_list.append(rng.randint(1, 100))
            kwargs[name] = elem_list

        elif kind in (FieldKind.LENGTH_OF, FieldKind.COUNT_OF):
            deferred_length_fields.append(fp)
            kwargs[name] = 0  # placeholder until target field is known

        elif kind == FieldKind.CHECKSUM:
            kwargs[name] = 0

        elif kind == FieldKind.VARINT:
            kwargs[name] = rng.randint(0, 1000)

        elif kind in (FieldKind.PRIMITIVE, FieldKind.PYTHON_PRIMITIVE):
            fmt = fp.fmt.lstrip("<>!=@")
            if fmt == "B":
                kwargs[name] = rng.randint(0, 255)
            elif fmt == "b":
                kwargs[name] = rng.randint(-128, 127)
            elif fmt == "H":
                kwargs[name] = rng.randint(0, 65535)
            elif fmt == "h":
                kwargs[name] = rng.randint(-32768, 32767)
            elif fmt == "I":
                kwargs[name] = rng.randint(0, 4294967295)
            elif fmt == "i":
                kwargs[name] = rng.randint(-2147483648, 2147483647)
            elif fmt == "Q":
                kwargs[name] = rng.randint(0, 1000000)
            elif fmt == "q":
                kwargs[name] = rng.randint(0, 1000000)
            elif fmt in ("e", "f", "d"):
                kwargs[name] = round(rng.uniform(1.0, 100.0), 3)
            elif fmt == "?":
                kwargs[name] = rng.choice([True, False])
            else:
                kwargs[name] = rng.randint(0, 255)

        else:
            kwargs[name] = 0

    # Resolve LengthOf and CountOf
    for fp in deferred_length_fields:
        if fp.name not in overrides:
            target_val = kwargs.get(fp.target_name)
            if target_val is not None and hasattr(target_val, "__len__"):
                kwargs[fp.name] = len(target_val) + (fp.delta or 0)
            else:
                kwargs[fp.name] = fp.delta or 0

    return cls(**kwargs)


__all__ = ["generate_dummy"]
