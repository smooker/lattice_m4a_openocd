# ispLSI 2032 — Fuse Map Reverse Engineering Notes
## Extracted from ispLEVER 5.0 (wine32)

Source: `/home/claude-agent/work/isplever5/.wine/drive_c/ispTOOLS5_0/`

---

## 1. Device Basics (from Data Book + ISP spec)

| Parameter | Value |
|-----------|-------|
| Device ID | 0x15 (00010101) |
| Family | pLSI/ispLSI 2000 |
| Address SR | 102 rows |
| Data SR | 80 bits (40 HIGH + 40 LOW) |
| Total cells | 8,160 |
| UES size | 160 bits |
| GLBs | 8 (A0-A7) |
| Macrocells/GLB | 4 |
| Total macrocells | 32 |
| Inputs/GLB | 18 (from GRP) |
| Product terms/GLB | 20 |
| ORP pools | 2 (16 I/O each) |
| Package (our chip) | 44-TQFP |

---

## 2. Fuse Map Physical Layout

From Data Book Table 8-9 (page 8-19):

```
JEDEC address → Physical location:
  L(row*80 + bit)  →  Row [row], Bit [bit]

  Bits  0-39  = HIGH order shift register
  Bits 40-79  = LOW order shift register

  Bits 38,39 (HIGH) and 78,79 (LOW) = always 0 (not fuses)
  → 38 real fuse bits per half, 76 per row
```

### Row Map (from our scan, v1.3):
```
Row   0-1  : Normal fuses (GRP/GLB)          2 rows
Row   2    : ARCHITECTURE (global config)     1 row     ← 7 stuck bits/half
Rows  3-42 : Normal fuses (GRP/GLB)         40 rows
Rows 43-58 : ARCHITECTURE (ORP/IOC config)  16 rows    ← 7 stuck bits/half
Rows 59-98 : Normal fuses (GRP/GLB)         40 rows
Row  99    : ARCHITECTURE (global config)     1 row     ← 7 stuck bits/half
Rows 100-101: Normal fuses (GRP/GLB)          2 rows
─────────────────────────────────────────────────────
Total: 84 normal + 18 architecture = 102 rows
```

### JEDEC Fuse Ranges:
```
Rows  0-1  : L000000 - L000159    (normal)
Row   2    : L000160 - L000239    (arch: global)
Rows  3-42 : L000240 - L003439    (normal)
Rows 43-58 : L003440 - L004719    (arch: ORP/IOC)
Rows 59-98 : L004720 - L007919    (normal)
Row  99    : L007920 - L007999    (arch: global)
Rows 100-101: L008000 - L008159   (normal)
```

---

## 3. Architecture Row Stuck Bits

Our scan found 7 non-programmable bit positions per half on arch rows:

```
Stuck positions: [7, 8, 17, 18, 27, 28, 37]
Pattern:          pair   pair    pair   single
Spacing:            10     10      9
```

These are NOT E2CMOS fuses — they are **MUX readback / configuration state bits**.

Exception: **Row 56 HIGH half** — only [7, 8, 17, 18, 27, 28] (missing bit 37).
→ Special pin without slew rate control (likely Y2/SCLK dedicated input).

Programmable arch bits per half: 38 - 7 = **31 real fuses** on arch rows.

---

## 4. Named Fuse Signals (from p2032.sdf)

Source: `ispTOOLS5_0/ispcomp/config/p2032.sdf`

### 4.1 Per-Macrocell Fuses (x4 per GLB, x8 GLBs = 32 macrocells)

| Fuse Name | Bits | Function |
|-----------|------|----------|
| `XnMFUSE0`, `XnMFUSE1` | 2 | XOR input mux (feedback/PT/VCC/GND) |
| `DnFUSE` | 1 | Register bypass (1=combinational, 0=registered) |
| `OnFUSE0`, `OnFUSE1` | 2 | Output source mux |
| **Subtotal per macrocell** | **5** | |
| **Total 32 macrocells** | **160** | |

### 4.2 Per-GLB Fuses (x8 GLBs)

| Fuse Name | Bits | Function |
|-----------|------|----------|
| `LC_CLK_FUSE0`-`LC_CLK_FUSE3` | 4 | Clock source mux (CLK0/CLK1/CLK2/PT) |
| `LC_CLKINV` | 1 | Clock polarity inversion |
| `RST0`, `RST1` | 2 | Reset source mux |
| `I16_FUSE0`, `I16_FUSE1` | 2 | Cross-GLB input 16 mux |
| `I17_FUSE0`, `I17_FUSE1` | 2 | Cross-GLB input 17 mux |
| `LCOEFUSE` | 1 | Logic cell OE enable |
| **Subtotal per GLB** | **12** | |
| **Total 8 GLBs** | **96** | |

### 4.3 Per-IOC (I/O Cell) Fuses (x32 I/O cells)

| Fuse Name | Bits | Function |
|-----------|------|----------|
| `IOOEFUSE0`, `IOOEFUSE1` | 2 | OE source mux (GOE0/GOE1/PTOE/VCC) |
| `IOOEPFUSE0` | 1 | OE polarity |
| `IOSIDFUSE0`-`IOSIDFUSE7` | 8 | ORP routing / signal ID |
| `IOOINVFUSE` | 1 | Output inversion |
| `SLEWFUSE` | 1 | Slew rate (0=fast, 1=slow) |
| **Subtotal per IOC** | **13** | |
| **Total 32 IOC** | **416** | |

### 4.4 Global Fuses

| Fuse Name | Bits | Function |
|-----------|------|----------|
| `RESETFUSE` / `RESET_POLARITY_FUSE` | 1 | Global reset polarity |
| ISP enable | 1 | Prevents use of ISP pins |
| ISP_EXCEPT_Y2 | 1 | ISP except Y2 pin |
| Y1_AS_RESET | 1 | Y1/RESET as reset (default=ON) |
| KEEP_XOR | 1 | Preserve user XOR |
| SECURITY | 1 | Security cell (program last!) |
| POWER | 2 | Power mode (Low/MedLow/MedHigh/High) |
| VOLTAGE | 1 | VCC/VCCIO select |
| OPENDRAIN (global) | 1 | Global open drain |
| OUTDELAY | 1 | Output delay |
| PULLUP (global) | 2 | Global pull-up (OFF/UP/DOWN/HOLD) |
| SLEWRATE (global) | 1 | Global slew rate default |

---

## 5. Hypothesis: Stuck Bits to Fuse Names

### ORP/IOC rows (43-58): 16 rows x 2 halves = 32 I/O cells

Each I/O cell has 7 non-fuse config bits at positions [7, 8, 17, 18, 27, 28, 37]:

```
Bit [7,8]   → IOOEFUSE0, IOOEFUSE1    (OE source mux, 2 bits)
Bit [17,18] → OnFUSE0, OnFUSE1        (Output config mux, 2 bits)
Bit [27,28] → XnMFUSE0, XnMFUSE1      (XOR mux, 2 bits)
Bit [37]    → SLEWFUSE                 (Slew rate, 1 bit)
```

OR alternatively (needs verification by test):
```
Bit [7,8]   → IOOEFUSE0, IOOEFUSE1    (OE source)
Bit [17,18] → I16_FUSE0, I16_FUSE1    (cross-GLB input mux)
Bit [27,28] → LC_CLK_FUSE0/1          (clock mux, first 2 of 4 bits)
Bit [37]    → SLEWFUSE                 (slew rate)
```

**Row 56 HIGH missing bit 37**: Pin Y2/SCLK is a dedicated input
— no output buffer, no SLEWFUSE.

### Global rows (2, 99): 2 rows x 2 halves = 4 half-rows of global config

Same stuck bit pattern — reading back current state of global MUX settings:
- Row 2: ISP, ISP_EXCEPT_Y2, Y1_AS_RESET, SECURITY, RESETFUSE, ...
- Row 99: POWER, VOLTAGE, global PULLUP, global SLEWRATE, ...

---

## 6. GRP/CSM Structure (from TDF)

The **Central Switch Matrix** (CSM = GRP) has two halves: **PMXT** (top) and **PMXB** (bottom).

```
Each GLB has 18 inputs (I0-I17)
Each input selects from GRP via a 4:1 mux (2 fuse bits)
→ 18 inputs x 2 bits x 8 GLBs = 288 CSM fuse bits

Plus: each AND gate has 36 programmable connections
      (18 inputs x true + complement)
→ 20 PTs x 36 = 720 AND fuses per GLB
→ 720 x 8 GLBs = 5,760 AND array fuses
```

### Normal row fuse budget estimate:
```
AND array: 5,760 fuses
CSM/GRP:     288 fuses (or more if multi-stage)
PT sharing:  ~48 fuses (demux controls)
Total:     ~6,096 fuses in normal rows
Actual:    84 rows x 76 bits = 6,384 fuses
Difference: 288 → feedback/routing fuses
```

---

## 7. AND Array Layout (from SDF primitives)

```
Per GLB: 20 product terms (And0-And19)
Each PT: 18 inputs x 2 (true+complement) = 36 fuse bits per PT

Product term assignment (per macrocell):
  MC0: PT0-PT4   (5 PTs, PT0 has demux)
  MC1: PT4-PT8   (5 PTs, PT4 has demux, shared with MC0)
  MC2: PT8-PT12  (5 PTs, PT8 has demux)
  MC3: PT12-PT19 (8 PTs, PT12+PT13+PT19 have demux)

Demux positions: PT0, PT4, PT8, PT12, PT13, PT19
→ Product term stealing/sharing between neighboring macrocells
```

---

## 8. Key Source Files in ispLEVER

| File | Size | Contents |
|------|------|----------|
| `ispcomp/config/p2032.sdf` | 75 KB | Master device architecture (binary+strings) |
| `ispcomp/config/p2032a08.tdf` | 26 KB | Timing arcs (speed grade -08) |
| `ispcpld/data/lc2k/l2032_44t.dev` | 2 KB | Pin assignments (44-TQFP) |
| `ispcpld/data/lc2k/2032t44.ddb` | 2 KB | Package graphics/coordinates |
| `ispcpld/bin/fuseasm.exe` | -- | JEDEC generator (reads .tt3 → .jed) |
| `ispcpld/config/plsie.ini` | -- | Schematic attribute IDs |
| `ispcpld/manuals/isplsi_lcs.pdf` | 104 KB | Constraint reference tables |

### fuseasm.exe internals (from strings):
```
Format: stfuse=%ld endfuse=%ld numPT=%d andinc=%d artyp=%s inc=%d
→ Defines fuse array geometry per block
→ .fus files referenced but NOT found on disk (generated dynamically)
```

---

## 9. Selective Erase Commands

| Command | Opcode | Erases |
|---------|--------|--------|
| UBE | 00011 | Everything (all rows + UES + security) |
| ERALL | 10000 | Everything including UES |
| GRPBE | 00100 | GRP array only (normal rows?) |
| GLBBE | 00101 | GLB array only (normal rows?) |
| ARCHBE | 00110 | Architecture + I/O config only (rows 2, 43-58, 99?) |

---

## 10. Verification Plan

### Phase 1: Confirm arch row assignment (ARCHBE test)
- ARCHBE erase → read all 102 rows
- Only rows 2, 43-58, 99 should change to erased state
- Confirms which rows belong to ARCH section

### Phase 2: Map SLEWFUSE (easiest single-bit test)
- Compile in ispLEVER: 1 output with SLOWSLEW=ON
- Compile again: same pin with default FAST
- Diff JEDEC files → identifies bit 37 position

### Phase 3: Map OE mux
- Compile with GOE0 vs GOE1 vs PTOE vs always-on
- Diff → identifies bits [7,8]

### Phase 4: Map output config
- Compile registered vs combinational output
- Diff → identifies bits [17,18] or other pair

### Phase 5: Full AND array walk
- Walking-0 on normal rows to map product term layout per GLB

---

## 11. Pin Map (44-TQFP, from l2032_44t.dev)

```
Pin  5 = Y0 (Clock input)
Pin  7 = ispEN
Pin  8 = SDI / dedicated input IN0
Pin 18 = SDO / dedicated input IN1
Pin 27 = SCLK / Y2 (clock)
Pin 28 = VCC
Pin 29 = RESET / Y1 (clock/reset)
Pin 30 = MODE
Pin 39 = GND
Pin 40 = GOE (Global Output Enable)

I/O pins: 1-4, 9-16, 19-26, 31-38, 41-44  (32 I/O total)
```

---

## 12. ispLEVER Constraint Names for ispLSI 1K/2K

### Global Constraints
| Constraint | Values | Default |
|------------|--------|---------|
| ISP | ON, OFF | ON |
| ISP_EXCEPT_Y2 | ON, OFF | OFF |
| Y1_AS_RESET | ON, OFF | ON |
| KEEP_XOR | ON, OFF | ON |
| POWER | Low, MedLow, MedHigh, High | High |
| SLEWRATE | SLOW, FAST | FAST |
| PULLUP | OFF, UP, DOWN, HOLD | user set |
| VOLTAGE | VCC, VCCIO | VCCIO |
| SECURITY | ON, OFF | OFF |
| OPENDRAIN | ON, OFF | OFF |
| OUTDELAY | ON, OFF | OFF |

### Per-Pin Constraints
| Constraint | Values | Default |
|------------|--------|---------|
| SLEWRATE | SLOW, FAST | global |
| PULLUP | OFF, UP, DOWN, HOLD | global |
| OSM BYPASS (CRIT) | signal list | None |
| IO TYPES (OPENDRAIN) | ON, OFF | OFF |
