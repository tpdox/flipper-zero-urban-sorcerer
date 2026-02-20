# Mazincea Urban Sorcerer Kit

Transform a stock Flipper Zero into a fully-loaded urban sorcery toolkit.

## What's Inside

The deploy script downloads, curates, and pushes the following to your Flipper's SD card:

- **Momentum firmware** -- manual flash step unlocks extended Sub-GHz, rolling codes, BLE spam, BadKB over Bluetooth, and 40+ bundled apps
- **229+ IR remotes** -- TVs (Samsung, LG, Sony, Vizio, TCL, Hisense, Panasonic, Philips), soundbars (JBL, Bose, Yamaha), ACs (Mitsubishi, Daikin, LG), projectors (Epson, BenQ), and fans (Dyson, Honeywell)
- **BadUSB payloads** -- Rick Roll (full-volume YouTube), Fake Hack Screen (hackertyper.net fullscreen), Mouse Jiggler (prevent sleep)
- **NFC tags** -- Instagram profile tap, WiFi auto-connect, Rick Roll link
- **953 Amiibo NFC dumps** -- full NTAG215 collection across all franchises
- **31 RTTTL music files** -- Mario, Zelda, Imperial March, Tetris, Rick Roll, Nokia, Simpsons, Take On Me
- **7 community apps** -- Metroflip, ProtoView, TPMS Reader, XRemote, Cross Remote, Ocarina, Mouse Jiggler
- **Tesla charge port signal** -- Sub-GHz open command

## Prerequisites

- **Flipper Zero** with [Momentum firmware](https://momentum-fw.dev/update) installed
- **Python 3.13+**
- **USB connection** to the Flipper (serial port `/dev/cu.usbmodemflip_*`)
- **Git**

## Quick Start

```bash
git clone <repo-url>
cd flipper

# Flash Momentum firmware first (use Chrome/Edge, not qFlipper):
# https://momentum-fw.dev/update

python3 deploy.py
```

## Usage

```bash
python3 deploy.py                 # Full deploy: download, curate, and upload everything
python3 deploy.py --skip-download # Redeploy from existing staging/ without re-downloading
python3 deploy.py --dry-run       # Preview what would be uploaded (no writes)
python3 verify.py                 # Verify deployment on the connected Flipper
```

## The Trick Arsenal

| Trick | Category | How to Access on Flipper |
|-------|----------|------------------------|
| TV power off (any brand) | Infrared | Infrared > Browse > select brand file > Power |
| Soundbar volume crank | Infrared | Infrared > Browse > select soundbar file > Vol_up |
| AC blast / shutoff | Infrared | Infrared > Browse > select AC file > Power |
| Projector kill | Infrared | Infrared > Browse > select projector file > Power |
| Rick Roll (USB) | BadUSB | Bad USB > RickRoll_macOS.txt > Run |
| Fake Hack Screen (USB) | BadUSB | Bad USB > FakeHackScreen_macOS.txt > Run |
| Mouse Jiggler (USB) | BadUSB | Bad USB > MouseJiggle.txt > Run |
| Instagram NFC tap | NFC | NFC > Saved > Instagram > Emulate |
| WiFi auto-connect tap | NFC | NFC > Saved > WiFi_Setup > Emulate |
| Rick Roll NFC tap | NFC | NFC > Saved > RickRoll > Emulate |
| Amiibo emulation | NFC | NFC > Saved > amiibo > pick character > Emulate |
| Tesla charge port open | Sub-GHz | Sub-GHz > Saved > Tesla file > Send |
| Play Mario theme | Music Player | Apps > Media > Music Player > select file |
| Transit card read | Apps | Apps > NFC > Metroflip |
| Sub-GHz signal decode | Apps | Apps > Sub-GHz > ProtoView |
| Tire pressure monitor | Apps | Apps > Sub-GHz > TPMS Reader |
| Advanced IR remote | Apps | Apps > Infrared > XRemote |
| IR + Sub-GHz macros | Apps | Apps > Infrared > Cross Remote |
| Zelda Ocarina | Apps | Apps > Media > Ocarina |

## Troubleshooting

**Serial port not found**

The deploy script auto-detects the Flipper at `/dev/cu.usbmodemflip_*`. If no port is found:
1. Make sure the Flipper is connected via USB and unlocked (not on the lock screen).
2. Close qFlipper -- it holds an exclusive lock on the serial port.
3. Check manually: `ls /dev/cu.usbmodemflip_*`
4. If the port name changed after firmware flash, pass it explicitly: `python3 deploy.py --port /dev/cu.usbmodemflip_YourName1`

**Permission errors on macOS**

If you get "Permission denied" on the serial port:
```bash
# Add your user to the dialout group (may require logout/login):
sudo dseditgroup -o edit -a $(whoami) -t user dialout

# Or run with sudo (not recommended for regular use):
sudo python3 deploy.py
```

**API version mismatch for apps**

Community .fap apps are compiled against a specific firmware API version. If an app crashes or shows "API mismatch" on launch:
1. Update Momentum firmware to the latest version at https://momentum-fw.dev/update
2. Re-run the app downloader: `python3 download_apps.py`
3. If the issue persists, the app may need to be rebuilt from source with `ufbt` against your firmware's SDK version.

## Project Structure

```
flipper/
  deploy.py              # Main deploy orchestrator
  verify.py              # Post-deploy verification
  download_resources.py  # Clone community repos into vendor/
  download_apps.py       # Fetch .fap binaries from Flipper App Catalog
  curate_ir.py           # Select IR remotes from Flipper-IRDB
  curate_badusb.py       # Stage BadUSB DuckyScript payloads
  curate_extras.py       # Stage music, Amiibo, and Sub-GHz files
  generate_nfc.py        # Generate NTAG215 NFC tag files
  flipper_serial.py      # Serial communication with Flipper CLI
  vendor/                # Downloaded community repos (gitignored)
  staging/               # Curated files ready for upload (gitignored)
```
