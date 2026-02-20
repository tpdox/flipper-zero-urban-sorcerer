#!/usr/bin/env python3
"""Download community resource repositories for the Flipper Zero toolkit.

Clones all required community repos into a vendor/ directory using shallow
clones (--depth 1) to minimise disk usage. Safe to re-run: existing repos
are skipped automatically.
"""

import os
import subprocess
import sys
from pathlib import Path

# Each entry is (clone URL, directory name inside vendor/)
REPOS = [
    ("https://github.com/Lucaslhm/Flipper-IRDB.git", "Flipper-IRDB"),
    ("https://github.com/Gioman101/FlipperAmiibo.git", "FlipperAmiibo"),
    ("https://github.com/neverfa11ing/FlipperMusicRTTTL.git", "FlipperMusicRTTTL"),
    ("https://github.com/I-Am-Jakoby/Flipper-Zero-BadUSB.git", "Flipper-Zero-BadUSB"),
    ("https://github.com/w0lfzk1n/Flipper-Zero-NFC-Trolls.git", "Flipper-Zero-NFC-Trolls"),
]

# Resolve vendor/ relative to this script so it works regardless of cwd.
VENDOR_DIR = Path(__file__).resolve().parent / "vendor"


def download_resources(vendor_dir: Path | None = None) -> Path:
    """Clone every repo listed in REPOS into *vendor_dir*.

    Parameters
    ----------
    vendor_dir:
        Target directory for cloned repos.  Defaults to ``vendor/`` next to
        this script.

    Returns
    -------
    Path
        The absolute path to the vendor directory.
    """
    if vendor_dir is None:
        vendor_dir = VENDOR_DIR

    vendor_dir = Path(vendor_dir).resolve()
    vendor_dir.mkdir(parents=True, exist_ok=True)
    print(f"Vendor directory: {vendor_dir}\n")

    for url, name in REPOS:
        dest = vendor_dir / name

        if dest.exists():
            print(f"[skip]  {name} already exists at {dest}")
            continue

        print(f"[clone] {name} ...")
        result = subprocess.run(
            ["git", "clone", "--depth", "1", url, str(dest)],
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            print(f"[error] Failed to clone {name}:", file=sys.stderr)
            print(result.stderr.strip(), file=sys.stderr)
            sys.exit(1)

        print(f"[done]  {name}")

    print(f"\nAll resources ready in {vendor_dir}")
    return vendor_dir


def main() -> None:
    """Entry point when running as a standalone script."""
    download_resources()


if __name__ == "__main__":
    main()
