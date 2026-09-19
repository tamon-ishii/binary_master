"""Declarative payload compression wrapper for binary_master."""

from __future__ import annotations

import bz2
import gzip
import lzma
import zlib
from typing import Any


def compress_data(data: bytes, algo: str = "zlib") -> bytes:
    """Compress bytes using the specified algorithm."""
    key = algo.lower()
    if key == "zlib":
        return zlib.compress(data)
    elif key == "gzip":
        return gzip.compress(data)
    elif key == "bz2":
        return bz2.compress(data)
    elif key in ("lzma", "xz"):
        return lzma.compress(data)
    elif key == "lz4":
        try:
            import lz4.frame  # type: ignore[import-not-found]
            return lz4.frame.compress(data)
        except ImportError:
            raise ValueError("lz4 compression requires the 'lz4' package to be installed")
    elif key == "zstd":
        try:
            import zstandard  # type: ignore[import-not-found]
            cctx = zstandard.ZstdCompressor()
            return cctx.compress(data)
        except ImportError:
            raise ValueError("zstd compression requires the 'zstandard' package to be installed")
    else:
        raise ValueError(f"Unknown compression algorithm: {algo!r}. Supported: 'zlib', 'gzip', 'bz2', 'lzma'")


def decompress_data(data: bytes, algo: str = "zlib") -> bytes:
    """Decompress bytes using the specified algorithm."""
    key = algo.lower()
    if key == "zlib":
        return zlib.decompress(data)
    elif key == "gzip":
        return gzip.decompress(data)
    elif key == "bz2":
        return bz2.decompress(data)
    elif key in ("lzma", "xz"):
        return lzma.decompress(data)
    elif key == "lz4":
        try:
            import lz4.frame
            return lz4.frame.decompress(data)
        except ImportError:
            raise ValueError("lz4 decompression requires the 'lz4' package to be installed")
    elif key == "zstd":
        try:
            import zstandard
            dctx = zstandard.ZstdDecompressor()
            return dctx.decompress(data)
        except ImportError:
            raise ValueError("zstd decompression requires the 'zstandard' package to be installed")
    else:
        raise ValueError(f"Unknown compression algorithm: {algo!r}. Supported: 'zlib', 'gzip', 'bz2', 'lzma'")


class CompressedBase:
    """Base marker for Compressed types."""
    _target_type: Any = bytes
    _algo: str = "zlib"


class CompressedMeta(type):
    """Metaclass enabling Compressed[T, algo='zlib'] subscription."""

    _target_type: Any = bytes
    _algo: str = "zlib"

    def __getitem__(cls, item: Any) -> type:
        if isinstance(item, tuple):
            target = item[0]
            algo = item[1] if len(item) > 1 else "zlib"
        else:
            target = item
            algo = "zlib"

        target_name = getattr(target, "__name__", str(target))
        name = f"Compressed[{target_name}, '{algo}']"
        return CompressedMeta(
            name,
            (CompressedBase,),
            {
                "_target_type": target,
                "_algo": str(algo).lower(),
            },
        )

    def __repr__(cls) -> str:
        target_name = getattr(cls._target_type, "__name__", str(cls._target_type))
        return f"Compressed[{target_name}, '{cls._algo}']"


class Compressed(CompressedBase, metaclass=CompressedMeta):
    """Declarative compression wrapper for binary_struct fields."""
    pass


class CompressedBytesMeta(type):
    """Metaclass enabling CompressedBytes['zlib'] subscription."""

    def __getitem__(cls, algo: Any) -> type:
        return Compressed[bytes, str(algo)]


class CompressedBytes(CompressedBase, metaclass=CompressedBytesMeta):
    """Convenience alias for Compressed[bytes, algo]."""
    pass
