# ruff: noqa: CPY001, PT009, PT027
"""Synthetic codec tests for the OASIS JPEG XL archive."""

from __future__ import annotations

import io
import unittest
from pathlib import Path

import imagecodecs
import numpy as np
import tifffile

from image_archive.codec import CodecError, decode_jxl, decode_tiff, encode_jxl, verify_jxl
from image_archive.contract import load_contract

REPO_ROOT = Path(__file__).resolve().parents[2]
SOURCE_CONTRACT = REPO_ROOT / "image_archive" / "axiom" / "source.toml"


class OasisImageCodecTest(unittest.TestCase):
    """Exercise the pinned HQ settings using only a generated local TIFF."""

    @staticmethod
    def _tiff_bytes(array: np.ndarray) -> bytes:
        output = io.BytesIO()
        tifffile.imwrite(output, array)
        return output.getvalue()

    def test_hq_jpegxl_round_trip_preserves_shape_and_uint16_dtype(self) -> None:
        """Encode one standard JPEG XL codestream for one source TIFF."""
        contract = load_contract(SOURCE_CONTRACT)
        source = np.arange(31 * 37, dtype=np.uint16).reshape(31, 37) * np.uint16(53)
        source_shape = (int(source.shape[0]), int(source.shape[1]))
        decoded_tiff = decode_tiff(self._tiff_bytes(source), expected_shape=source_shape)
        encoded = encode_jxl(decoded_tiff, contract.codec)
        decoded_jxl = verify_jxl(encoded, expected_shape=source_shape, expected_dtype=np.uint16)

        self.assertTrue(imagecodecs.jpegxl_check(encoded))
        self.assertEqual(decoded_jxl.shape, source.shape)
        self.assertEqual(decoded_jxl.dtype, source.dtype)
        np.testing.assert_array_equal(decode_jxl(encoded), decoded_jxl)

    def test_hq_settings_match_the_pinned_jump_lite_reference_defaults(self) -> None:
        """Keep the explicit effort-5 codestream equal to JUMP_lite HQ defaults."""
        contract = load_contract(SOURCE_CONTRACT)
        source = np.arange(31 * 37, dtype=np.uint16).reshape(31, 37)

        encoded = encode_jxl(source, contract.codec)
        reference = imagecodecs.jpegxl_encode(source, lossless=False, distance=1.0)

        self.assertEqual(encoded, reference)

    def test_tiff_decoder_rejects_wrong_shape_dtype_and_page_count(self) -> None:
        """Accept any 2D shape while rejecting wrong expectations, dtype, or page count."""
        source = np.arange(7 * 11, dtype=np.uint16).reshape(7, 11)
        source_shape = (int(source.shape[0]), int(source.shape[1]))
        self.assertEqual(tuple(decode_tiff(self._tiff_bytes(source)).shape), source_shape)
        with self.assertRaises(CodecError):
            decode_tiff(self._tiff_bytes(source), expected_shape=(7, 12))
        with self.assertRaises(CodecError):
            decode_tiff(self._tiff_bytes(source.astype(np.uint8)), expected_shape=source_shape)

        multipage = io.BytesIO()
        with tifffile.TiffWriter(multipage) as writer:
            writer.write(source)
            writer.write(source)
        with self.assertRaises(CodecError):
            decode_tiff(multipage.getvalue(), expected_shape=source_shape)

    def test_jpegxl_verifier_rejects_corruption_and_wrong_expectations(self) -> None:
        """Fail closed on invalid bytes or decoded shape and dtype drift."""
        contract = load_contract(SOURCE_CONTRACT)
        source = np.arange(13 * 17, dtype=np.uint16).reshape(13, 17)
        source_shape = (int(source.shape[0]), int(source.shape[1]))
        encoded = encode_jxl(source, contract.codec)

        with self.assertRaises(CodecError):
            decode_jxl(b"not-a-jpeg-xl-codestream")
        with self.assertRaises(CodecError):
            decode_jxl(encoded[: max(1, len(encoded) // 2)])
        with self.assertRaises(CodecError):
            verify_jxl(encoded, expected_shape=(13, 18), expected_dtype=np.uint16)
        with self.assertRaises(CodecError):
            verify_jxl(encoded, expected_shape=source_shape, expected_dtype=np.uint8)


if __name__ == "__main__":
    unittest.main()
