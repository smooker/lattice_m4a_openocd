#!/bin/bash
openocd --debug=2 \
    -f ../../ft2232h/ft2232h_smooker.cfg \
    -c "ftdi layout_signal nSRST -data 0x0010 -oe 0x0010" \
    -c "adapter speed 1000; transport select jtag" \
    -c "jtag newtap auto0 tap -irlen 8 -expected-id 0 -ircapture 0x15 -irmask 0x03" \
    -c "init"
