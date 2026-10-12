#!/usr/bin/env python3
"""Adrian Black's 8-Bit Dance Party: portrait edition for real Apple IIe.
Uses original C64 recording screenshot to create a static monochrome HGR
portrait; DOS 3.3 System Master startup and dual-AY/slot-4 music engine.
"""
from pathlib import Path
from PIL import Image,ImageEnhance,ImageDraw,ImageFont
import struct,math,random,wave,json,zipfile,hashlib
import numpy as np
ROOT=Path(__file__).resolve().parent
MASTER=ROOT/'DOS_3_3_MASTER.dsk'
# frame25.png extracted from user's provided C64 demo video at 25 seconds
BASE=0x4800
W,H=280,192
# Pre-rendered Apple II HGR page supplied with this source release.
# This preserves the converted portrait while avoiding redistribution of the
# original full-resolution source-video frame.
page = bytearray((ROOT / 'TITLE_HGR_PAGE.bin').read_bytes())
assert len(page) == 8192
# Optional monochrome preview reconstructed from the Apple II screen layout.
def hgr_addr(y):
 return 0x2000 + ((y & 7) << 10) + (((y >> 3) & 7) << 7) + (y >> 6) * 40
image = Image.new('L',(W,H),0)
for yy in range(H):
 for block in range(40):
  byte = page[hgr_addr(yy)-0x2000+block]
  for bit in range(7):
   image.putpixel((block*7+bit,yy),255 if byte & (1<<bit) else 0)
image.resize((840,576),Image.Resampling.NEAREST).save(ROOT/'ADRIAN_PORTRAIT_PREVIEW.png')
# Music v11: faithful note pitches and rhythmic entrances from the source
# NES Donkey Kong Introduction MIDI, credited to Yukio Kaneoka.
# MIDI transcription by Mikhail Hogrefe (transcription GitHub repository).
# 3 original NES voices mapped to AY1 A/B/C. AY2 has QUIET echo,
# bass reinforcement, and subtle percussive accents for a tasteful tribute.
# The source consists of a 1-beat pickup and 8 measures, 140 BPM, PPQ=384.
from mido import MidiFile
MIDI=ROOT/'DONKEY_KONG_INTRO_SOURCE.midi'
mid=MidiFile(MIDI)
assert mid.ticks_per_beat==384,mid.ticks_per_beat
assert len(mid.tracks)>=4,len(mid.tracks)
BPM=140
TICKS_PER_STEP=96  # exact sixteenth notes
source_notes=[]
for track in mid.tracks[1:4]:
 tick=0;on={};events=[]
 for msg in track:
  tick+=msg.time
  if msg.type=='note_on' and msg.velocity>0:
   on.setdefault((msg.channel,msg.note),[]).append((tick,msg.velocity))
  elif msg.type in ('note_off','note_on') and (msg.type=='note_off' or msg.velocity==0):
   key=(msg.channel,msg.note)
   begin,velocity=on[key].pop(0)
   events.append((begin,tick,msg.note,velocity))
 assert not any(on.values()), 'unclosed source note'
 source_notes.append(sorted(events))
last_tick=max(e[1] for ns in source_notes for e in ns)
# Source has a trailing silent beat after final note. Respect the MIDI EOT.
end_tick=max(sum(msg.time for msg in tr) for tr in mid.tracks)
assert end_tick%TICKS_PER_STEP==0,(end_tick,last_tick)
N_STEPS=end_tick//TICKS_PER_STEP
assert 0<N_STEPS<256, N_STEPS

def at(tick,track):
 for a,b,n,v in source_notes[track]:
  if a<=tick<b:return (a,b,n,v)
 return None

def period(note):
 if note is None:return 1
 f=440.0*(2**((note-69)/12))
 return max(1,min(4095,round(1_000_000/(16*f))))

steps=[]
for step in range(N_STEPS):
 tick=step*TICKS_PER_STEP
 m1=at(tick,0);m2=at(tick,1);b=at(tick,2)
 # Right chip doubles soft lead/bass to add depth, not drown out the score.
 echo=at(tick-96,0) if tick>=96 else None
 bass2=b
 notes=[m1[2] if m1 else None,
        m2[2] if m2 else None,
        b[2] if b else None,
        echo[2]-12 if echo else None,
        bass2[2]+12 if bass2 else None]
 # Gentle metronomic accent added to the original NES pulse/triangle parts;
 # no synthetic random-pitch 'melody' in this arrangement.
 accent = 1 if tick>=384 and ((tick-384)%384==0) else 0
 noise=12 if accent else 3
 steps.append(dict(notes=notes,volume=[13 if m1 else 0,10 if m2 else 0,
                 10 if b else 0,3 if echo else 0,3 if bass2 else 0,
                 3 if accent else 0],noise=noise,accent=accent))

# Pitch lookup indexed by 0..131, zero implies channel silent by envelope.
reg_table=[]
for channel in range(5):
 for high in (False,True):
  reg_table.append((f'P{channel}{"H" if high else "L"}',
      [((period(st['notes'][channel]) >> (8 if high else 0))&255) for st in steps]))
reg_table.append(('NOISE',[st['noise'] for st in steps]))

# Four intra-step volume updates retain exact rests/gates and shaped AY attack.
# Durations and pitches are never guessed from FFT -- sourced from MIDI.
for phase in range(4):
 tickoffset=phase*24
 for ch in range(6):
  vals=[]
  for si,st in enumerate(steps):
   tick=si*TICKS_PER_STEP+tickoffset
   if ch<3:
    note=at(tick,ch)
   elif ch==3:
    note=at(tick-96,0) if tick>=96 else None
   elif ch==4:
    note=at(tick,2)
   else:
    note=None
   if ch==5:
    level=st['volume'][5] if phase==0 else 0
   elif note is None:
    level=0
   else:
    onset,ending,_,_=note
    # Lead: fast attack, near-sustain. Second pulse: gentler.
    # NES triangle bass is less buzzy through softer AY volumes.
    if ch==0:curve=(1.0,.97,.90,.82)
    elif ch==1:curve=(1.0,.86,.72,.65)
    elif ch==2:curve=(.95,1.0,.90,.82)
    elif ch==3:curve=(1.0,.78,.62,.45)
    else:curve=(.90,.86,.77,.65)
    base=st['volume'][ch]
    level=round(base*curve[phase])
    if ending-tick<=24:level=max(0,level-2)
   vals.append(min(15,max(0,level)))
  reg_table.append((f'E{phase}{ch}',vals))
# Audio-driven graphic animation: compute active voice energy for this step.
METER_ROWS=list(range(157,102,-1));METER_BLOCK=37
meter_lo=[];meter_hi=[]
for yy in METER_ROWS:
 addr=hgr_addr(yy)+METER_BLOCK
 meter_lo.append(addr&255);meter_hi.append((addr>>8)&255)
meter_levels=[]
for st in steps:
 energy=sum(st['volume'][i]*[1.0,.6,.8,.2,.2,.15][i] for i in range(6))
 meter_levels.append(max(0,min(len(METER_ROWS),round(energy/27*len(METER_ROWS)))))

# 6502-compatible tiny assembler, no external binaries needed.
OPS={
'LDA':{'imm':0xA9,'zp':0xA5,'abs':0xAD,'absx':0xBD,'indy':0xB1},
'LDX':{'imm':0xA2,'zp':0xA6,'abs':0xAE},'LDY':{'imm':0xA0,'zp':0xA4,'abs':0xAC},
'STA':{'zp':0x85,'abs':0x8D,'indy':0x91},'STX':{'zp':0x86,'abs':0x8E},
'STY':{'zp':0x84,'abs':0x8C},
'JSR':{'abs':0x20},'JMP':{'abs':0x4C},'BIT':{'abs':0x2C},
'CMP':{'imm':0xC9},'CPX':{'imm':0xE0},'AND':{'imm':0x29},
'INC':{'zp':0xE6},'DEC':{'zp':0xC6},
'TAX':{'impl':0xAA},'TAY':{'impl':0xA8},'TXA':{'impl':0x8A},
'INY':{'impl':0xC8},'INX':{'impl':0xE8},'DEX':{'impl':0xCA},'DEY':{'impl':0x88},
'RTS':{'impl':0x60},'PHA':{'impl':0x48},'PLA':{'impl':0x68},
'SEI':{'impl':0x78},'CLI':{'impl':0x58},'PHP':{'impl':0x08},'PLP':{'impl':0x28},
'BNE':{'rel':0xD0},'BEQ':{'rel':0xF0},'BCC':{'rel':0x90},'BCS':{'rel':0xB0},'BPL':{'rel':0x10},'BMI':{'rel':0x30},
}
class Asm:
 def __init__(self):self.data=bytearray();self.labels={};self.fixups=[];self.lines=[]
 def here(self):return BASE+len(self.data)
 def mark(self,name):
  assert name not in self.labels,name
  self.labels[name]=self.here();self.lines.append(f'${self.here():04X} {name}:')
 def I(self,op,mode='impl',val=None):
  pc=self.here();self.data.append(OPS[op][mode]);n=2 if mode in ('abs','absx') else (0 if mode=='impl' else 1)
  if isinstance(val,str):self.fixups.append((len(self.data),mode,val,pc));self.data.extend(b'\0'*n)
  elif n==2:self.data+=struct.pack('<H',val)
  elif n==1:self.data.append(val&255)
  self.lines.append(f' ${pc:04X} {op:3s} {mode:4s} {str(val):15s}')
 def B(self,b):self.data.append(b&255)
 def resolve(self):
  for offset,mode,label,pc in self.fixups:
   if label[-1:] in ('<','>'):
    dst=self.labels[label[:-1]]
    value=(dst&255) if label[-1]=='<' else (dst>>8)
   else:value=self.labels[label]
   if mode in ('abs','absx'):self.data[offset:offset+2]=struct.pack('<H',value)
   elif mode=='rel':
    delta=value-(pc+2);assert -128<=delta<=127,(hex(pc),label,delta)
    self.data[offset]=delta&255
   else:self.data[offset]=value&255
  return bytes(self.data)

A=Asm();I=A.I
# Initial screen setup, copy full $2000-$3FFF with 32 x 256-byte block copy.
I('PHP');I('SEI')
for addr in (0xC002,0xC004,0xC00C):I('STA','abs',addr) # main read/write and 80-column OFF
for addr in (0xC050,0xC052,0xC054,0xC057):I('BIT','abs',addr)
I('LDA','imm','bitmap<');I('STA','zp',0x06)
I('LDA','imm','bitmap>');I('STA','zp',0x07)
I('LDA','imm',0);I('STA','zp',0x08)
I('LDA','imm',0x20);I('STA','zp',0x09)
I('LDX','imm',32)
A.mark('copy_page');I('LDY','imm',0)
A.mark('copy_byte');I('LDA','indy',0x06);I('STA','indy',0x08)
I('INY');I('BNE','rel','copy_byte')
I('INC','zp',0x07);I('INC','zp',0x09)
I('DEX');I('BNE','rel','copy_page')
# Initialize the two 6522s, hold each AY RESET low then release to inactive.
for base in (0xC400,0xC480):
 # Disable VIA interrupts so stale timer settings cannot disturb playback.
 I('LDA','imm',0x7F);I('STA','abs',base+0x0E)
 I('LDA','imm',0xFF);I('STA','abs',base+3)
 I('LDA','imm',0x07);I('STA','abs',base+2)
 I('LDA','imm',0);I('STA','abs',base)
 I('LDA','imm',4);I('STA','abs',base)
# Write mixer configuration: left: tone A B C, noise disabled; right A B tones, C noise only
for chip,name,mixer in [(0,'write_left',0x38),(1,'write_right',0x1C)]:
 for reg,val in [(7,mixer),(8,0),(9,0),(10,0)]:
  I('LDA','imm',reg);I('LDX','imm',val);I('JSR','abs',name)
I('LDA','imm',0);I('STA','zp',0x0A) # step index 0..127
A.mark('play_step')
# Every song step consists of constant-time writes to two chips.
# One chip's 3 tones (0..5), second chip 2 tones (0..3)
for ch in range(5):
 routine='write_left' if ch<=2 else 'write_right'
 reg=(ch if ch<=2 else ch-3)*2
 for high in (False,True):
  I('LDX','zp',0x0A)
  I('LDA','absx',f'P{ch}{"H" if high else "L"}')
  I('TAX');I('LDA','imm',reg+(1 if high else 0))
  I('JSR','abs',routine)
# Single noise generator on right chip. Frequency reg6.
I('LDX','zp',0x0A);I('LDA','absx','NOISE');I('TAX')
I('LDA','imm',6);I('JSR','abs','write_right')
# Four envelopes per eighth-note step. Dynamic six-voice volume gates
# are independent of note pitch and keep the sound crisp.
for stage in range(4):
 for ch in range(6):
  routine='write_left' if ch<=2 else 'write_right'
  reg=8+(ch if ch<=2 else ch-3)
  I('LDX','zp',0x0A)
  I('LDA','absx',f'E{stage}{ch}')
  I('TAX');I('LDA','imm',reg);I('JSR','abs',routine)
 if stage==0:
  I('LDX','zp',0x0A);I('LDA','absx','METERLVL');I('JSR','abs','update_meter')
 # Each phase ~51ms plus register/update overhead; about 140 BPM.
 # Timeouts are bounded CPU loops: no external 6522 IRQ/polling or hangs.
 I('LDX','imm',21 if stage==3 else 20);I('JSR','abs','delay')
I('BIT','abs',0xC000);I('BMI','rel','stop_key')
I('INC','zp',0x0A)
I('LDA','zp',0x0A);I('CMP','imm',N_STEPS);I('BCC','rel','play_step_near')
I('LDA','imm',0);I('STA','zp',0x0A)
A.mark('play_step_near');I('JMP','abs','play_step')
A.mark('update_meter')
I('STA','zp',0x0D)
I('LDY','imm',0)
I('LDX','imm',0)
A.mark('meter_clear')
I('LDA','absx','METERLO');I('STA','zp',0x06)
I('LDA','absx','METERHI');I('STA','zp',0x07)
I('LDA','imm',0);I('STA','indy',0x06)
I('INX');I('CPX','imm',55);I('BNE','rel','meter_clear')
I('LDX','imm',0)
A.mark('meter_fill')
I('LDA','zp',0x0D);I('BEQ','rel','meter_done')
I('DEC','zp',0x0D)
I('LDA','absx','METERLO');I('STA','zp',0x06)
I('LDA','absx','METERHI');I('STA','zp',0x07)
I('LDA','imm',0x7F);I('STA','indy',0x06)
I('INX');I('JMP','abs','meter_fill')
A.mark('meter_done')
I('RTS')
A.mark('stop_key')
I('BIT','abs',0xC010)
for f in ('write_left','write_right'):
 for reg in (8,9,10):
  I('LDA','imm',reg);I('LDX','imm',0);I('JSR','abs',f)
I('BIT','abs',0xC051)
I('PLP');I('RTS')
# Bounded busy loop, no interrupts, no dependence on DOS, never hangs on an external IRQ.
A.mark('delay')
I('LDY','imm',255)
A.mark('delay_y');I('DEY');I('BNE','rel','delay_y')
I('DEX');I('BNE','rel','delay')
I('RTS')
# AY writes to VIA ORA and ORB: LATCH(7), INACTIVE(4), WRITE(6), INACTIVE(4).
for label,base in [('write_left',0xC400),('write_right',0xC480)]:
 A.mark(label)
 I('STA','zp',0x0B);I('STX','zp',0x0C)
 I('STA','abs',base+1)
 I('LDA','imm',7);I('STA','abs',base)
 I('LDA','imm',4);I('STA','abs',base)
 I('LDA','zp',0x0C);I('STA','abs',base+1)
 I('LDA','imm',6);I('STA','abs',base)
 I('LDA','imm',4);I('STA','abs',base)
 I('RTS')
for label,arr in reg_table:
 A.mark(label)
 for value in arr:A.B(value)
A.mark('METERLVL')
for value in meter_levels:A.B(value)
A.mark('METERLO')
for value in meter_lo:A.B(value)
A.mark('METERHI')
for value in meter_hi:A.B(value)
A.mark('bitmap')
for value in page:A.B(value)
code=A.resolve()
assert BASE+len(code)<0x9600,hex(BASE+len(code))
assert len(code)<0x4E00
binary=struct.pack('<HH',BASE,len(code))+code
(ROOT/'PARTY.bin').write_bytes(binary)
(ROOT/'PARTY.raw').write_bytes(code)
(ROOT/'assembly_listing.txt').write_text('\n'.join(A.lines)+'\n')
(ROOT/'symbol_map.json').write_text(json.dumps({k:f'${v:04X}' for k,v in A.labels.items()},indent=2))
# Apple DOS 3.3 System Master disk copy. Free only user sectors, retain ALL boot tracks.
disk=bytearray(MASTER.read_bytes());assert len(disk)==143360
loc=lambda t,s:(t*16+s)*256
def sect_write(t,s,block):
 assert len(block)<=256
 disk[loc(t,s):loc(t,s)+256]=block.ljust(256,b'\0')
for t in range(3,35):
 if t!=17:
  for s in range(16):sect_write(t,s,b'')
for s in range(1,16):sect_write(17,s,b'')
used={(t,s) for t in range(3) for s in range(16)}|{(17,s) for s in range(16)}
free=[(t,s) for t in list(range(18,35))+list(range(3,17)) for s in range(15,-1,-1)]
def install(buf):
 chunks=[buf[i:i+256] for i in range(0,len(buf),256)]
 assert len(chunks)<=122
 table_sector=free.pop(0);used.add(table_sector)
 ts=bytearray(256)
 for i,chunk in enumerate(chunks):
  addr=free.pop(0);used.add(addr)
  sect_write(*addr,chunk)
  ts[12+2*i:14+2*i]=bytes(addr)
 sect_write(*table_sector,ts)
 return table_sector,len(chunks)+1
# Applesoft BASIC line: 10 PRINT CHR$(4);"BRUN PARTY"
body=bytes([0xBA,0xE7,ord('('),ord('4'),ord(')'),ord(';'),ord('"')])+b'BRUN PARTY'+b'"'
link=0x0801+4+len(body)+1
applesoft=struct.pack('<HH',link,10)+body+b'\0\0\0'
hello=struct.pack('<H',len(applesoft))+applesoft
entries=[('HELLO',0x82,install(hello)),('PARTY',0x84,install(binary))]
cat=bytearray(256)
for ix,(name,typ,(ts,sec_count)) in enumerate(entries):
 pos=11+ix*35
 cat[pos:pos+3]=bytes([ts[0],ts[1],typ]);cat[pos+3:pos+33]=bytes([ord(c)|0x80 for c in name.ljust(30)])
 cat[pos+33:pos+35]=struct.pack('<H',sec_count)
sect_write(17,15,cat)
v=bytearray(MASTER.read_bytes()[loc(17,0):loc(17,0)+256]);v[1:3]=bytes((17,15));v[6]=254
for t in range(35):
 free_mask=sum((1<<s) for s in range(16) if (t,s) not in used)
 v[0x38+4*t]=free_mask>>8;v[0x39+4*t]=free_mask&255
sect_write(17,0,v)
name='ADRIAN_BLACK_DONKEY_KONG_INTRO_V11.dsk'
(ROOT/name).write_bytes(disk)
# Sector-level validation including correct DOS 3.3 binary and BASIC file payload.
for filename,typ,(ts,count) in entries:
 table=disk[loc(*ts):loc(*ts)+256]
 rebuilt=b''.join(disk[loc(table[12+2*j],table[13+2*j]):loc(table[12+2*j],table[13+2*j])+256] for j in range(count-1))
 original=hello if filename=='HELLO' else binary
 assert rebuilt[:len(original)]==original,filename
assert disk[:3*16*256]==MASTER.read_bytes()[:3*16*256]
assert struct.unpack('<HH',binary[:4])==(BASE,len(code))
assert code[A.labels['bitmap']-BASE:A.labels['bitmap']-BASE+8192]==page
assert len(disk)==143360
# Create a short WAV preview from actual decoded AY note tables.
# This preview is NOT cycle-accurate hardware audio, but its notes/timing
# are generated from the same binary tables as the real disk.
SR=22050
step_length=60/BPM/4
sample_count=round(len(steps)*step_length*SR)
output=np.zeros((sample_count,2),dtype=np.float32)
phase_state=np.zeros(5,dtype=np.float64)
noise_rng=np.random.default_rng(2026)
env_tables={(ch,ph):dict(reg_table)[f'E{ph}{ch}'] for ch in range(6) for ph in range(4)}
for si,st in enumerate(steps):
 start=round(si*step_length*SR);end=min(sample_count,round((si+1)*step_length*SR))
 n=end-start
 if n<=0:continue
 sample_index=np.arange(n)
 t=sample_index/SR
 phindex=np.minimum(3,(t/step_length*4).astype(int))
 for ci,note in enumerate(st['notes']):
  if note is None:continue
  fre=1_000_000/(16*period(note))
  wavephase=(phase_state[ci]+fre*t)%1.0
  phase_state[ci]=(phase_state[ci]+fre*n/SR)%1.0
  sq=np.where(wavephase<.5,1.0,-1.0)
  amps=np.array([env_tables[(ci,ph)][si] for ph in range(4)],dtype=float)[phindex]
  scaled=(amps/15)**1.4
  output[start:end,0 if ci<3 else 1]+=sq*scaled*(.18 if ci<3 else .11)
 if st['accent']:
  dur=min(n,round(.016*SR))
  output[start:start+dur,1]+=noise_rng.uniform(-1,1,dur)*.07
output=np.tanh(output*1.2)*.8
with wave.open(str(ROOT/'MUSIC_SIMULATION.wav'),'wb') as f:
 f.setnchannels(2);f.setsampwidth(2);f.setframerate(SR)
 f.writeframes((output*32767).astype('<i2').tobytes())
# Keep the original source MIDI alongside the new disk for attribution.
readme=f'''ADRIAN'S 8-BIT DANCE PARTY / APPLE IIe STATIC TRIBUTE
Version: v11-Donkey-Kong-Intro / 12 October 2026

HARDWARE
- Apple IIe (works in main 64 KB; 128 KB and 80-column card optional)
- Composite monochrome or colour monitor (portrait uses black and white HGR)
- Mockingboard slot 4, two AY-3-8910 programmable sound generators
- Disk II compatible floppy controller (assumed slot 6), 140 KB disk

FILES ON DISK (only two)
A 002 HELLO  - Applesoft boot greeting: BRUN PARTY
B xxx PARTY  - 6502 executable with title card and 6-voice song

USE
Mount ADRIAN_BLACK_DONKEY_KONG_INTRO_V11.dsk in Drive 1 and boot.
Boot runs HELLO, which BRUNs PARTY automatically.
The picture remains static while music loops. Press any key to stop.
The sound player is strictly polling/delay based: no IRQ or SSI-263.

WHAT CHANGED
- Uses the notes and rhythms from Donkey Kong (NES) Introduction.
- Original composer: Yukio Kaneoka; MIDI transcription: Mikhail Hogrefe.
- Source: https://musescore.com/user/41962746/scores/10632349
- Two NES pulse voices plus NES triangle bass mapped to AY1 A/B/C.
- Second AY adds a quiet echo, octave reinforcement and restrained noise accents.
- 140 BPM, 4/4, F major/D minor, intro about 14 seconds, continuously looped.
- Four-stage envelopes preserve rests and articulation of the MIDI.
- No speech, no video; same portrait and vertical animated level meter.
- Keypress stops all sound and returns to DOS text mode.

IMPORTANT
- Assembled and disk sectors read back and verified, but NOT tested on
  real hardware. Audio depends on the specific Mockingboard implementation.
- Prior versions had unstable audio; this uses an interrupt-free player
  with MIDI-derived envelopes and bounded delays. Hardware testing is still needed.
- Pressing any key mutes all six channels, returns to text mode and DOS.
- Most Mockingboards use AY clocks near 1 MHz; frequency may vary slightly.
- Credit for C64 original: Machete (code/graphics), Linus (music).

BUILD
python build.py
Needs Python 3, Pillow, NumPy, and mido (required to parse the source MIDI). Supply a copy of your DOS 3.3 System Master as DOS_3_3_MASTER.dsk alongside this script (not included in source archive).

DISK IMAGE
{len(disk)} bytes, DOS 3.3 sector order, real boot tracks from supplied System Master.
6502 executable loaded at ${BASE:04X}, ends at ${BASE+len(code):04X} (< $9600).
8 KB bitmap maps to Apple HGR $2000-$3FFF with native scanline mapping.
Program binary size: {len(code)} bytes.
Music rows: {len(steps)} (one sixteenth per row), about 14.1 seconds per loop.
'''
(ROOT/'README.txt').write_text(readme)
manifest={'image':name,'size':len(disk),'program_load':hex(BASE),'program_end':hex(BASE+len(code)), 'program_size':len(code),'files':{'HELLO':len(hello),'PARTY':len(binary)},'music_steps':len(steps),'bpm_target':BPM,'source':'Donkey Kong NES Introduction', 'source_midi':'DONKEY_KONG_INTRO_SOURCE.midi','phase_envelopes':4,'boot_tracks_sha256':hashlib.sha256(disk[:3*16*256]).hexdigest(),'disk_sha256':hashlib.sha256(disk).hexdigest()}
(ROOT/'manifest.json').write_text(json.dumps(manifest,indent=2))
print(json.dumps(manifest,indent=2))
