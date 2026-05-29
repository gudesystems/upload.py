import os
import re
from typing import Optional


CUSTOM_SELECTION_PREFIX = "custom_selection_"


def is_custom_version_marker(version: Optional[str]) -> bool:
    if not version:
        return False
    return str(version).startswith(CUSTOM_SELECTION_PREFIX)


def is_explicit_firmware_selection(filename: Optional[str]) -> bool:
    if not filename:
        return False
    return "{version}" not in str(filename)


def infer_version_from_firmware_filename(filename: Optional[str]) -> Optional[str]:
    if not filename:
        return None

    stem = os.path.splitext(os.path.basename(str(filename)))[0]

    match = re.search(r"_v([A-Za-z0-9][A-Za-z0-9.\-]*)$", stem)
    if match:
        return match.group(1)

    match = re.search(r"([0-9]+(?:\.[0-9A-Za-z]+)+(?:-[A-Za-z0-9]+)?)$", stem)
    if match:
        return match.group(1)

    return None


def resolve_configured_firmware_version(
    prodid: Optional[str],
    filename: Optional[str],
    configured_version: Optional[str],
) -> Optional[str]:
    version = (configured_version or "").strip()
    if version and not is_custom_version_marker(version):
        return version
    return infer_version_from_firmware_filename(filename)


def format_firmware_version_for_display(prodid: Optional[str], version: Optional[str]) -> Optional[str]:
    display_version = (version or "").strip()
    if not display_version:
        return None

    if prodid and "R2" in str(prodid).upper() and "-R2" not in display_version.upper():
        display_version = f"{display_version}-R2"

    return display_version
