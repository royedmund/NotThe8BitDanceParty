# Apple IIe / Mockingboard Technical Notes (v11)

## Target hardware

- Apple IIe with at least 64 KB of RAM (128 KB tested configuration)
- 280 × 192 Hi-Res monochrome graphics; the 80-column card is not required
- Mockingboard in **slot 4**, with two AY-3-8910 sound chips
- Disk II-compatible drive in **slot 6**, DOS 3.3 140 KB disk
- SSI-263 speech chip is available but is not used in this edition

## Boot and runtime

The DOS 3.3 disk catalog has only **HELLO** (Applesoft BASIC autostart) and **PARTY** (6502 executable). HELLO runs `BRUN PARTY`. The program loads at **$4800** and ends at **$7E07**, then copies the 8192-byte native HGR memory image to **$2000–$3FFF**.

It runs the portrait, text `NOT THE 8-BIT DANCE PARTY!`, `APPLE //e` footer and the vertical animated meter. The bar graph tracks the note volume at sixteenth-note resolution. Keypress stops playback, mutes the AYs and returns to DOS.

Mockingboard VIA/AY interfaces are addressed at **$C400** and **$C480**. Five tone voices and one noise/percussion voice are arranged across both chips. There are no interrupt hooks or disk reads during music.

## Music

The score is the **Donkey Kong (NES) Introduction**, originally composed by **Yukio Kaneoka**, as transcribed to MIDI by **Mikhail Hogrefe**. Tempo target is 140 BPM; independent instruction-cycle estimates predict approximately 140.9 BPM. It consists of **132 sixteenth-note steps**, looping at roughly 14 seconds.

The three original MIDI lines provide the primary two melodic parts and bass. The remaining AY channels add restrained echo, bass reinforcement and light percussion. This is an adaptation of the NES score for an AY PSG, not a faithful simulation of the NES audio hardware or a direct C64 SID conversion.

Sources: https://musescore.com/user/41962746/scores/10632349 and https://github.com/mhogrefe/accurate-video-game-sheet-music/tree/main/nes/donkey-kong/01-introduction

## Rebuilding

Get the v11 source package from the repository. Extract its contents, put a **legitimately obtained Apple DOS 3.3 System Master** image in the source directory as `DOS_3_3_MASTER.dsk`, and use:

```sh
python3 -m pip install -r requirements.txt
python3 build.py
python3 verify_full_loop.py
python3 verify_timing.py
```

The source bundle includes the 8 KB HGR bitmap and MIDI source; original video footage is not needed. The source package does **not** redistribute a separate DOS System Master; the finished test disk has the required DOS boot tracks.

## Verification and caveats

The image is exactly **143,360 bytes** (140 KB), formatted as DOS 3.3 sector order. Binary load header and both DOS catalog file payloads passed disk-sector read-back verification. A limited 6502 instruction interpreter ran the **entire 132-step loop and restart**, exercised both AY chip interfaces, checked that the HGR pixels stay intact outside the moving meter, and verified keypress exit with sound muted.

**Physical Apple IIe testing has not yet been performed.** The instruction interpreter does not model actual Disk II boot-ROM behaviour or analog Mockingboard audio. The music may sound different from a software-rendered WAV preview, and external hardware timing or card revisions can still expose issues.

## Version history

- **v11:** MIDI-transcribed Donkey Kong NES introduction, ~140 BPM, shaped envelopes, full-loop tests.
- **v9–v10:** Portrait, animated meter and previous dance arrangements.
- **v5–v8:** Portrait revisions; simplified `APPLE //e` footer.
- **Earlier experiments:** C64 video and speech conversion prototypes, superseded due to quality and stability limitations.
