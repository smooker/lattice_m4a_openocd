# US Patent 5,412,260 — Lattice ISP/JTAG Pin Multiplexing

**Full PDF not available for direct download — patent offices block curl.**
To read the original: https://patents.google.com/patent/US5412260A/en

## Bibliographic Data

- **Patent**: US5412260A
- **Title**: Multiplexed control pins for in-system programming and boundary
  scan state machines in a high density programmable logic device
- **Filed**: August 13, 1993
- **Granted**: May 2, 1995
- **Inventors**: Cyrus Y. Tsui, Albert L. Chan, Kapil Shankar, Ju Shen
- **Assignee**: Lattice Semiconductor Corporation

## Abstract

Structure enabling both in-system programming and boundary-scan testing
using only five dedicated pins. A common interface shares control pins
between these two functions, with an ISPEN pin selecting operational mode.

## Core Innovation

Four control pins serve dual purposes:

| ISP Name | JTAG Name | Function |
|----------|-----------|----------|
| MODE | TMS | Mode select / Test mode select |
| SCLK | TCK | Shift clock / Test clock |
| SDI | TDI | Serial data input / Test data input |
| SDO | TDO | Serial data output / Test data output |

Plus **ISPEN** (in-system programming enable) = **5 pins total** instead of 8.

## Two Implementation Approaches

### 1. Separate State Machines
Input/output demultiplexers route signals to either ISP or boundary-scan
state machine based on ISPEN signal state.

### 2. Unified Instruction-Based (IEEE 1149.1)
Single TAP controller state machine executes private instructions
(per IEEE 1149.1-1990 standard) for both programming and testing.
ISC operations are implemented as "private" JTAG instructions.

## Operational Modes

| ISPEN | Clock | Mode |
|-------|-------|------|
| High | — | In-system programming |
| Low | Active | Boundary-scan test |
| Low | Inactive | Normal user operation |

Note: polarity may be inverted in actual products (e.g., 2032VE uses
BSCAN LOW = JTAG active). The key insight is the pin multiplexing.

## Relevance to ispLSI 2032

This patent covers the exact pin multiplexing used in ispLSI 2032:
- The "legacy serial ISP" (SDI/SDO/SCLK/MODE/ispEN) IS a JTAG interface
- The later 2032VE simply renamed the pins to their IEEE 1149.1 names
- Same silicon, same protocol, different marketing
