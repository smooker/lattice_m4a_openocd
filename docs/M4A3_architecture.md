# Lattice ispMACH 4A (M4A3) — Architecture & Fuse Map Analysis

## Overview

The Lattice ispMACH 4000 family (MACH 4) is a **PAL-based CPLD** — fundamentally different
from LUT-based FPGAs. The architecture is a classic sum-of-products (AND-OR) structure
organized into PAL blocks connected by a central switch matrix.

Reference datasheet: `M4A5-64_32-6JC.pdf` (62 pages, covers entire MACH 4 family).

---

## Part Number Decoding

```
M4A3 - 64 / 32 - 7 VC
│       │    │    │  └── Package: VC=44-TQFP, JC=44-PLCC, VC48=48-TQFP
│       │    │    └───── Speed grade: 7.5ns tPD (-5=5ns, -7=7.5ns, -10=10ns, -12=12ns)
│       │    └────────── I/O count: 32 pins
│       └─────────────── Macrocell count: 64 (4 blocks x 16)
└─────────────────────── Family: M4A3=3.3V Advanced, M4A5=5V Advanced
                                 M4=5V legacy, M4LV=3.3V legacy
```

## M4A3-64/32 Block Diagram

```
                        CLK0/I0   CLK1/I1
                           |         |
                           v         v
              +------------------------------------+
              |        Central Switch Matrix        |
              |    (full interconnect between all    |
              |     PAL block outputs & inputs)      |
              +--+--------+--------+--------+-------+
                 |        |        |        |
           +-----+   +---+   +----+   +----+
           v         v        v        v
      +---------+ +---------+ +---------+ +---------+
      | Block A | | Block B | | Block C | | Block D |
      |         | |         | |         | |         |
      | Input   | | Input   | | Input   | | Input   |
      | Switch  | | Switch  | | Switch  | | Switch  |
      | Matrix  | | Matrix  | | Matrix  | | Matrix  |
      |    |    | |    |    | |    |    | |    |    |
      |    v    | |    v    | |    v    | |    v    |
      | AND     | | AND     | | AND     | | AND     |
      | Array   | | Array   | | Array   | | Array   |
      | + Logic | | + Logic | | + Logic | | + Logic |
      | Alloc.  | | Alloc.  | | Alloc.  | | Alloc.  |
      |    |    | |    |    | |    |    | |    |    |
      |    v    | |    v    | |    v    | |    v    |
      | 16      | | 16      | | 16      | | 16      |
      | Macro-  | | Macro-  | | Macro-  | | Macro-  |
      | cells   | | cells   | | cells   | | cells   |
      |    |    | |    |    | |    |    | |    |    |
      |    v    | |    v    | |    v    | |    v    |
      | Output  | | Output  | | Output  | | Output  |
      | Switch  | | Switch  | | Switch  | | Switch  |
      | Matrix  | | Matrix  | | Matrix  | | Matrix  |
      +----+----+ +----+----+ +----+----+ +----+----+
           v           v          v           v
       I/O 0-7     I/O 8-15  I/O 16-23   I/O 24-31
       (8 pins)    (8 pins)   (8 pins)    (8 pins)
```

## Internal Structure — Per PAL Block

### AND Array (Programmable)
- **Rows** = product terms (AND gates)
- **Columns** = input signals (each signal has true + complement = 2 columns)
- Every intersection is a programmable fuse (EEPROM)
- Intact fuse = input connected; blown fuse = input disconnected

### Logic Allocator
- Each macrocell gets **5 dedicated product terms**
- Unused product terms can be **borrowed from neighboring macrocells**
- This is the "Logic Allocator" — redistributes product terms within a block

### Macrocell

```
                    Product Terms (from AND array)
                           |
                    +------v------+
                    |  Fixed OR   |
                    |  (sum of    |
                    |  products)  |
                    +------+------+
                           |
                    +------v------+
              +---->|  XOR gate   |<---- Polarity control
              |     +------+------+
              |            |
              |     +------v------+
              |     |   D/T FF    |<---- Clock (global or PT)
              |     |  (bypass    |<---- Reset (global or PT)
              |     |   for comb) |<---- Preset (global or PT)
              |     +------+------+
              |            |
              |     +------v------+
              |     |  Output     |
              |     |  Select     |---- Registered or combinatorial
              |     +------+------+
              |            |
              |            +-----------> To Output Switch Matrix -> I/O pin
              |            |
              +------------+-----------> Feedback to Central Switch Matrix
```

### Clocking
- **4 global clocks**: CLK0, CLK1, CLK2, CLK3 (dedicated pins, active on both edges)
- **Product term clocks**: any product term can drive the clock input
- **Per-macrocell**: individual clock source + polarity selection

### Output Enable
- **Global OE** pins (directly from package pins)
- **Product term OE**: any product term can control output enable
- **Per-macrocell** OE selection

---

## Fuse Map — Reverse Engineering Clues

### BSDL Programming Registers

From the M4A3 BSDL file (`M4A3_64_32_XXVC.bsdl`), the ISC programming uses two
key shift registers:

| Register | Size | JTAG Instruction |
|----------|------|------------------|
| `ROWREG` | 80 bits | `PRIV003` |
| `COLREG` | 378 bits | `PRIV004`, `PRIV007` |

### The 378 = 384 - 6 Insight

**COLREG[378]** is NOT a random number:

```
378 = 384 - 6
        |     +-- 6 dedicated clock/input pins (not in AND array)
        +-------- Total logical column positions
```

The 6 subtracted signals are the dedicated clock/input pins (CLK0/I0, CLK1/I1,
plus global OE/reset signals) that bypass the programmable AND array and feed
directly into clock generators and control logic.

This means **COLREG holds one row of the AND array fuse pattern** — 378 programmable
fuse bits per product term row.

### ROWREG[80] — Row Addressing

80 bits for row selection/control. For M4A3-64/32:
- 4 blocks x 16 macrocells x 5 product terms = 320 product terms total
- 80 bits likely encodes: row address + block select + control bits

### Programming Model

```
For each product term row:
  1. Shift ROWREG[80]  -> select row (via PRIV003 instruction)
  2. Shift COLREG[378] -> fuse pattern for that row (via PRIV004/PRIV007)
  3. Program pulse
  4. Repeat
```

### JTAG ISC Instructions (from BSDL)

| Instruction | Opcode (10-bit) | Function |
|-------------|-----------------|----------|
| BYPASS | 1111111111 | Standard bypass |
| EXTEST | 0000000000 | Boundary scan external test |
| SAMPLE | 0000000010 | Boundary scan sample |
| IDCODE | 0000000001 | Read 32-bit device ID |
| PRIV003 | — | Access ROWREG[80] |
| PRIV004 | — | Access COLREG[378] (read?) |
| PRIV007 | — | Access COLREG[378] (write?) |
| PRIV00F | — | Access PRIVR00F[5] (control?) |

### Reverse Engineering Strategy

To decode the fuse map, generate "probe" designs — minimal Verilog with one
feature changed at a time:

1. **AND array mapping**: single gate, vary input pin -> see which COLREG bits change
2. **Output routing**: same gate, move output to different pin -> identify Output Switch Matrix bits
3. **Input routing**: same gate, move input to different pin -> identify Input Switch Matrix bits
4. **Macrocell config**: D-FF vs combinatorial, polarity, clock source -> identify config bits
5. **Cross-block routing**: gate spanning two PAL blocks -> identify Central Switch Matrix bits

Each probe produces a JEDEC (.jed) file. Diff the JEDEC files to isolate which
fuses control which feature.

**Target: ~30-50 probe designs should map the entire M4A3-64/32 fuse structure.**

---

## Key Differences: M4 vs M4A3

| Feature | M4 (Vantis legacy) | M4A3 (Lattice advanced) |
|---------|--------------------|-----------------------|
| VCC | 5.0V | 3.3V |
| IR length | 6 bits | 10 bits |
| ISP (In-System Programming) | No | Yes (IEEE 1532) |
| Speed grades | 7.5-18 ns | 5-12 ns |
| JTAG standard | IEEE 1149.1 only | IEEE 1149.1 + 1532 |

---

## Toolchain — Current State

```
 Verilog source
     |
     v
 +----------+
 | iverilog  |  <- simulation & verification (INSTALLED)
 | + vvp     |
 +----------+
     |
     v
 +----------+
 | ispLEVER |  <- synthesis + fitting + JEDEC generation
 | Classic   |     (Windows-only, needs Wine or VM)
 +----------+     archive.org/download/ispLEVER_Classic_Base_1_8
     |
     v
 JEDEC (.jed) -> SVF (.svf) export
     |
     v
 +----------+
 | OpenOCD   |  <- JTAG programming (WORKING)
 | + UM232H  |
 +----------+
     |
     v
   M4A3 CPLD programmed!
```

**Goal**: Replace ispLEVER with an open-source fitter by reverse-engineering the
fuse map from JEDEC files generated by probe designs.

---

## References

- Datasheet: `docs/M4A5-64_32-6JC.pdf` (62 pages, MACH 4 family)
- BSDL (3.3V): `M4A3_64_32_XXVC.bsdl`
- BSDL (5V legacy): `BSDLM4-643244PinTQFP.BSM`
- ispLEVER Classic: archive.org/download/ispLEVER_Classic_Base_1_8
- BSDL source: bsdl.info/details.htm?sid=dbb7399451e3e14088ca59b002289d77
- Project IceStorm (inspiration): reverse-engineered Lattice iCE40 bitstream
