# Not The 8-Bit Dance Party! — Apple IIe Tribute

A retro-computing tribute to **Adrian Black / Digital Basement**, built for an **Apple IIe** and **Mockingboard in slot 4**.

The current experimental Apple IIe release is **v11**, featuring a static monochrome **280 × 192 Hi-Res portrait**, a vertical animated level meter, and a six-channel AY-3-8910 adaptation of the **Donkey Kong (NES, 1983) Introduction**.

## Download the boot disk

**[Download v11 Apple IIe boot disk (.dsk.gz)](apple2e/releases/ADRIAN_BLACK_DONKEY_KONG_INTRO_V11.dsk.gz)**

The image is compressed with gzip to keep the GitHub repository small. Decompress it to obtain the original 140 KB `.dsk` image:

```sh
gzip -dk ADRIAN_BLACK_DONKEY_KONG_INTRO_V11.dsk.gz
```

On Windows, 7-Zip can extract the `.gz` file. Mount the resulting `.dsk` in Drive 1 on an Apple IIe emulator or use suitable floppy/emulation hardware. Boot from Drive 1. Apple DOS 3.3 automatically executes `HELLO`, which launches `PARTY`. **Press any key** to stop the music and return to DOS.

https://youtu.be/0rz2XmdiCCc?si=GEtnIHl0jI_S6E6W

## Hardware

| Component | Target |
| --- | --- |
| Computer | Apple IIe (64 KB minimum; target machine has 128 KB) |
| Display | 280 × 192 monochrome Hi-Res graphics |
| Audio | Mockingboard, **slot 4**, two AY-3-8910 sound chips |
| Speech | SSI-263 available, **not used** in this edition |
| Disk | Disk II-compatible, 140 KB, slot 6 / Drive 1 |
| Software | Apple DOS 3.3; `HELLO` and `PARTY` only |

The static portrait is labelled **ADRIAN BLACK — NOT THE 8-BIT DANCE PARTY!**, with **APPLE //e** at the bottom. An animated vertical level bar follows the music.

## Development

- `apple2e/source/` contains the **Python/6502 builder**, independent test scripts and source input files.
- `apple2e/releases/` contains the compressed working disk image and its SHA-256 checksum.
- `apple2e/README.md` explains the build, memory layout and validation results.

To rebuild the disk, use Python 3, `Pillow`, `numpy`, `mido`, and a **separately obtained** DOS 3.3 System Master in DOS-order `.dsk` format named `DOS_3_3_MASTER.dsk`. The full DOS Master is *not* included in the editable source bundle. The pre-rendered 8 KB HGR framebuffer avoids requiring the original video or external fonts.

See [technical notes](apple2e/README.md) for details.

## Music and credits

- **Donkey Kong (NES)** music composed by **Yukio Kaneoka**; public MIDI transcription by **Mikhail Hogrefe**: [MuseScore score](https://musescore.com/user/41962746/scores/10632349) · [transcription files](https://github.com/mhogrefe/accurate-video-game-sheet-music/tree/main/nes/donkey-kong/01-introduction).
- The NES pulse and triangle parts were adapted for two **AY-3-8910 PSGs**, with soft echo, bass doubling and light noise percussion. Approximate tempo: **140 BPM**.
- Portrait and title are adapted from supplied C64 demo footage. Earlier C64 demo production credits include Machete (code/graphics) and Linus (music).

This is an independent fan tribute for retro-hardware experimentation, unaffiliated with Nintendo or Digital Basement. No ownership of the referenced score, video or platform software is claimed.

## Status

**Experimental, not confirmed on original Apple IIe hardware.** DOS disk sectors and file payloads were verified; a limited 6502 emulator tested the complete 132-step music loop plus restart, both AY register interfaces, the animated level meter and keyboard exit. The supplied WAV preview (if built locally) is a software approximation rather than recorded Mockingboard output.
