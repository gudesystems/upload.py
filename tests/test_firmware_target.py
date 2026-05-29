import unittest

from gude.firmware_target import (
    format_firmware_version_for_display,
    infer_version_from_firmware_filename,
    is_explicit_firmware_selection,
    resolve_configured_firmware_version,
)


class FirmwareTargetTests(unittest.TestCase):
    def test_infers_version_from_standard_firmware_filename(self):
        self.assertEqual(
            infer_version_from_firmware_filename("firmware-epc8041-r2_v1.6.0.bin"),
            "1.6.0",
        )

    def test_marks_literal_filename_as_explicit_selection(self):
        self.assertTrue(is_explicit_firmware_selection("firmware-epc8041-r2_v1.6.0.bin"))
        self.assertFalse(is_explicit_firmware_selection("firmware-epc8041-r2_v{version}.bin"))

    def test_resolves_display_version_from_custom_marker_and_filename(self):
        resolved = resolve_configured_firmware_version(
            "8041R2",
            "firmware-epc8041-r2_v1.6.0.bin",
            "custom_selection_1776408578377",
        )
        self.assertEqual(resolved, "1.6.0")
        self.assertEqual(format_firmware_version_for_display("8041R2", resolved), "1.6.0-R2")


if __name__ == "__main__":
    unittest.main()
