#!/usr/bin/env python3
"""Flipper Zero Deploy — top-level orchestrator.

Runs all download/curate scripts to build the staging directory, then pushes
everything to a connected Flipper Zero over serial.

Usage:
    python3 deploy.py                   # Full run: prepare + upload
    python3 deploy.py --skip-download   # Skip preparation, use existing staging/
    python3 deploy.py --dry-run         # Show what would be uploaded
    python3 deploy.py --port /dev/...   # Specify serial port manually

Steps:
    1. Run preparation scripts (download_resources, curate_ir, curate_badusb,
       generate_nfc, curate_extras, download_apps)
    2. Connect to Flipper over serial
    3. Create required directories on the SD card
    4. Push all staged files to the Flipper
    5. Print summary
"""

import argparse
import os
import sys
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths (resolved relative to this script)
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent
STAGING_DIR = SCRIPT_DIR / "staging"

# ---------------------------------------------------------------------------
# Amiibo subset — limit to popular franchises to keep serial upload practical.
# The full collection (~953 files) would take ages over 230400 baud serial.
# ---------------------------------------------------------------------------
AMIIBO_POPULAR_SERIES = [
    "zelda",
    "mario",
    "smash",
    "animal_crossing",
    "animal crossing",
    "splatoon",
    "pokemon",
    "kirby",
    "metroid",
    "fire_emblem",
    "fire emblem",
]

AMIIBO_MAX_FILES = 100

# ---------------------------------------------------------------------------
# Directory layout on the Flipper SD card
# ---------------------------------------------------------------------------
FLIPPER_DIRS = [
    "/ext/infrared",
    "/ext/badusb",
    "/ext/nfc",
    "/ext/nfc/amiibo",
    "/ext/subghz",
    "/ext/apps_data/music_player",
    "/ext/apps/NFC",
    "/ext/apps/Sub-GHz",
    "/ext/apps/Infrared",
    "/ext/apps/Media",
    "/ext/apps/USB",
]

# ---------------------------------------------------------------------------
# Mapping: staging subdirectory -> Flipper destination
# ---------------------------------------------------------------------------
UPLOAD_MAPPINGS = [
    # (staging_subdir, flipper_dest, glob_pattern, preserve_subdirs)
    ("infrared",      "/ext/infrared",              "*.ir",   False),
    ("badusb",        "/ext/badusb",                "*",      False),
    ("nfc",           "/ext/nfc",                   "*.nfc",  False),
    ("subghz",        "/ext/subghz",                "*",      False),
    ("music_player",  "/ext/apps_data/music_player", "*",     False),
]


# ---------------------------------------------------------------------------
# Step 1: Run preparation scripts
# ---------------------------------------------------------------------------

def run_preparation_scripts():
    """Import and run all preparation scripts in order.

    Each script's main() function is called directly (no subprocess).
    """
    steps = [
        ("download_resources", "download_resources", "Downloading vendor repos"),
        ("curate_ir",          "main",               "Curating IR files"),
        ("curate_badusb",      "main",               "Curating BadUSB payloads"),
        ("generate_nfc",       "main",               "Generating NFC tags"),
        ("curate_extras",      "main",               "Curating extras (music, amiibo, tesla)"),
        ("download_apps",      "main",               "Downloading FAP apps"),
    ]

    print("=" * 60)
    print("STEP 1: Preparing staging directory")
    print("=" * 60)

    for module_name, func_name, description in steps:
        print(f"\n{'─' * 60}")
        print(f"  {description} ({module_name}.{func_name})")
        print(f"{'─' * 60}\n")

        try:
            # Import the module from the same directory as this script.
            # We add SCRIPT_DIR to sys.path temporarily if needed.
            if str(SCRIPT_DIR) not in sys.path:
                sys.path.insert(0, str(SCRIPT_DIR))

            module = __import__(module_name)
            func = getattr(module, func_name)
            func()
        except SystemExit as e:
            # Some scripts call sys.exit(1) on error; don't let that kill us.
            if e.code not in (None, 0):
                print(f"\n[warn] {module_name}.{func_name}() exited with code {e.code}")
                print(f"       Continuing with remaining steps...")
        except Exception as e:
            print(f"\n[error] {module_name}.{func_name}() failed: {e}")
            print(f"        Continuing with remaining steps...")

    print(f"\n{'=' * 60}")
    print("Preparation complete.")
    print(f"{'=' * 60}\n")


# ---------------------------------------------------------------------------
# Step 2-4: Connect and upload
# ---------------------------------------------------------------------------

def collect_files_to_upload():
    """Walk the staging directory and build a list of (local_path, remote_path) tuples.

    Returns:
        list[tuple[Path, str]]: Files to upload with their Flipper destinations.
    """
    uploads = []

    # Standard flat mappings
    for subdir, flipper_dest, pattern, _preserve in UPLOAD_MAPPINGS:
        staging_sub = STAGING_DIR / subdir
        if not staging_sub.is_dir():
            continue
        for fpath in sorted(staging_sub.glob(pattern)):
            if fpath.is_file():
                # Sanitize filename: replace spaces with underscores
                # (Flipper CLI tokenizes on spaces)
                safe_name = fpath.name.replace(" ", "_")
                remote = f"{flipper_dest}/{safe_name}"
                uploads.append((fpath, remote))

    # Amiibo collection — limit to popular series subset
    amiibo_staging = STAGING_DIR / "nfc" / "amiibo"
    if amiibo_staging.is_dir():
        amiibo_files = _select_amiibo_subset(amiibo_staging)
        for fpath, rel_path in amiibo_files:
            remote = f"/ext/nfc/amiibo/{rel_path}"
            uploads.append((fpath, remote))

    # FAP apps — preserve category subdirectory
    apps_staging = STAGING_DIR / "apps"
    if apps_staging.is_dir():
        for fpath in sorted(apps_staging.rglob("*.fap")):
            # The category is the immediate parent directory name
            category = fpath.parent.name
            remote = f"/ext/apps/{category}/{fpath.name}"
            uploads.append((fpath, remote))

    return uploads


def _select_amiibo_subset(amiibo_root: Path) -> list[tuple[Path, str]]:
    """Select a popular subset of amiibo .nfc files.

    Returns up to AMIIBO_MAX_FILES files from popular franchises, with
    their relative paths preserved.

    Returns:
        list[tuple[Path, str]]: (absolute_path, relative_path_string) pairs.
    """
    all_nfc = sorted(amiibo_root.rglob("*.nfc"))
    total = len(all_nfc)

    if total == 0:
        return []

    # Filter to popular series based on directory/filename matching
    popular = []
    for fpath in all_nfc:
        rel = fpath.relative_to(amiibo_root)
        rel_lower = str(rel).lower()
        if any(series in rel_lower for series in AMIIBO_POPULAR_SERIES):
            popular.append((fpath, str(rel)))

    # Cap at AMIIBO_MAX_FILES
    selected = popular[:AMIIBO_MAX_FILES]

    if total > len(selected):
        print(
            f"\n[note] Amiibo collection has {total} files; "
            f"selecting {len(selected)} from popular series "
            f"({', '.join(s.title() for s in AMIIBO_POPULAR_SERIES[:5])}, ...) "
            f"to keep serial upload time reasonable."
        )
        print(
            f"       To upload the full collection, copy staging/nfc/amiibo/ "
            f"to the SD card directly via a card reader.\n"
        )

    return selected


def collect_required_dirs(uploads):
    """Determine which directories need to be created on the Flipper.

    Starts with the base FLIPPER_DIRS list, then adds any extra parent
    directories implied by the upload file list (e.g., amiibo subdirs).

    Returns:
        list[str]: Sorted list of unique directory paths to create.
    """
    dirs = set(FLIPPER_DIRS)

    for _local, remote in uploads:
        # Add the parent directory of every file we'll upload
        parent = remote.rsplit("/", 1)[0]
        while parent and parent != "/ext":
            dirs.add(parent)
            parent = parent.rsplit("/", 1)[0] if "/" in parent[1:] else ""

    return sorted(dirs)


def create_flipper_dirs(flipper, dirs, dry_run=False):
    """Create required directories on the Flipper SD card.

    Args:
        flipper: FlipperSerial instance.
        dirs: List of absolute paths to create.
        dry_run: If True, print but don't actually create.
    """
    print(f"\n{'=' * 60}")
    print("STEP 3: Creating directories on Flipper SD card")
    print(f"{'=' * 60}")

    for d in dirs:
        if dry_run:
            print(f"  [dry-run] mkdir {d}")
        else:
            try:
                flipper.storage_mkdir(d)
                print(f"  [mkdir] {d}")
            except (TimeoutError, OSError) as e:
                print(f"  [error] Failed to create {d}: {e}")


def upload_files(flipper, uploads, dry_run=False):
    """Push all files from staging to the Flipper.

    Args:
        flipper: FlipperSerial instance.
        uploads: List of (local_path, remote_path) tuples.
        dry_run: If True, print but don't actually write.

    Returns:
        tuple[int, int, int]: (success_count, fail_count, total_bytes)
    """
    print(f"\n{'=' * 60}")
    print("STEP 4: Uploading files to Flipper")
    print(f"{'=' * 60}")

    total = len(uploads)
    success = 0
    failed = 0
    total_bytes = 0

    for i, (local_path, remote_path) in enumerate(uploads, 1):
        file_size = local_path.stat().st_size
        size_str = _format_size(file_size)

        if dry_run:
            print(f"  [{i:>4}/{total}] [dry-run] {local_path.name} -> {remote_path} ({size_str})")
            success += 1
            total_bytes += file_size
            continue

        print(f"  [{i:>4}/{total}] {local_path.name} -> {remote_path} ({size_str})", end="")
        sys.stdout.flush()

        ok = False
        for attempt in range(2):  # retry once on failure
            try:
                if attempt > 0:
                    # Recovery: flush, brief pause, send newline to reset CLI
                    import termios as _termios
                    _termios.tcflush(flipper.fd, _termios.TCIOFLUSH)
                    time.sleep(0.5)
                    os.write(flipper.fd, b"\r\n")
                    time.sleep(0.3)
                    _termios.tcflush(flipper.fd, _termios.TCIFLUSH)
                    print(f" RETRY", end="")
                    sys.stdout.flush()

                start = time.monotonic()
                flipper.storage_write(str(local_path), remote_path)
                elapsed = time.monotonic() - start
                print(f"  OK ({elapsed:.1f}s)")
                success += 1
                total_bytes += file_size
                ok = True
                break
            except (TimeoutError, OSError, RuntimeError) as e:
                if attempt == 0:
                    last_err = e
                    continue
                print(f"  FAIL: {last_err}")
                failed += 1
            except KeyboardInterrupt:
                print("\n\n[!] Upload interrupted by user.")
                failed += (total - i)
                return success, failed, total_bytes

        if not ok and failed == 0:
            # Shouldn't happen, but safety net
            failed += 1

    return success, failed, total_bytes


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _format_size(nbytes):
    """Format a byte count as a human-readable string."""
    if nbytes < 1024:
        return f"{nbytes} B"
    elif nbytes < 1024 * 1024:
        return f"{nbytes / 1024:.1f} KB"
    else:
        return f"{nbytes / (1024 * 1024):.1f} MB"


def print_deploy_summary(success, failed, total_bytes, elapsed, dry_run=False):
    """Print a final summary of the deploy."""
    print(f"\n{'=' * 60}")
    if dry_run:
        print("DEPLOY SUMMARY (dry run)")
    else:
        print("DEPLOY SUMMARY")
    print(f"{'=' * 60}")

    total = success + failed
    print(f"  Files uploaded : {success}/{total}")
    if failed:
        print(f"  Files failed   : {failed}")
    print(f"  Total size     : {_format_size(total_bytes)}")
    print(f"  Elapsed time   : {elapsed:.1f}s")

    if dry_run:
        print(f"\n  This was a dry run. No files were actually written.")

    if failed:
        print(f"\n  WARNING: {failed} file(s) failed to upload.")
        print(f"  You may want to retry, or copy failed files via SD card reader.")

    print(f"{'=' * 60}\n")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Deploy curated files to a Flipper Zero over serial.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python3 deploy.py                   # Full run\n"
            "  python3 deploy.py --skip-download    # Skip preparation\n"
            "  python3 deploy.py --dry-run          # Preview upload\n"
            "  python3 deploy.py --port /dev/cu.usbmodemflip_Mazincea1\n"
        ),
    )
    parser.add_argument(
        "--skip-download",
        action="store_true",
        help="Skip step 1 (preparation scripts); use existing staging/ directory.",
    )
    parser.add_argument(
        "--port",
        type=str,
        default=None,
        help="Serial port for Flipper Zero (default: auto-detect).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be uploaded without actually writing to the Flipper.",
    )
    return parser.parse_args()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    """Top-level deploy orchestrator."""
    args = parse_args()

    print()
    print("=" * 60)
    print("  Flipper Zero Deploy")
    print("=" * 60)
    print()

    deploy_start = time.monotonic()

    # ------------------------------------------------------------------
    # Step 1: Preparation
    # ------------------------------------------------------------------
    if args.skip_download:
        print("[skip] Skipping preparation scripts (--skip-download)")
        if not STAGING_DIR.is_dir():
            print(f"\n[error] Staging directory not found: {STAGING_DIR}")
            print(f"        Run without --skip-download first to create it.")
            sys.exit(1)
    else:
        run_preparation_scripts()

    # ------------------------------------------------------------------
    # Collect files to upload
    # ------------------------------------------------------------------
    print(f"\n{'=' * 60}")
    print("STEP 2: Collecting files to upload")
    print(f"{'=' * 60}")

    uploads = collect_files_to_upload()
    if not uploads:
        print("\n[warn] No files found in staging directory. Nothing to upload.")
        sys.exit(0)

    print(f"\n  Found {len(uploads)} file(s) to upload.")
    total_size = sum(p.stat().st_size for p, _ in uploads)
    print(f"  Total size: {_format_size(total_size)}")

    # Show a breakdown by destination category
    categories = {}
    for _, remote in uploads:
        # Extract the top-level destination (e.g., /ext/infrared, /ext/apps/NFC)
        parts = remote.split("/")
        if len(parts) >= 3:
            cat = "/".join(parts[:3])
            if parts[2] == "apps" and len(parts) >= 4:
                cat = "/".join(parts[:4])
            elif parts[2] == "apps_data" and len(parts) >= 4:
                cat = "/".join(parts[:4])
            elif parts[2] == "nfc" and len(parts) >= 4 and parts[3] == "amiibo":
                cat = "/ext/nfc/amiibo"
        categories[cat] = categories.get(cat, 0) + 1

    for cat in sorted(categories):
        print(f"    {cat}: {categories[cat]} file(s)")

    # ------------------------------------------------------------------
    # Step 2b: Connect to Flipper
    # ------------------------------------------------------------------
    if args.dry_run:
        # In dry-run mode, skip the actual serial connection
        print(f"\n[dry-run] Skipping serial connection.")
        dirs = collect_required_dirs(uploads)
        create_flipper_dirs(None, dirs, dry_run=True)
        success, failed, total_bytes = upload_files(None, uploads, dry_run=True)
        elapsed = time.monotonic() - deploy_start
        print_deploy_summary(success, failed, total_bytes, elapsed, dry_run=True)
        return

    # Real connection
    print(f"\n{'─' * 60}")
    print("  Connecting to Flipper Zero...")
    print(f"{'─' * 60}")

    from flipper_serial import FlipperSerial

    try:
        with FlipperSerial(port=args.port) as flipper:
            print(f"  Connected on {flipper.port}")

            # Verify connection with a quick command
            try:
                info = flipper.send_command("device_info", timeout=10.0)
                for line in info.split("\n"):
                    if "hardware_name" in line:
                        print(f"  Device: {line.split(':', 1)[-1].strip()}")
                        break
            except (TimeoutError, OSError):
                print("  [warn] Could not read device_info, continuing anyway...")

            # Step 3: Create directories
            dirs = collect_required_dirs(uploads)
            create_flipper_dirs(flipper, dirs)

            # Step 4: Upload files
            success, failed, total_bytes = upload_files(flipper, uploads)

    except FileNotFoundError as e:
        print(f"\n[error] {e}")
        print("        Is your Flipper Zero connected via USB?")
        sys.exit(1)
    except OSError as e:
        print(f"\n[error] Serial connection failed: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n\n[!] Deploy interrupted by user.")
        sys.exit(130)

    # ------------------------------------------------------------------
    # Step 5: Summary
    # ------------------------------------------------------------------
    elapsed = time.monotonic() - deploy_start
    print_deploy_summary(success, failed, total_bytes, elapsed)


if __name__ == "__main__":
    main()
