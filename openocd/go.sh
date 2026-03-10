#!/bin/bash
openocd --debug=2 \
    -f ./um232h_smooker_6010.cfg \
    -c "adapter speed 2000; transport select jtag; jtag newtap auto0 tap -irlen 10 -expected-id 0x17486157; "
#    -c "adapter speed 2000; transport select jtag; pld create lattice tap0"

#-c "adapter speed 2000; transport select jtag; jtag newtap auto0 tap -irlen 10 -expected-id 0x029070dd; init; exit;"
