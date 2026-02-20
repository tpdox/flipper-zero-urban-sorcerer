# Mazincea Urban Sorcerer Kit — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Transform a stock Flipper Zero "Mazincea" into a fully-loaded urban sorcerer toolkit with Momentum firmware, community apps, IR/NFC/SubGHz databases, BadUSB payloads, and an automated deploy script.

**Architecture:** A Python deploy script (`deploy.py`) downloads all required community resources (repos, FAP files, databases) into a local `vendor/` staging directory, then pushes files to the Flipper's SD card over serial using the Flipper CLI's `storage write` command. The Flipper must be running Momentum firmware (flashed manually via web updater before running the script).

**Tech Stack:** Python 3.13+, Flipper Zero serial CLI (230400 baud), ufbt (Flipper build tool), git

---

## Prerequisites (Manual Steps)

Before running the deploy script, the user must:

1. **Flash Momentum firmware:**
   - Open Chrome/Edge and go to https://momentum-fw.dev/update
   - Close qFlipper if running
   - Connect Flipper via USB
   - Click "Connect" → select the Flipper → click "Flash"
   - Wait for completion (~3-5 minutes)
   - Flipper reboots with Momentum firmware

2. **Verify Flipper is connected:**
   ```bash
   ls /dev/cu.usbmodemflip_*
   ```
   Expected: `/dev/cu.usbmodemflip_Mazincea1` (serial name may change after firmware flash)

---

### Task 1: Serial Communication Module

**Files:**
- Create: `flipper_serial.py`

**Step 1: Write the serial helper module**

This module handles all communication with the Flipper Zero over its CLI serial interface. The Flipper CLI accepts commands at 230400 baud and responds with text output terminated by `>:` prompt.

Key functions:
- `FlipperSerial.__init__(port)` — opens serial connection
- `FlipperSerial.send_command(cmd)` — sends command, reads response until prompt
- `FlipperSerial.storage_write(local_path, remote_path)` — writes a file to Flipper SD card using `storage write_chunk`
- `FlipperSerial.storage_mkdir(path)` — creates directory on Flipper
- `FlipperSerial.storage_list(path)` — lists directory contents
- `FlipperSerial.storage_stat(path)` — checks if file/dir exists
- `FlipperSerial.close()` — closes connection

The Flipper's `storage write_chunk` command works as follows:
1. Send `storage write_chunk <path> <size>\r\n`
2. Flipper responds with `Ready\r\n`
3. Send exactly `<size>` bytes of data
4. Flipper responds with `OK` or error
5. Repeat for each chunk (max chunk size: 512 bytes)

For binary files (like .fap), use `storage write_chunk` with raw bytes.
For text files, same approach.

**Step 2: Test serial connection**

```bash
python3 flipper_serial.py
```

The module should include a `__main__` block that connects, runs `device_info`, prints the firmware version, and disconnects. Expected output includes `firmware_version` showing Momentum firmware.

**Step 3: Commit**

```bash
git add flipper_serial.py
git commit -m "feat: add Flipper Zero serial communication module"
```

---

### Task 2: Resource Downloader

**Files:**
- Create: `download_resources.py`

**Step 1: Write the download/clone script**

This script downloads all required community resources into `vendor/` directory:

```
vendor/
├── Flipper-IRDB/          (git clone)
├── FlipperAmiibo/         (git clone)
├── FlipperMusicRTTTL/     (git clone)
├── badusb-payloads/       (git clone I-Am-Jakoby repo)
├── nfc-trolls/            (git clone NFC-Trolls repo)
├── tesla/                 (single .sub file download)
└── asset-packs/           (download pirate/cyberpunk pack)
```

Repos to clone:
- `https://github.com/Lucaslhm/Flipper-IRDB.git` (IR database)
- `https://github.com/Gioman101/FlipperAmiibo.git` (Amiibo NFC dumps)
- `https://github.com/neverfa11ing/FlipperMusicRTTTL.git` (music files, try also UberGuidoZ/Flipper as fallback)
- `https://github.com/I-Am-Jakoby/Flipper-Zero-BadUSB.git` (BadUSB payloads)
- `https://github.com/w0lfzk1n/Flipper-Zero-NFC-Trolls.git` (NFC prank tags)

The script should:
- Skip cloning if the repo already exists (for re-runs)
- Do a shallow clone (`--depth 1`) to save time/space
- Print progress for each repo
- Return the `vendor/` path for use by the deploy script

**Step 2: Run it**

```bash
python3 download_resources.py
```

Expected: all repos cloned into `vendor/`, total size ~500MB-1GB.

**Step 3: Commit**

```bash
git add download_resources.py
git commit -m "feat: add resource downloader for community repos"
```

---

### Task 3: IR Database Curator

**Files:**
- Create: `curate_ir.py`

**Step 1: Write the IR file curator**

This script selects the most useful IR files from the Flipper-IRDB clone and stages them in `staging/infrared/`. The IRDB is massive — we only want the most relevant brands.

Target brands per category:

**TVs:** Samsung, LG, Sony, Vizio, TCL, Hisense, Panasonic, Philips, Toshiba, Sharp
**Soundbars:** JBL, Bose, Sony, Samsung, Vizio, Yamaha, Polk, Harman_Kardon, Sonos
**ACs:** Mitsubishi, Daikin, LG, Carrier, Fujitsu, Toshiba
**Projectors:** Epson, BenQ, NEC, Optoma, ViewSonic
**Fans:** Dyson, Honeywell
**Cameras:** Canon, Nikon (if available)

The script should:
- Walk the IRDB directory tree
- Match folders/files by brand name (case-insensitive)
- Copy matching .ir files to `staging/infrared/` with `Category_Brand_Model.ir` naming
- Print a summary: N files selected, total size
- If a category folder has too many files for one brand (>10), take the ones with the most generic/universal names

**Step 2: Run it**

```bash
python3 curate_ir.py
```

Expected: `staging/infrared/` populated with curated .ir files.

**Step 3: Commit**

```bash
git add curate_ir.py
git commit -m "feat: add IR database curator for Flipper-IRDB"
```

---

### Task 4: BadUSB Payload Curator

**Files:**
- Create: `curate_badusb.py`

**Step 1: Write the BadUSB payload curator**

Selects specific payloads from the I-Am-Jakoby repo and writes custom ones to `staging/badusb/`.

Payloads to include:
1. **RickRoll.txt** — Opens browser, navigates to Rick Astley YouTube video, maximizes, sets volume to max. Target: macOS (use `open` command) with Windows fallback.
2. **FakeHackScreen.txt** — Opens browser to hackertyper.net, goes fullscreen (F11).
3. **MouseJiggle.txt** — Simulates tiny mouse movements every 30 seconds to prevent sleep.

DuckyScript format reference:
```
DELAY 500
GUI SPACE
DELAY 500
STRING Terminal
DELAY 500
ENTER
DELAY 1000
STRING open https://www.youtube.com/watch?v=dQw4w9WgXcQ
ENTER
```

The script should:
- Find the best matching payloads from the cloned repo
- Write custom macOS-optimized payloads where the repo ones are Windows-only
- Copy everything to `staging/badusb/`
- Print list of included payloads

**Step 2: Run it**

```bash
python3 curate_badusb.py
```

Expected: `staging/badusb/` populated with .txt DuckyScript payloads.

**Step 3: Commit**

```bash
git add curate_badusb.py
git commit -m "feat: add BadUSB payload curator with macOS-optimized scripts"
```

---

### Task 5: NFC Tag Generator

**Files:**
- Create: `generate_nfc.py`

**Step 1: Write the NFC tag generator**

Creates Flipper-compatible .nfc files for NDEF emulation. The Flipper NFC file format for NTAG215 emulation is:

```
Filetype: Flipper NFC device
Version: 4
Device type: NTAG215
UID: 04 XX XX XX XX XX XX
ATQA: 44 00
SAK: 00
...page data...
```

The generator should create:
1. **Instagram.nfc** — NDEF URL record pointing to user's Instagram profile
2. **WiFi_Connect.nfc** — NDEF WiFi record with user's SSID and password
3. **Contact.nfc** — NDEF vCard with user's name and phone
4. **RickRoll.nfc** — NDEF URL to Rick Astley video

The script should prompt for:
- Instagram username
- WiFi SSID and password
- Contact name and phone number

Output .nfc files to `staging/nfc/`.

Note: This is the most complex task. NDEF encoding into NTAG215 page format requires:
- NDEF message header (type, length)
- NDEF record (TNF, type, payload)
- Capability container on page 3
- NDEF data starting on page 4
- Each page is 4 bytes

If generating valid NTAG215 dumps proves too complex, fall back to creating simple text files with instructions to use the on-device NFC Maker app instead.

**Step 2: Run it**

```bash
python3 generate_nfc.py
```

Expected: `staging/nfc/` populated with .nfc files (or instruction files).

**Step 3: Commit**

```bash
git add generate_nfc.py
git commit -m "feat: add NFC tag generator for NDEF emulation"
```

---

### Task 6: Music and Amiibo Curator

**Files:**
- Create: `curate_extras.py`

**Step 1: Write the extras curator**

Selects music files and Amiibo dumps for staging:

**Music (RTTTL):**
- Mario Bros theme
- Zelda theme
- Imperial March (Star Wars)
- Tetris theme
- Never Gonna Give You Up
- Nokia ringtone
- Simpsons theme
- Take On Me

Search the cloned RTTTL repo for files matching these names. Copy to `staging/music_player/`.

**Amiibo:**
- Copy the entire Amiibo collection to `staging/nfc/amiibo/`
- The files are already in Flipper .nfc format

**Tesla Sub-GHz:**
- The Tesla charge port .sub file. This is a well-known signal at 315 MHz.
- Search community repos or create from known parameters. Copy to `staging/subghz/`.
- Note: verify this file exists in community repos before including.

**Step 2: Run it**

```bash
python3 curate_extras.py
```

Expected: `staging/music_player/`, `staging/nfc/amiibo/`, and `staging/subghz/` populated.

**Step 3: Commit**

```bash
git add curate_extras.py
git commit -m "feat: add music, Amiibo, and Sub-GHz file curator"
```

---

### Task 7: Community FAP App Downloader

**Files:**
- Create: `download_apps.py`

**Step 1: Write the FAP downloader**

Downloads pre-built .fap files for community apps not bundled with Momentum firmware.

Strategy:
1. For apps available on the Flipper App Hub (lab.flipper.net), use ufbt to install them
2. For GitHub-only apps, clone the repo and build with ufbt
3. Fall back to downloading pre-built .fap from GitHub releases

Apps to install:
- Metroflip
- FlipperNested
- Mfkey32 (FlipperMfkey)
- ProtoView
- TPMS
- XRemote
- Cross Remote
- Ocarina
- Mouse Jiggler

The `ufbt` tool can install apps from the catalog:
```bash
ufbt install <app_id>
```

Or build from source:
```bash
cd <cloned_app_repo>
ufbt build
# produces dist/<app_name>.fap
```

Stage built .fap files to `staging/apps/<category>/` matching Flipper's app directory structure:
- `staging/apps/NFC/` for NFC apps
- `staging/apps/Sub-GHz/` for Sub-GHz apps
- `staging/apps/Infrared/` for IR apps
- `staging/apps/GPIO/` for GPIO apps
- `staging/apps/Games/` for game apps

**Step 2: Run it**

```bash
python3 download_apps.py
```

Expected: `staging/apps/` populated with .fap files.

**Step 3: Commit**

```bash
git add download_apps.py
git commit -m "feat: add community FAP app downloader"
```

---

### Task 8: Main Deploy Script

**Files:**
- Create: `deploy.py`

**Step 1: Write the main deploy orchestrator**

This is the top-level script that:
1. Runs all download/curate scripts to populate `staging/`
2. Connects to Flipper over serial
3. Creates required directories on Flipper SD card
4. Pushes all staged files to the correct locations
5. Verifies deployment

File mapping (staging → Flipper):
```
staging/infrared/*         → /ext/infrared/
staging/badusb/*           → /ext/badusb/
staging/nfc/*.nfc          → /ext/nfc/
staging/nfc/amiibo/*       → /ext/nfc/amiibo/
staging/subghz/*           → /ext/subghz/
staging/music_player/*     → /ext/apps_data/music_player/
staging/apps/**/*.fap      → /ext/apps/<category>/
```

The deploy script should:
- Accept `--skip-download` flag to skip re-downloading (use existing staging/)
- Accept `--port` flag to specify serial port (default: auto-detect `/dev/cu.usbmodemflip_*`)
- Show progress bar / file count during upload
- Handle serial timeouts gracefully
- Print a summary at the end (files uploaded, categories, total size)

**Step 2: Run deploy (dry-run first)**

```bash
python3 deploy.py --dry-run
```

Expected: shows what would be uploaded without actually writing.

**Step 3: Run deploy for real**

```bash
python3 deploy.py
```

Expected: all files pushed to Flipper. Summary printed.

**Step 4: Commit**

```bash
git add deploy.py
git commit -m "feat: add main deploy script for Flipper Zero loadout"
```

---

### Task 9: Verification Script

**Files:**
- Create: `verify.py`

**Step 1: Write the verification script**

Connects to Flipper and verifies the deployment:

1. Check firmware version (should be Momentum)
2. List `/ext/infrared/` — verify IR files present
3. List `/ext/badusb/` — verify payload files present
4. List `/ext/nfc/` — verify NFC tags present
5. List `/ext/subghz/` — verify Sub-GHz files present
6. List `/ext/apps/` recursively — verify .fap apps present
7. List `/ext/apps_data/music_player/` — verify music files present

Print a checklist-style report:
```
[OK] Firmware: Momentum mntm-012
[OK] IR Database: 47 files
[OK] BadUSB Payloads: 3 files
[OK] NFC Tags: 4 files + 612 Amiibo
[OK] Sub-GHz: 1 file
[OK] Apps: 9 FAP files
[OK] Music: 8 RTTTL files
```

**Step 2: Run verification**

```bash
python3 verify.py
```

Expected: all checks pass.

**Step 3: Commit**

```bash
git add verify.py
git commit -m "feat: add deployment verification script"
```

---

### Task 10: Project Documentation

**Files:**
- Create: `README.md` (only because this is the project root and it needs usage instructions)

**Step 1: Write README with setup and usage instructions**

Content:
- Project name and one-line description
- Prerequisites (Momentum firmware, Python 3.13+, USB connection)
- Quick start (3 commands: clone, flash firmware, run deploy)
- What gets installed (brief list of trick categories)
- Re-deployment instructions
- Troubleshooting (serial port not found, permission errors)

**Step 2: Commit all**

```bash
git add README.md
git commit -m "docs: add README with setup and usage instructions"
```

---

## Implementation Notes

- **Serial chunk size:** The Flipper's `storage write_chunk` has a 512-byte max chunk size. Large files (like .fap apps at ~50KB) need many chunks. Include a progress indicator.
- **Serial port detection:** After Momentum firmware flash, the serial port name may change from `flip_Mazincea1`. Auto-detect by globbing `/dev/cu.usbmodemflip_*`.
- **Binary files:** .fap and .nfc files are binary. Use `storage write_chunk` with raw bytes, not text mode.
- **Rate limiting:** Add small delays (50ms) between serial commands to avoid overwhelming the Flipper's CLI parser.
- **Amiibo size:** The full Amiibo collection is large (600+ files). Consider offering a "lite" mode that only includes the most popular ones (Zelda, Mario, Smash Bros, Animal Crossing).
- **ufbt SDK:** ufbt is installed and working. The SDK targets firmware API 72.1 (stock). For Momentum-compatible builds, may need to update the SDK target: `ufbt update --channel=dev`.
