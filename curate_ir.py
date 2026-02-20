"""IR Database Curator — select useful .ir files from Flipper-IRDB.

Walks the local Flipper-IRDB clone and copies the most useful IR files for
popular brands into staging/infrared/, ready for upload to a Flipper Zero.

The IRDB is organized as:
    vendor/Flipper-IRDB/<Category>/<Brand>/<file>.ir

This script filters by category + brand, caps each brand at 10 files, and
copies matches to a flat staging directory.

Usage:
    python3 curate_ir.py
"""

import os
import shutil
import sys


# Path to the local Flipper-IRDB clone, relative to this script's directory.
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
IRDB_ROOT = os.path.join(SCRIPT_DIR, "vendor", "Flipper-IRDB")
STAGING_DIR = os.path.join(SCRIPT_DIR, "staging", "infrared")

# Maximum number of .ir files to keep per brand within a category.
MAX_FILES_PER_BRAND = 10

# Target brands grouped by IRDB category folder name.
# Keys must match the actual top-level directory names in Flipper-IRDB.
TARGET_BRANDS = {
    "TVs": [
        "Samsung", "LG", "Sony", "Vizio", "TCL",
        "Hisense", "Panasonic", "Philips", "Toshiba", "Sharp",
    ],
    "SoundBars": [
        "JBL", "Bose", "Sony", "Samsung", "Vizio",
        "Yamaha", "Polk", "Harman_Kardon", "Sonos",
    ],
    "ACs": [
        "Mitsubishi", "Daikin", "LG", "Carrier", "Fujitsu", "Toshiba",
    ],
    "Projectors": [
        "Epson", "BenQ", "NEC", "Optoma", "ViewSonic",
    ],
    "Fans": [
        "Dyson", "Honeywell",
    ],
    "Cameras": [
        "Canon", "Nikon",
    ],
}


def find_ir_files(irdb_root):
    """Walk the IRDB tree and return every .ir file path found.

    Returns:
        list[str]: Absolute paths to .ir files, sorted alphabetically.
    """
    ir_files = []
    for dirpath, _dirnames, filenames in os.walk(irdb_root):
        for fname in filenames:
            if fname.lower().endswith(".ir"):
                ir_files.append(os.path.join(dirpath, fname))
    ir_files.sort()
    return ir_files


def match_files(ir_files, irdb_root):
    """Filter .ir files by category and brand.

    For each category/brand pair in TARGET_BRANDS, selects files whose path
    (relative to irdb_root) contains the brand name (case-insensitive match
    anywhere in the path). Files are further scoped to their category
    directory so a "Sony" TV file won't accidentally appear as a "Sony"
    soundbar file.

    If a single brand has more than MAX_FILES_PER_BRAND matches, only the
    first MAX_FILES_PER_BRAND (sorted alphabetically) are kept.

    Returns:
        list[tuple[str, str, str]]: List of (source_path, category, brand)
            tuples for every selected file.
    """
    selected = []

    for category, brands in TARGET_BRANDS.items():
        category_dir = os.path.join(irdb_root, category)
        # Pre-filter to files that live under this category directory.
        category_lower = (category_dir + os.sep).lower()
        category_files = [
            f for f in ir_files if f.lower().startswith(category_lower)
        ]

        for brand in brands:
            brand_lower = brand.lower()
            # Match: the brand name appears somewhere in the path relative
            # to the category dir (typically as a folder name).
            matches = [
                f for f in category_files
                if brand_lower in f[len(category_dir):].lower()
            ]
            # Sort alphabetically and cap at MAX_FILES_PER_BRAND.
            matches.sort()
            for path in matches[:MAX_FILES_PER_BRAND]:
                selected.append((path, category, brand))

    return selected


def clean_staging(staging_dir):
    """Remove and recreate the staging directory."""
    if os.path.exists(staging_dir):
        shutil.rmtree(staging_dir)
    os.makedirs(staging_dir, exist_ok=True)


def copy_files(selected, staging_dir):
    """Copy selected .ir files into the staging directory.

    Files are placed directly in staging_dir with their original filename.
    If two source files have the same name, a numeric suffix is appended to
    avoid collisions.

    Returns:
        int: Total bytes copied.
    """
    total_bytes = 0
    used_names = set()

    for src_path, _category, _brand in selected:
        base = os.path.basename(src_path)
        dest_name = base

        # Handle name collisions by appending _2, _3, etc.
        if dest_name.lower() in used_names:
            name, ext = os.path.splitext(base)
            counter = 2
            while True:
                dest_name = f"{name}_{counter}{ext}"
                if dest_name.lower() not in used_names:
                    break
                counter += 1

        used_names.add(dest_name.lower())
        dest_path = os.path.join(staging_dir, dest_name)
        shutil.copy2(src_path, dest_path)
        total_bytes += os.path.getsize(dest_path)

    return total_bytes


def print_summary(selected, total_bytes):
    """Print a human-readable summary of what was selected."""
    print(f"\n{'=' * 60}")
    print("IR Database Curation Summary")
    print(f"{'=' * 60}")

    # Per-category breakdown
    category_counts = {}
    for _path, category, brand in selected:
        key = (category, brand)
        category_counts[key] = category_counts.get(key, 0) + 1

    current_category = None
    for (category, brand), count in sorted(category_counts.items()):
        if category != current_category:
            print(f"\n  {category}:")
            current_category = category
        print(f"    {brand:<20s} {count} file{'s' if count != 1 else ''}")

    # Totals
    if total_bytes < 1024:
        size_str = f"{total_bytes} B"
    elif total_bytes < 1024 * 1024:
        size_str = f"{total_bytes / 1024:.1f} KB"
    else:
        size_str = f"{total_bytes / (1024 * 1024):.1f} MB"

    print(f"\n{'=' * 60}")
    print(f"Total: {len(selected)} files selected, {size_str}")
    print(f"Staged to: {STAGING_DIR}")
    print(f"{'=' * 60}\n")


def main():
    """Entry point: curate IR files from the IRDB into staging."""
    # Check that the IRDB clone exists.
    if not os.path.isdir(IRDB_ROOT):
        print(
            f"ERROR: Flipper-IRDB not found at {IRDB_ROOT}\n"
            f"\n"
            f"Please clone it first. You can run:\n"
            f"  git clone --depth 1 https://github.com/Lucaslhm/Flipper-IRDB.git "
            f"vendor/Flipper-IRDB\n"
            f"\n"
            f"Or run download_resources.py which handles this automatically.",
            file=sys.stderr,
        )
        sys.exit(1)

    print("Scanning Flipper-IRDB for .ir files...")
    ir_files = find_ir_files(IRDB_ROOT)
    print(f"Found {len(ir_files)} total .ir files in IRDB.")

    print("Matching files by category and brand...")
    selected = match_files(ir_files, IRDB_ROOT)

    if not selected:
        print("WARNING: No matching .ir files found. Check IRDB structure.")
        sys.exit(0)

    print(f"Cleaning staging directory: {STAGING_DIR}")
    clean_staging(STAGING_DIR)

    print("Copying selected files to staging...")
    total_bytes = copy_files(selected, STAGING_DIR)

    print_summary(selected, total_bytes)


if __name__ == "__main__":
    main()
