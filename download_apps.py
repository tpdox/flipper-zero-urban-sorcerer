#!/usr/bin/env python3
"""Community FAP App Downloader for Flipper Zero.

Downloads pre-built .fap files from the Flipper App Catalog API and stages
them into category-specific directories under staging/apps/.

The Flipper App Catalog at https://catalog.flipperzero.one/api/v0/ provides
pre-built .fap binaries keyed by firmware API version and target.

Because Momentum firmware may use a different API version than official
firmware, the script tries the user's API version first and falls back to
the latest available build.  A compatibility note is printed when the
downloaded build was compiled for a different API version.

Usage:
    python3 download_apps.py
"""

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).resolve().parent
STAGING_DIR = SCRIPT_DIR / "staging" / "apps"

# Flipper App Catalog base URL.
CATALOG_API = "https://catalog.flipperzero.one/api/v0"

# Hardware target (all Flipper Zeros are f7).
TARGET = "f7"

# API versions to try, in order of preference.
# 72.1 = Momentum/Unleashed (based on official 0.105.x)
# 87.1 = Latest official firmware (1.4.1-rc)
API_VERSIONS_TO_TRY = ["72.1", "87.1"]

# Category name -> catalog category ID mapping (from the catalog API).
CATEGORY_IDS = {
    "Sub-GHz":   "64971d0f6617ba37a4bc79b3",
    "NFC":       "64971d10be1a76c06747de26",
    "Infrared":  "64971d106617ba37a4bc79b6",
    "USB":       "64971d11be1a76c06747de2c",
    "Games":     "64971d11be1a76c06747de2f",
    "Media":     "64971d116617ba37a4bc79bc",
    "Tools":     "64971d11577d519190ede5c5",
    "GPIO":      "64971d106617ba37a4bc79b9",
    "Bluetooth": "64a69817effe1f448a4053b4",
}

# Reverse lookup: category ID -> name.
CATEGORY_NAMES = {v: k for k, v in CATEGORY_IDS.items()}

# Apps to download.
# Each entry: (catalog_alias, display_name, staging_subdirectory)
# The staging_subdirectory overrides the catalog category when we want a
# specific layout.
APPS = [
    ("metroflip",       "Metroflip",       "NFC"),
    ("protoview",       "ProtoView",       "Sub-GHz"),
    ("tpms",            "TPMS Reader",     "Sub-GHz"),
    ("flipper_xremote", "XRemote",         "Infrared"),
    ("xremote",         "Cross Remote",    "Infrared"),
    ("ocarina",         "Ocarina",         "Media"),
    ("mouse_jiggler",   "Mouse Jiggler",   "USB"),
]

# GitHub release fallbacks for apps that may not be in the catalog or whose
# catalog builds are incompatible.
# Each entry: (catalog_alias, GitHub owner/repo, asset_name_pattern)
GITHUB_FALLBACKS = {
    "metroflip":       ("luu176/Metroflip",              "metroflip.fap"),
    "flipper_xremote": ("kala13x/flipper-xremote",       ".fap"),
    "tpms":            ("wosk/flipperzero-tpms",         ".fap"),
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def api_get_json(path: str) -> dict | list:
    """GET a JSON response from the Flipper App Catalog API."""
    url = f"{CATALOG_API}/{path}"
    req = urllib.request.Request(url)
    req.add_header("Accept", "application/json")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def fetch_app_metadata(alias: str) -> dict | None:
    """Fetch application metadata from the catalog.

    Returns the full app dict or None on failure.
    """
    try:
        return api_get_json(f"0/application/{alias}")
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None
        raise


def download_fap_from_catalog(
    version_id: str,
    api_version: str,
) -> bytes | None:
    """Download a .fap binary from the catalog for a specific API version.

    Returns the raw bytes or None if no compatible build exists.
    """
    url = (
        f"{CATALOG_API}/application/version/{version_id}"
        f"/build/compatible?target={TARGET}&api={api_version}"
    )
    try:
        with urllib.request.urlopen(url, timeout=60) as resp:
            return resp.read()
    except urllib.error.HTTPError:
        return None


def download_fap_from_github(
    repo: str,
    asset_pattern: str,
) -> tuple[bytes, str] | None:
    """Download the latest .fap asset from a GitHub release.

    Parameters
    ----------
    repo : str
        GitHub owner/repo string, e.g. ``luu176/Metroflip``.
    asset_pattern : str
        Substring that the asset filename must contain (e.g. ``.fap``).

    Returns
    -------
    tuple[bytes, str] | None
        A ``(data, filename)`` tuple, or ``None`` if no matching asset was
        found.
    """
    api_url = f"https://api.github.com/repos/{repo}/releases"
    req = urllib.request.Request(api_url)
    req.add_header("Accept", "application/vnd.github+json")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            releases = json.loads(resp.read())
    except urllib.error.HTTPError:
        return None

    if not releases:
        return None

    # Walk releases newest-first looking for a .fap asset.
    for release in releases:
        for asset in release.get("assets", []):
            name = asset["name"]
            if asset_pattern in name and name.endswith(".fap"):
                download_url = asset["browser_download_url"]
                try:
                    with urllib.request.urlopen(download_url, timeout=60) as r:
                        return r.read(), name
                except urllib.error.HTTPError:
                    continue

    return None


# ---------------------------------------------------------------------------
# Main logic
# ---------------------------------------------------------------------------

def download_apps(
    staging_dir: Path | None = None,
    api_versions: list[str] | None = None,
) -> dict[str, str]:
    """Download all configured community apps.

    Parameters
    ----------
    staging_dir : Path | None
        Where to stage downloaded .fap files.  Defaults to
        ``staging/apps/`` next to this script.
    api_versions : list[str] | None
        Firmware API versions to try, in preference order.

    Returns
    -------
    dict[str, str]
        Mapping of app alias to result status string.
    """
    if staging_dir is None:
        staging_dir = STAGING_DIR
    staging_dir = Path(staging_dir).resolve()

    if api_versions is None:
        api_versions = API_VERSIONS_TO_TRY

    results: dict[str, str] = {}

    print(f"Staging directory: {staging_dir}")
    print(f"Target: {TARGET}")
    print(f"API versions to try: {', '.join(api_versions)}")
    print(f"Apps to download: {len(APPS)}")
    print(f"{'=' * 60}\n")

    for alias, display_name, category in APPS:
        print(f"[{display_name}] ({alias})")

        # Determine output directory and filename.
        out_dir = staging_dir / category
        out_dir.mkdir(parents=True, exist_ok=True)
        fap_path = out_dir / f"{alias}.fap"

        # Skip if already downloaded (idempotent).
        if fap_path.exists():
            size = fap_path.stat().st_size
            print(f"  [skip] Already exists: {fap_path} ({size:,} bytes)")
            results[alias] = "skipped (already exists)"
            print()
            continue

        # ------------------------------------------------------------------
        # Strategy 1: Flipper App Catalog
        # ------------------------------------------------------------------
        downloaded = False
        meta = fetch_app_metadata(alias)

        if meta is not None:
            version_id = meta["current_version"]["_id"]
            version_str = meta["current_version"].get("version", "?")
            build_info = meta["current_version"].get("current_build", {})
            build_api = build_info.get("sdk", {}).get("api", "?")

            print(f"  Catalog: v{version_str}, build API {build_api}")

            for api_ver in api_versions:
                print(f"  Trying API {api_ver}...", end=" ")
                data = download_fap_from_catalog(version_id, api_ver)
                if data is not None:
                    fap_path.write_bytes(data)
                    compat_note = ""
                    if api_ver != api_versions[0]:
                        compat_note = (
                            f" (built for API {api_ver}; "
                            f"your firmware uses {api_versions[0]} -- "
                            f"may need firmware update)"
                        )
                    print(f"OK ({len(data):,} bytes){compat_note}")
                    results[alias] = (
                        f"catalog v{version_str} api={api_ver} "
                        f"({len(data):,} bytes)"
                    )
                    downloaded = True
                    break
                else:
                    print("not available")
        else:
            print("  Catalog: not found")

        # ------------------------------------------------------------------
        # Strategy 2: GitHub releases (fallback)
        # ------------------------------------------------------------------
        if not downloaded and alias in GITHUB_FALLBACKS:
            repo, pattern = GITHUB_FALLBACKS[alias]
            print(f"  Trying GitHub releases: {repo}")
            result = download_fap_from_github(repo, pattern)
            if result is not None:
                data, filename = result
                fap_path.write_bytes(data)
                print(
                    f"  [github] Downloaded {filename} "
                    f"({len(data):,} bytes)"
                )
                print(
                    "  WARNING: GitHub release may not match your "
                    "firmware API version"
                )
                results[alias] = (
                    f"github {repo} ({len(data):,} bytes)"
                )
                downloaded = True
            else:
                print("  [github] No .fap asset found in releases")

        # ------------------------------------------------------------------
        # Final status
        # ------------------------------------------------------------------
        if not downloaded:
            print("  [FAIL] Could not download from any source")
            results[alias] = "FAILED"
        else:
            print(f"  -> {fap_path}")

        print()

    return results


def print_summary(results: dict[str, str]) -> None:
    """Print a human-readable summary table."""
    print(f"{'=' * 60}")
    print("Download Summary")
    print(f"{'=' * 60}")

    succeeded = 0
    failed = 0
    skipped = 0

    for alias, display_name, _category in APPS:
        status = results.get(alias, "unknown")
        if "FAILED" in status:
            marker = "FAIL"
            failed += 1
        elif "skipped" in status.lower():
            marker = "SKIP"
            skipped += 1
        else:
            marker = " OK "
            succeeded += 1
        print(f"  [{marker}] {display_name:<20s} {status}")

    print(f"\n  Total: {succeeded} downloaded, {skipped} skipped, {failed} failed")
    print(f"  Staged to: {STAGING_DIR}")

    if any("api=" in s and "72.1" not in s for s in results.values()):
        print()
        print(
            "  NOTE: Some apps were downloaded for a different API version "
            "than your firmware."
        )
        print(
            "  If apps crash or show 'API mismatch', you may need to update "
            "your Momentum firmware"
        )
        print("  or build the apps from source with ufbt against your SDK.")

    print(f"{'=' * 60}")


def main() -> None:
    """Entry point when running as a standalone script."""
    results = download_apps()
    print_summary(results)

    # Exit with error code if any app failed completely.
    if any(v == "FAILED" for v in results.values()):
        sys.exit(1)


if __name__ == "__main__":
    main()
