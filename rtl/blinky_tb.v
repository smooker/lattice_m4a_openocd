// blinky_tb.v — Testbench for blinky.v
//
// Run: iverilog -o blinky_tb blinky.v blinky_tb.v && vvp blinky_tb

`timescale 1ns / 1ps

module blinky_tb;

    reg clk, in_a, in_b;
    wire blink, cnt1, cnt0;
    wire and_out, or_out, xor_out, not_out;

    blinky uut (
        .clk(clk),
        .in_a(in_a),
        .in_b(in_b),
        .blink(blink),
        .cnt1(cnt1),
        .cnt0(cnt0),
        .and_out(and_out),
        .or_out(or_out),
        .xor_out(xor_out),
        .not_out(not_out)
    );

    // Clock: 10ns period (100 MHz, but doesn't matter for simulation)
    initial clk = 0;
    always #5 clk = ~clk;

    initial begin
        $dumpfile("blinky.vcd");
        $dumpvars(0, blinky_tb);

        // --- Test combinatorial gates ---
        $display("=== Combinatorial gates ===");
        $display("  A  B | AND  OR XOR NOT_A");

        in_a = 0; in_b = 0; #1;
        $display("  %b  %b |  %b    %b   %b    %b", in_a, in_b, and_out, or_out, xor_out, not_out);

        in_a = 0; in_b = 1; #1;
        $display("  %b  %b |  %b    %b   %b    %b", in_a, in_b, and_out, or_out, xor_out, not_out);

        in_a = 1; in_b = 0; #1;
        $display("  %b  %b |  %b    %b   %b    %b", in_a, in_b, and_out, or_out, xor_out, not_out);

        in_a = 1; in_b = 1; #1;
        $display("  %b  %b |  %b    %b   %b    %b", in_a, in_b, and_out, or_out, xor_out, not_out);

        // --- Test counter: reset then count 10 cycles ---
        $display("");
        $display("=== Counter (reset + 10 clocks) ===");

        // Assert reset (in_b = 0)
        in_b = 0; #10;
        $display("After reset:  blink=%b cnt1=%b cnt0=%b", blink, cnt1, cnt0);

        // Release reset, count
        in_b = 1;
        $display(" clk# | blink cnt1 cnt0");

        repeat (10) begin
            @(posedge clk);
            #1;
            $display("      |   %b     %b    %b", blink, cnt1, cnt0);
        end

        $display("");
        $display("Done.");
        $finish;
    end

endmodule
