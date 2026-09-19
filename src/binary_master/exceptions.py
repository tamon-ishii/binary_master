"""Exceptions for binary-master."""

from __future__ import annotations

from typing import Any


class BinaryMasterError(Exception):
    """Base exception for all binary-master errors."""


class ChecksumMismatchError(BinaryMasterError):
    """Raised when a checksum or CRC verification fails."""

    def __init__(self, expected: Any = None, actual: Any = None, message: str = ""):
        if actual is None and isinstance(expected, str):
            message = expected
            expected = None
        self.expected = expected
        self.actual = actual
        if not message:
            exp_s = f"0x{expected:08X}" if isinstance(expected, int) else repr(expected)
            act_s = f"0x{actual:08X}" if isinstance(actual, int) else repr(actual)
            message = f"Checksum mismatch: expected {exp_s}, got {act_s}"
        super().__init__(message)


class InvalidMagicError(BinaryMasterError):
    """Raised when a magic number/string verification fails."""

    def __init__(self, expected: Any = None, actual: Any = None, message: str = ""):
        if actual is None and isinstance(expected, str):
            message = expected
            expected = None
        self.expected = expected
        self.actual = actual
        if not message:
            message = f"Invalid magic: expected {expected!r}, got {actual!r}"
        super().__init__(message)


class InvalidConstantError(BinaryMasterError):
    """Raised when a constant field value does not match expected value."""

    def __init__(self, field_name: str = "", expected: object = None, actual: object = None, message: str = ""):
        if expected is None and actual is None and field_name:
            message = field_name
            field_name = ""
        self.field_name = field_name
        self.expected = expected
        self.actual = actual
        if not message:
            message = f"Constant field '{field_name}' mismatch: expected {expected!r}, got {actual!r}"
        super().__init__(message)


class InvalidEnumError(BinaryMasterError):
    """Raised when an invalid raw value cannot be mapped to an enum."""

    def __init__(self, enum_cls: Any = None, raw_value: object = None, message: str = ""):
        if raw_value is None and isinstance(enum_cls, str):
            message = enum_cls
            enum_cls = None
        self.enum_cls = enum_cls
        self.raw_value = raw_value
        if not message:
            cls_name = getattr(enum_cls, "__name__", str(enum_cls))
            message = f"Value {raw_value!r} is not a valid member of {cls_name}"
        super().__init__(message)


class RangeValidationError(BinaryMasterError, ValueError):
    """Raised when a field value is outside its declared Range[Type, min, max]."""

    def __init__(
        self,
        field_name: str = "",
        val: Any = None,
        min_val: Any = None,
        max_val: Any = None,
        message: str = "",
    ):
        self.field_name = field_name
        self.val = val
        self.min_val = min_val
        self.max_val = max_val
        if not message:
            message = f"Field '{field_name}' value {val!r} is out of valid range [{min_val!r}, {max_val!r}]"
        super().__init__(message)


class TotalSizeExceededError(BinaryMasterError, ValueError):
    """Raised when serialized struct size exceeds declared total_size."""
    pass


class OffsetError(BinaryMasterError):
    """Base exception for Offset errors."""
    pass


class DuplicateOffsetError(OffsetError, ValueError):
    """Raised when an offset key is already registered or duplicated."""
    pass


class OffsetNotFoundError(OffsetError, KeyError):
    """Raised when an offset key does not exist."""
    pass

