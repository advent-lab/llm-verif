`timescale 1ns/1ps

module tb_llm;

  // -----------------------------------------------------------------------
  // Register address indices  (wb_adr_i[9:2] field)
  // -----------------------------------------------------------------------
  localparam [7:0] MODER_ADR      = 8'h00;
  localparam [7:0] INT_SOURCE_ADR = 8'h01;
  localparam [7:0] INT_MASK_ADR   = 8'h02;
  localparam [7:0] IPGT_ADR       = 8'h03;
  localparam [7:0] IPGR1_ADR      = 8'h04;
  localparam [7:0] IPGR2_ADR      = 8'h05;
  localparam [7:0] PACKETLEN_ADR  = 8'h06;
  localparam [7:0] COLLCONF_ADR   = 8'h07;
  localparam [7:0] TX_BD_NUM_ADR  = 8'h08;
  localparam [7:0] CTRLMODER_ADR  = 8'h09;
  localparam [7:0] MIIMODER_ADR   = 8'h0A;
  localparam [7:0] MIICOMMAND_ADR = 8'h0B;
  localparam [7:0] MIIADDRESS_ADR = 8'h0C;
  localparam [7:0] MIITX_DATA_ADR = 8'h0D;
  localparam [7:0] MIIRX_DATA_ADR = 8'h0E;
  localparam [7:0] MIISTATUS_ADR  = 8'h0F;
  localparam [7:0] MAC_ADDR0_ADR  = 8'h10;
  localparam [7:0] MAC_ADDR1_ADR  = 8'h11;
  localparam [7:0] HASH0_ADR      = 8'h12;
  localparam [7:0] HASH1_ADR      = 8'h13;
  localparam [7:0] TX_CTRL_ADR    = 8'h14;
  localparam [7:0] RX_CTRL_ADR    = 8'h15;

  // MODER register bit positions (used for write-data coverpoints)
  localparam MODER_RXEN    =  0;
  localparam MODER_TXEN    =  1;
  localparam MODER_LOOPBCK =  7;
  localparam MODER_FULLD   = 10;
  localparam MODER_CRCE    = 13;
  localparam MODER_HUGEEN  = 14;
  localparam MODER_PAD     = 15;

  // CTRLMODER bit positions
  localparam CTRLMODER_RXFLOW = 1;
  localparam CTRLMODER_TXFLOW = 2;

  // Clock periods (ns)
  localparam CLK_WB = 10;   // 100 MHz WISHBONE
  localparam CLK_TX = 40;   // 25 MHz MII TX
  localparam CLK_RX = 40;   // 25 MHz MII RX

  // -----------------------------------------------------------------------
  // DUT interface signals
  // -----------------------------------------------------------------------
  // WISHBONE common
  reg         wb_clk_i;
  reg         wb_rst_i;
  reg  [31:0] wb_dat_i;
  wire [31:0] wb_dat_o;
  wire        wb_err_o;

  // WISHBONE slave
  reg  [11:2] wb_adr_i;
  reg   [3:0] wb_sel_i;
  reg         wb_we_i;
  reg         wb_cyc_i;
  reg         wb_stb_i;
  wire        wb_ack_o;

  // WISHBONE master
  wire [31:0] m_wb_adr_o;
  wire  [3:0] m_wb_sel_o;
  wire        m_wb_we_o;
  reg  [31:0] m_wb_dat_i;
  wire [31:0] m_wb_dat_o;
  wire        m_wb_cyc_o;
  wire        m_wb_stb_o;
  reg         m_wb_ack_i;
  reg         m_wb_err_i;
  wire  [2:0] m_wb_cti_o;
  wire  [1:0] m_wb_bte_o;

  // MII TX
  reg         mtx_clk_pad_i;
  wire  [3:0] mtxd_pad_o;
  wire        mtxen_pad_o;
  wire        mtxerr_pad_o;

  // MII RX
  reg         mrx_clk_pad_i;
  reg   [3:0] mrxd_pad_i;
  reg         mrxdv_pad_i;
  reg         mrxerr_pad_i;
  reg         mcoll_pad_i;
  reg         mcrs_pad_i;

  // MIIM
  wire        mdc_pad_o;
  reg         md_pad_i;
  wire        md_pad_o;
  wire        md_padoe_o;

  wire        int_o;

  // -----------------------------------------------------------------------
  // DUT instantiation
  // -----------------------------------------------------------------------
  ethmac dut (
    .wb_clk_i      (wb_clk_i),
    .wb_rst_i      (wb_rst_i),
    .wb_dat_i      (wb_dat_i),
    .wb_dat_o      (wb_dat_o),
    .wb_adr_i      (wb_adr_i),
    .wb_sel_i      (wb_sel_i),
    .wb_we_i       (wb_we_i),
    .wb_cyc_i      (wb_cyc_i),
    .wb_stb_i      (wb_stb_i),
    .wb_ack_o      (wb_ack_o),
    .wb_err_o      (wb_err_o),
    .m_wb_adr_o    (m_wb_adr_o),
    .m_wb_sel_o    (m_wb_sel_o),
    .m_wb_we_o     (m_wb_we_o),
    .m_wb_dat_i    (m_wb_dat_i),
    .m_wb_dat_o    (m_wb_dat_o),
    .m_wb_cyc_o    (m_wb_cyc_o),
    .m_wb_stb_o    (m_wb_stb_o),
    .m_wb_ack_i    (m_wb_ack_i),
    .m_wb_err_i    (m_wb_err_i),
    .m_wb_cti_o    (m_wb_cti_o),
    .m_wb_bte_o    (m_wb_bte_o),
    .mtx_clk_pad_i (mtx_clk_pad_i),
    .mtxd_pad_o    (mtxd_pad_o),
    .mtxen_pad_o   (mtxen_pad_o),
    .mtxerr_pad_o  (mtxerr_pad_o),
    .mrx_clk_pad_i (mrx_clk_pad_i),
    .mrxd_pad_i    (mrxd_pad_i),
    .mrxdv_pad_i   (mrxdv_pad_i),
    .mrxerr_pad_i  (mrxerr_pad_i),
    .mcoll_pad_i   (mcoll_pad_i),
    .mcrs_pad_i    (mcrs_pad_i),
    .mdc_pad_o     (mdc_pad_o),
    .md_pad_i      (md_pad_i),
    .md_pad_o      (md_pad_o),
    .md_padoe_o    (md_padoe_o),
    .int_o         (int_o)
  );

  // -----------------------------------------------------------------------
  // Clock generation
  // -----------------------------------------------------------------------
  initial wb_clk_i     = 0;
  always  #(CLK_WB/2)  wb_clk_i     = ~wb_clk_i;

  initial mtx_clk_pad_i = 0;
  always  #(CLK_TX/2)  mtx_clk_pad_i = ~mtx_clk_pad_i;

  initial mrx_clk_pad_i = 0;
  always  #(CLK_RX/2)  mrx_clk_pad_i = ~mrx_clk_pad_i;

  // =========================================================================
  // COVERGROUPS  —  all coverpoints reference only DUT interface signals
  // =========================================================================

  // -------------------------------------------------------------------------
  // 1. WISHBONE slave — register space (addr[11:10]==2'b00): which register
  //    is accessed and whether the access is a read or a write
  // -------------------------------------------------------------------------
  covergroup cg_wb_reg_access @(posedge wb_clk_i iff
      (wb_stb_i && wb_cyc_i && |wb_sel_i && !wb_adr_i[11] && !wb_adr_i[10]));
    option.cross_auto_bin_max = 0;

    cp_reg_addr: coverpoint wb_adr_i[9:2] {
      bins moder       = {MODER_ADR};
      bins int_source  = {INT_SOURCE_ADR};
      bins int_mask    = {INT_MASK_ADR};
      bins ipgt        = {IPGT_ADR};
      bins ipgr1       = {IPGR1_ADR};
      bins ipgr2       = {IPGR2_ADR};
      bins packetlen   = {PACKETLEN_ADR};
      bins collconf    = {COLLCONF_ADR};
      bins tx_bd_num   = {TX_BD_NUM_ADR};
      bins ctrlmoder   = {CTRLMODER_ADR};
      bins miimoder    = {MIIMODER_ADR};
      bins miicommand  = {MIICOMMAND_ADR};
      bins miiaddress  = {MIIADDRESS_ADR};
      bins miitx_data  = {MIITX_DATA_ADR};
      bins miirx_data  = {MIIRX_DATA_ADR};
      bins miistatus   = {MIISTATUS_ADR};
      bins mac_addr0   = {MAC_ADDR0_ADR};
      bins mac_addr1   = {MAC_ADDR1_ADR};
      bins hash0       = {HASH0_ADR};
      bins hash1       = {HASH1_ADR};
      bins tx_ctrl     = {TX_CTRL_ADR};
      bins rx_ctrl     = {RX_CTRL_ADR};
      bins unmapped[]  = default;
    }

    cp_rw: coverpoint wb_we_i {
      bins rd = {1'b0};
      bins wr = {1'b1};
    }

    cx_reg_rw: cross cp_reg_addr, cp_rw {
      bins wr_moder      = binsof(cp_reg_addr.moder)      && binsof(cp_rw.wr);
      bins rd_moder      = binsof(cp_reg_addr.moder)      && binsof(cp_rw.rd);
      bins rd_int_source = binsof(cp_reg_addr.int_source) && binsof(cp_rw.rd);
      bins wr_int_mask   = binsof(cp_reg_addr.int_mask)   && binsof(cp_rw.wr);
      bins rd_int_mask   = binsof(cp_reg_addr.int_mask)   && binsof(cp_rw.rd);
      bins wr_ipgt       = binsof(cp_reg_addr.ipgt)       && binsof(cp_rw.wr);
      bins wr_ipgr1      = binsof(cp_reg_addr.ipgr1)      && binsof(cp_rw.wr);
      bins wr_ipgr2      = binsof(cp_reg_addr.ipgr2)      && binsof(cp_rw.wr);
      bins wr_packetlen  = binsof(cp_reg_addr.packetlen)  && binsof(cp_rw.wr);
      bins rd_packetlen  = binsof(cp_reg_addr.packetlen)  && binsof(cp_rw.rd);
      bins wr_collconf   = binsof(cp_reg_addr.collconf)   && binsof(cp_rw.wr);
      bins wr_tx_bd_num  = binsof(cp_reg_addr.tx_bd_num)  && binsof(cp_rw.wr);
      bins rd_tx_bd_num  = binsof(cp_reg_addr.tx_bd_num)  && binsof(cp_rw.rd);
      bins wr_ctrlmoder  = binsof(cp_reg_addr.ctrlmoder)  && binsof(cp_rw.wr);
      bins wr_miimoder   = binsof(cp_reg_addr.miimoder)   && binsof(cp_rw.wr);
      bins wr_miicommand = binsof(cp_reg_addr.miicommand) && binsof(cp_rw.wr);
      bins wr_miiaddress = binsof(cp_reg_addr.miiaddress) && binsof(cp_rw.wr);
      bins wr_miitx_data = binsof(cp_reg_addr.miitx_data) && binsof(cp_rw.wr);
      bins rd_miirx_data = binsof(cp_reg_addr.miirx_data) && binsof(cp_rw.rd);
      bins rd_miistatus  = binsof(cp_reg_addr.miistatus)  && binsof(cp_rw.rd);
      bins wr_mac_addr0  = binsof(cp_reg_addr.mac_addr0)  && binsof(cp_rw.wr);
      bins wr_mac_addr1  = binsof(cp_reg_addr.mac_addr1)  && binsof(cp_rw.wr);
      bins wr_hash0      = binsof(cp_reg_addr.hash0)      && binsof(cp_rw.wr);
      bins wr_hash1      = binsof(cp_reg_addr.hash1)      && binsof(cp_rw.wr);
      bins rd_tx_ctrl    = binsof(cp_reg_addr.tx_ctrl)    && binsof(cp_rw.rd);
      bins rd_rx_ctrl    = binsof(cp_reg_addr.rx_ctrl)    && binsof(cp_rw.rd);
    }
  endgroup

  // -------------------------------------------------------------------------
  // 2. WISHBONE slave — buffer descriptor space (addr[11:10]==2'b01)
  // -------------------------------------------------------------------------
  covergroup cg_wb_bd_access @(posedge wb_clk_i iff
      (wb_stb_i && wb_cyc_i && |wb_sel_i && !wb_adr_i[11] && wb_adr_i[10]));
    option.cross_auto_bin_max = 0;

    cp_bd_rw: coverpoint wb_we_i {
      bins rd = {1'b0};
      bins wr = {1'b1};
    }

    cp_bd_sel: coverpoint wb_sel_i {
      bins full_word = {4'hF};
      bins partial[] = default;
    }

    cx_bd_rw_sel: cross cp_bd_rw, cp_bd_sel {
      bins full_wr = binsof(cp_bd_rw.wr) && binsof(cp_bd_sel.full_word);
      bins full_rd = binsof(cp_bd_rw.rd) && binsof(cp_bd_sel.full_word);
    }
  endgroup

  // -------------------------------------------------------------------------
  // 3. WISHBONE slave — error and ACK response coverage
  // -------------------------------------------------------------------------
  covergroup cg_wb_response @(posedge wb_clk_i iff (wb_cyc_i && wb_stb_i));
    option.cross_auto_bin_max = 0;

    cp_ack: coverpoint wb_ack_o {
      bins no_ack = {1'b0};
      bins ack    = {1'b1};
    }

    cp_err: coverpoint wb_err_o {
      bins no_err = {1'b0};
      bins err    = {1'b1};
    }

    cp_rw: coverpoint wb_we_i {
      bins rd = {1'b0};
      bins wr = {1'b1};
    }

    // ACK to read vs write
    cx_ack_rw: cross cp_ack, cp_rw {
      bins read_ack  = binsof(cp_ack.ack) && binsof(cp_rw.rd);
      bins write_ack = binsof(cp_ack.ack) && binsof(cp_rw.wr);
    }

    // Error on read vs write
    cx_err_rw: cross cp_err, cp_rw {
      bins read_err  = binsof(cp_err.err) && binsof(cp_rw.rd);
      bins write_err = binsof(cp_err.err) && binsof(cp_rw.wr);
    }

    // Error vs ACK mutual exclusion sanity
    cx_ack_err: cross cp_ack, cp_err {
      bins ack_only = binsof(cp_ack.ack) && binsof(cp_err.no_err);
      bins err_only = binsof(cp_ack.no_ack) && binsof(cp_err.err);
    }
  endgroup

  // -------------------------------------------------------------------------
  // 4. MODER register write — mode bit-field coverage at write time
  //    All coverpoints sample wb_dat_i (testbench input signal, no DUT hierarchy)
  // -------------------------------------------------------------------------
  covergroup cg_moder_write @(posedge wb_clk_i iff
      (wb_stb_i && wb_cyc_i && wb_we_i && |wb_sel_i &&
       !wb_adr_i[11] && !wb_adr_i[10] && wb_adr_i[9:2] == MODER_ADR));
    option.cross_auto_bin_max = 0;

    cp_txen: coverpoint wb_dat_i[MODER_TXEN] {
      bins tx_disable = {1'b0};
      bins tx_enable  = {1'b1};
    }

    cp_rxen: coverpoint wb_dat_i[MODER_RXEN] {
      bins rx_disable = {1'b0};
      bins rx_enable  = {1'b1};
    }

    cp_fulld: coverpoint wb_dat_i[MODER_FULLD] {
      bins half_duplex = {1'b0};
      bins full_duplex = {1'b1};
    }

    cp_loopbck: coverpoint wb_dat_i[MODER_LOOPBCK] {
      bins no_loopback = {1'b0};
      bins loopback    = {1'b1};
    }

    cp_pad: coverpoint wb_dat_i[MODER_PAD] {
      bins no_pad = {1'b0};
      bins pad    = {1'b1};
    }

    cp_crce: coverpoint wb_dat_i[MODER_CRCE] {
      bins crc_off = {1'b0};
      bins crc_on  = {1'b1};
    }

    cp_hugeen: coverpoint wb_dat_i[MODER_HUGEEN] {
      bins no_huge = {1'b0};
      bins huge_en = {1'b1};
    }

    // TX+RX enable versus full/half duplex
    cx_txrx_duplex: cross cp_txen, cp_rxen, cp_fulld {
      bins en_both_full = binsof(cp_txen.tx_enable)  && binsof(cp_rxen.rx_enable)  &&
                          binsof(cp_fulld.full_duplex);
      bins en_both_half = binsof(cp_txen.tx_enable)  && binsof(cp_rxen.rx_enable)  &&
                          binsof(cp_fulld.half_duplex);
      bins tx_only_full = binsof(cp_txen.tx_enable)  && binsof(cp_rxen.rx_disable) &&
                          binsof(cp_fulld.full_duplex);
      bins tx_only_half = binsof(cp_txen.tx_enable)  && binsof(cp_rxen.rx_disable) &&
                          binsof(cp_fulld.half_duplex);
      bins rx_only      = binsof(cp_txen.tx_disable) && binsof(cp_rxen.rx_enable);
      bins both_off     = binsof(cp_txen.tx_disable) && binsof(cp_rxen.rx_disable);
    }

    // CRC and padding together
    cx_crc_pad: cross cp_crce, cp_pad {
      bins crc_and_pad   = binsof(cp_crce.crc_on)  && binsof(cp_pad.pad);
      bins crc_no_pad    = binsof(cp_crce.crc_on)  && binsof(cp_pad.no_pad);
      bins no_crc_pad    = binsof(cp_crce.crc_off) && binsof(cp_pad.pad);
      bins no_crc_no_pad = binsof(cp_crce.crc_off) && binsof(cp_pad.no_pad);
    }

    // Loopback versus duplex mode
    cx_loop_duplex: cross cp_loopbck, cp_fulld {
      bins loop_full    = binsof(cp_loopbck.loopback)    && binsof(cp_fulld.full_duplex);
      bins loop_half    = binsof(cp_loopbck.loopback)    && binsof(cp_fulld.half_duplex);
      bins no_loop_full = binsof(cp_loopbck.no_loopback) && binsof(cp_fulld.full_duplex);
      bins no_loop_half = binsof(cp_loopbck.no_loopback) && binsof(cp_fulld.half_duplex);
    }
  endgroup

  // -------------------------------------------------------------------------
  // 5. CTRLMODER register write — flow control bit coverage
  // -------------------------------------------------------------------------
  covergroup cg_ctrlmoder_write @(posedge wb_clk_i iff
      (wb_stb_i && wb_cyc_i && wb_we_i && |wb_sel_i &&
       !wb_adr_i[11] && !wb_adr_i[10] && wb_adr_i[9:2] == CTRLMODER_ADR));
    option.cross_auto_bin_max = 0;

    cp_txflow: coverpoint wb_dat_i[CTRLMODER_TXFLOW] {
      bins txflow_off = {1'b0};
      bins txflow_on  = {1'b1};
    }

    cp_rxflow: coverpoint wb_dat_i[CTRLMODER_RXFLOW] {
      bins rxflow_off = {1'b0};
      bins rxflow_on  = {1'b1};
    }

    cx_flow_cfg: cross cp_txflow, cp_rxflow {
      bins both_on    = binsof(cp_txflow.txflow_on)  && binsof(cp_rxflow.rxflow_on);
      bins tx_on_only = binsof(cp_txflow.txflow_on)  && binsof(cp_rxflow.rxflow_off);
      bins rx_on_only = binsof(cp_txflow.txflow_off) && binsof(cp_rxflow.rxflow_on);
      bins both_off   = binsof(cp_txflow.txflow_off) && binsof(cp_rxflow.rxflow_off);
    }
  endgroup

  // -------------------------------------------------------------------------
  // 6. PACKETLEN register write — frame length range coverage
  // -------------------------------------------------------------------------
  covergroup cg_packetlen_write @(posedge wb_clk_i iff
      (wb_stb_i && wb_cyc_i && wb_we_i && |wb_sel_i &&
       !wb_adr_i[11] && !wb_adr_i[10] && wb_adr_i[9:2] == PACKETLEN_ADR));
    option.cross_auto_bin_max = 0;

    // MinFL lives in bits [15:0], MaxFL in bits [31:16]
    cp_minfl: coverpoint wb_dat_i[15:0] {
      bins min_zero    = {16'h0000};
      bins min_small   = {[16'h0001:16'h003C]};    // 1..60 bytes
      bins min_default = {16'h0040};               // 64 bytes (default min)
      bins min_other[] = default;
    }

    cp_maxfl: coverpoint wb_dat_i[31:16] {
      bins max_default    = {16'h05EE};            // 1518 bytes (default)
      bins max_jumbo      = {[16'h05EF:16'hFFFF]}; // > 1518 (jumbo / huge)
      bins max_small      = {[16'h0001:16'h05ED]};
      bins max_zero       = {16'h0000};
    }

    cx_minfl_maxfl: cross cp_minfl, cp_maxfl {
      bins default_sizes   = binsof(cp_minfl.min_default) && binsof(cp_maxfl.max_default);
      bins small_max       = binsof(cp_minfl.min_small)   && binsof(cp_maxfl.max_small);
      bins jumbo_max       = binsof(cp_minfl.min_default) && binsof(cp_maxfl.max_jumbo);
    }
  endgroup

  // -------------------------------------------------------------------------
  // 7. MIICOMMAND write — MIIM scan/read/write command bits
  // -------------------------------------------------------------------------
  covergroup cg_miicommand_write @(posedge wb_clk_i iff
      (wb_stb_i && wb_cyc_i && wb_we_i && |wb_sel_i &&
       !wb_adr_i[11] && !wb_adr_i[10] && wb_adr_i[9:2] == MIICOMMAND_ADR));
    option.cross_auto_bin_max = 0;

    cp_scanstat: coverpoint wb_dat_i[2] {
      bins no_scan = {1'b0};
      bins scan    = {1'b1};
    }

    cp_rstat: coverpoint wb_dat_i[1] {
      bins no_read = {1'b0};
      bins read    = {1'b1};
    }

    cp_wctrldata: coverpoint wb_dat_i[0] {
      bins no_write = {1'b0};
      bins write    = {1'b1};
    }

    cx_miim_cmd: cross cp_scanstat, cp_rstat, cp_wctrldata {
      bins read_phy    = binsof(cp_rstat.read)      && binsof(cp_wctrldata.no_write) &&
                         binsof(cp_scanstat.no_scan);
      bins write_phy   = binsof(cp_wctrldata.write) && binsof(cp_rstat.no_read)      &&
                         binsof(cp_scanstat.no_scan);
      bins scan_phy    = binsof(cp_scanstat.scan)   && binsof(cp_rstat.no_read)      &&
                         binsof(cp_wctrldata.no_write);
    }
  endgroup

  // -------------------------------------------------------------------------
  // 8. MII TX output — nibble patterns, TX-enable transitions, error
  // -------------------------------------------------------------------------
  covergroup cg_mii_tx @(posedge mtx_clk_pad_i);
    option.cross_auto_bin_max = 0;

    cp_mtxen: coverpoint mtxen_pad_o {
      bins tx_idle   = {1'b0};
      bins tx_active = {1'b1};
    }

    cp_mtxen_trans: coverpoint mtxen_pad_o {
      bins tx_start  = (1'b0 => 1'b1);  // frame begins
      bins tx_end    = (1'b1 => 1'b0);  // frame ends
      bins tx_cont   = (1'b1 => 1'b1);
      bins tx_inter  = (1'b0 => 1'b0);  // inter-frame gap
    }

    cp_mtxd: coverpoint mtxd_pad_o {
      bins preamble_nib = {4'h5};    // 0101 – preamble
      bins sfd_nib      = {4'hD};    // 1101 – SFD
      bins all_zeros    = {4'h0};
      bins all_ones     = {4'hF};
      bins other[]      = default;
    }

    cp_mtxerr: coverpoint mtxerr_pad_o {
      bins no_err = {1'b0};
      bins tx_err = {1'b1};
    }

    // Specific nibbles observed while TX is active
    cx_txen_nibble: cross cp_mtxen, cp_mtxd {
      bins preamble_during_tx = binsof(cp_mtxen.tx_active) && binsof(cp_mtxd.preamble_nib);
      bins sfd_during_tx      = binsof(cp_mtxen.tx_active) && binsof(cp_mtxd.sfd_nib);
      bins zero_during_tx     = binsof(cp_mtxen.tx_active) && binsof(cp_mtxd.all_zeros);
      bins ones_during_tx     = binsof(cp_mtxen.tx_active) && binsof(cp_mtxd.all_ones);
      bins other_during_tx    = binsof(cp_mtxen.tx_active) && binsof(cp_mtxd.other);
    }

    // TX error asserted during active transmission
    cx_txen_err: cross cp_mtxen, cp_mtxerr {
      bins err_during_tx = binsof(cp_mtxen.tx_active) && binsof(cp_mtxerr.tx_err);
    }
  endgroup

  // -------------------------------------------------------------------------
  // 9. MII RX input — nibble patterns, DV transitions, RX error
  // -------------------------------------------------------------------------
  covergroup cg_mii_rx @(posedge mrx_clk_pad_i);
    option.cross_auto_bin_max = 0;

    cp_mrxdv: coverpoint mrxdv_pad_i {
      bins rx_idle   = {1'b0};
      bins rx_active = {1'b1};
    }

    cp_mrxdv_trans: coverpoint mrxdv_pad_i {
      bins rx_start = (1'b0 => 1'b1);   // SoF — first DV pulse
      bins rx_end   = (1'b1 => 1'b0);   // EoF — DV de-asserted
      bins rx_cont  = (1'b1 => 1'b1);
      bins rx_idle  = (1'b0 => 1'b0);
    }

    cp_mrxd: coverpoint mrxd_pad_i {
      bins preamble_nib = {4'h5};
      bins sfd_nib      = {4'hD};
      bins all_zeros    = {4'h0};
      bins all_ones     = {4'hF};
      bins other[]      = default;
    }

    cp_mrxerr: coverpoint mrxerr_pad_i {
      bins no_err = {1'b0};
      bins rx_err = {1'b1};
    }

    // Specific nibble patterns observed while DV is active
    cx_rxdv_nibble: cross cp_mrxdv, cp_mrxd {
      bins preamble_active = binsof(cp_mrxdv.rx_active) && binsof(cp_mrxd.preamble_nib);
      bins sfd_active      = binsof(cp_mrxdv.rx_active) && binsof(cp_mrxd.sfd_nib);
      bins data_zero       = binsof(cp_mrxdv.rx_active) && binsof(cp_mrxd.all_zeros);
      bins data_ones       = binsof(cp_mrxdv.rx_active) && binsof(cp_mrxd.all_ones);
      bins data_other      = binsof(cp_mrxdv.rx_active) && binsof(cp_mrxd.other);
    }

    // RX error asserted during active reception
    cx_rxdv_err: cross cp_mrxdv, cp_mrxerr {
      bins err_during_rx = binsof(cp_mrxdv.rx_active) && binsof(cp_mrxerr.rx_err);
    }
  endgroup

  // -------------------------------------------------------------------------
  // 10. PHY conditions — collision and carrier sense vs TX activity
  // -------------------------------------------------------------------------
  covergroup cg_phy_conditions @(posedge mtx_clk_pad_i);
    option.cross_auto_bin_max = 0;

    cp_coll: coverpoint mcoll_pad_i {
      bins no_coll = {1'b0};
      bins coll    = {1'b1};
    }

    cp_crs: coverpoint mcrs_pad_i {
      bins idle_channel = {1'b0};
      bins busy_channel = {1'b1};
    }

    cp_txen: coverpoint mtxen_pad_o {
      bins tx_idle   = {1'b0};
      bins tx_active = {1'b1};
    }

    // Collision during active TX (half-duplex contention)
    cx_coll_txen: cross cp_coll, cp_txen {
      bins coll_during_tx   = binsof(cp_coll.coll)    && binsof(cp_txen.tx_active);
      bins coll_between_frm = binsof(cp_coll.coll)    && binsof(cp_txen.tx_idle);
      bins clean_tx         = binsof(cp_coll.no_coll) && binsof(cp_txen.tx_active);
    }

    // Carrier sense during TX (deference / backoff trigger)
    cx_crs_txen: cross cp_crs, cp_txen {
      bins crs_during_tx   = binsof(cp_crs.busy_channel) && binsof(cp_txen.tx_active);
      bins crs_before_tx   = binsof(cp_crs.busy_channel) && binsof(cp_txen.tx_idle);
    }

    // Collision and carrier sense simultaneously
    cx_coll_crs: cross cp_coll, cp_crs {
      bins both_asserted = binsof(cp_coll.coll) && binsof(cp_crs.busy_channel);
    }
  endgroup

  // -------------------------------------------------------------------------
  // 11. WISHBONE master (DMA) — TX reads and RX writes to memory
  // -------------------------------------------------------------------------
  covergroup cg_wb_master @(posedge wb_clk_i iff m_wb_cyc_o);
    option.cross_auto_bin_max = 0;

    cp_m_we: coverpoint m_wb_we_o {
      bins dma_read  = {1'b0};   // TX path: read frame data from memory
      bins dma_write = {1'b1};   // RX path: write received data to memory
    }

    cp_m_stb: coverpoint m_wb_stb_o {
      bins stb_low  = {1'b0};
      bins stb_high = {1'b1};
    }

    cp_m_ack: coverpoint m_wb_ack_i {
      bins no_ack = {1'b0};
      bins ack    = {1'b1};
    }

    cp_m_err: coverpoint m_wb_err_i {
      bins no_err = {1'b0};
      bins err    = {1'b1};
    }

    cp_m_cti: coverpoint m_wb_cti_o {
      bins classic      = {3'b000};
      bins incrementing = {3'b010};  // burst
      bins end_burst    = {3'b111};
      bins other[]      = default;
    }

    // DMA read (TX) and write (RX) successfully completed
    cx_dma_ack: cross cp_m_we, cp_m_ack {
      bins read_acked  = binsof(cp_m_we.dma_read)  && binsof(cp_m_ack.ack);
      bins write_acked = binsof(cp_m_we.dma_write) && binsof(cp_m_ack.ack);
    }

    // DMA bus error on read vs write
    cx_dma_err: cross cp_m_we, cp_m_err {
      bins read_err  = binsof(cp_m_we.dma_read)  && binsof(cp_m_err.err);
      bins write_err = binsof(cp_m_we.dma_write) && binsof(cp_m_err.err);
    }

    // Burst type × DMA direction
    cx_cti_dir: cross cp_m_cti, cp_m_we {
      bins burst_read   = binsof(cp_m_cti.incrementing) && binsof(cp_m_we.dma_read);
      bins burst_write  = binsof(cp_m_cti.incrementing) && binsof(cp_m_we.dma_write);
      bins eob_read     = binsof(cp_m_cti.end_burst)    && binsof(cp_m_we.dma_read);
      bins eob_write    = binsof(cp_m_cti.end_burst)    && binsof(cp_m_we.dma_write);
    }
  endgroup

  // -------------------------------------------------------------------------
  // 12. MIIM interface — MDC clock, data direction, MD signal patterns
  // -------------------------------------------------------------------------
  covergroup cg_miim @(posedge wb_clk_i);
    option.cross_auto_bin_max = 0;

    cp_mdc: coverpoint mdc_pad_o {
      bins mdc_low  = {1'b0};
      bins mdc_high = {1'b1};
    }

    cp_mdc_trans: coverpoint mdc_pad_o {
      bins mdc_rise = (1'b0 => 1'b1);
      bins mdc_fall = (1'b1 => 1'b0);
    }

    cp_md_oe: coverpoint md_padoe_o {
      bins md_input  = {1'b0};   // read from PHY — DUT receives
      bins md_output = {1'b1};   // write to PHY  — DUT drives
    }

    cp_md_out: coverpoint md_pad_o {
      bins md_low  = {1'b0};
      bins md_high = {1'b1};
    }

    cp_md_in: coverpoint md_pad_i {
      bins md_low  = {1'b0};
      bins md_high = {1'b1};
    }

    // MDC toggling while driving vs receiving
    cx_mdc_dir: cross cp_mdc, cp_md_oe {
      bins mdc_high_write = binsof(cp_mdc.mdc_high) && binsof(cp_md_oe.md_output);
      bins mdc_high_read  = binsof(cp_mdc.mdc_high) && binsof(cp_md_oe.md_input);
    }

    // MD output data while DUT is driving the pin
    cx_md_out_oe: cross cp_md_out, cp_md_oe {
      bins drive_high = binsof(cp_md_out.md_high) && binsof(cp_md_oe.md_output);
      bins drive_low  = binsof(cp_md_out.md_low)  && binsof(cp_md_oe.md_output);
    }

    // MD input data while DUT is listening
    cx_md_in_oe: cross cp_md_in, cp_md_oe {
      bins receive_high = binsof(cp_md_in.md_high) && binsof(cp_md_oe.md_input);
      bins receive_low  = binsof(cp_md_in.md_low)  && binsof(cp_md_oe.md_input);
    }
  endgroup

  // -------------------------------------------------------------------------
  // 13. Interrupt output — assertion, de-assertion and sustained patterns
  // -------------------------------------------------------------------------
  covergroup cg_interrupt @(posedge wb_clk_i);
    option.cross_auto_bin_max = 0;

    cp_int: coverpoint int_o {
      bins no_irq = {1'b0};
      bins irq    = {1'b1};
    }

    cp_int_trans: coverpoint int_o {
      bins irq_rise  = (1'b0 => 1'b1);   // interrupt asserted
      bins irq_fall  = (1'b1 => 1'b0);   // interrupt cleared
      bins irq_hold  = (1'b1 => 1'b1);   // sustained pending interrupt
      bins irq_clear = (1'b0 => 1'b0);   // no pending interrupt
    }

    // Interrupt with WB bus read of INT_SOURCE (software clearing)
    cp_int_source_rd: coverpoint
        (wb_stb_i && wb_cyc_i && !wb_we_i && |wb_sel_i &&
         !wb_adr_i[11] && !wb_adr_i[10] && wb_adr_i[9:2] == INT_SOURCE_ADR) {
      bins no_read = {1'b0};
      bins reading = {1'b1};
    }

    cx_int_source_read: cross cp_int, cp_int_source_rd {
      bins int_active_read  = binsof(cp_int.irq)    && binsof(cp_int_source_rd.reading);
      bins int_cleared_read = binsof(cp_int.no_irq) && binsof(cp_int_source_rd.reading);
    }
  endgroup

  // -------------------------------------------------------------------------
  // 14. Simultaneous TX+RX — observable via MII interface (full-duplex test)
  // -------------------------------------------------------------------------
  covergroup cg_simult_txrx @(posedge wb_clk_i);
    option.cross_auto_bin_max = 0;

    cp_tx_act: coverpoint mtxen_pad_o {
      bins tx_idle = {1'b0};
      bins tx_xmit = {1'b1};
    }

    cp_rx_act: coverpoint mrxdv_pad_i {
      bins rx_idle = {1'b0};
      bins rx_recv = {1'b1};
    }

    cp_coll: coverpoint mcoll_pad_i {
      bins no_coll = {1'b0};
      bins coll    = {1'b1};
    }

    // Simultaneous TX and RX (valid in full-duplex, indicates contention in half)
    cx_simult: cross cp_tx_act, cp_rx_act {
      bins tx_and_rx   = binsof(cp_tx_act.tx_xmit) && binsof(cp_rx_act.rx_recv);
      bins tx_only     = binsof(cp_tx_act.tx_xmit) && binsof(cp_rx_act.rx_idle);
      bins rx_only     = binsof(cp_tx_act.tx_idle) && binsof(cp_rx_act.rx_recv);
      bins both_idle   = binsof(cp_tx_act.tx_idle) && binsof(cp_rx_act.rx_idle);
    }

    // Collision while simultaneously transmitting and receiving
    cx_simult_coll: cross cp_tx_act, cp_rx_act, cp_coll {
      bins coll_while_txrx = binsof(cp_tx_act.tx_xmit) && binsof(cp_rx_act.rx_recv) &&
                             binsof(cp_coll.coll);
      bins coll_tx_only    = binsof(cp_tx_act.tx_xmit) && binsof(cp_rx_act.rx_idle) &&
                             binsof(cp_coll.coll);
    }
  endgroup

  // =========================================================================
  // Covergroup instantiation
  // =========================================================================
  cg_wb_reg_access    cov_wb_reg_access;
  cg_wb_bd_access     cov_wb_bd_access;
  cg_wb_response      cov_wb_response;
  cg_moder_write      cov_moder_write;
  cg_ctrlmoder_write  cov_ctrlmoder_write;
  cg_packetlen_write  cov_packetlen_write;
  cg_miicommand_write cov_miicommand_write;
  cg_mii_tx           cov_mii_tx;
  cg_mii_rx           cov_mii_rx;
  cg_phy_conditions   cov_phy_conditions;
  cg_wb_master        cov_wb_master;
  cg_miim             cov_miim;
  cg_interrupt        cov_interrupt;
  cg_simult_txrx      cov_simult_txrx;

  initial begin
    cov_wb_reg_access    = new();
    cov_wb_bd_access     = new();
    cov_wb_response      = new();
    cov_moder_write      = new();
    cov_ctrlmoder_write  = new();
    cov_packetlen_write  = new();
    cov_miicommand_write = new();
    cov_mii_tx           = new();
    cov_mii_rx           = new();
    cov_phy_conditions   = new();
    cov_wb_master        = new();
    cov_miim             = new();
    cov_interrupt        = new();
    cov_simult_txrx      = new();
  end

  // BEGIN_STIMULUS
  initial begin
    // Stimulus goes here

    $finish;
  end
  // END_STIMULUS

  // =========================================================================
  // Timeout watchdog
  // =========================================================================
  initial begin
    #10_000_000; // 10 ms at 1 ns resolution
    $display("WATCHDOG TIMEOUT – simulation did not finish");
    $finish;
  end

endmodule
