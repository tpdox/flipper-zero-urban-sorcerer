#!/usr/bin/env python3
"""Curate RTTTL music, Amiibo NFC dumps, and Tesla Sub-GHz files into staging.

Selects RTTTL music files matching popular songs, copies the full Amiibo
NFC collection, and looks for Tesla charge-port .sub files from vendor repos.

Usage:
    python3 curate_extras.py
"""

import os
import shutil
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths (resolved relative to this script so cwd doesn't matter)
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent
VENDOR_DIR = SCRIPT_DIR / "vendor"

MUSIC_VENDOR = VENDOR_DIR / "FlipperMusicRTTTL"
AMIIBO_VENDOR = VENDOR_DIR / "FlipperAmiibo"

STAGING_MUSIC = SCRIPT_DIR / "staging" / "music_player"
STAGING_AMIIBO = SCRIPT_DIR / "staging" / "nfc" / "amiibo"
STAGING_SUBGHZ = SCRIPT_DIR / "staging" / "subghz"

# ---------------------------------------------------------------------------
# Music search patterns -- case-insensitive substring matches on filenames
# ---------------------------------------------------------------------------
MUSIC_SEARCHES: dict[str, list[str]] = {
    "Mario Bros": ["mario"],
    "Zelda": ["zelda"],
    "Imperial March (Star Wars)": ["imperial", "sw_impe"],
    "Tetris": ["tetris"],
    "Rick Roll": ["rick astley", "rickroll", "rick_roll", "never gonna give", "never_gonna_give"],
    "Nokia Ringtone": ["nokia"],
    "Simpsons": ["simpsons", "simpson"],
    "Take On Me": ["take on me", "takeonme"],
}

MUSIC_EXTENSIONS = {".txt", ".rtttl"}

# Tesla Sub-GHz search patterns (case-insensitive substring on filename)
TESLA_PATTERNS = [
    "tesla_charge_port",
    "tesla_chrgport",
    "tesla_charge",
    "tesla",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _clean_staging(staging: Path) -> None:
    """Remove and recreate a staging directory for a clean run."""
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True, exist_ok=True)


def _find_music_files(vendor_root: Path) -> list[Path]:
    """Recursively find all .txt and .rtttl files under the music vendor repo."""
    results: list[Path] = []
    for dirpath, _dirnames, filenames in os.walk(vendor_root):
        for fname in filenames:
            if Path(fname).suffix.lower() in MUSIC_EXTENSIONS:
                results.append(Path(dirpath) / fname)
    results.sort()
    return results


def _match_music(all_files: list[Path]) -> dict[str, list[Path]]:
    """Match music files against our song search patterns.

    Returns a dict mapping song display-name to matched file paths.
    """
    matched: dict[str, list[Path]] = {}

    for song_name, patterns in MUSIC_SEARCHES.items():
        hits: list[Path] = []
        for fpath in all_files:
            fname_lower = fpath.name.lower()
            if any(pat in fname_lower for pat in patterns):
                hits.append(fpath)
        if hits:
            matched[song_name] = sorted(hits)

    return matched


def _copy_music(matched: dict[str, list[Path]], staging: Path) -> int:
    """Copy matched music files to staging, handling name collisions.

    Returns the number of files copied.
    """
    used_names: set[str] = set()
    copied = 0

    for _song, paths in sorted(matched.items()):
        for src in paths:
            dest_name = src.name
            # Handle collisions
            if dest_name.lower() in used_names:
                stem = src.stem
                suffix = src.suffix
                counter = 2
                while True:
                    dest_name = f"{stem}_{counter}{suffix}"
                    if dest_name.lower() not in used_names:
                        break
                    counter += 1

            used_names.add(dest_name.lower())
            shutil.copy2(src, staging / dest_name)
            copied += 1

    return copied


def _copy_amiibo(vendor_root: Path, staging: Path) -> int:
    """Copy the entire Amiibo NFC collection to staging.

    Returns the number of .nfc files copied.
    """
    copied = 0
    for dirpath, _dirnames, filenames in os.walk(vendor_root):
        for fname in filenames:
            if not fname.lower().endswith(".nfc"):
                continue
            src = Path(dirpath) / fname
            # Preserve the directory structure relative to the vendor root
            rel = src.relative_to(vendor_root)
            dest = staging / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
            copied += 1

    return copied


def _find_tesla_sub_files() -> list[Path]:
    """Search all vendor directories for Tesla charge port .sub files."""
    results: list[Path] = []
    for dirpath, _dirnames, filenames in os.walk(VENDOR_DIR):
        for fname in filenames:
            if not fname.lower().endswith(".sub"):
                continue
            fname_lower = fname.lower()
            if any(pat in fname_lower for pat in TESLA_PATTERNS):
                results.append(Path(dirpath) / fname)
    results.sort()
    return results


def _write_tesla_placeholder(staging: Path) -> None:
    """Write a placeholder note about where to find a Tesla .sub file."""
    note_path = staging / "Tesla_charge_port_README.txt"
    note_path.write_text(
        "Tesla Charge Port Opener - Sub-GHz File\n"
        "========================================\n"
        "\n"
        "No Tesla charge port .sub file was found in the vendor repos.\n"
        "\n"
        "You can find community-created Tesla charge port .sub files at:\n"
        "\n"
        "  - Flipper Zero Discord community (#sub-ghz channel)\n"
        "  - https://github.com/UberGuidoZ/Flipper (community collection)\n"
        "  - Flipper Zero forums: https://forum.flipper.net/\n"
        "\n"
        "Common filenames to look for:\n"
        "  - Tesla_charge_port.sub\n"
        "  - Tesla_ChrgPort.sub\n"
        "  - Tesla_Open_Charge_Port.sub\n"
        "\n"
        "Place the .sub file in your Flipper's SD card under /subghz/\n"
    )


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

def _print_summary(
    music_matched: dict[str, list[Path]],
    music_count: int,
    amiibo_count: int,
    tesla_files: list[Path],
) -> None:
    """Print a human-readable summary of everything staged."""
    print(f"\n{'=' * 60}")
    print("Extras Curation Summary")
    print(f"{'=' * 60}")

    # Music
    print(f"\n  Music (RTTTL) -- {music_count} files staged")
    print(f"  Staged to: {STAGING_MUSIC}")
    for song, paths in sorted(music_matched.items()):
        print(f"    {song}: {len(paths)} file{'s' if len(paths) != 1 else ''}")
        for p in paths:
            print(f"      - {p.name}")

    # Amiibo
    print(f"\n  Amiibo (NFC) -- {amiibo_count} files staged")
    print(f"  Staged to: {STAGING_AMIIBO}")
    if amiibo_count > 200:
        print(f"  NOTE: Large collection ({amiibo_count} files) will be deployed.")

    # Tesla Sub-GHz
    print(f"\n  Tesla Sub-GHz -- {len(tesla_files)} file{'s' if len(tesla_files) != 1 else ''} found")
    print(f"  Staged to: {STAGING_SUBGHZ}")
    if tesla_files:
        for f in tesla_files:
            print(f"    - {f.name}")
    else:
        print("    (placeholder note written -- no .sub file found in vendor repos)")

    # Totals
    total = music_count + amiibo_count + len(tesla_files)
    print(f"\n{'=' * 60}")
    print(f"Total files staged: {total}")
    print(f"{'=' * 60}\n")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    """Curate RTTTL music, Amiibo NFC, and Tesla Sub-GHz into staging."""

    # -----------------------------------------------------------------------
    # Music (RTTTL)
    # -----------------------------------------------------------------------
    music_matched: dict[str, list[Path]] = {}
    music_count = 0

    if MUSIC_VENDOR.is_dir():
        print("Scanning FlipperMusicRTTTL for music files...")
        all_music = _find_music_files(MUSIC_VENDOR)
        print(f"  Found {len(all_music)} total music files in vendor repo.")

        music_matched = _match_music(all_music)
        if music_matched:
            _clean_staging(STAGING_MUSIC)
            music_count = _copy_music(music_matched, STAGING_MUSIC)
            print(f"[done]  Staged {music_count} music file(s)")
        else:
            print("[warn]  No matching music files found.")
    else:
        print(
            f"[skip]  FlipperMusicRTTTL not found at {MUSIC_VENDOR}\n"
            f"        Clone it with:\n"
            f"          git clone --depth 1 "
            f"https://github.com/neverfa11ing/FlipperMusicRTTTL.git "
            f"vendor/FlipperMusicRTTTL"
        )

    # -----------------------------------------------------------------------
    # Amiibo (NFC)
    # -----------------------------------------------------------------------
    amiibo_count = 0

    if AMIIBO_VENDOR.is_dir():
        print("\nCopying Amiibo NFC collection...")
        _clean_staging(STAGING_AMIIBO)
        amiibo_count = _copy_amiibo(AMIIBO_VENDOR, STAGING_AMIIBO)
        if amiibo_count > 200:
            print(
                f"[note]  Large Amiibo collection: {amiibo_count} files "
                f"will be deployed to the Flipper."
            )
        print(f"[done]  Staged {amiibo_count} Amiibo NFC file(s)")
    else:
        print(
            f"[skip]  FlipperAmiibo not found at {AMIIBO_VENDOR}\n"
            f"        Clone it with:\n"
            f"          git clone --depth 1 "
            f"https://github.com/Gioman101/FlipperAmiibo.git "
            f"vendor/FlipperAmiibo"
        )

    # -----------------------------------------------------------------------
    # Tesla Sub-GHz
    # -----------------------------------------------------------------------
    print("\nSearching vendor repos for Tesla charge port .sub files...")
    tesla_files = _find_tesla_sub_files()

    _clean_staging(STAGING_SUBGHZ)
    if tesla_files:
        for src in tesla_files:
            shutil.copy2(src, STAGING_SUBGHZ / src.name)
        print(f"[done]  Staged {len(tesla_files)} Tesla .sub file(s)")
    else:
        print("[info]  No Tesla .sub file found in vendor repos; writing placeholder note.")
        _write_tesla_placeholder(STAGING_SUBGHZ)

    # -----------------------------------------------------------------------
    # Summary
    # -----------------------------------------------------------------------
    _print_summary(music_matched, music_count, amiibo_count, tesla_files)


if __name__ == "__main__":
    main()
