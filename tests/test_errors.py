"""Unit tests for error classification helpers."""

import unittest

from pixelart_converter.errors import (
    ConversionError,
    ErrorCode,
    sample_demo_error,
    user_message_for,
)


class UserMessageTest(unittest.TestCase):
    def test_each_code_has_a_default_message(self) -> None:
        for code in ErrorCode:
            message = user_message_for(code)
            self.assertIsInstance(message, str)
            self.assertTrue(message.strip())

    def test_encoder_unavailable_mentions_no_gpl_fallback(self) -> None:
        message = user_message_for(ErrorCode.ENCODER_UNAVAILABLE)
        self.assertIn("GPL", message)


class ConversionErrorTest(unittest.TestCase):
    def test_from_code_uses_default_message(self) -> None:
        error = ConversionError.from_code(ErrorCode.INVALID_INPUT)
        self.assertEqual(error.code, ErrorCode.INVALID_INPUT)
        self.assertEqual(error.message, user_message_for(ErrorCode.INVALID_INPUT))
        self.assertIsNone(error.detail)

    def test_from_code_accepts_custom_message_and_detail(self) -> None:
        error = ConversionError.from_code(
            ErrorCode.OUTPUT_PATH,
            message="Cannot write to /readonly/out.mp4",
            detail="Permission denied",
        )
        self.assertEqual(error.message, "Cannot write to /readonly/out.mp4")
        self.assertEqual(error.detail, "Permission denied")

    def test_log_message_includes_detail_when_present(self) -> None:
        error = ConversionError.from_code(
            ErrorCode.UNKNOWN,
            detail="exit=1 stderr tail omitted from user message",
        )
        self.assertIn("detail:", error.log_message())
        self.assertIn(error.detail, error.log_message())

    def test_log_message_omits_detail_when_absent(self) -> None:
        error = ConversionError.from_code(ErrorCode.CANCELLED)
        self.assertNotIn("detail:", error.log_message())


class SampleDemoErrorTest(unittest.TestCase):
    def test_sample_is_encoder_unavailable_with_detail(self) -> None:
        error = sample_demo_error()
        self.assertEqual(error.code, ErrorCode.ENCODER_UNAVAILABLE)
        self.assertIsNotNone(error.detail)
        self.assertNotIn(error.detail, error.message)


if __name__ == "__main__":
    unittest.main()
