# M4A3-64/32 Open-Source Workflow

From Verilog to programmed chip — without ispLEVER.

---

## Toolchain Overview

```
  Verilog (.v)
      |
      v
 +---------+
 | iverilog |  Simulation & verification
 | + vvp    |  Status: INSTALLED
 +---------+
      |
      v
 +---------+
 |  Yosys   |  Synthesis: Verilog -> gate-level netlist
 |          |  Status: BUILDING (git submodule)
 +---------+
      |
      v
  BLIF / JSON netlist
      |
      v
 +---------+
 |  m4afit  |  Fitter: netlist -> fuse map (OUR TOOL, to be written)
 |          |  Maps gates to PAL blocks, macrocells, product terms
 +---------+  Status: PLANNED (after fuse map RE)
      |
      v
  JEDEC (.jed)
      |
      v
 +---------+
 | jed2svf  |  Convert JEDEC fuse map to SVF JTAG commands
 |          |  (or program directly via ISC protocol)
 +---------+  Status: PLANNED
      |
      v
  SVF (.svf)
      |
      v
 +---------+
 | OpenOCD  |  JTAG programming via FTDI UM232H
 | + UM232H |  Status: WORKING
 +---------+
      |
      v
  M4A3 CPLD programmed!
```

---

## Step-by-Step

### 1. Write Verilog

```bash
cd rtl/
vim blinky.v
```

Design constraints for M4A3-64/32:
- Max 64 macrocells (4 blocks x 16)
- Max 32 I/O pins
- 2 global clocks (CLK0/I0, CLK1/I1)
- 5 product terms per macrocell (borrowable from neighbors)
- D or T flip-flops, no RAM, no DSP

### 2. Simulate

```bash
make sim        # compile + run testbench
make wave       # show gtkwave command
```

Verify logic before synthesis. Fix bugs here — iteration is free.

### 3. Synthesize (Yosys)

```bash
make synth      # Yosys: Verilog -> BLIF netlist
```

Yosys converts Verilog to a technology-independent gate netlist.
For PAL/CPLD targets, we need sum-of-products form:

```
yosys -p "read_verilog blinky.v; synth -top blinky; abc -sop; write_blif blinky.blif"
```

The `-sop` option tells ABC to produce sum-of-products (AND-OR)
instead of LUT mapping — this matches the PAL architecture directly.

### 4. Fit (m4afit — to be written)

```bash
make fit        # m4afit: BLIF -> JEDEC
```

The fitter maps the gate netlist onto M4A3 hardware:
1. Assign equations to PAL blocks and macrocells
2. Allocate product terms (5 per macrocell, borrow if needed)
3. Route through Central Switch Matrix
4. Configure macrocells (D/T FF, polarity, clock, OE)
5. Map I/O pins through Output/Input Switch Matrices
6. Generate fuse map as JEDEC file

This is the piece that requires reverse-engineering the fuse map first.

### 5. Program

```bash
make program    # OpenOCD: SVF -> JTAG -> CPLD
```

Two options:
- **SVF**: convert JEDEC to SVF, play through OpenOCD's SVF player
- **Direct ISC**: use OpenOCD TCL to shift fuse data via ISC protocol

### 6. Verify (readback)

```bash
make readback   # OpenOCD: read fuse map from chip via ISC_READ
make verify     # compare readback against JEDEC file
```

---

## Fuse Map Reverse Engineering

The fitter (step 4) requires knowledge of the fuse map. To obtain it:

### What We Have

- IEEE 1532 ISC protocol fully decoded from BSDL
- ISC_READ can dump all 30,618 fuses (80 rows x 378 + 1 config row)
- Complete dump takes ~200ms via JTAG
- EEPROM conditioning patterns reveal internal array structure

### The Plan

```
Phase 1: Baseline
  - Read blank chip (all fuses should be 1)
  - Record as reference

Phase 2: Probe Designs (30-50 designs)
  - Each probe tests ONE feature change
  - Program via ispLEVER SVF (one last time!)
  - Read back fuse map via ISC_READ
  - Diff against blank/previous

  Probe sequence:
    a) Single AND gate:     pin A0 & A1 -> B0
    b) Move output:         pin A0 & A1 -> B1    (diff = output routing)
    c) Move input:          pin A2 & A1 -> B0    (diff = input routing)
    d) Change gate:         pin A0 | A1 -> B0    (diff = product term)
    e) Add flip-flop:       registered output     (diff = macrocell config)
    f) Change clock:        CLK0 vs CLK1          (diff = clock select)
    g) Cross-block:         A0 & C0 -> B0         (diff = central switch matrix)
    h) Product term borrow: 6+ inputs on one cell (diff = logic allocator)

Phase 3: Build Fuse Database
  - Correlate bit positions with features
  - Document as machine-readable format

Phase 4: Write m4afit
  - Input: BLIF netlist from Yosys
  - Output: JEDEC fuse file
  - Algorithm: greedy placement + routing
```

---

## Make Targets

| Target | Tool | Status | Description |
|--------|------|--------|-------------|
| `make sim` | iverilog + vvp | WORKING | Compile and simulate |
| `make wave` | gtkwave | WORKING | Show waveform viewer command |
| `make synth` | Yosys | BUILDING | Synthesize to gate netlist |
| `make fit` | m4afit | PLANNED | Fit netlist to M4A3 fuse map |
| `make jedec` | m4afit | PLANNED | Generate JEDEC file |
| `make svf` | jed2svf | PLANNED | Convert JEDEC to SVF |
| `make program` | OpenOCD | WORKING | Program chip via JTAG |
| `make readback` | OpenOCD | PLANNED | Dump fuse map from chip |
| `make verify` | diff | PLANNED | Verify programmed vs expected |
| `make clean` | - | WORKING | Remove generated files |

---

## File Structure

```
lattice_m4a_openocd/
  rtl/                  Design files
    blinky.v              First test design
    blinky_tb.v           Testbench
    Makefile              Build targets
  openocd/              JTAG programming
    go.sh                 JTAG scan script
    um232h_smooker_6010.cfg  FTDI adapter config
  yosys/                Synthesis tool (git submodule)
  docs/                 Documentation
    M4A3_architecture.md  Architecture & block diagrams
    M4A3-64_32_specs.md   Electrical specs & pinout
    M4A3_ISC_protocol.md  ISC read/write protocol
    WORKFLOW.md           This file
    M4A5-64_32-6JC.pdf    MACH 4 datasheet
  M4A3_64_32_XXVC.bsdl  BSDL model (3.3V, ISC)
  BSDLM4-643244PinTQFP.BSM  BSDL model (5V, legacy)
```

---

*"kato za beli hora, bez da polzvame typ, nekadyren uzhasen windows"*
