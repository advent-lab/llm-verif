module rgb_color_space_hsv (
    input               clk,
    input               rst,

    // Memory ports to initialize (1/delta) values
    input               we,
    input       [7:0]   waddr,
    input      [24:0]   wdata,

    // Input data with valid.
    input               valid_in,
    input       [7:0]   r_component,
    input       [7:0]   g_component,
    input       [7:0]   b_component,

    // Output values
    output reg [11:0]   h_component,  // Output in fx10.2 format, degree value = (h_component)/4
    output reg [12:0]   s_component,  // Output in fx1.12 format. % value = (s_component/4096)*100
    output reg [11:0]   v_component,  // % value = (v_componente/255) * 100
    output reg          valid_out
);

    integer j;

    reg      [7:0]    valid_in_shreg;
    reg signed [12:0] pre_hue;
    reg      [11:0]   i_max, i_min, stage1_max, stage1_min, stage1_b;
    reg       [8:0]   hue_degrees_offset;
    reg       [2:0]   i_max_r, i_max_g, i_max_b;

    reg      [12:0]   g_sub_b_shreg [0:1];
    reg      [12:0]   b_sub_r_shreg [0:1];
    reg      [12:0]   r_sub_g_shreg [0:1];
    reg      [11:0]   i_max_shreg [0:1];
    reg      [11:0]   i_min_shreg [0:1];

    wire     [25:0]   saturation_result;
    wire     [24:0]   inv_i_max, inv_delta_i;
    wire     [11:0]   almost_hue;
    reg signed [11:0] hue;

    assign valid_out = valid_in_shreg[7];
    assign v_component = i_max;
    assign s_component = saturation_result;
    assign h_component = hue;

    reg signed [12:0] g_sub_b, b_sub_r, r_sub_g, delta_i;

    // Internally upscaled 12-bit values for fixed point precision
    wire [11:0] r_scaled = {4'b0000, r_component}; // Scale 8-bit to 12-bit
    wire [11:0] g_scaled = {4'b0000, g_component}; // Scale 8-bit to 12-bit
    wire [11:0] b_scaled = {4'b0000, b_component}; // Scale 8-bit to 12-bit

    // Subtraction logic, to find difference of inputs and delta value
    // Calculate g-b, b-r, r-g and max-min values to be used in h calculation
    always @(posedge clk or posedge rst) begin
        if (rst) begin
            g_sub_b <= 13'd0;
            b_sub_r <= 13'd0;
            r_sub_g <= 13'd0;
            delta_i <= 13'd0;
        end else begin
            g_sub_b <= $signed(g_scaled) - $signed(b_scaled);
            b_sub_r <= $signed(b_scaled) - $signed(r_scaled);
            r_sub_g <= $signed(r_scaled) - $signed(g_scaled);
            delta_i <= $signed(i_max) - $signed(i_min);
        end
    end

    // Memory to store 1/delta values (256 values)
    // 0,1/1,1/2,1/3...1/255)
    // These values are used to multiply with (g-b)/(b-r)/(r-g) for calculation
    // h value. It is easy to store inverse values and do multiplication
    // than division.
    dual_port_ram inverse_component_inst (
        .clk(clk),
        .we(we),
        .waddr(waddr),
        .wdata(wdata),
        .ren_a(1'b1),
        .raddr_a(i_max[7:0]),
        .rdata_a(inv_i_max),
        .ren_b(1'b1),
        .raddr_b(delta_i[7:0]),
        .rdata_b(inv_delta_i)
    );

    // Pre hue constant multiplier for h calculation
    // Multiply with 60 degrees.
    // Used 2 stage pipeline
    localparam signed [6:0] CONST_60 = 7'd60;
    reg signed [18:0] pre_hue_prod;

    always @(posedge clk or posedge rst) begin
        if (rst) begin
            pre_hue_prod <= 19'd0;
        end else begin
            pre_hue_prod <= pre_hue * CONST_60;
        end
    end

    // Saturation calculation multiplier
    saturation_mult saturation_mult_0 (
        .clk(clk),
        .rst(rst),
        .a(inv_i_max), // Read inverted value from memory port1
        .b({1'b0, delta_i[11:0]}), // Delta value (max-min)
        .result(saturation_result)
    );

    // h value calculation multiplier
    hue_mult hue_mult_inst (
        .clk(clk),
        .rst(rst),
        .dataa(pre_hue_prod), // Product from constant 60 multiplication
        .datab(inv_delta_i), // Read inverted data from memory port2
        .result(almost_hue)
    );

    // Final h value addition logic
    always @(posedge clk or posedge rst) begin
        if (rst)
            hue <= 'd0;
        else
            hue <= $signed(almost_hue) + $signed({1'b0, {hue_degrees_offset, 2'd0}});
    end

    // Pipelining registers to help in each stage of data processing
    // Help with multiplications and additions
    always @(posedge clk or posedge rst) begin
        if (rst) begin
            // Reset all registers and shift registers
            g_sub_b_shreg[0] <= 0;
            b_sub_r_shreg[0] <= 0;
            r_sub_g_shreg[0] <= 0;
            i_max_shreg[0] <= 0;
            i_min_shreg[0] <= 0;

            // Reset the shift registers for all stages
            for (j = 0; j < 2; j = j + 1) begin
                g_sub_b_shreg[j+1] <= 0;
                b_sub_r_shreg[j+1] <= 0;
                r_sub_g_shreg[j+1] <= 0;
                i_max_shreg[j+1] <= 0;
                i_min_shreg[j+1] <= 0;
            end
        end else begin
            // Normal operation when reset is not asserted
            g_sub_b_shreg[0] <= g_sub_b;
            b_sub_r_shreg[0] <= b_sub_r;
            r_sub_g_shreg[0] <= r_sub_g;
            i_max_shreg[0] <= i_max;
            i_min_shreg[0] <= i_min;

            // Shift register updates
            for (j = 0; j < 2; j = j + 1) begin
                g_sub_b_shreg[j+1] <= g_sub_b_shreg[j];
                b_sub_r_shreg[j+1] <= b_sub_r_shreg[j];
                r_sub_g_shreg[j+1] <= r_sub_g_shreg[j];
                i_max_shreg[j+1] <= i_max_shreg[j];
                i_min_shreg[j+1] <= i_min_shreg[j];
            end
        end
    end

    // Calculate max and min values
    // Shift valid in for total latency cycles
    // and assign to output valid when output data is ready
    always @(posedge clk or posedge rst) begin
        if (rst) begin
            valid_in_shreg <= 0;
            stage1_max <= 0;
            stage1_min <= 0;
            stage1_b <= 0;
            i_max_r <= 0;
            i_max_g <= 0;
            i_max_b <= 0;
            i_max <= 0;
            i_min <= 0;
        end else begin
            valid_in_shreg <= {valid_in_shreg[6:0], valid_in};
            i_max_r[2] <= i_max_r[1];
            i_max_g[2] <= i_max_g[1];
            i_max_b[2] <= i_max_b[1];

            if (valid_in) begin
                stage1_b <= b_component;
                if (r_component > g_component) begin
                    stage1_max <= r_component;
                    stage1_min <= g_component;
                    i_max_r[0] <= 1;
                    i_max_g[0] <= 0;
                    i_max_b[0] <= 0;
                end else begin
                    stage1_max <= g_component;
                    stage1_min <= r_component;
                    i_max_r[0] <= 0;
                    i_max_g[0] <= 1;
                    i_max_b[0] <= 0;
                end
            end

            if (valid_in_shreg[0]) begin
                if (stage1_max > stage1_b) begin
                    i_max      <= stage1_max;
                    i_max_r[1] <= i_max_r[0];
                    i_max_g[1] <= i_max_g[0];
                    i_max_b[1] <= i_max_b[0];
                end else begin
                    i_max      <= stage1_b;
                    i_max_r[1] <= 0;
                    i_max_g[1] <= 0;
                    i_max_b[1] <= 1;
                end

                if (stage1_min < stage1_b) i_min <= stage1_min;
                else                       i_min <= stage1_b;
            end
        end
    end

    // Select degree value to add for h calculation
    always @(posedge clk or posedge rst) begin
        if (rst) begin
            pre_hue <= 'd0;
            hue_degrees_offset <= 'd0;
        end else begin
            if (valid_in_shreg[2]) begin
                if (i_max_shreg[0] == i_min_shreg[0]) begin
                    pre_hue <= 0;
                    hue_degrees_offset <= 9'd0;
                end else if ((i_max_r[2]) && (~g_sub_b_shreg[0][12])) begin
                    pre_hue <= g_sub_b_shreg[0];
                    hue_degrees_offset <= 9'd0;
                end else if ((i_max_r[2]) && (g_sub_b_shreg[0][12])) begin
                    pre_hue <= g_sub_b_shreg[0];
                    hue_degrees_offset <= 9'd360;
                end else if (i_max_g[2]) begin
                    pre_hue <= b_sub_r_shreg[0];
                    hue_degrees_offset <= 9'd120;
                end else if (i_max_b[2]) begin
                    pre_hue <= r_sub_g_shreg[0];
                    hue_degrees_offset <= 9'd240;
                end
            end
        end
    end
endmodule

// Write port to initialize 1/delta values, and two read ports.
// 1. Read port --> read 1/delta address
// 2. Read port --> read 1/max address
// Memory is used to store inverted values (0 to 1/255) such that multiplication can be
// performed easily than division.
module dual_port_ram (
    input               clk,
    input               we,
    input       [7:0]   waddr,
    input      [24:0]   wdata,
    input               ren_a,
    input       [7:0]   raddr_a,
    output reg [24:0]   rdata_a,
    input               ren_b,
    input       [7:0]   raddr_b,
    output reg [24:0]   rdata_b
);

    reg [24:0] ram [0:255];

    always @(posedge clk) begin
        if (we) begin
            ram[waddr] <= wdata;
        end
    end

    always @(posedge clk) begin
        if (ren_a) begin
            rdata_a <= ram[raddr_a];
        end
    end

    always @(posedge clk) begin
        if (ren_b) begin
            rdata_b <= ram[raddr_b];
        end
    end
endmodule

// This is used to multiply delta value with inverted cmax value from memory
// (used to calculate s, saturation)
module saturation_mult (
    input  wire         clk,
    input  wire         rst,
    input  wire [24:0]  a,
    input  wire [12:0]  b,
    output [25:0]  result
);

    reg [24:0] A_reg;
    reg [12:0] B_reg;
    reg [38:0] mult_result;
    reg [25:0] rounded_result;

    always @(posedge clk or posedge rst) begin
        if (rst) begin
            A_reg <= 25'd0;
            B_reg <= 13'd0;
        end else begin
            A_reg <= a;
            B_reg <= b;
        end
    end

    always @(posedge clk or posedge rst) begin
        if (rst) begin
            mult_result <= 'd0;
        end else begin
            mult_result <= A_reg * B_reg;
        end
    end

    always @(posedge clk or posedge rst) begin
        if (rst) begin
            rounded_result <= 'd0;
        end else begin
            rounded_result <= mult_result[38:12] + mult_result[11];
        end
    end

    assign result = rounded_result;
endmodule

//used for h, hue calculation
module hue_mult (
    input               clk,
    input               rst,
    input signed [18:0] dataa,
    input      [24:0]   datab,
    output reg signed [11:0] result
);

    reg signed [43:0] mult_stage1;

    always @(posedge clk or posedge rst) begin
        if (rst)
            mult_stage1 <= 44'd0;
        else
            mult_stage1 <= $signed(dataa) * $signed({1'b0, datab});
    end

    always @(posedge clk or posedge rst) begin
        if (rst)
            result <= 12'd0;
        else
            result <= mult_stage1[33:22];
    end
endmodule
