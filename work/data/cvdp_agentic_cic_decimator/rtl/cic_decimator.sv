module cic_decimator #(
    parameter int WIDTH     = 16,
    parameter int RMAX      = 2,
    parameter int M         = 1,
    parameter int N         = 2,
    parameter int REG_WIDTH = WIDTH + $clog2((RMAX * M)**N)
) (
    input  logic                      clk,
    input  logic                      rst,
    input  logic [WIDTH-1:0]          input_tdata,
    input  logic                      input_tvalid,
    input  logic                      output_tready,
    input  logic [$clog2(RMAX+1)-1:0] rate,
    output logic                      input_tready,
    output logic [REG_WIDTH-1:0]      output_tdata,
    output logic                      output_tvalid
);

    
    logic [$clog2(RMAX+1)-1:0] cycle_reg;
    logic [REG_WIDTH-1:0] int_reg [0:N-1];
    logic [REG_WIDTH-1:0] comb_reg [0:N-1];

    
    logic [REG_WIDTH-1:0] int_reg_0 = int_reg[0];
    logic [REG_WIDTH-1:0] int_reg_1 = int_reg[1];
    logic [REG_WIDTH-1:0] comb_reg_0 = comb_reg[0];
    logic [REG_WIDTH-1:0] comb_reg_1 = comb_reg[1];

    assign input_tready  = output_tready || (cycle_reg != 0);
    assign output_tdata  = comb_reg[N-1];
    assign output_tvalid = input_tvalid && (cycle_reg == 0);

    
    initial begin
        cycle_reg = 0;
        for (int i = 0; i < N; i++) begin
            int_reg[i]  = 0;
            comb_reg[i] = 0;
        end
    end

    
    genvar k;
    generate
        for (k = 0; k < N; k++) begin : integrator
            always_ff @(posedge clk) begin
                if (rst) begin
                    int_reg[k] <= 0;
                end else begin
                    if (input_tready && input_tvalid) begin
                        if (k == 0) begin
                            int_reg[k] <= $signed(int_reg[k]) + $signed(input_tdata);
                        end else begin
                            int_reg[k] <= $signed(int_reg[k]) + $signed(int_reg[k-1]);
                        end
                    end
                end
            end
        end
    endgenerate

    
    generate
        for (k = 0; k < N; k++) begin : comb
            logic [REG_WIDTH-1:0] delay_reg [0:M-1];

            
            initial begin
                for (int i = 0; i < M; i++) begin
                    delay_reg[i] = 0;
                end
            end

            always_ff @(posedge clk) begin
                if (rst) begin
                    for (int i = 0; i < M; i++) begin
                        delay_reg[i] <= 0;
                    end
                    comb_reg[k] <= 0;
                end else begin
                    if (output_tready && output_tvalid) begin
                        if (k == 0) begin
                            delay_reg[0] <= $signed(int_reg[N-1]);
                            comb_reg[k] <= $signed(int_reg[N-1]) - $signed(delay_reg[M-1]);
                        end else begin
                            delay_reg[0] <= $signed(comb_reg[k-1]);
                            comb_reg[k] <= $signed(comb_reg[k-1]) - $signed(delay_reg[M-1]);
                        end
                        for (int i = 0; i < M-1; i++) begin
                            delay_reg[i+1] <= delay_reg[i];
                        end
                    end
                end
            end
        end
    endgenerate


    always_ff @(posedge clk) begin
        if (rst) begin
            cycle_reg <= 0;
        end else begin
            if (input_tready && input_tvalid) begin
                if ((cycle_reg < RMAX - 1) && (cycle_reg < rate - 1)) begin
                    cycle_reg <= cycle_reg + 1;
                end else begin
                    cycle_reg <= 0;
                end
            end
        end
    end

endmodule
