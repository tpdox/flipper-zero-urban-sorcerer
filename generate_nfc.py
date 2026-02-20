#!/usr/bin/env python3
"""Generate Flipper-compatible .nfc files for NDEF NFC tag emulation.

Creates NTAG215 tag dumps containing NDEF URI records that the Flipper Zero
can emulate.  Each tag gets a random 7-byte UID (NXP manufacturer prefix 04)
and a properly structured NDEF message.
"""

import os
import random
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths (resolved relative to this script so cwd doesn't matter)
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent
STAGING_DIR = SCRIPT_DIR / "staging" / "nfc"

# ---------------------------------------------------------------------------
# NTAG215 constants
# ---------------------------------------------------------------------------
NTAG215_PAGES = 135          # 135 pages of 4 bytes each (540 bytes total)
BYTES_PER_PAGE = 4
CAPABILITY_CONTAINER = [0xE1, 0x10, 0x3F, 0x00]  # NDEF magic, v1.0, 504 bytes, r/w

# URI prefix codes per NFC Forum URI RTD
URI_PREFIXES: dict[int, str] = {
    0x00: "",
    0x01: "http://www.",
    0x02: "https://www.",
    0x03: "http://",
    0x04: "https://",
}

# ---------------------------------------------------------------------------
# Tags to generate: (filename, URL)
# ---------------------------------------------------------------------------
TAGS: list[tuple[str, str]] = [
    ("Instagram.nfc",   "https://www.instagram.com/yourusername"),
    ("WiFi_Setup.nfc",  "https://wifi-qr.com"),
    ("Contact.nfc",     "https://linktr.ee/yourusername"),
    ("RickRoll.nfc",    "https://www.youtube.com/watch?v=dQw4w9WgXcQ"),
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _random_uid() -> list[int]:
    """Generate a random 7-byte UID starting with 04 (NXP manufacturer)."""
    return [0x04] + [random.randint(0x00, 0xFF) for _ in range(6)]


def _match_uri_prefix(url: str) -> tuple[int, str]:
    """Find the longest matching URI prefix and return (code, remainder).

    The NFC Forum URI Record Type Definition encodes common URL prefixes as
    a single byte to save space.  We try the longest prefixes first.
    """
    # Sort by longest prefix first so we match greedily.
    for code in (0x02, 0x01, 0x04, 0x03):
        prefix = URI_PREFIXES[code]
        if url.startswith(prefix):
            return code, url[len(prefix):]
    return 0x00, url


def _build_ndef_uri_message(url: str) -> list[int]:
    """Build a complete NDEF message (TLV-wrapped) for a URI record.

    Returns the bytes that go into the user data area (pages 4+), including:
      - NDEF Message TLV  (type=0x03, length, payload)
      - Terminator TLV    (0xFE)
    """
    prefix_code, uri_remainder = _match_uri_prefix(url)
    uri_bytes = list(uri_remainder.encode("utf-8"))

    # NDEF record: header D1 (MB=1, ME=1, SR=1, TNF=001 well-known)
    #   type length = 1, payload length, type = 'U' (0x55)
    payload = [prefix_code] + uri_bytes
    payload_length = len(payload)

    ndef_record = [
        0xD1,                  # Record header: MB|ME|SR|TNF=well-known
        0x01,                  # Type length = 1
        payload_length,        # Payload length (short record, 1 byte)
        0x55,                  # Type = "U" (URI)
    ] + payload

    ndef_message_length = len(ndef_record)

    # TLV wrapper: type=0x03 (NDEF Message), length, data
    if ndef_message_length < 0xFF:
        tlv = [0x03, ndef_message_length] + ndef_record
    else:
        # 3-byte length format for messages >= 255 bytes
        tlv = [0x03, 0xFF,
               (ndef_message_length >> 8) & 0xFF,
               ndef_message_length & 0xFF] + ndef_record

    # Terminator TLV
    tlv.append(0xFE)

    return tlv


def _build_ntag215_pages(uid: list[int], url: str) -> list[list[int]]:
    """Build all 135 pages of an NTAG215 tag with the given UID and URL.

    Pages 0-2:   UID and internal data
    Page 3:      Capability container
    Pages 4-129: User data (NDEF message, zero-padded)
    Pages 130-134: Dynamic lock bytes and configuration
    """
    pages: list[list[int]] = []

    # --- Pages 0-2: UID and internal bytes ---
    # For 7-byte UID [04 AA BB CC DD EE FF]:
    #   Page 0: 04 AA BB (BCC0 = 04 ^ AA ^ BB ^ 0x88)
    #   Page 1: CC DD EE FF  (wait, actually for NTAG215 7-byte UID layout):
    # The real NTAG215 memory layout for a 7-byte UID:
    #   Page 0: UID0 UID1 UID2 BCC0   (BCC0 = 0x88 ^ UID0 ^ UID1 ^ UID2)
    #   Page 1: UID3 UID4 UID5 UID6
    #   Page 2: BCC1 Internal LockByte0 LockByte1
    # where BCC1 = UID3 ^ UID4 ^ UID5 ^ UID6

    bcc0 = 0x88 ^ uid[0] ^ uid[1] ^ uid[2]
    bcc1 = uid[3] ^ uid[4] ^ uid[5] ^ uid[6]

    pages.append([uid[0], uid[1], uid[2], bcc0])       # Page 0
    pages.append([uid[3], uid[4], uid[5], uid[6]])      # Page 1
    pages.append([bcc1, 0x48, 0x00, 0x00])              # Page 2 (internal=0x48, locks=0)

    # --- Page 3: Capability Container ---
    pages.append(list(CAPABILITY_CONTAINER))

    # --- Pages 4+: NDEF data ---
    ndef_data = _build_ndef_uri_message(url)

    # User data area is pages 4-129 (126 pages = 504 bytes)
    user_area_size = 126 * BYTES_PER_PAGE
    # Pad NDEF data to fill the full user area.
    ndef_data.extend([0x00] * (user_area_size - len(ndef_data)))

    for i in range(0, user_area_size, BYTES_PER_PAGE):
        pages.append(ndef_data[i:i + BYTES_PER_PAGE])

    # --- Pages 130-134: Dynamic lock bytes and configuration ---
    pages.append([0x01, 0x00, 0x0F, 0xBD])  # Page 130: dynamic lock
    pages.append([0x00, 0x00, 0x00, 0x04])   # Page 131: RFUI
    pages.append([0x5F, 0x00, 0x00, 0x00])   # Page 132: CFG0 (MIRROR_CONF, AUTH0=0x5F)
    pages.append([0x00, 0x00, 0x00, 0x00])   # Page 133: CFG1
    pages.append([0x00, 0x00, 0x00, 0x00])   # Page 134: PWD (all zeros)

    assert len(pages) == NTAG215_PAGES, f"Expected {NTAG215_PAGES} pages, got {len(pages)}"
    return pages


def _format_nfc_file(uid: list[int], pages: list[list[int]]) -> str:
    """Format pages into the Flipper .nfc file format string."""
    uid_str = " ".join(f"{b:02X}" for b in uid)
    sig_str = " ".join(["00"] * 32)
    mifare_ver = "00 04 04 02 01 00 11 03"

    lines = [
        "Filetype: Flipper NFC device",
        "Version: 4",
        "Device type: NTAG215",
        f"UID: {uid_str}",
        "ATQA: 44 00",
        "SAK: 00",
        f"Signature: {sig_str}",
        f"Mifare version: {mifare_ver}",
        "Counter 0: 0",
        "Tearing 0: 00",
        "Counter 1: 0",
        "Tearing 1: 00",
        "Counter 2: 0",
        "Tearing 2: 00",
        f"Pages total: {NTAG215_PAGES}",
    ]

    for i, page in enumerate(pages):
        page_str = " ".join(f"{b:02X}" for b in page)
        lines.append(f"Page {i}: {page_str}")

    return "\n".join(lines) + "\n"


def _generate_tag(filename: str, url: str, staging: Path) -> None:
    """Generate a single .nfc file in the staging directory."""
    uid = _random_uid()
    pages = _build_ntag215_pages(uid, url)
    content = _format_nfc_file(uid, pages)

    dest = staging / filename
    dest.write_text(content)
    print(f"  [done]  {filename:20s}  UID={' '.join(f'{b:02X}' for b in uid)}  URL={url}")


def _print_summary(staging: Path, count: int) -> None:
    """Print a summary of generated files."""
    print(f"\n{'=' * 60}")
    print(f"NFC Tag Generation Summary")
    print(f"{'=' * 60}")
    print(f"Staging directory : {staging}")
    print(f"Tags generated    : {count}")
    print(f"Tag type          : NTAG215 (135 pages)")
    print(f"{'=' * 60}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    """Generate Flipper-compatible NTAG215 .nfc files into staging/nfc/."""
    print("Generating NFC tag files ...")

    STAGING_DIR.mkdir(parents=True, exist_ok=True)

    count = 0
    for filename, url in TAGS:
        _generate_tag(filename, url, STAGING_DIR)
        count += 1

    _print_summary(STAGING_DIR, count)


if __name__ == "__main__":
    main()
