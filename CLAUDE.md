# Flipper Zero Urban Sorcerer Kit — Claude Code Playbook

> **Point Claude Code at this repo and say: "Set up my Flipper Zero"**
>
> This file tells Claude exactly how to deploy a fully-loaded toolkit to your Flipper Zero.
> No manual steps required beyond flashing firmware and plugging in USB.

## What This Project Does

Transforms a stock Flipper Zero into an urban sorcery toolkit by downloading community resources, curating the best files, and pushing everything over USB serial — all in one command.

**Final loadout:** 229 IR remotes, 3 BadUSB payloads, NFC tags, 100 Amiibo dumps, 31 music files, 7 community apps.

## Prerequisites

Before starting, the user must:

1. **Own a Flipper Zero** connected via USB
2. **Flash Momentum firmware** — guide them to https://momentum-fw.dev/update in Chrome/Edge (NOT Safari, NOT qFlipper on Apple Silicon)
3. **Close qFlipper** and any other app holding the serial port
4. **Have Python 3.10+** and **Git** installed

## How to Deploy

The entire deploy is a single command:

```bash
python3 deploy.py
```

This runs all sub-scripts in order:
1. `download_resources.py` — clones community repos (Flipper-IRDB, BadUSB, Amiibo) into `vendor/`
2. `curate_ir.py` — selects 229 useful IR remotes from thousands in Flipper-IRDB
3. `curate_badusb.py` — stages 3 macOS-optimized BadUSB payloads
4. `generate_nfc.py` — generates NDEF-formatted NTAG215 NFC tag files
5. `curate_extras.py` — stages music files, Amiibo subset, Sub-GHz signals
6. `download_apps.py` — fetches .fap app binaries from Flipper App Catalog
7. Connects to the Flipper over serial and uploads all 375+ files
8. `verify.py` can be run after to confirm the deploy

## Customization Points

When a user wants to personalize their setup, these are the files to edit:

### NFC Tags (`generate_nfc.py`)
The `TAGS` list near the top defines what NFC tags get created. Each entry is a dict with `name`, `uri_code`, and `uri_string`. Edit these for the user's actual info:

```python
TAGS = [
    {"name": "Instagram", "uri_code": 0x03, "uri_string": "instagram.com/THEIR_USERNAME"},
    {"name": "WiFi_Setup", "uri_code": 0x00, "uri_string": "wifi://..."},
    {"name": "RickRoll", "uri_code": 0x04, "uri_string": "youtube.com/watch?v=dQw4w9WgXcQ"},
]
```

URI prefix codes: `0x00` = no prefix, `0x01` = `http://www.`, `0x02` = `https://www.`, `0x03` = `https://`, `0x04` = `http://`

### BadUSB Payloads (`curate_badusb.py`)
The `CUSTOM_PAYLOADS` dict contains DuckyScript payloads. Current payloads are macOS-optimized (use `GUI SPACE` for Spotlight). For Windows targets, replace `GUI SPACE` with `GUI r` for Run dialog.

### IR Remote Selection (`curate_ir.py`)
The `BRAND_PRIORITY` dict controls which brands get included and how many files per brand. Add or remove brands as needed.

### Amiibo Selection (`deploy.py`)
The `AMIIBO_POPULAR_SERIES` list controls which Amiibo franchises get uploaded. The full collection is 953 files; the default selects 100 from popular series to keep serial upload under 10 minutes.

### Apps (`download_apps.py`)
The `APPS` list defines which .fap apps to download from the Flipper App Catalog. Each entry has an `app_id` and `alias`. Add new apps by finding their ID on the catalog.

## Serial Communication Details

`flipper_serial.py` handles all device communication. Key technical notes:

- **Baud rate:** 230400, 8N1, raw mode via termios (no pyserial dependency)
- **Port auto-detection:** scans `/dev/cu.usbmodemflip_*` (macOS) and `/dev/ttyACM*` (Linux)
- **Line endings:** Commands use `\r\n` EXCEPT `storage write_chunk` which uses `\r` only (the Flipper CLI triggers on `\r` but leaves `\n` in the input buffer, corrupting chunked writes)
- **ANSI stripping:** Momentum firmware echoes VT100 escape codes (`\x1b[4h`/`\x1b[4l`); these are stripped before response parsing
- **Chunked writes:** Files are uploaded in 512-byte chunks via `storage write_chunk`
- **Retry logic:** Failed uploads get one automatic retry with serial buffer recovery

## Troubleshooting

| Problem | Cause | Fix |
|---------|-------|-----|
| `OSError: Resource busy` | qFlipper or another app holds the serial port | Close qFlipper, Momentum web updater, any terminal with `screen`/`minicom` |
| `No Flipper Zero found` | Device not connected or on lock screen | Plug in USB, unlock the Flipper, check `ls /dev/cu.usbmodemflip_*` |
| `could not find command 'estorage'` | Line ending bug (should be fixed) | Verify `flipper_serial.py` uses `\r` not `\r\n` for write_chunk commands |
| `API mismatch` on an app | App compiled for different firmware version | Update Momentum firmware, re-run `python3 download_apps.py` |
| Uploads timing out | Flipper busy or serial buffer full | Unplug/replug USB, restart Flipper, try again |

## Project Structure

```
deploy.py              # Main orchestrator — run this
verify.py              # Post-deploy verification
flipper_serial.py      # Serial communication (raw termios, no dependencies)
download_resources.py  # Clone community repos into vendor/
download_apps.py       # Fetch .fap binaries from Flipper App Catalog API
curate_ir.py           # Select IR remotes from Flipper-IRDB
curate_badusb.py       # Stage BadUSB DuckyScript payloads
generate_nfc.py        # Generate NTAG215 NFC tag files from scratch
curate_extras.py       # Stage music, Amiibo, Sub-GHz files
vendor/                # Community repos (gitignored, re-cloneable)
staging/               # Curated files ready for upload (gitignored, regenerated)
```

## For Claude: Step-by-Step Guide for New Users

When someone says "set up my Flipper" or "deploy to my Flipper", follow this sequence:

1. **Check prerequisites:** Python 3.10+, Git, Flipper connected via USB, Momentum firmware flashed
2. **Ask about customization:** Do they want custom NFC tags? (Instagram handle, WiFi network, etc.) If yes, edit `generate_nfc.py` TAGS list before deploying
3. **Close port conflicts:** Have them close qFlipper or any serial monitors
4. **Run deploy:** `python3 deploy.py`
5. **Verify:** `python3 verify.py`
6. **Walk through the toolkit:** Show them how to access each feature on the Flipper (see the Trick Arsenal table in README.md)

If the deploy fails mid-upload, it's safe to re-run with `--skip-download` to avoid re-cloning repos:
```bash
python3 deploy.py --skip-download
```

## For Claude: How to Extend the Toolkit

If a user wants to add new capabilities:

- **New IR remote:** Add the brand to `BRAND_PRIORITY` in `curate_ir.py`, or drop a `.ir` file directly in `staging/infrared/`
- **New BadUSB payload:** Add an entry to `CUSTOM_PAYLOADS` in `curate_badusb.py`
- **New NFC tag:** Add an entry to `TAGS` in `generate_nfc.py`
- **New app:** Find the app ID on https://catalog.flipperzero.one, add to `APPS` in `download_apps.py`
- **New Sub-GHz signal:** Place `.sub` files in `staging/subghz/`
- **New music:** Place `.fmf` RTTTL files in `staging/music_player/`

After changes, re-run `python3 deploy.py --skip-download` to push updates.
