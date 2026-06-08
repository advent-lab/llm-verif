# Ethernet IP Core Design Document

**Author:** Igor Mohor  
IgorM@opencores.org

**Rev. 0.4**  
**October 29, 2002**

---

## Revision History

| Rev | Date | Author | Description |
|-----|------|--------|-------------|
| 0.1 | 09/09/02 | Igor Mohor | First Draft |
| 0.2 | 22/10/02 | Igor Mohor | Description of Core Modules added (figure), Some test description added. |
| 0.3 | 29/10/02 | Igor Mohor | Some figures added. |
| 0.4 | 29/10/02 | IM | Description of test cases added. |

---

## Table of Contents

1. [Introduction](#1-introduction)
    - 1.1 Ethernet IP Core Introduction
    - 1.2 Ethernet IP Core Features
    - 1.3 Ethernet IP Core Directory Structure

2. [Ethernet MAC IP Core](#2-ethernet-mac-ip-core)
    - 2.1 Overview
    - 2.2 Core File Hierarchy
    - 2.3 Description of Core Modules

3. [Ethernet MAC IP Core Testbench](#3-ethernet-mac-ip-core-testbench)
    - 3.1 Overview
    - 3.2 Testbench File Hierarchy
    - 3.3 Description of Testbench Modules
    - 3.4 Description of Testcases

---

## 1. Introduction

### 1.1 Ethernet IP Core Introduction

The Ethernet IP Core is a MAC (Media Access Controller). It connects to the Ethernet PHY chip on one side and to the WISHBONE SoC bus on the other. The core has been designed to offer as much flexibility as possible to all kinds of applications.

Chapter 2 describes file hierarchy, description of modules, core design considerations and constants regarding the Ethernet IP Core.

Chapter 3 describes test bench file hierarchy, description of modules, test bench design considerations, description of test cases and constants regarding the test bench.

### 1.2 Ethernet IP Core Features

The following lists the main features of the Ethernet IP core:

- Performing MAC layer functions of IEEE 802.3 and Ethernet
- Automatic 32-bit CRC generation and checking
- Delayed CRC generation
- Preamble generation and removal
- Automatically pad short frames on transmit
- Detection of too long or too short packets (length limits)
- Possible transmission of packets that are bigger than standard packets
- Full duplex support
- 10 and 100 Mbps bit rates supported
- Automatic packet abortion on Excessive deferral limit, too small inter packet gap, when enabled
- Flow control and automatic generation of control frames in full duplex mode (IEEE 802.3x)
- Collision detection and auto retransmission on collisions in half duplex mode (CSMA/CD protocol)
- Complete status for TX/RX packets
- IEEE 802.3 Media Independent Interface (MII)
- WISHBONE SoC Interconnection Rev. B2 and B3 compliant interface
- Internal RAM for holding 128 TX/RX buffer descriptors
- Interrupt generation on all events

### 1.3 Ethernet IP Core Directory Structure

```
ethernet/
├── rtl/
│   └── verilog/
│       ├── eth_top.v
│       ├── eth_crc.v
│       ├── eth_cop.v
│       ├── eth_miim.v
│       ├── eth_defines.v
│       ├── timescale.v
│       ├── eth_random.v
│       ├── eth_fifo.v
│       ├── eth_wishbone.v
│       ├── eth_maccontrol.v
│       ├── eth_rxaddrcheck.v
│       ├── eth_txstatem.v
│       ├── eth_transmitcontrol.v
│       ├── eth_txethmac.v
│       ├── generic_spram.v
│       ├── eth_rxcounters.v
│       ├── eth_rxstatem.v
│       ├── eth_outputcontrol.v
│       ├── eth_register.v
│       ├── eth_receivecontrol.v
│       ├── eth_registers.v
│       ├── eth_shiftreg.v
│       ├── eth_txcounters.v
│       ├── eth_clockgen.v
│       ├── eth_rxethmac.v
│       └── eth_macstatus.v
├── bench/
│   └── verilog/
│       ├── tb_ethernet.v
│       ├── tb_eth_defines.v
│       ├── tb_cop.v
│       ├── eth_host.v
│       └── eth_memory.v
├── sim/
│   └── rtl_sim/
│       ├── src/
│       └── run/
└── doc/
     ├── eth_speci.pdf
     ├── eth_design_document.pdf
     └── (other documentation)
```

There are two major parts of the Verilog code in the ethernet directory:

1. **RTL Code** – The code for the Ethernet MAC IP core is located in `ethernet/rtl/verilog/`
2. **Testbench Code** – The code for the Ethernet MAC Testbench is located in `ethernet/bench/verilog/`

The documentation is in the `ethernet/doc` subdirectory and consists of:
- Ethernet IP Core Data Sheet
- Ethernet IP Core Specification
- Ethernet IP Core Design document

The `ethernet/sim` subdirectory is used for running simulations. The `rtl_sim` subdirectory is used for RTL (functional) simulation of the core with simulator-specific directories:

- **bin** – Scripts needed for running simulators
- **run** – Directory from which simulations are executed; provides startup and cleanup scripts
- **log** – Compiler and elaboration log files
- **out** – Simulation output directory (dump files, testbench output, etc.)

---

## 2. Ethernet MAC IP Core

### 2.1 Overview

The Ethernet MAC IP Core consists of seven main units:

1. **WISHBONE Interface** – Connects the core to the WISHBONE bus with both master and slave interfaces
2. **Transmit Module** – Performs all transmitting-related operations (preamble generation, padding, CRC, etc.)
3. **Receive Module** – Performs all reception-related operations (preamble removal, CRC check, etc.)
4. **Control Module** – Performs all flow control operations in full duplex mode
5. **MII Module** – Provides an interface to the external Ethernet PHY chip
6. **Status Module** – Records different statuses written to buffer descriptors
7. **Register Module** – Contains registers used for Ethernet MAC operation

#### 2.1.1 WISHBONE Interface

Consists of both master and slave interfaces and connects the core to the WISHBONE bus. The master interface is used for storing received data frames to memory and loading transmit data from memory. The interface is WISHBONE Revision B.2 and B.3 compatible (selectable with the `ETH_WISHBONE_B3` define in `eth_defines.v`).

#### 2.1.2 Transmit Module

Performs all transmitting-related operations (preamble generation, padding, CRC, etc.).

#### 2.1.3 Receive Module

Performs all reception-related operations (preamble removal, CRC check, etc.).

#### 2.1.4 Control Module

Performs all flow control-related operations when Ethernet is used in full duplex mode.

#### 2.1.5 MII Module (Media Independent Module)

Provides a Media Independent interface to the external Ethernet PHY chip.

#### 2.1.6 Status Module

Records different statuses that are written to the related buffer descriptors or used in some other modules.

#### 2.1.7 Register Module

Registers used for Ethernet MAC operation are in this module.

### 2.2 Core File Hierarchy

RTL source files of the Ethernet core are located in `ethernet/rtl/verilog/`. Each file implements one module in the hierarchy.

```
ethernet/rtl/verilog/
├── eth_top.v
├── eth_crc.v
├── eth_cop.v
├── eth_miim.v
├── eth_defines.v
├── timescale.v
├── eth_random.v
├── eth_fifo.v
├── eth_wishbone.v
├── eth_maccontrol.v
├── eth_rxaddrcheck.v
├── eth_txstatem.v
├── eth_transmitcontrol.v
├── eth_txethmac.v
├── generic_spram.v
├── eth_rxcounters.v
├── eth_rxstatem.v
├── eth_outputcontrol.v
├── eth_register.v
├── eth_receivecontrol.v
├── eth_registers.v
├── eth_shiftreg.v
├── eth_txcounters.v
├── eth_clockgen.v
├── eth_rxethmac.v
└── eth_macstatus.v
```

**Documentation files:**
```
ethernet/doc/
├── eth_speci.pdf
├── eth_design_document.pdf
└── Ethernet Datasheet (prl.).pdf
```

### 2.3 Description of Core Modules

The top-level module `eth_top.v` contains submodules: `eth_miim.v`, `eth_registers.v`, `eth_maccontrol.v`, `eth_txethmac.v`, `eth_rxethmac.v`, `eth_wishbone.v`, `eth_macstatus.v`, and synchronization/multiplexing logic.

#### 2.3.1 MII Module (eth_miim.v)

The MII module is an interface to the external Ethernet PHY chip. It is used for setting PHY configuration registers and reading status from it. The interface consists of two signals:
- **MDC** – Clock signal
- **MDIO** – Bi-directional data signal

The MDIO signal is combined from input signal `Mdi`, output signal `Mdo`, and enable signal `MdoEn` in an additional module.

**Submodules:**
- `eth_clockgen.v` – Generates MII clock signal and enable
- `eth_shiftreg.v` – Handles serialization/deserialization
- `eth_outputcontrol.v` – Generates output signals and preamble

**MII Operations:**

To read or write data from the PHY chip:

1. Set the MIIMODER register:
    - Clock divider for appropriate MDC frequency
    - Preamble generation (optional)
    - Module reset (optional)

2. Set PHY address and register address in MIIADDRESS register

3. (If writing) Write data to MIITX_DATA register

4. Write appropriate value to MIICOMMAND register to start operation

5. (If reading) Read result from MIIRX_DATA register

The MIISTATUS register reflects the MII module status. The LinkFail status is cleared only after a read to the PHY's status register (address 0x1) returns OK status.

##### 2.3.1.1 eth_outputcontrol Module

- Generates MII serial output signal (`Mdo`)
- Generates enable signal (`MdoEn`) for the output
- Generates the MII preamble (32-bit when enabled via MIIMODER bit 8)

##### 2.3.1.2 eth_clockgen Module

- Generates MII clock signal (MDC) – output clock for the PHY interface
- Generates MdcEn enable signal for reduced frequency operation
- MDC is obtained by dividing the main clock with a value in the MIIMODER register (range 1–255)

##### 2.3.1.3 eth_shiftreg Module

- Serializes data toward Ethernet PHY chip (Mdo)
- Parallelizes input data from Ethernet PHY chip (Mdi) and stores to Prsd register
- Generates LinkFail signal (reflected in MIISTATUS register bit 0)

#### 2.3.2 Receive Module (eth_rxethmac.v)

The Receive module handles receiving data from the external PHY chip. The PHY receives serial data from the physical medium, assembles it to nibbles, and sends it as `MRxD[3:0]` with a "data valid" marker (`MRxDV`). The receive module assembles nibbles into bytes, removes preamble and CRC, and sends data to the WISHBONE interface.

**Submodules:**
- `eth_crc.v` – Cyclic Redundancy Check
- `eth_rxaddrcheck.v` – Address recognition
- `eth_rxcounters.v` – Counters for reception
- `eth_rxstatem.v` – State machine

**Receiver Configuration Signals:**

- **HugEn** – Enable reception of oversized packets (larger than MaxFL)
- **DlyCrcEn** – Delayed CRC checking (starts 4 bytes after data valid)
- **r_IFG** – Minimum Inter Frame Gap; set to 1 to receive all frames regardless of IFG
- **r_Pro, r_Bro, r_Iam** – Address recognition modes
- **MAC, HASH0, HASH1** – Address filtering registers

**Output Signals:**

- **RxValid, RxStartFrm, RxEndFrm** – Data validity markers
- **Broadcast, Multicast** – Frame type indicators
- **CrcHash, CrcHashGood** – CRC-based address filtering

##### 2.3.2.1 CRC Module (eth_crc.v)

Validates the correctness of incoming packets by checking the CRC value. The CRC is also used by the TX module for CRC generation.

**CRC Checking Process:**

1. Transmitter appends CRC (calculated from data) to create a frame
2. Receiver recalculates CRC from received data (including the CRC bytes)
3. If result differs from the "CRC Magic Number" (0xc704dd7b), `CrcError` is set

##### 2.3.2.2 Address Recognition Module (eth_rxaddrcheck.v)

Decides whether a packet will be received or rejected based on:

- **Promiscuous Mode** (`r_Pro`) – If set, all frames are received; if cleared, destination address is checked
- **Broadcast Rejection** (`r_Bro`) – If set, broadcast address frames are rejected (requires `r_Pro` cleared)
- **MAC Address** – Compared to destination address when not in promiscuous mode; frame accepted on match
- **Hash Table** (`r_Iam`) – Uses hash table algorithm on 48-bit addresses (mapped to 64 bits); frame accepted if corresponding bit is set in HASH registers

Packet reception always begins regardless of destination address. Once the destination address is received, it is checked against the above conditions. If no match occurs, reception is aborted (`RxAbort` set), the packet is not written to memory, and the receive buffer is flushed.

##### 2.3.2.3 RxCounters Module (eth_rxcounters.v)

Contains three counters:

- **ByteCnt** – General counter for receive module
- **IFGCounter** – Counts Inter Frame Gap
- **DlyCrcCnt** – Used when delayed CRC operation is enabled

Also contains comparators for various purposes.

##### 2.3.2.4 RxStatem Module (eth_rxstatem.v)

Single state machine with six states:

1. **StateIdle** – Waiting for valid data
2. **StatePreamble** – Receiving preamble
3. **StateSFD** – Receiving Start Frame Delimiter
4. **StateData0** – Receiving even-indexed data nibbles
5. **StateData1** – Receiving odd-indexed data nibbles
6. **StateDrop** – Dropping frame due to IFG violation

**Operation:**

- After reset, SM enters StateDrop, then StateIdle
- When MRxDV is set, SM transitions to StatePreamble if a 0x5 nibble is not immediately received
- After receiving 0x5 nibble, SM moves to StateSFD waiting for 0xd nibble
- If `IFGCounterEq24` is set (appropriate inter-frame gap detected or IFG disabled):
  - SM alternates between StateData0 and StateData1 to assemble frame
  - SM transitions to StateIdle when MRxDV clears
- If `IFGCounterEq24` is cleared (insufficient gap):
  - SM goes to StateDrop; frame is rejected
  - SM returns to StateIdle when MRxDV clears

#### 2.3.3 Transmit Module (eth_txethmac.v)

The Transmit module handles transmission of data received from the WISHBONE interface in byte form. It also receives signals marking frame start (`TxStartFrm`) and end (`TxEndFrm`). The module signals the WISHBONE interface via `TxUsedData` when the next byte is needed.

**Submodules:**
- `eth_crc.v` – Generates 32-bit CRC appended to data
- `eth_random.v` – Generates random backoff delay after collision
- `eth_txcounters.v` – Counters for transmission
- `eth_txstatem.v` – State machine

**PHY Interface Signals:**

- **MTxD** – Data nibble to be transmitted
- **MTxEn** – Transmit enable (tells PHY transmission is valid)
- **MTxErr** – Transmit error indicator

**WISHBONE Interface Signals:**

- **TxDone** – Transmission successfully finished
- **TxRetry** – Transmission needs to be repeated (collision in half-duplex mode)
- **TxAbort** – Transmission aborted
- **TxUsedData** – Request for next data byte

**Transmission Outcomes:**

- **Success** (`TxDone`): Frame transmitted successfully
- **Retry** (`TxRetry`): Normal collision occurred (half-duplex mode only)
- **Abort** (`TxAbort`):
  - Packet exceeds maximum size (MAXFL)
  - Underrun (WISHBONE cannot provide data on time)
  - Excessive deferral (state machine in defer state too long)
  - Late collision (occurs after COLLVALID bytes of preamble)
  - Maximum retry limit exceeded (MAXRET)

**Additional Signals:**

- **WillTransmit** – Notifies receiver that transmission will start
- **ResetCollision** – Resets collision synchronizing flip-flop
- **ColWindow** – Valid collision window; collisions outside this window are late collisions
- **RetryCnt** – Retry counter
- **Data_Crc, Enable_Crc, Initialize_Crc** – CRC generation control

##### 2.3.3.1 CRC Module (eth_crc.v)

Calculates CRC appended to the data frame. Also used in the RX module for CRC checking.

##### 2.3.3.2 Random Module (eth_random.v)

Upon collision, transmitter sends a "jam" pattern (0x99999999) then stops. Before retransmission, backoff delay is calculated here using Binary Exponential algorithm. Backoff time is randomized within predefined limits that increase with collision count.

##### 2.3.3.3 TxCounters Module (eth_txcounters.v)

Contains three counters:

- **DlyCrcCnt** – Used for delayed CRC generation
- **NibCnt** – Counts nibbles
- **ByteCnt** – Counts bytes (resolution depends on need)

##### 2.3.3.4 TxStatem Module (eth_txstatem.v)

State machine with eleven states:

1. **StateIdle** – Waiting for transmission request
2. **StatePreamble** – Transmitting preamble (0x5555555)
3. **StateData0** – Transmitting even-indexed data nibbles
4. **StateData1** – Transmitting odd-indexed data nibbles
5. **StatePAD** – Padding frame to minimum length
6. **StateFCS** – Appending 32-bit CRC
7. **StateIPG** – Inter Packet Gap
8. **StateJam** – Transmitting jam pattern
9. **StateJam_q** – Jam state continuation
10. **StateBackOff** – Collision backoff wait
11. **StateDefer** – Deferring transmission

**Normal Transmission Flow:**

1. WISHBONE sets `TxStartFrm` for two cycles with first data byte
2. SM moves to StatePreamble; `MTxEn` set to 1; preamble nibbles (0x5) transmitted
3. SFD nibble (0xd) transmitted
4. SM alternates between StateData0/StateData1; TxUsedData signals for next byte
5. When `TxEndFrm` received, depending on configuration:
    - **Minimum length met, CRC enabled** → StateFCS → StateDefer → StateIPG → StateIdle
    - **Minimum length met, CRC disabled** → StateDefer → StateIPG → StateIdle
    - **Below minimum, padding enabled** → StatePAD → StateFCS → StateDefer → StateIPG → StateIdle
    - **Below minimum, padding disabled, CRC enabled** → StateFCS → StateDefer → StateIPG → StateIdle
    - **Below minimum, padding disabled, CRC disabled** → StateDefer → StateIPG → StateIdle

#### 2.3.4 Control Module (eth_maccontrol.v)

Handles data flow control in 100Mbps full duplex mode by sending and receiving pause control frames.

**Flow Control Operation:**

- When the device connected to the WISHBONE interface cannot process received packets, it requests a pause by sending a pause control frame to the other station
- Upon receiving pause request, the other station stops transmitting
- Transmission resumes after the pause time expires or the pause request is disabled

**Submodules:**
- `eth_transmitcontrol.v` – Handles transmit flow control
- `eth_receivecontrol.v` – Handles receive flow control

**Multiplexing:**

Logic multiplexes data and control signals:
- Normal transmission signals (TxData, TxStartFrm, TxEndFrm, TxUsedData, TxAbort, TxDone)
- Control frame transmission signals

When control frames are sent, padding and CRC generation are automatically enabled (PadOut and CrcEnOut signals).

#### 2.3.5 Status Module (eth_macstatus.v)

Monitors Ethernet MAC operations and writes status to related buffer descriptors after each completed operation.

**RX Status Signals:**

Statuses are latched at end of reception (TakeSample = 1) and reset shortly after (LoadRxStatus = 1).

- **LatchedMRxErr** – PHY detected error during frame reception
- **LatchedCrcError** – Frame with invalid CRC received (affect pause frame processing)
- **InvalidSymbol** – Invalid symbol detected (100 Mbps mode, PHY sets data to 0xe)
- **RxLateCollision** – Late collision during reception
- **ShortFrame** – Frame shorter than minimum length (controlled by RECSMALL bit in MODER)
- **ReceivedPacketTooBig** – Frame exceeds maximum size (controlled by HUGEN bit in MODER)
- **DribbleNibble** – Extra nibble at end of frame (frame not byte-aligned); simultaneous with CRC error

**TX Status Signals:**

- **RetryCntLatched** – Number of retries before successful transmission (written to RTRY field of TX BD)
- **RetryLimit** – Retransmission attempts exceeded limit (bit RL set in TX BD)
- **LateCollLatched** – Late collision during transmission; transmission aborted (bit LC set in TX BD)
- **DeferLatched** – Frame deferred before successful transmission (bit DF set in TX BD)
- **CarrierSenseLost** – Carrier Sense lost during transmission (bit CS set in TX BD)

**Other Status Signals (Generated in Other Modules):**

- **UnderRun** – Detected in WISHBONE module; host could not provide data on time
- **OverRun** – Detected in WISHBONE module; host could not store data on time; RX FIFO overflowed
- **Miss** – Set when PRO bit enabled; indicates received frame does not contain valid address

**Additional Signals:**

- **ReceivedLengthOK** – Received frame has valid length
- **ReceiveEnd** – End of reception (used in control module for cleanup and pause timer)

#### 2.3.6 Registers Module (eth_registers.v)

Contains registers used for Ethernet MAC operation. Refer to the Ethernet IP Core Specification for detailed register descriptions.

All registers are described as 32-bit but only the required width is used; remaining bits are fixed to zero. Each register is instantiated with two parameters:
- **WIDTH** – Register width
- **RESET_VALUE** – Reset value (zero or predefined)

##### 2.3.6.1 eth_register Module (eth_register.v)

Single-register module parameterized with:
- **WIDTH** – Register width
- **RESET_VALUE** – Reset value

#### 2.3.7 WISHBONE Interface Module (eth_wishbone.v)

Interfaces the Ethernet MAC with other devices (memory, host) via two WISHBONE buses (slave and master).

**Functions:**

- Master/slave WISHBONE interface management
- Buffer descriptor storage (internal RAM)
- TX and RX FIFO management
- Clock domain crossing synchronization
- TX/RX operation sequencing (read BD, fill FIFO, start transmission, write status)

##### 2.3.7.1 WISHBONE Slave Interface

Addresses Ethernet registers and buffer descriptors through a single interface. Registers are in `eth_registers` module; BDs are in internal RAM. Register/BD selection is done in `eth_top`. All accesses reaching `eth_wishbone` are for buffer descriptors.

Output signals (from slave interface) can be registered or not, controlled by `ETH_REGISTERED_OUTPUTS` define in `eth_defines.v`.

##### 2.3.7.2 WISHBONE Master Interface

The Ethernet core uses the WISHBONE master interface to access memory where data buffers are stored. Both TX and RX access through the same interface via a multiplexing state machine.

**Key Signals:**

- **MasterWbTX** – Transmitter uses WISHBONE bus
- **MasterWbRX** – Receiver uses WISHBONE bus
- **ReadTxDataFromMemory_2** – Transmitter requests data
- **WriteRxDataToMemory** – Receiver requests write
- **MasterAccessFinished** – Access complete (acknowledge or error)
- **cyc_cleared** – Cycle signal cleared for COP traffic limitations
- **tx_burst, rx_burst** – Burst transaction signals

**Non-Aligned Access Handling:**

**TX non-aligned access:**
- Pointer stored in TxPointerMSB (word-aligned) and TxPointerLSB (byte offset)
- TxPointerLSB_rst used to reset after first access
- TxLength decremented by valid bytes (1–4)

**RX non-aligned access:**
- Pointer stored in RxPointerMSB (word-aligned) and RxPointerLSB_rst (byte offset)
- RxByteSel indicates which bytes are valid
- RxByteCnt counts bytes within word

##### 2.3.7.3 TX and RX Buffer Descriptors

Buffer descriptors are located at addresses 0x400–0x7FF (internal RAM). Each BD is 8 bytes: 4 bytes status + 4 bytes pointer.

Access to BDs requires the MAC to be out of reset. Once the READY bit is set in TX BD (or RX BD), the descriptor cannot be changed until the transmitter (or receiver) clears it.

**Total:** 128 BDs shared between TX and RX

**Distribution:** Controlled by TX_BD_NUM register
- Example: TX_BD_NUM = 0x32 → 50 TX BDs + 78 RX BDs
- TX BDs: 0x400–0x58C
- RX BDs: 0x590–0x7FC

Three devices access the single-port RAM:
- Host (WISHBONE slave interface)
- Transmitter
- Receiver

A state machine (WbEn, RxEn, TxEn generation) provides smart multiplexing based on RxEn_needed and TxEn_needed signals.

**RX BD Access Flow:**
1. After reset, RxBDRead = 1, RxBDReady = 0; RxEn_needed = 1
2. Read cycle fetches empty BD (EMPTY bit = 1)
3. Another read fetches pointer from BD + RxPointerRead offset
4. RxEn_needed = 0; reception starts
5. When frame received (ShiftEnded = 1), RxBDReady = 0, RxEn_needed = 1
6. Status written to RX BD; address incremented; next BD read begins

**TX BD Access Flow:** Similar to RX, using TxBDRead, TxBDReady, TxPointerRead, TxStatusWrite signals.

##### 2.3.7.4 TX and RX FIFO

Both TX and RX have FIFOs. Configuration defines in `eth_defines.v`:
- **TX FIFO:** TX_FIFO_CNT_WIDTH, TX_FIFO_DEPTH, TX_FIFO_DATA_WIDTH
- **RX FIFO:** RX_FIFO_CNT_WIDTH, RX_FIFO_DEPTH, RX_FIFO_DATA_WIDTH

Currently both are 16 words deep.

**TX FIFO Operation:**
- TX BD read (status + pointer)
- Data read from memory via master WISHBONE → TX FIFO
- Transmission starts when FIFO full (minimize underruns)
- Next read when space available for ≥1 word

**RX FIFO Operation:**
- RX BD read (status + pointer) + incoming data in FIFO (≥1 word)
- Write to memory immediately
- Next frame reception after FIFO empty

##### 2.3.7.5 Synchronization Logic

Standard approach: at least two flip-flops used for clock domain crossing. Signals available long before use may not be synchronized.

---

## 3. Ethernet MAC IP Core Testbench

### 3.1 Overview

The testbench provides a complete environment for testing the Ethernet MAC IP Core, including:
- Simplified Ethernet PHY model
- WISHBONE bus models with monitors
- Test cases for stimulus and verification

### 3.2 Testbench File Hierarchy

Source files are located in `ethernet/bench/verilog/`:

```
tb_ethernet.v
├── eth_top.v (UUT – Unit Under Test)
├── eth_phy.v
│   ├── PHY control register
│   ├── PHY status register
│   ├── RX function (error generation)
│   └── TX function
├── wb_bus_monitor.v (master monitor)
├── wb_bus_monitor.v (slave monitor)
├── wb_master_behavioral.v
│   ├── wb_master32.v
│   └── SRAM block
├── wb_slave_behavioral.v
│   └── SRAM block
├── tb_eth_defines.v
├── tb_cop.v
├── eth_host.v
└── eth_memory.v
```

**Key Modules:**
- **tb_ethernet.v** – Top testbench module (test environment, tasks, UUT instantiation)
- **eth_phy.v** – Simplified Intel LXT971A PHY chip model
- **wb_bus_monitor.v** – Monitors WISHBONE bus activity and protocol compliance
- **wb_master_behavioral.v** – WISHBONE master initiates cycles; includes wb_master32.v submodule
- **wb_slave_behavioral.v** – WISHBONE slave responds to master cycles
- **eth_host.v, eth_memory.v** – Host and memory models

### 3.3 Description of Testbench Modules

#### 3.3.1 Ethernet PHY Module (eth_phy.v)

Simulates a simplified Intel LXT971A PHY chip.

**Clock Signals:**

- **mtx_clk_o** – Transmit clock
- **mrx_clk_o** – Receive clock
- Frequency: 2.5 MHz (10 Mbps) or 25 MHz (100 Mbps), controlled by bit [13]
- TX and RX clocks are asynchronous
- When link is down, RX clock oscillates randomly between 2–40 MHz

**PHY Registers:**

- Control register
- Status register
- Two Identification registers

**MIIM Interface:**

Connected to Ethernet core; all transactions monitored with error/warning reporting.

**Carrier Sense & Collision:**

Both signals can be set via tasks.

**Data Transmission:**

- **PHY receiving** (Ethernet core transmitting): PHY controls protocol (preamble, SFD, length control, data storage to PHY memory)
- **PHY transmitting** (Ethernet core receiving): PHY generates various preambles (variable length, intentional errors); reads data from PHY memory (testbench must write data beforehand)

#### 3.3.2 WISHBONE Submodules

##### 3.3.2.1 wb_bus_monitor.v

Monitors both WISHBONE buses for protocol errors:

1. **Master to Slave Bus** – Ethernet MAC core master sending to slave (memory interface)
2. **Slave to Master Bus** – External master (behavioral model) sending to Ethernet MAC core slave (register/BD access)

Two bus monitors, one per bus.

##### 3.3.2.2 wb_master_behavioral.v

Initiates WISHBONE cycles to the Ethernet MAC core slave (for register and BD access). Includes `wb_master32.v` submodule for generating proper WISHBONE cycles. Contains SRAM block.

Controlled via top-level directives.

##### 3.3.2.3 wb_slave_behavioral.v

Responds to cycles initiated by the Ethernet MAC core master (data read/write). Response type and timing controlled by top-level. Contains SRAM block.

### 3.4 Description of Testcases

Helper tasks (clear_memories, hard_reset, reset_mac, reset_mii) support proper testbench operation but are not standalone testcases.

All testcases are in `tb_ethernet.v`. Many testcases are combined with multiple tasks or are parts of larger tasks. System parameters (wbm_init_waits, wbm_subseq_waits, etc.) are used with various combinations during test execution.

**Test Results:** Log files in `ethernet/sim/rtl_sim/nc_sim/log/`:
- **eth_tb.log** – SUCCESSFUL/FAIL status for all testcases
- **eth_tb_wb_m_mon.log** – Master WISHBONE bus monitoring results
- **eth_tb_wb_s_mon.log** – Slave WISHBONE bus monitoring results
- **eth_tb_phy.log** – PHY signal monitoring results

#### 3.4.1 MAC Registers and Buffer Descriptors Tests

**Register Tests (test_access_to_mac_reg):**

- Walking 1 pattern across MAC registers using single cycles
- Maximum register value testing
- Testing register values after writing inverse reset values
- Register behavior after hard reset of MAC

**Buffer Descriptor Tests:**

- Walking 1 pattern across MAC buffer descriptors
- RAM value preservation after hard reset and logic reset

#### 3.4.2 MIIM Module Tests

**Clock Divider Tests:**

- Test MII clock divider with all possible frequencies

**PHY Read/Write Tests:**

- Various PHY register reads
- Various PHY register writes (including non-writable registers)
- PHY reset via MII interface

**PHY Address Tests (Walking One):**

- Walking one pattern across PHY address (with/without preamble)
- Walking one pattern across PHY register address (with/without preamble)
- Walking one pattern across PHY data (with/without preamble)

**Error/Edge Case Tests:**

- Read from incorrect PHY address (host receives high-Z data)
- Write to incorrect PHY address; read from correct address
- Sliding stop scan command immediately after read request (with/without preamble)
- Sliding stop scan command immediately after write request (with/without preamble)

**Status Duration Tests:**

- BUSY/NVALID status timing during write (with/without preamble)
- BUSY/NVALID status timing during scan (with/without preamble)

**Scan/LinkFail Tests:**

- Scan status from PHY with LinkFail bit detection (with/without preamble)
- Scan status with sliding/alternating LinkFail bit (with/without preamble)
- Sliding stop scan command after 2nd scan (with/without preamble)

