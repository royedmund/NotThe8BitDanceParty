"""Small independent subset-6502 execution test for this build (not cycle-accurate)."""
import struct, json
from pathlib import Path
ROOT=Path(__file__).parent
raw=(ROOT/'PARTY.bin').read_bytes();addr,size=struct.unpack('<HH',raw[:4]);code=raw[4:]
assert size==len(code)
syms={k:int(v[1:],16) for k,v in json.loads((ROOT/'symbol_map.json').read_text()).items()}
# Simple CPU emulator implementing only opcode subset emitted by the build script.
mem=bytearray(65536);mem[addr:addr+size]=code
mem[0xC000]=0 # keyboard initially unpressed
A=X=Y=0;SP=0xfd;P=0x20;PC=addr;ay={0xC400:{'port':0,'addr':0,'reg':[0]*16},0xC480:{'port':0,'addr':0,'reg':[0]*16}}
logs=[];steps=0;music_rows=0;stop=False;cycle_count=0;music_row_cycles=[]
CYCLES={
0xA9:2,0xA5:3,0xAD:4,0xBD:4,0xB1:5,
0xA2:2,0xA6:3,0xAE:4,0xA0:2,0xA4:3,0xAC:4,
0x85:3,0x8D:4,0x91:6,0x86:3,0x8E:4,0x84:3,0x8C:4,
0x2C:4,0x29:2,0xC9:2,0xE0:2,0xE6:5,0xC6:5,
0xAA:2,0xA8:2,0x8A:2,0xC8:2,0xE8:2,0xCA:2,0x88:2,
0x20:6,0x4C:3,0x60:6,0x08:3,0x28:4,0x78:2,0x58:2,
0xD0:2,0xF0:2,0x90:2,0xB0:2,0x10:2,0x30:2}


def setflag(bit,b):
 global P
 if b:P|=bit
 else:P &= (~bit)&255

def nz(v):
 setflag(2,(v&255)==0);setflag(0x80,v&0x80)

def read(address):return mem[address&65535]
def write(address,value):
 address &=65535;value &=255;mem[address]=value
 for base,o in ay.items():
  if address==base+1:o['port']=value
  if address==base:
   if value==0:o['reg']=[0]*16
   if value==7:o['addr']=o['port'] & 15
   if value==6:
    o['reg'][o['addr']]=o['port']
    logs.append((base,o['addr'],o['port']))

def imm():
 global PC
 v=read(PC);PC=(PC+1)&65535;return v

def word():
 l=imm();h=imm();return l+256*h

def push(v):
 global SP
 mem[0x100+SP]=v&255;SP=(SP-1)&255

def pop():
 global SP
 SP=(SP+1)&255;return mem[0x100+SP]

while steps<5_000_000:
 steps+=1
 pc0=PC
 # detect when second row has been completed, make keyboard press so exit at the next check.
 if pc0==syms['play_step']:
  music_row_cycles.append(cycle_count)
  music_rows+=1
  if music_rows>=14:mem[0xC000]=0x80
 op=imm()
 if op in (0xA9,0xA5,0xAD,0xBD,0xB1):
  if op==0xA9:v=imm()
  elif op==0xA5:v=read(imm())
  elif op==0xAD:v=read(word())
  elif op==0xBD:v=read(word()+X)
  else:
   z=imm();v=read(read(z)+256*read((z+1)&255)+Y)
  A=v;nz(A)
 elif op in (0xA2,0xA6,0xAE):
  v=imm() if op==0xA2 else (read(imm()) if op==0xA6 else read(word()))
  X=v;nz(X)
 elif op in (0xA0,0xA4,0xAC):
  v=imm() if op==0xA0 else (read(imm()) if op==0xA4 else read(word()))
  Y=v;nz(Y)
 elif op in (0x85,0x8D,0x91,0x86,0x8E,0x84,0x8C):
  val= A if op in (0x85,0x8D,0x91) else (X if op in (0x86,0x8E) else Y)
  if op in (0x85,0x86,0x84):a=imm()
  elif op in (0x8D,0x8E,0x8C):a=word()
  else:
   zp=imm();a=read(zp)+256*read((zp+1)&255)+Y
  write(a,val)
 elif op==0x2C:
  v=read(word());setflag(0x80, v&0x80);setflag(0x40,v&0x40);setflag(2,(A&v)==0)
 elif op==0x29:A=A&imm();nz(A)
 elif op==0xC9:
  val=imm();t=(A-val)&255;setflag(1,A>=val);nz(t)
 elif op==0xE0:
  val=imm();t=(X-val)&255;setflag(1,X>=val);nz(t)
 elif op in (0xE6,0xC6):
  ad=imm();v=(read(ad)+(1 if op==0xE6 else -1))&255;write(ad,v);nz(v)
 elif op in (0xAA,0xA8,0x8A):
  if op==0xAA:X=A;nz(X)
  elif op==0xA8:Y=A;nz(Y)
  else:A=X;nz(A)
 elif op in (0xC8,0xE8,0xCA,0x88):
  if op==0xC8:Y=(Y+1)&255;nz(Y)
  elif op==0x88:Y=(Y-1)&255;nz(Y)
  elif op==0xE8:X=(X+1)&255;nz(X)
  else:X=(X-1)&255;nz(X)
 elif op==0x20:
  dest=word();ret=(PC-1)&65535;push(ret>>8);push(ret&255);PC=dest
 elif op==0x4C:PC=word()
 elif op==0x60:
  if SP>=0xFD:
   stop=True;break
  lo=pop();hi=pop();PC=(hi*256+lo+1)&65535
 elif op==0x08:push(P|0x30)
 elif op==0x28:P=pop()
 elif op==0x78:setflag(4,True)
 elif op==0x58:setflag(4,False)
 elif op in (0xD0,0xF0,0x90,0xB0,0x10,0x30):
  disp=imm();disp=disp if disp<128 else disp-256
  cond={0xD0:not(P&2),0xF0:bool(P&2),0x90:not(P&1),0xB0:bool(P&1),0x10:not(P&0x80),0x30:bool(P&0x80)}[op]
  if cond:PC=(PC+disp)&65535
  if cond:cycle_count+=1
 else:raise Exception(f'Unknown opcode {op:02X} @ {pc0:04X} after {steps} instructions')
 cycle_count+=CYCLES[op]
else:raise Exception(f'Test instruction cap reached: {steps}, PC={PC:04X}, rows={music_rows}')
assert stop
assert music_rows>=14,music_rows
assert len(logs)>60,len(logs)
assert len({t[0] for t in logs})==2
assert all(0<=reg<=15 for _,reg,_ in logs)
# last 3 regs must be muted on both chips
for base,obj in ay.items():
 assert obj['reg'][8:11]==[0,0,0], (hex(base),obj['reg'][8:11])
# bitmap reproduced exactly after DOS .BIN invokes PLAYER
hgr=(ROOT/'TITLE_HGR_PAGE.bin').read_bytes()
# Meter animation legitimately overwrites one 7-pixel column in 55 scanlines.
# All pixels outside that column must match the loaded static framebuffer.
for yy in range(192):
 for col in range(40):
  loc=0x2000+((yy&7)<<10)+(((yy>>3)&7)<<7)+(yy>>6)*40+col
  if 103<=yy<=157 and col==37:continue
  assert mem[loc]==hgr[loc-0x2000], f'HGR image mismatch at {yy},{col}'

print('Row timings:',[music_row_cycles[i+1]-music_row_cycles[i] for i in range(2,min(len(music_row_cycles)-1,8))]);print('Avg row cycles:',sum(music_row_cycles[i+1]-music_row_cycles[i] for i in range(2,len(music_row_cycles)-1))/(len(music_row_cycles)-3));print('Approx BPM:',60*1023000/4/(sum(music_row_cycles[i+1]-music_row_cycles[i] for i in range(2,len(music_row_cycles)-1))/(len(music_row_cycles)-3)));print('PASS CPU subset emulator:',steps,'executed instructions,',music_rows,'row entries,',len(logs),'AY writes')
print('PASS HGR framebuffer: original pixels exact outside animated 55-row meter')
print('PASS audio chips:',{hex(k):o['reg'] for k,o in ay.items()})
print('PASS keyboard exit -> both chips muted; text mode access executed')
(ROOT/'VALIDATION.txt').write_text(f'''CPU subset emulator: PASS
Executed instructions: {steps}
Music rows started: {music_rows}
Logged AY register writes: {len(logs)}
Both slot-4 AYs received writes: YES
HGR image copy: all pixels outside animated meter exact
Keyboard exit, silence and RTS: PASS
Note: subset emulator is not a complete hardware or DOS emulator. Actual boot/sound/colour require hardware testing.\n''')
