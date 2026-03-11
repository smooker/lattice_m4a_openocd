#!/bin/bash
openocd --debug=2 \
    -f ../ft2232h/ft2232h_smooker.cfg \
    -c "adapter speed 2000; transport select jtag; jtag newtap auto0 tap -irlen 10 -expected-id 0x17486157; "
#    -c "adapter speed 2000; transport select jtag; pld create lattice tap0"

#-c "adapter speed 2000; transport select jtag; jtag newtap auto0 tap -irlen 10 -expected-id 0x029070dd; init; exit;"
