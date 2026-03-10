# Makefile for M4A3-64/32 Verilog simulation
# Usage: make sim | make wave | make clean

DESIGN = blinky
TOP    = $(DESIGN)_tb

SRC    = $(DESIGN).v $(TOP).v
VVP    = $(TOP).vvp
VCD    = $(DESIGN).vcd

.PHONY: sim wave clean jedec svf

sim: $(VVP)
	vvp $<

$(VVP): $(SRC)
	iverilog -o $@ $^

wave: sim
	@echo "Run from host: gtkwave /chroot/claude/home/claude-agent/work/lattice_m4a_openocd/rtl/$(VCD)"

jedec:
	@echo "TODO: requires ispLEVER Classic (Wine)"
	@echo "  1. Open ispLEVER, create project for M4A3-64/32-VC"
	@echo "  2. Add $(DESIGN).v as source"
	@echo "  3. Run: Synthesize -> Fit -> JEDEC export"
	@echo "  4. Output: $(DESIGN).jed"

svf: jedec
	@echo "TODO: requires ispLEVER Classic (Wine)"
	@echo "  In ispLEVER: File -> Export -> SVF"
	@echo "  Output: $(DESIGN).svf"
	@echo ""
	@echo "Then program: cd ../openocd && openocd -f um232h_smooker_6010.cfg \\"
	@echo "  -c 'adapter speed 2000; transport select jtag' \\"
	@echo "  -c 'jtag newtap auto0 tap -irlen 10 -expected-id 0x17486157' \\"
	@echo "  -c 'init' -c 'svf ../rtl/$(DESIGN).svf' -c 'shutdown'"

clean:
	rm -f $(VVP) $(VCD)
