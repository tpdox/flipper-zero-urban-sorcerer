# Mazincea Urban Sorcerer Kit — Design Document

**Device:** Flipper Zero "Mazincea" (HW v12, US region)
**Current firmware:** 0.105.0 (Official, Aug 2024)
**Target firmware:** Momentum (mntm-012+)

## Overview

Transform a stock Flipper Zero into a fully-loaded urban toolkit with a curated mix of custom firmware, community apps, pre-loaded databases, and a deployment script for reproducible setup.

## Phase 1: Momentum Firmware

Flash Momentum firmware via Web Updater (https://momentum-fw.dev/update) in Chrome/Edge. Do NOT use qFlipper on macOS (known crash on Apple Silicon).

**Unlocks:**
- Extended Sub-GHz: 281-361, 378-481, 749-962 MHz (all regional locks removed)
- Rolling code transmission
- FindMyFlipper (Apple FindMy network tracking)
- BLE Spam (device notification flooding)
- BadKB over Bluetooth (wireless HID)
- NFC Maker (create NDEF tags on-device)
- Weather Station decoder
- POCSAG pager decoder
- 40+ bundled apps
- Asset pack system for custom themes

SD card data is preserved during firmware install.

## Phase 2: Community App Stack

| App | Source | Purpose |
|-----|--------|---------|
| Ocarina | Flipper App Hub | Zelda Ocarina of Time instrument |
| Metroflip | github.com/luu176/Metroflip | Transit card reader |
| FlipperNested | github.com/AloneLiberty/FlipperNested | Mifare Classic key recovery |
| Mfkey32 | github.com/noproto/FlipperMfkey | On-device Mifare key cracker |
| ProtoView | github.com/antirez/protoview | Sub-GHz signal decoder |
| TPMS | github.com/wosk/flipperzero-tpms | Tire pressure monitor reader |
| XRemote | github.com/kala13x/flipper-xremote | Advanced IR remote |
| Cross Remote | github.com/leedave/flipper-zero-cross-remote | IR + Sub-GHz macro remote |
| Mouse Jiggler | Flipper App Hub | Keep computer awake |

## Phase 3: SD Card Loadout

### Sub-GHz Files
- Tesla charge port open signal (.sub)

### Infrared Database (from Flipper-IRDB)
Curated selection:
- TVs: Samsung, LG, Sony, Vizio, TCL, Hisense, Panasonic, Philips
- Soundbars: JBL, Bose, Sony, Samsung, Vizio, Yamaha, Polk, Harman Kardon
- ACs: Mitsubishi, Daikin, LG, Carrier, Fujitsu
- Projectors: Epson, BenQ, NEC, Optoma
- Fans: Dyson, Honeywell
- Cameras: Canon, Nikon (IR shutter trigger)

### BadUSB Payloads
- RickRoll (full-volume YouTube)
- FakeHackScreen (GeekTyper fullscreen)
- AcidBurn Roast (system audit + text-to-speech roast)
- Wallpaper Troll

### NFC Tags
- Instagram profile link
- WiFi auto-connect (user's network)
- Contact vCard
- Troll collection (curated from NFC-Trolls repo)

### Amiibo Collection
- Full NTAG215 .nfc dump library

### Music
- RTTTL files: Mario, Zelda, Imperial March, meme songs

### Asset Packs
- Custom theme (cyberpunk or pirate aesthetic)

## Phase 4: Deploy Script (deploy.py)

Python script that:
1. Clones/downloads all required repos and files
2. Filters and selects relevant IR, NFC, BadUSB, and music files
3. Pushes files to Flipper over serial (/dev/cu.usbmodemflip_Mazincea1)
4. Creates personalized NFC tags (Instagram, WiFi, contact)
5. Verifies deployment by listing SD card contents
6. Supports re-deployment after firmware updates

### Dependencies
- Python 3.13+
- pyserial (for serial communication)
- git (for cloning repos)
- No pip install required on the Flipper

## Phase 5: Custom "Sorcerer Mode" FAP (future)

Quick-select wheel app for one-tap access to frequently used tricks. Deferred to after initial deployment is verified working.

## Implementation Order

1. Write deploy.py with serial communication helpers
2. Flash Momentum firmware (manual step via web updater)
3. Run deploy.py to push full loadout
4. Verify all apps and files on device
5. Create personalized NFC tags
6. Test each trick category

## Success Criteria

- Momentum firmware running on Mazincea
- All community apps installed and launchable
- IR database loaded with curated remotes
- BadUSB payloads ready to execute
- NFC tags created and emulatable
- Amiibo collection accessible
- Music files playable
- Deploy script reproducible for future re-setup
