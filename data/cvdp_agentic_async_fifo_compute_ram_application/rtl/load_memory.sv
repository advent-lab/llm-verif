module raw_memory #(
    // Parameter definitions for the raw memory module
    parameter p_data_width = 32,          // Width of data bus
              p_addr_width = 16,       // Width of address bus
              p_ram_depth = 1 << p_addr_width  // Depth of the RAM, calculated based on address width
)
(
    //common input ports
    input i_rst_n,                                  // Active-low reset signal
    input i_clk_memory,                             // Clock signal for memory operations

    // Input ports for memory instantiation
    input [p_addr_width-1:0] i_raw_memory_wr_rd_address,          // Address for read/write operations
    input [p_data_width-1:0] i_raw_memory_wr_data,                // Data input for write operations
    input i_raw_memory_wr_en,                       // Write enable signal
    input i_raw_memory_wr_data_valid,               // Valid signal for write data
    input i_resultant_memory_rd_en,

    // Output ports for memory instantiation
    output reg [p_data_width-1:0] o_resultant_memory_rd_data,  // Data output for read operations
    
    input [2:0] i_dsp_status,             // DSP status input
    input i_start_t,                      // Start signal for the DSP operation
    input i_stop_t,                       // Stop signal for the DSP operation
    
    input [p_addr_width-1:0] i_initial_fetch_addr,  // Initial address for data fetch
    input [p_addr_width-1:0] i_initial_store_addr,  // Initial address for data store
    input i_fetch_fifo_full,
    output reg [p_data_width-1:0] o_fetch_fifo_wr_data,
    output reg o_fetch_fifo_wr_en,

    input i_store_fifo_empty,
    input [p_data_width-1:0] i_store_fifo_rd_data,
    output reg o_store_fifo_rd_en
    );

    localparam p_dsp_state_done                         = 3'd5 ;  // Operation done state
    localparam p_memory_idle                            = 3'd0 ;
    localparam p_external_memory_write_state            = 3'd1 ;
    localparam p_external_memory_read_state             = 3'd2 ;
    localparam p_fetch_fifo_write_state                 = 3'd3 ;
    localparam p_store_fifo_processed_data_wait_state   = 3'd4 ;
    localparam p_store_fifo_read_state                  = 3'd5 ;
    //State Register
    reg [2:0] r_memory_state;
    // Internal wire for memory busy signal
    wire w_memory_busy;
    // Assign memory busy signal to indicate either raw write or resultant read is active
    assign w_memory_busy = i_raw_memory_wr_en || i_resultant_memory_rd_en;

    // Memory array declaration
    reg [p_data_width-1:0] r_ram [p_ram_depth-1:0]; // Memory array with depth based on address width

    // Sequential logic for memory read/write operations
    integer i;  // Loop variable for initialization

    reg r_start_old;                             // Previous start signal
    reg r_stop_old;                              // Previous stop signal
    reg [p_addr_width-1:0] r_start_store_address;
    reg [p_addr_width-1:0] r_start_fetch_address;
    // Memory DSP operations
    always @(posedge i_clk_memory or negedge i_rst_n) begin
        if (!i_rst_n) begin
            o_resultant_memory_rd_data<={p_data_width{1'b0}};
            r_start_store_address<={p_addr_width{1'b0}};
            r_start_fetch_address<={p_addr_width{1'b0}};
            o_store_fifo_rd_en<=1'b0;
            o_fetch_fifo_wr_en<=1'b0;
            r_start_old<=1'b0;
            r_stop_old<=1'b0;
            o_fetch_fifo_wr_data<={p_data_width{1'b0}};
            r_memory_state<=p_memory_idle;
        end
        else
        begin
            case(r_memory_state)
            p_memory_idle:
            begin
                o_resultant_memory_rd_data<={p_data_width{1'b0}};
                r_start_store_address<={p_addr_width{1'b0}};
                r_start_fetch_address<={p_addr_width{1'b0}};
                o_store_fifo_rd_en<=1'b0;
                o_fetch_fifo_wr_en<=1'b0;
                o_fetch_fifo_wr_data<={p_data_width{1'b0}};
                case({i_raw_memory_wr_en,i_resultant_memory_rd_en})
                2'b00:
                begin
                    if(i_start_t!=r_start_old)
                    begin
                        r_start_old<=i_start_t;
                        r_start_store_address<=i_initial_store_addr;
                        r_start_fetch_address<=i_initial_fetch_addr;
                        if(!i_fetch_fifo_full) begin  //initially only fetch fifo will be fed.
                            r_memory_state<=p_fetch_fifo_write_state;
                            o_store_fifo_rd_en<=1'b0;
                        end
                    end
                end
                2'b01:
                begin
                    r_memory_state<=p_external_memory_read_state;
                end
                2'b10:
                begin
                    r_memory_state<=p_external_memory_write_state;
                end
                default:
                begin
                    r_memory_state<=p_memory_idle;
                end
                endcase
                
            end
            p_external_memory_write_state:  // Memory write operation from external stimulus.
            begin
                case({i_raw_memory_wr_en,i_resultant_memory_rd_en})
                
                2'b10:
                begin
                    if(i_raw_memory_wr_data_valid)
                    begin
                        r_ram[i_raw_memory_wr_rd_address] <= i_raw_memory_wr_data; // Write data to the specified address
                    end
                end
                default:
                begin
                    r_memory_state<=p_memory_idle;
                end
                endcase
            end
            p_external_memory_read_state:   // Memory read operation from external stimulus.
            begin
                case({i_raw_memory_wr_en,i_resultant_memory_rd_en})
                2'b01:
                begin
                    o_resultant_memory_rd_data<=r_ram[i_raw_memory_wr_rd_address];
                end
                default:
                begin
                    r_memory_state<=p_memory_idle;
                end
                endcase
            end
             
            p_fetch_fifo_write_state:
            begin
                if((i_dsp_status==p_dsp_state_done) || (r_stop_old!=i_stop_t))
                begin
                    r_memory_state<=p_memory_idle;
                    r_stop_old<=i_stop_t;
                end
                else
                begin
                    case({i_raw_memory_wr_en,i_resultant_memory_rd_en})
                    2'b00:
                    begin
                        if(!i_fetch_fifo_full)
                        begin
                            o_fetch_fifo_wr_en<=1'b1;
                            o_fetch_fifo_wr_data<=r_ram[r_start_fetch_address];
                            r_start_fetch_address<=r_start_fetch_address+1;
                            o_store_fifo_rd_en<=1'b0;
                            r_memory_state<=p_store_fifo_processed_data_wait_state; //wait for processed data fed into store fifo.
                        end
                    end
                    default:
                    begin
                        r_memory_state<=p_memory_idle;
                    end
                    
                    endcase
                end
            end
            p_store_fifo_processed_data_wait_state:
            begin
                if((i_dsp_status==p_dsp_state_done) || (r_stop_old!=i_stop_t))
                begin
                    r_memory_state<=p_memory_idle;
                    r_stop_old<=i_stop_t;
                end
                else
                begin
                    case({i_raw_memory_wr_en,i_resultant_memory_rd_en})
                    2'b00:
                    begin
                        o_fetch_fifo_wr_en<=1'b0;
                        o_store_fifo_rd_en<=1'b0;
                        if(!i_store_fifo_empty)  //this going low means processed data has came from DSP.
                        begin
                            r_memory_state<=p_store_fifo_read_state;
                        end
                    end
                    default:
                    begin
                        r_memory_state<=p_memory_idle;
                    end
                    
                    endcase
                end
            end
            p_store_fifo_read_state:
            begin
                if((i_dsp_status==p_dsp_state_done) || (r_stop_old!=i_stop_t))
                begin
                    r_memory_state<=p_memory_idle;
                    r_stop_old<=i_stop_t;
                end
                else
                begin
                    case({i_raw_memory_wr_en,i_resultant_memory_rd_en})
                    2'b00:
                    begin
                        if(!i_store_fifo_empty)
                        begin
                            o_store_fifo_rd_en<=1'b1;
                            r_ram[r_start_store_address]<=i_store_fifo_rd_data;
                            r_memory_state<=p_fetch_fifo_write_state;
                            r_start_store_address<=r_start_store_address+1; // increasing next store address
                        end
                    end
                    default:
                    begin
                        r_memory_state<=p_memory_idle;
                    end
                    endcase
                end
            end
            endcase
        end
    end



endmodule