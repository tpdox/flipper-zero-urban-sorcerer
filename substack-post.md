# Reviving a Dusty Flipper Zero with Claude: From Forgotten Gadget to Urban Sorcery Toolkit

## The Drawer of Abandoned Projects

Every engineer has one. The drawer (or shelf, or box under the desk) where half-finished projects go to die. Raspberry Pis still in their anti-static bags. Arduinos with three wires soldered to nothing. Dev boards purchased at 2am after one too many YouTube rabbit holes.

In my drawer: a Flipper Zero named "Mazincea." Purchased in 2024 with grand ambitions. Used once to read a hotel key card. Abandoned.

Last week I was cleaning out old projects and found it wedged between a USB hub and some jumper wires. The screen still worked. The firmware was a year out of date. And I thought: what if I actually set this thing up the way I always meant to?

Not just the defaults. The *full loadout.*

## What Even Is a "Full Loadout"?

If you're not familiar with the Flipper Zero, it's a pocket-sized multi-tool for wireless protocols — infrared, NFC, Sub-GHz radio, BadUSB, Bluetooth, RFID. Think of it as a Swiss Army knife for signals.

Out of the box it's capable but sparse. The real power comes from the community ecosystem:

- **Custom firmware** like Momentum that unlocks extended frequency ranges and adds dozens of built-in apps
- **Infrared databases** — community-maintained collections of remote control codes for thousands of devices
- **BadUSB payloads** — DuckyScript files that execute keystroke sequences when plugged into a computer
- **NFC tag files** — pre-built NDEF records for sharing links, WiFi credentials, or contact info
- **Amiibo dumps** — NTAG215 NFC files that emulate Nintendo Amiibo figures
- **Community apps** — .fap binaries for transit card reading, signal decoding, advanced remotes, and more

Setting all this up manually means cloning half a dozen GitHub repos, hand-picking files from databases with thousands of entries, converting between formats, building apps against the right firmware API version, and then pushing everything to the device over a serial connection at 230400 baud.

It's a full afternoon of fiddly work even if you know exactly what you're doing. Which I did not.

## "Just Describe What You Want"

This is where the experiment got interesting. Instead of spending hours reading wiki pages and forum threads, I described to Claude what I wanted: a Flipper Zero configured as an "urban sorcery toolkit" — a curated set of useful tricks for everyday city life. Turn off annoying bar TVs. Rick Roll your friends. Share your Instagram with a tap. Read transit cards. Play the Mario theme to break awkward silences.

Claude and I went through a proper design process. We brainstormed the loadout, evaluated tradeoffs (flat IR directory vs. nested by brand? generate NFC tags from scratch vs. use templates?), and settled on an architecture: a set of Python scripts that would download, curate, and deploy everything through a single command.

Here's what we built:

### The Pipeline

```
download_resources.py  →  Clone community repos (Flipper-IRDB, BadUSB payloads, Amiibo dumps)
curate_ir.py           →  Select 229 useful IR remotes from 4,000+ in the database
curate_badusb.py       →  Stage 3 macOS-optimized BadUSB payloads
generate_nfc.py        →  Generate NDEF-formatted NTAG215 .nfc files from scratch
curate_extras.py       →  Pick music files, Amiibo subset, Sub-GHz signals
download_apps.py       →  Fetch .fap binaries from the Flipper App Catalog API
flipper_serial.py      →  Raw serial communication with the Flipper CLI
deploy.py              →  Orchestrate everything into a single deploy command
verify.py              →  Post-deploy verification
```

One `python3 deploy.py` and you go from stock Flipper to 375 files deployed in about 7 minutes.

### The IR Curation Problem

The community Flipper-IRDB repository has over 4,000 infrared remote files. You don't want all of them — you want the useful ones. The curator script selects based on brand priority lists and file quality (preferring files with more signal definitions). It landed on 229 files covering:

- TVs from Samsung, LG, Sony, Vizio, TCL, Hisense, Panasonic, Philips
- Soundbars from JBL, Bose, Sony, Yamaha
- ACs from Mitsubishi, Daikin, LG, Carrier
- Projectors from Epson and BenQ
- Dyson and Honeywell fans
- Canon and Nikon camera shutter triggers

### NFC Tags from Scratch

Rather than using template files, we wrote a generator that builds NTAG215 NFC dumps byte-by-byte. It constructs proper NDEF records — URI records for links, WiFi Configuration Token records for network sharing — and wraps them in the full NTAG215 memory layout with correct page structure, capability containers, and TLV framing.

This means you can generate a tag for any URL, any WiFi network, or any contact card without needing a phone app or an NFC writer.

## The Serial Protocol Rabbit Hole

This is where things got genuinely fun from an engineering perspective.

The Flipper Zero exposes a CLI over USB serial at 230400 baud. You send text commands, it sends text responses. Simple enough. The `storage write_chunk` command lets you upload files in 512-byte chunks: send the command, wait for "Ready", send raw bytes, wait for acknowledgement, repeat.

We wrote the serial module using raw file descriptors and termios — no pyserial dependency. It worked perfectly against stock firmware in testing.

Then we flashed Momentum firmware.

Everything broke.

### Bug 1: The Invisible Responses

Momentum firmware echoes CLI commands with VT100 ANSI escape codes — specifically `\x1b[4h` and `\x1b[4l]` (insert mode on/off) wrapped around each character. Our code was looking for the string "Ready" in the response, but what it actually received was `\x1b[4hR\x1b[4l\x1b[4he\x1b[4l\x1b[4ha\x1b[4l...`. The "Ready" was there, just buried in escape sequences.

Fix: a regex stripper that removes all ANSI escape sequences before parsing responses.

### Bug 2: The Phantom Command

We were sending `\r\n{command}\r\n` to be safe. But the Flipper CLI processes the first `\r\n` as an empty command submission, generating a `could not find command ''` error. Harmless but noisy, and it sometimes left garbage in the response buffer.

Fix: drain to a clean prompt before each command instead of prefixing with newlines.

### Bug 3: The Off-By-One (The Real Monster)

After fixing the first two bugs, most files uploaded fine — but files larger than ~1.5KB would still fail randomly. The error was bizarre: `could not find command 'estorage'`. The first character of "storage" was being eaten.

We traced it down to the byte level. After each chunk upload, the response included an extra byte at the end — specifically, the *last byte of the chunk data* was leaking past the prompt. The Flipper had consumed only 511 of our 512 bytes.

Root cause: the Flipper CLI triggers command processing on `\r` (carriage return) but leaves `\n` (linefeed) sitting in the input buffer. When `storage write_chunk` starts reading raw data bytes, it consumes that leftover `\n` as byte 0 of the chunk. So it only reads 511 actual data bytes, and byte 512 leaks into the CLI input buffer as a stray character.

Fix: send commands with `\r` only, not `\r\n`. One character. That was the entire fix.

```python
# Before (broken):
os.write(self.fd, f"{cmd}\r\n".encode("utf-8"))

# After (working):
os.write(self.fd, f"{cmd}\r".encode("utf-8"))
```

Debugging this took longer than writing the rest of the deployment pipeline combined. And it was the most satisfying bug to squash.

## The Result

375 files. Zero failures. 6 minutes 39 seconds.

```
============================================================
STEP 5: Summary
============================================================
  Uploaded: 375 / 375 files
  Failed:   0
  Total:    2.1 MB in 399.2s
```

The Flipper now has:
- 229 IR remotes for any TV, soundbar, AC, projector, or fan you'll encounter
- 3 BadUSB payloads optimized for macOS
- NFC tags for sharing your Instagram, WiFi, and a Rick Roll
- 100 Animal Crossing Amiibo for Nintendo Switch
- 31 chiptune songs
- 7 community apps for transit cards, signal decoding, and advanced remotes

## What I Learned

**AI is really good at reviving abandoned projects.** The activation energy for side projects is usually the boring setup work — reading documentation, figuring out file formats, writing glue code. That's exactly what LLMs excel at. The interesting parts (the serial protocol debugging, the design decisions about what to include) stayed interesting. The tedious parts disappeared.

**Byte-level debugging is still byte-level debugging.** Claude helped me reason about the serial protocol, but we still had to trace actual bytes on the wire to find the `\r\n` bug. There's no shortcut for that kind of low-level detective work. We did it together, but the bug didn't care whether a human or an AI was looking at the hex dump.

**The community ecosystem matters more than the device.** The Flipper Zero hardware is fine, but the real value is in the thousands of community-contributed IR files, BadUSB scripts, app plugins, and NFC dumps. The curation problem — selecting the useful 5% from the available 100% — is where most of the deployment script's logic lives.

**One afternoon > one year of "I'll get to it."** The Flipper sat in my drawer for over a year. Setting it up took one evening with Claude's help. The ratio of "time spent thinking about doing it" to "time spent actually doing it" was approximately 365:1.

## Try It Yourself

The whole project is open source. If you have a Flipper Zero collecting dust:

```bash
git clone https://github.com/tpdox/flipper-zero-urban-sorcerer.git
cd flipper
# Flash Momentum firmware: https://momentum-fw.dev/update
python3 deploy.py
```

One command. Seven minutes. No more drawer of shame.

https://github.com/tpdox/flipper-zero-urban-sorcerer

---

*What forgotten hardware is sitting in your drawer? I'm curious what other devices could get the "one-command revival" treatment. Drop a comment — maybe we'll build the next one together.*
