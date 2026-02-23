# LinkedIn Post

---

**I found a Flipper Zero collecting dust in my drawer. 3 hours later, Claude turned it into an urban sorcery toolkit.**

We all have that drawer. The one with the Raspberry Pi you never set up, the Arduino from that workshop, the dev board you bought at 2am after watching a YouTube video.

Mine had a Flipper Zero. Bought it in 2024. Used it once. Forgot about it.

Last night I pulled it out and wondered: what if I actually set this thing up properly? Not just the factory defaults — the full loadout. Custom firmware, 229 IR remotes, BadUSB payloads, NFC tags, Amiibo dumps, transit card readers, the works.

The problem: configuring a Flipper Zero is tedious. You're downloading files from 6 different GitHub repos, hand-picking IR databases, converting NFC payloads, building FAP apps against the right API version, and pushing everything over serial at 230400 baud. It's a full afternoon of work if you know what you're doing.

So I described what I wanted to Claude and we built a complete deployment pipeline together:

- A serial communication module that talks raw CLI protocol to the Flipper (no pyserial — just termios and file descriptors)
- Curators that pull from community repos and select the useful stuff (229 IR remotes from a database of thousands)
- An NFC tag generator that creates NDEF-formatted NTAG215 dumps from scratch
- A one-command deploy script that pushes 375 files over USB in ~7 minutes

The interesting engineering problem was the serial protocol. Momentum firmware (the custom firmware we flashed) echoes VT100 ANSI escape codes in its CLI responses. And the Flipper's CLI triggers on carriage return but leaves the linefeed in the input buffer — which corrupts chunked file transfers with an off-by-one error. Debugging that down to the byte level was genuinely fun.

The whole thing is open source. One command to go from stock Flipper to fully loaded toolkit.

What forgotten hardware is sitting in YOUR drawer?

GitHub: https://github.com/tpdox/flipper-zero-urban-sorcerer

#Python #OpenSource #HardwareHacking #FlipperZero #Claude #AI #SideProjects #Engineering
