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

### Fuse map structure hypothesis (v1.3, SUPERSEDED by v1.5)
```
OLD hypothesis (WRONG — based on scan only):
Rows  0-1     : normal fuses — 2 rows
Row   2       : ARCHITECTURE config — 1 row
Rows  3-42    : normal fuses — 40 rows
Rows 43-58    : ARCHITECTURE config — 16 rows
Rows 59-98    : normal fuses — 40 rows
Row  99       : ARCHITECTURE config — 1 row
Rows 100-101  : normal fuses — 2 rows
```

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
NOTE: stuck bits are on GRP rows (not ARCH as first assumed) — see v1.5 results.

### AND array structure (from SDF)
- 20 PTs per GLB, each 36 fuses (18 inputs × true+complement)
- PT assignment: MC0=PT0-4, MC1=PT4-8, MC2=PT8-12, MC3=PT12-19
- Demux at PT0, PT4, PT8, PT12, PT13, PT19 (product term sharing)

### GRP/CSM structure (from TDF)
- PMXT (top) + PMXB (bottom) halves
- 18 inputs × 4:1 mux (2 bits) × 8 GLBs = 288 CSM fuses
- AND array: 20 PTs × 36 × 8 GLBs = 5,760 fuses

## SELECTIVE ERASE RESULTS (v1.5, 2026-03-12)

### ARCHBE erased 14 rows: [0,1,2,3,4,5,6, 95,96,97,98,99,100,101]
- Two groups of 7 at each END of the array
- NOT rows 43-58 as hypothesized!
- These are the global config rows (ISP, SECURITY, RESET, CLOCK, POWER, etc.)

### GRPBE erased 21 rows: [43-58, 67,76,85,97,101] + 6 partial [66,81,84,94,96,100]
- Rows 43-58 are GRP! The stuck bits [7,8,17,18,27,28,37] are GRP MUX readback
- Scattered rows beyond 58: possibly GRP crossbar connections to specific GLBs

### GLBBE erased 83 rows: [3-50, 67-101] (most of the chip)
- Includes the main AND array for all 8 GLBs
- Overlaps with both ARCHBE and GRPBE sections

### 8 mystery rows: [59,60,61,62,63,64,65,66] — NOT erased by anything!
- Could be UES (160 bits = 2 rows) — but that's only 2, not 8
- Could be hardwired / read-only configuration
- Needs separate investigation

### Revised fuse map (v1.5):
```
Rows  0-6    : ARCHITECTURE (global config)     7 rows  ← ARCHBE
Rows  7-42   : GLB AND array                   36 rows  ← GLBBE only
Rows 43-58   : GRP routing pool                16 rows  ← GRPBE (has MUX readback bits)
Rows 59-66   : ??? MYSTERY — not erased by any  8 rows  ← UES? hardwired?
Rows 67-94   : GLB AND array                   28 rows  ← GLBBE only
Rows 95-101  : ARCHITECTURE (global config)     7 rows  ← ARCHBE
```

### Erase section overlaps (unexpected!):
```
ARCH ∩ GRP  = [97, 101]
ARCH ∩ GLB  = [3,4,5,6, 95,96,97,98,99,100,101]
GRP  ∩ GLB  = [43-50, 67,76,85,97,101]
Union       = 94 of 102 rows
Uncovered   = [59,60,61,62,63,64,65,66]
```

### Anomalies to investigate:
1. Row 101 MISMATCH during GRPBE write — unreliable data for that row?
2. GLBBE readback shows 0xFFFFFFFFFF (bits 38,39 = 1) — should be 0x3FFFFFFFFF
3. Row 50 reads 0x0000000000 in GLBBE spot-check — stuck bits disappeared?!
4. Significant erase overlaps — sections share rows
5. Partial erases (half-erased rows in GRPBE) — half H=0, half L=erased

## Full documentation
→ See `ispLSI2032_FUSEMAP_RE.md` in this directory

## Next steps
- [x] ~~Selective erase test (ARCHBE/GRPBE/GLBBE)~~ — DONE (v1.5)
- [ ] Investigate mystery rows 59-66 (try UES read/write commands PROGUES/VERUES)
- [ ] Re-run scan on rows 59-66 after fresh UBE to check if they're writable
- [ ] Investigate 0xFFFFFFFFFF readback after GLBBE (bits 38,39 should be 0)
- [ ] Investigate partial erases in GRPBE (half-erased rows)
- [ ] Walking-0 on normal rows to map AND array / GRP structure
- [ ] Compile something in ispLEVER for 2032 when Gentoo32 is available
