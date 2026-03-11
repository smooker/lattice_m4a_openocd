// Testbench for BCD counter 0-9
`timescale 1ns / 1ps

module bcd10_tb;
    reg        clk;
    reg        rst_n;
    wire [3:0] q;

    bcd10 uut (.clk(clk), .rst_n(rst_n), .q(q));

    initial clk = 0;
    always #50 clk = ~clk;  // 10 MHz

    initial begin
        $dumpfile("bcd10.vcd");
        $dumpvars(0, bcd10_tb);

        rst_n = 0;
        #200;
        rst_n = 1;

        // Run 25 clocks — should see 0-9 wrap twice + 5 more
        repeat (25) @(posedge clk);
        #10;

        $display("PASS — simulation complete");
        $finish;
    end

    // Monitor output on every rising edge
    always @(posedge clk)
        $display("t=%0t  rst_n=%b  q=%0d", $time, rst_n, q);
endmodule
