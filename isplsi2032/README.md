# ispLSI2032 — Lattice ispLSI 2000 Family

Available on donor PCBs in the lab.

## VOLTAGE WARNING

The ispLSI 2032 family has **multiple voltage variants**:

| Variant        | VCC      | ISP         | JTAG                   | FT2232H direct?   | IDCODE     |
|----------------|----------|-------------|------------------------|--------------------|------------|
| ispLSI 2032    | **5V**   | Hidden JTAG | **Yes**                | YES (5V tolerant)  | None (0x00000005) |
| ispLSI 2032A   | **5V**   | Hidden JTAG | **Yes**                | YES (5V tolerant)  | TBD        |
| ispLSI 2032V   | **3.3V** | IEEE 1532   | **Yes** (IR=5)         | YES                | 0x00301043 |
| ispLSI 2032VL  | **3.3V** | IEEE 1532   | **Yes** (IR=5)         | YES                | TBD        |
| ispLSI 2032E   | **5V**   | IEEE 1532   | **Yes** (IR=5)         | YES (5V tolerant)  | 0x00A4E043 |
| ispLSI 2032VE  | **3.3V** | IEEE 1532   | **Yes** (IR=5) + BScan | YES                | 0x10301043 |

**FT2232H is +5V tolerant on all I/O** — direct connection to ALL variants, no level shifter!
- "Legacy ISP" is actually JTAG with different pin names (Lattice patent US5412260A)
- All variants have JTAG capability
- For 5V chips: FT2232H outputs 3.3V HIGH → accepted as HIGH (VIH >= 2.0V)
- Hold ispEN (pin 7) LOW to enable JTAG mode

## Device Summary

| Parameter | Value |
|-----------|-------|
| Family | ispLSI 2000 |
| Macrocells | 32 (8 GLB x 4) |
| I/O pins | 32 + 2 dedicated inputs |
| Clock pins | 3 dedicated (Y0, Y1, Y2) |
| OE pins | 1 dedicated (GOE 0) |
| IR length | 5 bits (JTAG variants only) |
| JTAG | V/VL/E variants only |
| ISP | Legacy serial (2032/A) or IEEE 1532 (V/VL/E) |
| Architecture | GLB (AND/OR/XOR array) |
| Density | ~1K PLD gates |
| fMAX | 180 MHz (-180 grade) |
| Interconnect | Global Routing Pool (GRP) |
| Erase cycles | 10,000 (ispLSI) |
| Data retention | 20 years |
| Technology | E²CMOS |

## Architecture

- 8 Generic Logic Blocks (GLBs): A0..A7, 4 macrocells each
- Each GLB: 18 inputs from GRP, programmable AND/OR/XOR array
- Macrocell: combinatorial or registered output
- Global Routing Pool (GRP): full interconnect between all GLBs
- Output Routing Pool (ORP): connects GLB outputs to I/O cells
- 3 dedicated clock pins (Y0, Y1/RESET, Y2/SCLK)
- 1 global output enable (GOE 0)

## Packages

| Package | Pins | Suffix |
|---------|------|--------|
| PLCC | 44 | -xLJ44 |
| TQFP | 44 | -xLT44, -xLTN44 |
| TQFP | 48 | -xLTN48 |

## ISC Instructions (JTAG variants: V/VL/E)

From BSDL (bsdl.info), IR length = 5 bits:

| Instruction | Opcode | Description |
|-------------|--------|-------------|
| ISC_ENABLE | 10101 | Enter ISC mode |
| ISC_DISABLE | 11110 | Exit ISC mode |
| ISC_ADDRESS_SHIFT | 00001 | Load row address |
| ISC_DATA_SHIFT | 00010 | Shift fuse data |
| ISC_READ | 01010 | Read fuse row |
| ISC_ERASE | 00011 | Erase device |
| ISC_NOOP | 11001 | No operation |
| ISC_DISCHARGE | 10100 | Discharge programming voltage |
| ISC_PROGRAM_SECURITY | 01001 | Set security fuse |
| IDCODE | 10110 | Read JTAG IDCODE |

## JTAG/ISP Scan Results (plain ispLSI 2032-135LT44)

First successful JTAG communication on 2026-03-11 via FT2232H + OpenOCD.
Bit-bang probing on same date confirmed key parameters.

### Confirmed Parameters (bit-bang probed)

| Parameter             | Value                                        |
|-----------------------|----------------------------------------------|
| **IR length**         | **8 bits** (NOT 5 like V/VE variants!)       |
| **DR length**         | **8 bits** (but see NOTE below)              |
| **Shift register**    | Works correctly (data echoes with 8-bit delay)|
| Scan chain            | 1 TAP found                                  |
| **Device ID**         | **0x15 (00010101)** — confirmed by datasheet!|
| **Security fuse**     | **Likely SET — needs re-evaluation**         |

### ⚠️ CRITICAL CORRECTION (2026-03-11, fresh review)

**The `0x15` response IS the device identifier, NOT "oscillating SDO"!**

From 1996 Lattice Data Book, ispLSI 2032 datasheet (p.2-185):
> "The device identifier for the ispLSI 2032 is **0001 0101 (15 hex)**.
> This code is the unique device identifier which is generated when
> a **read ID command** is performed."

The previous analysis incorrectly concluded that `0x15` was a meaningless
oscillating pattern. In fact, the chip IS responding with its device ID.
This means **the ISP controller is NOT completely dead** — it processes
at least the read-ID command.

**What needs re-evaluation:**
1. The "DR length = 8 bits" conclusion — the real data register is **80 bits**
   and address register is **102 bits** (per datasheet p.2-186). The 8-bit
   measurement may have been reading only the device ID register.
2. The "all 256 opcodes give identical response" conclusion — some opcodes
   may activate the 80-bit or 102-bit registers, but were tested with only
   8-bit reads.
3. The security fuse conclusion — the chip responding with its ID suggests
   it may not be fully locked, or that read-ID bypasses security.

### Shift Register Layout (from datasheet p.2-186)

```
Data In ──→ [39... High Order SR ...0] ──→ SDO
(SDI)   ──→ [79... Low Order SR ...40] ──→ SDO

                          SDI
                           ↓
                        [101]
                          :    Address
                          :    Shift Register
                        [ 0]   (102 bits)
                           ↓
                          SDO
```

- **Data Register**: 80 bits total, two halves (High: 39→0, Low: 79→40)
- **Address Register**: 102 bits (one bit per E²CMOS row)
- **Logic 1** in address SR enables the row for programming or verification
- **Total E²CMOS cells**: 8,160 (102 rows × 80 bits)

### Probing Scripts

All scripts in `isplsi2032/`:

| Script | Description |
|--------|-------------|
| `bitbang_isp.py` | v1 — basic JTAG + legacy ISP, IR/DR length detection |
| `bitbang_isp2.py` | v2 — protocol variants A-E, ispEN on ADBUS5 |
| `bitbang_isp3.py` | v3 — patent-based protocol, 256-opcode brute-force |
| `bitbang_isp4.py` | v4 — MODE=1 commands, clock edges, SDO observation |
| `bitbang_isp5.py` | v5 — first 3-state ISP attempt (timing issues) |
| `bitbang_isp6.py` | **v6 — correct 3-state ISP protocol — WORKS!** |
| `detect_irlen.py` | pyftdi JTAG IR length detection (needs libusb) |
| `probe_ir.tcl` | OpenOCD TCL probe script |

### Bit-Bang Results Summary

#### Phase 1: OpenOCD probing (irlen=5, then irlen=8)

- All 256 IR opcodes via JTAG → identical DR behavior (`0x05` capture)
- No opcode activates a different DR register
- ISC_ERASE (0x03) had no effect

#### Phase 2: Direct bit-bang (bitbang_isp.py, ispEN=GND)

- **IR = 8 bits**, **DR = 8 bits** (ones-then-zeros method)
- MODE=0: SDO idle high, shift register works (A5 in → A5 out)
- MODE=1: SDO = 0 (all zeros)
- Capture value `0x15` — **THIS IS THE DEVICE ID** (datasheet p.2-185 confirms!)

#### Phase 3: With external PSU + ispEN on ADBUS5 (v3, v4)

Key improvement: external 5V power supply (phone charger) instead of
FT2232H 5V rail. ispEN moved from hardwired GND to ADBUS5 for
proper HIGH→LOW ISP entry sequence.

**bitbang_isp3.py (patent-based protocol):**
- TEST 1: `capture=0xFF` before any MODE pulse (chip in normal mode)
- After any MODE pulse: always reads `0x15`
- All 256 commands (MODE=0 shift + MODE=1 pulse + MODE=0 read) → `0x15`
- All 256 commands with 32-bit read → `0x00000015`
- Variable MODE pulse count (1-16) → no change
- Two-phase (cmd + addr + read) → no change
- ISC flow adapted for 8-bit → no change
- 128-bit reads → `0x15` in low 8 bits only

**bitbang_isp4.py (MODE=1 commands):**
- MODE=1 read = `0x00`, MODE=0 read = `0x15` (two different outputs)
- 256 opcodes via MODE=1 → 128 give `0x00`, 128 give `0x15`
  - Split is based on **last SDI bit** during MODE=1 (bit 7 of command)
  - Bit 7 = 0 → response `0x15`; bit 7 = 1 → response `0x00`
  - **Not a real command response — just SDI leaking into readout**
- TEST 7 (SDO observation): MODE=0 → SDO oscillates **1,0,1,0** (fixed pattern);
  MODE=1 → SDO = 0 always

#### Phase 5: bitbang_isp6.py — Correct 3-state ISP protocol (2026-03-11)

**THE BREAKTHROUGH.** Using the proper IDLE→SHIFT→EXECUTE state machine
from the 1996 Data Book (not JTAG!), the chip responds to all commands:

| Test | Result | Meaning |
|------|--------|---------|
| Device ID | 0x00 (bug) | get_id() used MODE=H; fix: MODE=L for shift-out |
| **FLOWTHRU** | **0xA5** | **ISP state machine ACCEPTS COMMANDS!** |
| UBE | Executed | Bulk erase ran (300ms wait) |
| **Fuse read** | **0x3FFFFFFFFF** | **Chip returns fuse data!** (erased = all 1s) |
| ERALL | Executed | Erase-all ran as fallback |
| FLOWTHRU post-erase | 0xA5 | Still working after erase |

**Fuse readback (rows 0, 1, 50, 101):**
- All rows: HIGH = `0x3FFFFFFFFF`, LOW = `0x3FFFFFFFFF`
- Pattern: `0011_1111...1111` (38 ones, 2 leading zeros) = erased state
- The 2 leading zeros likely mean only 38 of 40 bits per half are fuses

**get_id() bug**: MODE=H during shift-out causes SDO=SDI bypass (always 0).
Fix applied: Phase 1 (MODE=H, SDI=L, 1 clock) loads ID, Phase 2 (MODE=L, 7 clocks)
shifts it out. **Needs re-run to confirm 0x15.**

### Security Fuse — Status: LIKELY CLEAR (or UBE worked!)

The chip responds to FLOWTHRU, UBE, ADDSHFT, VER/LDH, VER/LDL, DATASHFT,
and ERALL — **all ISP commands work**. Fuse data reads back as `0x3FFFFFFFFF`
(erased state).

Either:
1. The security fuse was never set (previous "locked" conclusion was wrong protocol)
2. UBE successfully erased the security fuse along with everything else
3. Both — wrong protocol led to wrong conclusion

**If the chip IS security-locked**, the fallback options are:
- **UBE (00011)** — "The only way to erase the security cell is to perform
  a bulk erase" (1996 Data Book). UBE erases EVERYTHING including security.
- **Elevated voltage** on ispEN or RESET (12V VPROG)
- **Blank chip** — try an unprogrammed ispLSI 2032
- **ispLEVER/ispVM** — proprietary tools may know the correct IR mapping

## JTAG Pins (V/VL/E variants)

Standard 4-wire JTAG: TCK, TDI, TDO, TMS

## Legacy ISP Pins (all variants)

| Pin | 44-TQFP | Function (ISP mode) | Function (normal) |
|-----|---------|--------------------|--------------------|
| ispEN | 7 | Enable ISP (active low) | NC |
| SDI/IN0 | 8 | Serial data in | Dedicated input |
| SDO/IN1 | 18 | Serial data out | Dedicated input |
| MODE | 30 | ISP state control | NC |
| SCLK/Y2 | 27 | Serial clock | Clock Y2 |

## TQFP44 → DIP Adapter Wiring

Generic Chinese TQFP adapter (~1 лв).  Dual-sided PCB:
- **Front (0.8mm pitch)**: TQFP 32–64 pin
- **Back (0.5mm pitch)**: TQFP up to 100 pin

**No pinout table is provided** — user must create their own mapping for each chip!
Pin 1 is **top-left** on TQFP44.

![TQFP44 adapter](media/tqfp44_adapter.jpg)

The adapter has 64 holes but only 44 are used.  Each side has a gap of 5 unused holes.
Sides 1–2: gap at end; sides 3–4: gap at start (chip centered, traces route outward).

| Chip pins | Adapter holes | Offset | Gap position     |
|-----------|---------------|--------|------------------|
|  1 – 11   |  1 – 11       | +0     | end (12–16)      |
| 12 – 22   | 17 – 27       | +5     | end (28–32)      |
| 23 – 33   | 38 – 48       | +15    | start (33–37)    |
| 34 – 44   | 54 – 64       | +20    | start (49–53)    |

### FT2232H → Adapter Wiring (8 wires)

| Chip pin | Adapter | Signal        | FT2232H          |
|----------|---------|---------------|------------------|
|  6, 28   |  6, 43  | VCC           | +5V              |
|  7       |  7      | ispEN         | ADBUS5 (was GND) |
|  8       |  8      | SDI (TDI)     | ADBUS1           |
| 17, 39   | 22, 59  | GND           | GND              |
| 18       | 23      | SDO (TDO)     | ADBUS2           |
| 27       | 42      | SCLK (TCK)    | ADBUS0           |
| 29       | 44      | RESET/Y1      | ADBUS4 (nSRST)  |
| 30       | 45      | MODE (TMS)    | ADBUS3           |

## OpenOCD Quick Test

```bash
# Plain ispLSI 2032 (irlen=8):
openocd -f ../../ft2232h/ft2232h_smooker.cfg \
    -c "ftdi layout_signal nSRST -data 0x0010 -oe 0x0010" \
    -c "adapter speed 1000; transport select jtag" \
    -c "jtag newtap auto0 tap -irlen 8 -expected-id 0 -ircapture 0x15 -irmask 0x03" \
    -c "init"

# V/VL/E variants (irlen=5):
openocd -f ../../ft2232h/ft2232h_smooker.cfg \
    -c "adapter speed 1000; transport select jtag" \
    -c "jtag newtap auto0 tap -irlen 5" \
    -c "init"
```

## Speed Grades

| Grade | fmax (MHz) | tpd (ns) |
|-------|-----------|----------|
| -180 | 180 | 5.0 |
| -150 | 154 | 5.5 |
| -135 | 137 | 7.5 |
| -110 | 111 | 10.0 |
| -80 | 84 | 15.0 |

## vs M4A3-64/32

|             | ispLSI2032          | M4A3-64/32     |
|-------------|---------------------|----------------|
| Macrocells  | 32 (8x4)           | 64 (4x16)      |
| IR length   | **8 bits** (plain)  | 10 bits        |
| Blocks      | 8 GLB x 4 MC       | 4 PAL x 16 MC  |
| GLB inputs  | 18                  | 33             |
| VCC         | 5V or 3.3V (V/VL)  | 3.3V           |
| ISP         | Legacy or IEEE 1532 | IEEE 1532      |
| Fuse access | **Working** (3-state ISP, v6) | Fully decoded  |
| fmax        | 180 MHz             | 250 MHz        |

## TODO

- [x] **Identify exact variant**: ispLSI 2032-135LT44 (5V, 137MHz, plain 2032)
- [x] Desolder from donor PCB (Cognex TURBO ACR/M/ALRM 2.0)
- [x] Mount on TQFP44→DIP adapter
- [x] **JTAG scan** — chain works, BYPASS OK, **no standard IDCODE** (smooker wins the bet!)
- [x] **Determine actual IR length** — **8 bits!** (bit-bang probed, NOT 5 like V/VE)
- [x] **DR length** — 8 bits
- [x] **V/VE ISC opcodes don't work** — wrong IR length (5-bit opcodes in 8-bit IR)
- [x] **Brute-force all 256 IR opcodes** with irlen=8 — all identical DR
- [x] **Bit-bang probing** — 4 protocol variants, 256 opcodes each:
  - JTAG standard (OpenOCD): all opcodes → same 8-bit DR
  - Patent-based (MODE=0 shift, MODE=1 execute): all → `0x15`
  - MODE=1 commands + MODE=0 read: response depends only on last SDI bit
  - Multi-phase (cmd+addr+data): no change
- [x] **ispEN toggle** — moved to ADBUS5 for proper HIGH→LOW entry, no effect
- [x] **External PSU** — 5V phone charger (FT2232H 5V too weak, gives wrong reads!)
- [x] **SDO analysis** — reads 0x15 on MODE=0, always 0 on MODE=1
- [x] **0x15 = DEVICE ID** — confirmed by 1996 Data Book p.2-185 (chip IS responding!)
- [x] ~~CONCLUSION: SECURITY FUSE IS SET~~ — **RETRACTED, re-tested with v6: chip responds!**
- [x] **1996 Lattice Data Book found!** — full ISP protocol documented (Section 8, pp.8-1..8-30)
- [x] **ISP instruction set decoded** — 5-bit commands, UBE=00011 erases entire device incl. security
- [x] **Security fuse clearing**: "The only way to erase the security cell is to perform a bulk erase (UBE)"
- [x] **ispLSI 2032 register sizes**: Address SR=102 bits, Data SR=80 bits, Total=8160 cells
- [x] **bitbang_isp6.py — correct 3-state ISP protocol — WORKS!**
  - Goto_IDLE → Get_ID (bug: returned 0x00, fix applied: MODE=L for shift-out)
  - Change_State (HH transition) between IDLE/SHIFT/EXECUTE
  - 5-bit commands via Shift_Command (MODE=L, LSB first)
  - Proper register widths: 102-bit address, 40-bit data per half
- [x] **FLOWTHRU (01110) = 0xA5** — ISP state machine ACCEPTS COMMANDS!
- [x] **UBE (00011) via 3-state ISP** — executed successfully (300ms wait)
- [x] **VER/LDH + VER/LDL** — returns fuse data! 0x3FFFFFFFFF per half (erased state)
- [x] **ADDSHFT + 102-bit address** — rows 0, 1, 50, 101 all read back OK
- [ ] **Re-test Get_ID** — fix applied (MODE=L for shift-out), needs re-run to confirm 0x15
- [ ] If UBE works on secured chip: full read-back, then program test pattern
- [ ] Try with a blank (unprogrammed) ispLSI 2032 chip
- [ ] Try bulk erase with elevated voltage (VPROG ~12V) as fallback

## ISP Instruction Set (from 1996 Lattice Data Book, Table 4, p.8-11)

Source: `docs/1996_Lattice_Data_Book.pdf` (61MB, 959 pages, from bitsavers.org)

| Instruction | Operation | Description |
|------------|-----------|-------------|
| 00000 | NOP | No operation |
| 00001 | ADDSHFT | Address Register Shift (from SDI) |
| 00010 | DATASHFT | Data Register Shift (into/out of data serial SR) |
| **00011** | **UBE** | **User Bulk Erase: Erase entire device (incl. security!)** |
| 10000 | ERALL | Erase entire device including UES |
| 00100 | GRPBE | GRP Bulk Erase (GRP array only) |
| 00101 | GLBBE | GLB Bulk Erase (GLB array only) |
| 00110 | ARCHBE | Architecture Bulk Erase (arch + I/O config only) |
| 00111 | PRGMH | Program High Order Bits |
| 01000 | PRGML | Program Low Order Bits |
| **01001** | **PRGMSC** | **Program Security Cell (one-way, blocks verify/load)** |
| 01010 | VER/LDH | Verify/Load High Order Bits |
| 01011 | VER/LDL | Verify/Load Low Order Bits |
| 01110 | FLOWTHRU | Bypass (SDI→SDO direct) |
| 10010 | VE/LDH | Verify Erase/Load High Order |
| 10011 | VE/LDL | Verify Erase/Load Low Order |
| 01111 | PROGUES | Program UES (User Electronic Signature) |
| 10001 | VERUES | Verify UES |

### ISP Timing (Table 5, p.8-12, ispLSI 1000E/2000/3000/6000)

| Parameter | Description | Min | Typ | Max | Units |
|-----------|-------------|-----|-----|-----|-------|
| Vccp | Programming Voltage | 4.75 | 5.0 | 5.25 | V |
| tpwp | Programming Pulse Width | 80 | — | 160 | ms |
| **tbew** | **Bulk Erase Pulse Width** | **200** | — | — | **ms** |
| tpwv | Verify Pulse Width | 20 | — | — | µs |
| tsu1 | Setup Time, ISP state machine | 0.1 | — | — | µs |
| tsu2 | Setup Time, Program/Erase Cycle | 200 | — | — | µs |
| tclkh | Clock Pulse Width High/Low | 0.5 | — | — | µs |
| trst | Reset Time from Valid Vcc | 45 | — | — | µs |

### ISP 3-State Machine Protocol (Section 8, pp.8-1..8-38)

**The plain ispLSI 2032 does NOT use IEEE 1149.1 JTAG TAP controller!**
It uses Lattice's proprietary 3-state ISP state machine, controlled by MODE + SDI.
The "8-bit IR" measured via JTAG probing is irrelevant — wrong protocol entirely.

The 3-state machine (Figure 3, p.8-2):

```
           HL            HH             HH
    ┌──→ IDLE/ID ───→ SHIFT ───→ EXECUTE
    │    (read ID)   (commands)   (run cmd)
    │     HL↺          LX↺          LX↺
    └─────HL───────────┘      └──HL──┘

Transitions on rising edge of SCLK:
  H = HIGH, L = LOW, X = don't care
  First letter = MODE, second = SDI
```

**State transitions:**
| From | MODE | SDI | To | Purpose |
|------|------|-----|----|---------|
| any | H | L | **IDLE** | Reset / stay idle |
| IDLE | H | H | **SHIFT** | Start loading commands |
| SHIFT | L | X | **SHIFT** | Clock data in/out (shift) |
| SHIFT | H | H | **EXECUTE** | Run loaded command |
| SHIFT | H | L | **IDLE** | Abort to idle |
| EXECUTE | L | X | **EXECUTE** | Continue execution (clocks for shift cmds) |
| EXECUTE | H | H | **EXECUTE** | Stay (unused) |
| EXECUTE | H | L | **IDLE** | Done, return to idle |

### Pin-Level Procedures (from pp.8-32..8-33)

**Goto_IDLE** — reset to idle from any state:
```
MODE=H, SDI=L → wait tsu → SCLK↑ → wait tclkh → SCLK↓
```

**Get_ID** — read 8-bit device ID (in IDLE state, NO command needed!):
```
MODE=H, SDI=L                    ← HL = stay in IDLE
SCLK↑, wait tclkh, SCLK↓       ← first clock loads ID
read SDO → bit[0]               ← LSB first!
repeat 7 more times:
  SCLK↑, wait, SCLK↓, read SDO → bit[1..7]
Result: 0x15 = 00010101 for ispLSI 2032
```

**Change_State** — transition to next state (IDLE→SHIFT or SHIFT→EXECUTE):
```
MODE=H, SDI=H → wait tsu        ← HH = advance
SCLK↑ → wait th
MODE=L, SDI=L → wait tclkh      ← settle into new state
SCLK↓
```

**Shift_Command** — shift 5-bit instruction (in SHIFT state):
```
MODE=L                           ← MODE low = data shifting
for bit 0..4 (LSB first):
  SDI = command_bit[i]
  wait tsu
  SCLK↑ → wait tclkh → SCLK↓
```

**Shift_Data_In** — shift N bits into device (in EXECUTE state after ADDSHFT/DATASHFT):
```
MODE=L
for bit 0..N-1:
  SDI = data_bit[i]
  wait tsu
  SCLK↑ → wait tclkh → SCLK↓
```

**Shift_Data_Out** — shift N bits out (in EXECUTE state after VER/LDH etc.):
```
MODE=L
for bit 0..N-1:
  SCLK↑ → wait tclkh → SCLK↓
  read SDO → data_bit[i]
```

**Execute_Command** — start execution (for PRGM/ERASE/VERIFY):
```
MODE=L, SDI=L → wait tsu
SCLK↑ → wait twh → SCLK↓
```

### Complete Programming Sequence (one row)

```
--- Enter ISP mode ---
1. ispEN = LOW, wait trst (45 µs)

--- Read Device ID (verify chip) ---
2. Goto_IDLE
3. Get_ID → expect 0x15

--- Bulk Erase (required before programming) ---
4. Change_State (IDLE → SHIFT)
5. Shift_Command: UBE = 00011 (5 bits, LSB first: 1,1,0,0,0)
6. Change_State (SHIFT → EXECUTE)
7. Execute_Command + Wait tbew (200 ms)
8. Change_State (EXECUTE → back, via IDLE)

--- Program row N ---
9.  Change_State (→ SHIFT)
10. Shift_Command: ADDSHFT = 00001 (LSB first: 1,0,0,0,0)
11. Change_State (SHIFT → EXECUTE)
12. Shift_Data_In: 102-bit address (walking-1 selects row)
13. Change_State (EXECUTE → SHIFT, via HH then HL→IDLE→HH→SHIFT... or direct)

14. Shift_Command: DATASHFT = 00010 (LSB first: 0,1,0,0,0)
15. Change_State (SHIFT → EXECUTE)
16. Shift_Data_In: 40-bit HIGH order data
17. Change_State (→ SHIFT)

18. Shift_Command: PRGMH = 00111 (LSB first: 1,1,1,0,0)
19. Change_State (SHIFT → EXECUTE)
20. Execute_Command + Wait tpwp (80-160 ms)
21. Change_State (→ SHIFT)

22. Shift_Command: DATASHFT = 00010
23. Change_State (SHIFT → EXECUTE)
24. Shift_Data_In: 40-bit LOW order data
25. Change_State (→ SHIFT)

26. Shift_Command: PRGML = 01000 (LSB first: 0,0,0,1,0)
27. Change_State (SHIFT → EXECUTE)
28. Execute_Command + Wait tpwp (80-160 ms)

29. Repeat 9-28 for all 102 rows

--- Exit ISP mode ---
30. Goto_IDLE
31. ispEN = HIGH
```

### Verification Sequence (one row)

```
1. Shift_Command: ADDSHFT → Execute → Shift 102-bit address
2. Shift_Command: VER/LDH = 01010 → Execute + wait tpwv (20 µs)
3. Shift_Command: DATASHFT → Execute → Shift_Data_Out 40-bit HIGH
4. Compare with expected data
5. Shift_Command: VER/LDL = 01011 → Execute + wait tpwv
6. Shift_Command: DATASHFT → Execute → Shift_Data_Out 40-bit LOW
7. Compare with expected data
```

### Register Sizes (Table 8, p.8-19)

| Register | ispLSI 2032 |
|----------|-------------|
| Address SR | **102 bits** |
| Data SR (High Order) | **40 bits** (fuses 0-39) |
| Data SR (Low Order) | **40 bits** (fuses 40-79) |
| Data SR Total | **80 bits** |
| Device ID | **8 bits** (0x15) |
| Command Register | **5 bits** |
| Total E²CMOS cells | **8,160** |

### Key Insight: NOT JTAG!

The plain ispLSI 2032 uses a **proprietary 3-state ISP state machine**, not
IEEE 1149.1 JTAG. The V/VL/E/VE variants added JTAG TAP support later.

The previous probing sessions tried both JTAG and ISP protocols, but may not
have followed the exact 3-state machine sequence described above. Specifically:
- The HH transition (MODE=H + SDI=H + clock) to move between states
- The 5-bit command shifting with MODE=L
- The separate ADDSHFT/DATASHFT execute phases with correct bit counts
- The proper timing (tsu=0.1µs, tclk=0.5µs, tpwp=80ms, tbew=200ms)

The "8-bit IR" measured via JTAG was likely the device ID (0x15) being read
back through the JTAG bypass register, not a real IR length measurement.
