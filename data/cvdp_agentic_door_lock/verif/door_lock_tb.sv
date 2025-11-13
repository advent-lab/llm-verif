`timescale 1ns/1ps

module door_lock_tb;

    parameter PASSWORD_LENGTH = 4;
    parameter MAX_TRIALS = 4;

    logic                         clk;
    logic                         srst;
    logic [3:0]                   key_input;
    logic                         key_valid;
    logic                         confirm;
    logic                         admin_override;
    logic                         admin_set_mode;
    logic [PASSWORD_LENGTH*4-1:0] new_password;
    logic                         new_password_valid;
    wire                          door_unlock;
    wire                          lockout;

    // DUT instantiation
    door_lock #(
        .PASSWORD_LENGTH(PASSWORD_LENGTH),
        .MAX_TRIALS(MAX_TRIALS)
    ) dut (
        .clk(clk),
        .srst(srst),
        .key_input(key_input),
        .key_valid(key_valid),
        .confirm(confirm),
        .admin_override(admin_override),
        .admin_set_mode(admin_set_mode),
        .new_password(new_password),
        .new_password_valid(new_password_valid),
        .door_unlock(door_unlock),
        .lockout(lockout)
    );

    // Clock generation
    initial begin
        clk = 0;
        forever #5 clk = ~clk;
    end

    // Test sequence
    initial begin
        // Initialize
        srst = 1;
        key_input = 0;
        key_valid = 0;
        confirm = 0;
        admin_override = 0;
        admin_set_mode = 0;
        new_password = 0;
        new_password_valid = 0;

        #20;
        srst = 0;
        #20;

        // Try entering some keys
        @(posedge clk);
        key_input = 4'h1;
        key_valid = 1;
        @(posedge clk);
        key_valid = 0;

        @(posedge clk);
        key_input = 4'h2;
        key_valid = 1;
        @(posedge clk);
        key_valid = 0;

        @(posedge clk);
        key_input = 4'h3;
        key_valid = 1;
        @(posedge clk);
        key_valid = 0;

        @(posedge clk);
        key_input = 4'h4;
        key_valid = 1;
        @(posedge clk);
        key_valid = 0;

        // Try confirming
        @(posedge clk);
        confirm = 1;
        @(posedge clk);
        confirm = 0;

        #50;

        // Test admin override
        @(posedge clk);
        admin_override = 1;
        #20;
        @(posedge clk);
        admin_override = 0;

        #50;

        // Test admin set mode
        @(posedge clk);
        admin_set_mode = 1;
        new_password = 16'h5678;
        new_password_valid = 1;
        @(posedge clk);
        admin_set_mode = 0;
        new_password_valid = 0;

        #50;

        // Try the new password
        @(posedge clk);
        key_input = 4'h5;
        key_valid = 1;
        @(posedge clk);
        key_valid = 0;

        @(posedge clk);
        key_input = 4'h6;
        key_valid = 1;
        @(posedge clk);
        key_valid = 0;

        @(posedge clk);
        key_input = 4'h7;
        key_valid = 1;
        @(posedge clk);
        key_valid = 0;

        @(posedge clk);
        key_input = 4'h8;
        key_valid = 1;
        @(posedge clk);
        key_valid = 0;

        @(posedge clk);
        confirm = 1;
        @(posedge clk);
        confirm = 0;

        #100;
        $finish;
    end

    // Monitor
    initial begin
        $monitor("Time=%0t srst=%b key_input=%h key_valid=%b confirm=%b door_unlock=%b lockout=%b",
                 $time, srst, key_input, key_valid, confirm, door_unlock, lockout);
    end

endmodule
