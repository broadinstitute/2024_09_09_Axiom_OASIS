# ruff: noqa: CPY001, EM101, EM102, TRY003, TRY301
"""Strict TIFF decoding and JPEG XL encoding for the OASIS image archive."""

from __future__ import annotations

import io
from typing import TYPE_CHECKING, Final

import imagecodecs
import numpy as np
import tifffile

if TYPE_CHECKING:
    from numpy.typing import DTypeLike, NDArray

from oasis_images.contract import CodecContract

IMAGE_DIMENSIONS: Final = 2
UINT16_BYTES: Final = 2


class CodecError(ValueError):
    """Raised when an input or output violates the archive image contract."""


def _shape(expected_shape: tuple[int, int]) -> tuple[int, int]:
    if (
        type(expected_shape) is not tuple
        or len(expected_shape) != IMAGE_DIMENSIONS
        or any(type(dimension) is not int or dimension <= 0 for dimension in expected_shape)
    ):
        raise CodecError("expected_shape must be a pair of positive integers")
    return expected_shape


def _plane(array: object, expected_shape: tuple[int, int] | None) -> NDArray[np.uint16]:
    if not isinstance(array, np.ndarray):
        raise CodecError("decoded image is not a NumPy array")
    if array.ndim != IMAGE_DIMENSIONS:
        raise CodecError(f"expected one 2D image plane, got shape {array.shape}")
    if array.dtype.kind != "u" or array.dtype.itemsize != UINT16_BYTES:
        raise CodecError(f"expected uint16 pixels, got dtype {array.dtype}")
    if expected_shape is not None and tuple(array.shape) != _shape(expected_shape):
        raise CodecError(f"expected image shape {expected_shape}, got {array.shape}")
    return np.ascontiguousarray(array, dtype=np.uint16)


def _payload(data: bytes, label: str) -> bytes:
    if type(data) is not bytes or not data:
        raise CodecError(f"{label} payload must be non-empty bytes")
    return data


def _codec(codec: CodecContract) -> CodecContract:
    if not isinstance(codec, CodecContract):
        raise CodecError("codec must be a CodecContract")
    if codec.name != "jpegxl":
        raise CodecError("invalid JPEG XL codec settings")
    return codec


def decode_tiff(
    data: bytes,
    expected_shape: tuple[int, int] | None = None,
) -> NDArray[np.uint16]:
    """Decode exactly one 2D uint16 TIFF plane."""
    payload = _payload(data, "TIFF")
    shape = _shape(expected_shape) if expected_shape is not None else None
    try:
        with tifffile.TiffFile(io.BytesIO(payload)) as tiff:
            if len(tiff.pages) != 1:
                raise CodecError(f"expected one TIFF page, got {len(tiff.pages)}")
            array = tiff.asarray()
    except CodecError:
        raise
    except Exception as error:
        raise CodecError(f"cannot decode TIFF: {error}") from error
    return _plane(array, shape)


def encode_jxl(array: NDArray[np.generic], codec: CodecContract) -> bytes:
    """Encode one 2D uint16 plane as the pinned standard JPEG XL codestream."""
    plane = _plane(array, None)
    settings = _codec(codec)
    if not imagecodecs.JPEGXL.available:
        raise CodecError("imagecodecs JPEG XL support is unavailable")
    try:
        encoded = imagecodecs.jpegxl_encode(
            plane,
            lossless=settings.lossless,
            distance=settings.distance,
            effort=settings.effort,
            bitspersample=16,
            usecontainer=False,
            numthreads=1,
        )
    except Exception as error:
        raise CodecError(f"cannot encode JPEG XL: {error}") from error
    result = bytes(encoded)
    if not result or not imagecodecs.jpegxl_check(result):
        raise CodecError("encoder did not produce a JPEG XL codestream")
    return result


def decode_jxl(data: bytes) -> NDArray[np.uint16]:
    """Decode one standard JPEG XL codestream into a 2D uint16 plane."""
    payload = _payload(data, "JPEG XL")
    if not imagecodecs.JPEGXL.available:
        raise CodecError("imagecodecs JPEG XL support is unavailable")
    if not imagecodecs.jpegxl_check(payload):
        raise CodecError("payload is not a JPEG XL codestream")
    try:
        array = imagecodecs.jpegxl_decode(payload)
    except Exception as error:
        raise CodecError(f"cannot decode JPEG XL: {error}") from error
    return _plane(array, None)


def verify_jxl(
    data: bytes,
    expected_shape: tuple[int, int],
    expected_dtype: DTypeLike,
) -> NDArray[np.uint16]:
    """Decode a JPEG XL codestream and require the expected shape and dtype."""
    shape = _shape(expected_shape)
    try:
        dtype = np.dtype(expected_dtype)
    except (TypeError, ValueError) as error:
        raise CodecError(f"invalid expected dtype: {expected_dtype!r}") from error
    array = decode_jxl(data)
    if tuple(array.shape) != shape:
        raise CodecError(f"expected JPEG XL shape {shape}, got {array.shape}")
    if array.dtype != dtype:
        raise CodecError(f"expected JPEG XL dtype {dtype}, got {array.dtype}")
    return array


__all__ = [
    "CodecError",
    "decode_jxl",
    "decode_tiff",
    "encode_jxl",
    "verify_jxl",
]
