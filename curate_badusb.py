#!/usr/bin/env python3
"""Curate BadUSB DuckyScript payloads into staging/badusb/.

Writes a set of custom macOS-optimised payloads and optionally copies
interesting community payloads from the I-Am-Jakoby vendor repo.
"""

import shutil
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths (resolved relative to this script so cwd doesn't matter)
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent
STAGING_DIR = SCRIPT_DIR / "staging" / "badusb"
VENDOR_BADUSB = SCRIPT_DIR / "vendor" / "Flipper-Zero-BadUSB"

# ---------------------------------------------------------------------------
# Custom payloads - written directly, no external dependency
# ---------------------------------------------------------------------------
CUSTOM_PAYLOADS: dict[str, str] = {
    "RickRoll_macOS.txt": """\
REM Flipper Zero Rick Roll - macOS
REM Opens YouTube Rick Roll at max volume
DELAY 500
GUI SPACE
DELAY 700
STRING terminal
DELAY 500
ENTER
DELAY 1000
STRING osascript -e 'set volume output volume 100'
ENTER
DELAY 300
STRING open https://www.youtube.com/watch?v=dQw4w9WgXcQ
ENTER
DELAY 500
STRING exit
ENTER
""",
    "FakeHackScreen_macOS.txt": """\
REM Flipper Zero Fake Hack Screen - macOS
REM Opens hackertyper in fullscreen
DELAY 500
GUI SPACE
DELAY 700
STRING safari
DELAY 500
ENTER
DELAY 1500
GUI l
DELAY 300
STRING https://hackertyper.net
ENTER
DELAY 2000
CTRL GUI f
""",
    "MouseJiggle.txt": """\
REM Flipper Zero Mouse Jiggler
REM Keeps computer awake by moving mouse slightly
ID 1234:5678
DELAY 1000
STRING LOOP
MOUSE_MOVE 1 0
DELAY 500
MOUSE_MOVE -1 0
DELAY 30000
REPEAT
""",
}

# Directories inside the vendor repo that are likely to contain fun /
# harmless payloads worth curating.
VENDOR_INTERESTING_DIRS = [
    "Payloads/Prank",
    "Payloads/Fun",
    "Payloads/Recon",
]

# Only copy files with these extensions from the vendor repo.
PAYLOAD_EXTENSIONS = {".txt", ".ducky"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _clean_staging(staging: Path) -> None:
    """Remove and recreate the staging directory for a clean run."""
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True, exist_ok=True)


def _write_custom_payloads(staging: Path) -> list[str]:
    """Write built-in custom payloads and return their filenames."""
    written: list[str] = []
    for name, content in CUSTOM_PAYLOADS.items():
        dest = staging / name
        dest.write_text(content)
        written.append(name)
    return written


def _copy_vendor_payloads(staging: Path) -> list[str]:
    """Copy interesting payloads from the I-Am-Jakoby vendor repo.

    Returns a list of destination filenames (may be empty if the repo is
    not cloned yet).
    """
    if not VENDOR_BADUSB.is_dir():
        print(f"[info]  Vendor repo not found at {VENDOR_BADUSB} -- skipping")
        return []

    copied: list[str] = []
    for subdir in VENDOR_INTERESTING_DIRS:
        search_root = VENDOR_BADUSB / subdir
        if not search_root.is_dir():
            continue
        for payload_file in sorted(search_root.rglob("*")):
            if not payload_file.is_file():
                continue
            if payload_file.suffix.lower() not in PAYLOAD_EXTENSIONS:
                continue
            # Prefix with the category so names stay unique.
            category = subdir.replace("/", "_")
            dest_name = f"{category}_{payload_file.name}"
            dest = staging / dest_name
            shutil.copy2(payload_file, dest)
            copied.append(dest_name)

    return copied


def _print_summary(custom: list[str], vendor: list[str]) -> None:
    """Print a human-readable summary of everything staged."""
    total = len(custom) + len(vendor)
    print(f"\n{'=' * 50}")
    print(f"BadUSB Payload Curation Summary")
    print(f"{'=' * 50}")
    print(f"Staging directory : {STAGING_DIR}")
    print(f"Custom payloads   : {len(custom)}")
    for name in custom:
        print(f"  - {name}")
    print(f"Vendor payloads   : {len(vendor)}")
    for name in vendor:
        print(f"  - {name}")
    print(f"{'─' * 50}")
    print(f"Total staged      : {total}")
    print(f"{'=' * 50}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    """Curate BadUSB payloads into staging/badusb/."""
    print("Curating BadUSB payloads ...")
    _clean_staging(STAGING_DIR)

    custom = _write_custom_payloads(STAGING_DIR)
    print(f"[done]  Wrote {len(custom)} custom payload(s)")

    vendor = _copy_vendor_payloads(STAGING_DIR)
    if vendor:
        print(f"[done]  Copied {len(vendor)} vendor payload(s)")

    _print_summary(custom, vendor)


if __name__ == "__main__":
    main()
