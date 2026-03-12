# ispLSI 2032 Fuse RE — Knowledge Log

## Verified Facts (DO NOT re-test — save EEPROM cycles)

### Device basics
- Device ID: 0x15 — always passes
- FLOWTHRU: 0xA5 — always passes
- Erased state: H=0x3FFFFFFFFF L=0x3FFFFFFFFF — confirmed on rows 0, 50, 101
- Fast vs slow read: match — confirmed on row 0
- Bulk erase works — confirmed multiple times

### Bit boundary (diag-bits, row 0, 100 kHz)
- Bits 0-5 single-bit SET on HIGH and LOW halves: ALL PASS
- Bits 0-5 walking-0 (clear from erased) on HIGH: ALL PASS
- Conclusion: all 38 bits per half are real programmable fuses ON NORMAL ROWS

### Speed sensitivity (diag-speed, row 0)
- Tested at 100/50/20/10/5 kHz — ALL PASS on all patterns
- Conclusion: speed is NOT the issue

### Row isolation (diag-row)
- Row 2 fails ISOLATED (fresh erase, no prior writes) — it's the row, not the sequence
- Rows 0,1,3,4,5 all PASS with same pattern

## FULL SCAN RESULTS (v1.3, 2026-03-12)

### Summary: 84 PASS, 18 FAIL out of 102 rows

### Failing rows (3 groups):
```
Row  2        — lone (global config?)
Rows 43-58    — block of 16 (ORP routing?)
Row 99        — lone (global config?)

Gaps: [41, 1,1,1,1,1,1,1,1,1,1,1,1,1,1,1, 41]
```

### Stuck bit pattern (SAME on almost all failing rows):
```
Stuck positions: [7, 8, 17, 18, 27, 28, 37]
Periodicity:      7,8 ... 17,18 ... 27,28 ... 37
                  = pairs every 10 bits (with <<2 shift: SR positions 9,10,19,20,29,30,39)
```
Exception: Row 56 HIGH half — only [7,8,17,18,27,28] (missing bit 37)

### Fuse map structure hypothesis
```
Rows  0-1     : normal fuses (GLB/GRP?) — 2 rows
Row   2       : ARCHITECTURE config (global) — 1 row
Rows  3-42    : normal fuses (GLB AND array? GRP?) — 40 rows
Rows 43-58    : ARCHITECTURE config (ORP/IO) — 16 rows (= 2 ORPs × 8 GLBs?)
Rows 59-98    : normal fuses (GLB AND array? GRP?) — 40 rows
Row  99       : ARCHITECTURE config (global) — 1 row
Rows 100-101  : normal fuses — 2 rows
```
Normal rows: 84 (= 8 GLBs × 10 rows + 4 GRP rows? or 2×40 + 4?)
Arch rows: 18 (= 16 ORP + 2 global config)

### Stuck bits = NOT fuses
The 7 stuck positions per half are NOT E²CMOS fuses. They are likely:
- MUX select readback (ORP routing, clock select, I/O mode)
- Hardwired configuration bits
- They read the CURRENT state of the routing MUX, not programmable cells
- Erased state (all 1s) = default MUX position

### Architecture from datasheet
- 8 GLBs (A0-A7), 4 macrocells each = 32 total
- Each GLB: 18 inputs from GRP, 20 product terms
- ORP: 2 pools, each connects 4 GLBs (16 outputs) to 16 I/O cells
- I/O cell: input/output/bidir, OE mux (GOE + PTOE), slew rate
- 3 clocks (Y0→CLK0, Y1→CLK1, Y2→CLK2), clock MUX per GLB
- Separate erase: GRPBE, GLBBE, ARCHBE

## Effective fuse geometry
- 84 programmable rows × 38 bits × 2 halves = 6384 real fuses
- 18 architecture rows with 31 fuses + 7 config bits × 2 halves
- Total: 6384 + 18×31×2 = 6384 + 1116 = 7500 fuses + 252 config bits = 7752
- Datasheet says 8160 E²CMOS cells — close enough (diff may be config row + I0/I1)

## Named Fuse Signals (from ispLEVER 5.0 SDF, 2026-03-12)

### Per-IOC (I/O Cell) — 13 fuses each, 32 cells
- IOOEFUSE0/1 (2b): OE source mux (GOE0/GOE1/PTOE/VCC)
- IOOEPFUSE0 (1b): OE polarity
- IOSIDFUSE0-7 (8b): ORP routing / signal ID
- IOOINVFUSE (1b): output inversion
- SLEWFUSE (1b): slew rate

### Per-Macrocell — 5 fuses each, 32 macrocells
- XnMFUSE0/1 (2b): XOR input mux
- DnFUSE (1b): register bypass (comb vs registered)
- OnFUSE0/1 (2b): output source mux

### Per-GLB — 12 fuses each, 8 GLBs
- LC_CLK_FUSE0-3 (4b): clock source mux
- LC_CLKINV (1b): clock polarity
- RST0/1 (2b): reset source mux
- I16_FUSE0/1, I17_FUSE0/1 (4b): cross-GLB input mux
- LCOEFUSE (1b): OE enable

### Stuck bit → fuse name hypothesis
```
Bit [7,8]   → IOOEFUSE0/1     (OE source mux)
Bit [17,18] → OnFUSE0/1       (Output config) or LC_CLK related
Bit [27,28] → XnMFUSE0/1      (XOR mux) or RST0/1
Bit [37]    → SLEWFUSE         (slew rate)
Row 56 HIGH missing [37] = Y2/SCLK pin (no output buffer → no SLEWFUSE)
```

### AND array structure (from SDF)
- 20 PTs per GLB, each 36 fuses (18 inputs × true+complement)
- PT assignment: MC0=PT0-4, MC1=PT4-8, MC2=PT8-12, MC3=PT12-19
- Demux at PT0, PT4, PT8, PT12, PT13, PT19 (product term sharing)

### GRP/CSM structure (from TDF)
- PMXT (top) + PMXB (bottom) halves
- 18 inputs × 4:1 mux (2 bits) × 8 GLBs = 288 CSM fuses
- AND array: 20 PTs × 36 × 8 GLBs = 5,760 fuses

## Full documentation
→ See `ispLSI2032_FUSEMAP_RE.md` in this directory

## Next steps
- [ ] **ARCHBE selective erase** — confirm rows 2, 43-58, 99 are arch section
- [ ] **GRPBE selective erase** — which normal rows are GRP?
- [ ] **GLBBE selective erase** — which normal rows are GLB?
- [ ] Write arch rows with stuck bits masked (set those 7 positions to 1)
- [ ] Walking-0 on normal rows to map AND array / GRP structure
- [ ] Compile something in ispLEVER for 2032 when Gentoo32 is available
