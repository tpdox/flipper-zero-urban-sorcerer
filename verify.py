#!/usr/bin/env python3
"""Flipper Zero Deployment Verification.

Connects to the Flipper Zero and verifies that the Mazincea Urban Sorcerer Kit
deployment was successful by checking firmware, file counts, and directory
contents across all expected categories.

Usage:
    python3 verify.py                  # Auto-detect Flipper port
    python3 verify.py --port /dev/...  # Specify serial port manually
"""

import argparse
import sys

from flipper_serial import FlipperSerial


# ---------------------------------------------------------------------------
# Verification checks — each is (label, directory, extension, recursive)
# ---------------------------------------------------------------------------
FILE_CHECKS = [
    ("IR Database", "/ext/infrared", ".ir", False),
    ("BadUSB Payloads", "/ext/badusb", ".txt", False),
    ("NFC Tags", "/ext/nfc", ".nfc", False),       # excluding amiibo subdir
    ("Amiibo Collection", "/ext/nfc/amiibo", ".nfc", True),
    ("Sub-GHz Files", "/ext/subghz", ".sub", False),
    ("Apps", "/ext/apps", ".fap", True),
    ("Music", "/ext/apps_data/music_player", None, False),
]


def check_firmware(flipper):
    """Check firmware via device_info and return (ok, description).

    Looks for 'Momentum' in the firmware origin or a firmware_version key.
    Returns a tuple of (passed: bool, summary: str).
    """
    try:
        info = flipper.send_command("device_info", timeout=10.0)
    except (TimeoutError, OSError) as exc:
        return False, f"Could not read device_info: {exc}"

    firmware_version = None
    firmware_origin = None

    for line in info.split("\n"):
        line = line.strip()
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip().lower()
        value = value.strip()
        if key == "firmware_version":
            firmware_version = value
        elif key == "firmware_origin":
            firmware_origin = value

    # Build a readable label
    label_parts = []
    if firmware_origin:
        label_parts.append(firmware_origin)
    if firmware_version:
        label_parts.append(firmware_version)
    label = " ".join(label_parts) if label_parts else "unknown"

    # Consider it OK if we got any firmware version string at all, or if
    # "Momentum" appears anywhere in the device_info output.
    if firmware_origin and "momentum" in firmware_origin.lower():
        return True, f"Firmware: {label}"
    if firmware_version:
        return True, f"Firmware: {label}"

    return False, f"Firmware: {label} (could not confirm version)"


def count_files(flipper, directory, extension, recursive):
    """Count files matching *extension* in *directory* on the Flipper.

    When *recursive* is True, descend into subdirectories.
    When *extension* is None, count all files regardless of extension.

    For the special case of NFC Tags (non-recursive /ext/nfc), we skip
    the 'amiibo' subdirectory since that is counted separately.

    Returns:
        tuple[int, bool]: (count, directory_exists)
    """
    try:
        entries = flipper.storage_list(directory)
    except (TimeoutError, OSError):
        return 0, False

    if not entries:
        # Check if the response was an error or just empty
        return 0, False

    count = 0
    subdirs = []

    for name, entry_type in entries:
        if entry_type == "file":
            if extension is None or name.lower().endswith(extension):
                count += 1
        elif entry_type == "dir":
            # For the top-level /ext/nfc check, skip the amiibo subdir
            if directory == "/ext/nfc" and name.lower() == "amiibo":
                continue
            if recursive:
                subdirs.append(f"{directory}/{name}")

    # Recurse into subdirectories
    for subdir in subdirs:
        sub_count, _ = count_files(flipper, subdir, extension, recursive)
        count += sub_count

    return count, True


def run_checks(flipper):
    """Run all verification checks and return results.

    Returns:
        list[tuple[bool, str]]: List of (passed, description) for each check.
    """
    results = []

    # 1. Firmware check
    passed, description = check_firmware(flipper)
    results.append((passed, description))

    # 2-8. File count checks
    for label, directory, extension, recursive in FILE_CHECKS:
        count, exists = count_files(flipper, directory, extension, recursive)

        if not exists or count == 0:
            file_word = "files"
            results.append((False, f"{label}: 0 files in {directory}"))
        else:
            file_word = "file" if count == 1 else "files"
            results.append((True, f"{label}: {count} {file_word} in {directory}"))

    return results


def print_report(results):
    """Print the checklist-style verification report."""
    print()
    print("Mazincea Urban Sorcerer Kit - Deployment Verification")
    print("=" * 55)
    print()

    passed_count = 0
    total_count = len(results)

    for passed, description in results:
        icon = "[OK]" if passed else "[!!]"
        print(f"  {icon} {description}")
        if passed:
            passed_count += 1

    print()
    print(f"Verification: {passed_count}/{total_count} checks passed")
    print()


def main():
    parser = argparse.ArgumentParser(
        description="Verify Flipper Zero deployment (Mazincea Urban Sorcerer Kit)"
    )
    parser.add_argument(
        "--port",
        default=None,
        help="Serial port for the Flipper (default: auto-detect)",
    )
    args = parser.parse_args()

    # Connect
    try:
        flipper = FlipperSerial(port=args.port)
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
    except OSError as exc:
        print(f"ERROR: Could not open serial port: {exc}", file=sys.stderr)
        sys.exit(1)

    try:
        results = run_checks(flipper)
        print_report(results)

        # Exit with non-zero status if any check failed
        total_passed = sum(1 for passed, _ in results if passed)
        if total_passed < len(results):
            sys.exit(1)
    finally:
        flipper.close()


if __name__ == "__main__":
    main()
