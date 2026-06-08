# Ethernet IP Core Specification

**Author:** Igor Mohor  
IgorM@opencores.org

**Rev. 1.19**  
**November 27, 2002**

---

## Revision History

| Rev. | Date | Author | Description |
|------|------|--------|-------------|
| 0.1 | 13/03/01 | Igor Mohor | First Draft |
| 0.2 | 17/03/01 | Igor Mohor | MDC clock divider changed. Instead of the clock select bits CLKS[2:0] the clock divider bits CLKDIV[7:0] are used. |
| 1.0 | 21/03/01 | Igor Mohor | MII module completed. Revision changed to 1.0 due to cvs demands. |
| 1.1 | 16/04/01 | IM | DMA support and buffer descriptors added. |
| 1.2 | 24/05/01 | IM | Registers revised. |
| 1.3 | 05/06/01 | IM | Status is written to the status registers. DMA channels 2 and 3 are not used any more. Figures that are implementation specific removed from the document. |
| 1.4 | 03/07/01 | IM | COLLCONF register changed bit width. BCKPRESS and BCKPNBEN bit removed from MODER. LOOPBCK added. |
| 1.5 | 21/07/01 | IM | Signal RD0_O (Restart Descriptor for channel 0) added. Per packet CRC, BD changed. |
| 1.6 | 03/12/01 | IM | BD section rewritten. |
| 1.7 | 05/12/01 | IM | TX_BD_NUM register used instead of RX_BD_BASE_ADDR register. |
| 1.8 | 07/01/02 | IM | Minor typos fixed |
| 1.9 | 30/01/02 | IM | RST bit in MODER register is 1 after reset, initial collision window changed. |
| 1.10 | 18/02/02 | IM | Address recognition system added. Buffer Descriptors changed. DMA section changed. Ports changed. |
| 1.11 | 02/03/02 | IM | Typos fixed, INT_SOURCE and INT_MASK registers changed. |
| 1.12 | 15/03/02 | IM | TX_BD_NUM, MAC_ADDR0 and MAC_ADDR1 register description changed. |
| 1.13 | 15/04/02 | Jeanne Wiegelmann | Document revised. |
| 1.14 | 14/05/02 | IM | Minor typos fixed. |
| 1.15 | 14/08/02 | IM | LINKFAIL and NVALID bit description changed in the MIISTATUS register. TX_BD_NUM changed. External DMA support removed from the document. |
| 1.16 | 04/09/02 | IM | RX_BD_NUM changed to TX_BD_NUM in the register table. MIIRX_DATA bits changed to read only. MIIMRST bit in MIIMODER register moved from bit[10] to bit[9]. Description of the RXEN and TXEN bits in MODER register is modified. Description of the CTRLMODER and INT_SOURCE register changed. |
| 1.17 | 14/11/02 | IM | Few minor changes in the Tx BD, Rx BD and Host Interface sections. Bit description in the INT_SOURCE register improved. Frame reception section fixed. Minimum tx and rx length defined in the Frame Transmission and Frame Reception sections. RST bit in MODER removed. |
| 1.18 | 22/11/02 | IM | MIIMRST (Reset of the MIIM module) not used any more in the MIIMODER register. Control Frame bit (CF) added to the RX buffer descriptor. Control frame detection section updated. |
| 1.19 | 27/11/02 | IM | Control frame detection section improved. |

---

## Table of Contents

1. [Introduction](#1-introduction)
2. [IO Ports](#2-io-ports)
    - 2.1 Ethernet Core IO ports
    - 2.1.1 Host Interface Ports
    - 2.1.2 PHY Interface ports
3. [Registers](#3-registers)
    - 3.1 MODER (Mode Register)
    - 3.2 INT_SOURCE (Interrupt Source Register)
    - 3.3 INT_MASK (Interrupt Mask Register)
    - 3.4–3.21 [Register descriptions]
4. [Operation](#4-operation)
    - 4.1 Resetting Ethernet Core
    - 4.2 Host Interface Operation
    - 4.3–4.6 [Operation details]
5. [Architecture](#5-architecture)
    - 5.1–5.5 [Architecture sections]

---

## 1. Introduction

The Ethernet IP Core consists of five modules:

- **MAC (Media Access Control) module** – formed by transmit, receive, and control module
- **MII (Media Independent Interface) Management module**
- **Host Interface**

The Ethernet IP Core is capable of operating at 10 or 100 Mbps for Ethernet and Fast Ethernet applications. An external PHY is needed for the complete Ethernet solution.

---

## 2. IO Ports

### 2.1 Ethernet Core IO Ports

The Ethernet IP Core uses three types of signals to connect to media:

- WISHBONE signals to connect to the Host Interface
- MII Management signals to connect to the PHY
- Reset signals (for resetting different parts of the Ethernet IP Core)

#### 2.1.1 Host Interface Ports

All signals listed below are active HIGH, unless otherwise noted. Signal direction is with respect to the Ethernet IP Core.

| Port | Width | Direction | Description |
|------|-------|-----------|-------------|
| CLK_I | 1 | I | Clock Input |
| RST_I | 1 | I | Reset Input |
| ADDR_I | 32 | I | Address Input |
| DATA_I | 32 | I | Data Input |
| DATA_O | 32 | O | Data Output |
| SEL_I | 4 | I | Select Input Array. Indicates which bytes are valid on the data bus. Whenever this signal is not 1111b during a valid access, the ERR_O is asserted. |
| WE_I | 1 | I | Write Input. Indicates a Write Cycle when asserted high or a Read Cycle when asserted low. |
| STB_I | 1 | I | Strobe Input. Indicates the beginning of a valid transfer cycle. |
| CYC_I | 1 | I | Cycle Input. Indicates that a valid bus cycle is in progress. |
| ACK_O | 1 | O | Acknowledgment Output. Indicates a normal Cycle termination. |
| ERR_O | 1 | O | Error Acknowledgment Output. Indicates an abnormal cycle termination. |
| INTA_O | 1 | O | Interrupt Output A. |
| M_ADDR_O | 32 | O | Address Output |
| M_DATA_I | 32 | I | Data Input |
| M_DATA_O | 32 | O | Data Output |
| M_SEL_O | 4 | I | Select Output Array. Indicates which bytes are valid on the data bus. Whenever this signal is not 1111b during a valid access, the ERR_I is asserted. |
| M_WE_O | 1 | O | Write Output. Indicates a Write Cycle when asserted high or a Read Cycle when asserted low. |
| M_STB_O | 1 | O | Strobe Output. Indicates the beginning of a valid transfer cycle. |
| M_CYC_O | 1 | O | Cycle Output. Indicates that a valid bus cycle is in progress. |
| M_ACK_I | 1 | I | Acknowledgment Input. Indicates a normal cycle termination. |
| M_ERR_I | 1 | I | Error Acknowledgment Input. Indicates an abnormal cycle termination. |

#### 2.1.2 PHY Interface Ports

All signals listed below are active HIGH, unless otherwise noted. Signal direction is with respect to the Ethernet IP Core.

| Port | Width | Direction | Description |
|------|-------|-----------|-------------|
| MTxClk | 1 | I | Transmit Nibble or Symbol Clock. The PHY provides the MTxClk signal. It operates at a frequency of 25 MHz (100 Mbps) or 2.5 MHz (10 Mbps). The clock is used as a timing reference for the transfer of MTxD[3:0], MtxEn, and MTxErr. |
| MTxD[3:0] | 4 | O | Transmit Data Nibble. Signals are the transmit data nibbles. They are synchronized to the rising edge of MTxClk. When MTxEn is asserted, PHY accepts the MTxD. |
| MTxEn | 1 | O | Transmit Enable. When asserted, this signal indicates to the PHY that the data MTxD[3:0] is valid and the transmission can start. The transmission starts with the first nibble of the preamble. The signal remains asserted until all nibbles to be transmitted are presented to the PHY. It is deasserted prior to the first MTxClk, following the final nibble of a frame. |
| MTxErr | 1 | O | Transmit Coding Error. When asserted for one MTxClk clock period while MTxEn is also asserted, this signal causes the PHY to transmit one or more symbols that are not part of the valid data or delimiter set somewhere in the frame being transmitted to indicate that there has been a transmit coding error. |
| MRxClk | 1 | I | Receive Nibble or Symbol Clock. The PHY provides the MRxClk signal. It operates at a frequency of 25 MHz (100 Mbps) or 2.5 MHz (10 Mbps). The clock is used as a timing reference for the reception of MRxD[3:0], MRxDV, and MRxErr. |
| MRxDV | 1 | I | Receive Data Valid. The PHY asserts this signal to indicate to the Rx MAC that it is presenting the valid nibbles on the MRxD[3:0] signals. The signal is asserted synchronously to the MRxClk. MRxDV is asserted from the first recovered nibble of the frame to the final recovered nibble. It is then deasserted prior to the first MRxClk that follows the final nibble. |
| MRxD[3:0] | 4 | I | Receive Data Nibble. These signals are the receive data nibble. They are synchronized to the rising edge of MRxClk. When MRxDV is asserted, the PHY sends a data nibble to the Rx MAC. For a correctly interpreted frame, seven bytes of a preamble and a completely formed SFD must be passed across the interface. |
| MRxErr | 1 | I | Receive Error. The PHY asserts this signal to indicate to the Rx MAC that a media error was detected during the transmission of the current frame. MRxErr is synchronous to the MRxClk and is asserted for one or more MRxClk clock periods and then deasserted. |
| MColl | 1 | I | Collision Detected. The PHY asynchronously asserts the collision signal MColl after the collision has been detected on the media. When deasserted, no collision is detected on the media. |
| MCrS | 1 | I | Carrier Sense. The PHY asynchronously asserts the carrier sense MCrS signal after the medium is detected in a non-idle state. When deasserted, this signal indicates that the media is in an idle state (and the transmission can start). |
| MDC | 1 | O | Management Data Clock. This is a clock for the MDIO serial data channel. |
| MDIO | 1 | I/O | Management Data Input/Output. Bi-directional serial data channel for PHY/STA communication. |

---

## 3. Registers

This section describes all base, control, and status registers inside the Ethernet IP Core. The Address field indicates a relative address in hexadecimal. Width specifies the number of bits in the register, and Access specifies the valid access types to that register. **RW** = read and write access; **R** = read-only access.

| Name | Address | Width | Access | Description |
|------|---------|-------|--------|-------------|
| MODER | 0x00 | 32 | RW | Mode Register |
| INT_SOURCE | 0x04 | 32 | RW | Interrupt Source Register |
| INT_MASK | 0x08 | 32 | RW | Interrupt Mask Register |
| IPGT | 0x0C | 32 | RW | Back to Back Inter Packet Gap Register |
| IPGR1 | 0x10 | 32 | RW | Non Back to Back Inter Packet Gap Register 1 |
| IPGR2 | 0x14 | 32 | RW | Non Back to Back Inter Packet Gap Register 2 |
| PACKETLEN | 0x18 | 32 | RW | Packet Length (minimum and maximum) Register |
| COLLCONF | 0x1C | 32 | RW | Collision and Retry Configuration |
| TX_BD_NUM | 0x20 | 32 | RW | Transmit Buffer Descriptor Number |
| CTRLMODER | 0x24 | 32 | RW | Control Module Mode Register |
| MIIMODER | 0x28 | 32 | RW | MII Mode Register |
| MIICOMMAND | 0x2C | 32 | RW | MII Commend Register |
| MIIADDRESS | 0x30 | 32 | RW | MII Address Register. Contains the PHY address and the register within the PHY address. |
| MIITX_DATA | 0x34 | 32 | RW | MII Transmit Data. The data to be transmitted to the PHY. |
| MIIRX_DATA | 0x38 | 32 | RW | MII Receive Data. The data received from the PHY. |
| MIISTATUS | 0x3C | 32 | RW | MII Status Register |
| MAC_ADDR0 | 0x40 | 32 | RW | MAC Individual Address0. The LSB four bytes of the individual address are written to this register. |
| MAC_ADDR1 | 0x44 | 32 | RW | MAC Individual Address1. The MSB two bytes of the individual address are written to this register. |
| ETH_HASH0_ADR | 0x48 | 32 | RW | HASH0 Register |
| ETH_HASH1_ADR | 0x4C | 32 | RW | HASH1 Register |
| ETH_TXCTRL | 0x50 | 32 | RW | Transmit Control Register |

---

### 3.1 MODER (Mode Register)

**Reset Value:** `0000A000h`

| Bit # | Access | Description |
|-------|--------|-------------|
| 31–17 | | Reserved |
| 16 | RW | **RECSMALL** – Receive Small Packets. 0 = Packets smaller than MINFL are ignored. 1 = Packets smaller than MINFL are accepted. |
| 15 | RW | **PAD** – Padding Enabled. 0 = Do not add pads to short frames. 1 = Add pads to short frames (until the minimum frame length is equal to MINFL). |
| 14 | RW | **HUGEN** – Huge Packets Enable. 0 = The maximum frame length is MAXFL. All additional bytes are discarded. 1 = Frames up 64 KB are transmitted. |
| 13 | RW | **CRCEN** – CRC Enable. 0 = Tx MAC does not append the CRC (passed frames already contain the CRC). 1 = Tx MAC appends the CRC to every frame. |
| 12 | RW | **DLYCRCEN** – Delayed CRC Enabled. 0 = Normal operation (CRC calculation starts immediately after the SFD). 1 = CRC calculation starts 4 bytes after the SFD. |
| 11 | | Reserved |
| 10 | RW | **FULLD** – Full Duplex. 0 = Half duplex mode. 1 = Full duplex mode. |
| 9 | RW | **EXDFREN** – Excess Defer Enabled. 0 = When the excessive deferral limit is reached, a packet is aborted. 1 = MAC waits for the carrier indefinitely. |
| 8 | RW | **NOBCKOF** – No Backoff. 0 = Normal operation (a binary exponential backoff algorithm is used). 1 = Tx MAC starts retransmitting immediately after the collision. |
| 7 | RW | **LOOPBCK** – Loop Back. 0 = Normal operation. 1 = TX is looped back to the RX. |
| 6 | RW | **IFG** – Interframe Gap for Incoming Frames. 0 = Normal operation (minimum IFG is required for a frame to be accepted). 1 = All frames are accepted regardless to the IFG. |
| 5 | RW | **PRO** – Promiscuous. 0 = Check the destination address of the incoming frames. 1 = Receive the frame regardless of its address. |
| 4 | RW | **IAM** – Individual Address Mode. 0 = Normal operation (physical address is checked when the frame is received). 1 = The individual hash table is used to check all individual addresses received. |
| 3 | RW | **BRO** – Broadcast Address. 0 = Receive all frames containing the broadcast address. 1 = Reject all frames containing the broadcast address unless the PRO bit = 1. |
| 2 | RW | **NOPRE** – No Preamble. 0 = Normal operation (7-byte preamble). 1 = No preamble is sent. |
| 1 | RW | **TXEN** – Transmit Enable. 0 = Transmit is disabled. 1 = Transmit is enabled. If the value written to the TX_BD_NUM register equals 0x0 (zero buffer descriptors are used), then the transmitter is automatically disabled regardless of the TXEN bit. |
| 0 | RW | **RXEN** – Receive Enable. 0 = Receive is disabled. 1 = Receive is enabled. If the value written to the TX_BD_NUM register equals 0x80 (all buffer descriptors are used for transmit buffer descriptors, so there is no receive BD), then receiver is automatically disabled regardless of the RXEN bit. |

> **NOTE:** Registers should not be changed after the TXEN or RXEN bits is set.

---

### 3.2 INT_SOURCE (Interrupt Source Register)

**Reset Value:** `00000000h`

| Bit # | Access | Description |
|-------|--------|-------------|
| 31–7 | | Reserved |
| 6 | RW | **RXC** – Receive Control Frame. This bit indicates that the control frame was received. It is cleared by writing 1 to it. Bit RXFLOW (CTRLMODER register) must be set to 1 in order to get the RXC bit set. |
| 5 | RW | **TXC** – Transmit Control Frame. This bit indicates that a control frame was transmitted. It is cleared by writing 1 to it. Bit TXFLOW (CTRLMODER register) must be set to 1 in order to get the TXC bit set. |
| 4 | RW | **BUSY** – Busy. This bit indicates that a buffer was received and discarded due to a lack of buffers. It is cleared by writing 1 to it. This bit appears regardless to the IRQ bits in the Receive or Transmit Buffer Descriptors. |
| 3 | RW | **RXE** – Receive Error. This bit indicates that an error occurred while receiving data. It is cleared by writing 1 to it. This bit appears only when IRQ bit is set in the Receive Buffer Descriptor. |
| 2 | RW | **RXB** – Receive Frame. This bit indicates that a frame was received. It is cleared by writing 1 to it. This bit appears only when IRQ bit is set in the Receive Buffer Descriptor. If a control frame is received, then RXC bit is set instead of the RXB bit. |
| 1 | RW | **TXE** – Transmit Error. This bit indicates that a buffer was not transmitted due to a transmit error. It is cleared by writing 1 to it. This bit appears only when IRQ bit is set in the Transmit Buffer Descriptor. |
| 0 | RW | **TXB** – Transmit Buffer. This bit indicates that a buffer has been transmitted. It is cleared by writing 1 to it. This bit appears only when IRQ bit is set in the Transmit Buffer Descriptor. |

---

### 3.3 INT_MASK (Interrupt Mask Register)

**Reset Value:** `00000000h`

| Bit # | Access | Description |
|-------|--------|-------------|
| 31–7 | | Reserved |
| 6 | RW | **RXC_M** – Receive Control Frame Mask. 0 = Event masked. 1 = Event causes an interrupt. |
| 5 | RW | **TXC_M** – Transmit Control Frame Mask. 0 = Event masked. 1 = Event causes an interrupt. |
| 4 | RW | **BUSY_M** – Busy Mask. 0 = Event masked. 1 = Event causes an interrupt. |
| 3 | RW | **RXE_M** – Receive Error Mask. 0 = Event masked. 1 = Event causes an interrupt. |
| 2 | RW | **RXF_M** – Receive Frame Mask. 0 = Event masked. 1 = Event causes an interrupt. |
| 1 | RW | **TXE_M** – Transmit Error Mask. 0 = Event masked. 1 = Event causes an interrupt. |
| 0 | RW | **TXB_M** – Transmit Buffer Mask. 0 = Event masked. 1 = Event causes an interrupt. |

---

### 3.4 IPGT (Back to Back Inter Packet Gap Register)

**Reset Value:** `00000012h`

| Bit # | Access | Description |
|-------|--------|-------------|
| 31–7 | | Reserved |
| 6–0 | RW | **IPGT** – Back to Back Inter Packet Gap. **Full Duplex:** The recommended value is 0x15, which equals 0.96 μs IPG (100 Mbps) or 9.6 μs (10 Mbps). The desired period in nibble times minus 6 should be written to the register. **Half Duplex:** The recommended value and default is 0x12, which equals 0.96 μs IPG (100 Mbps) or 9.6 μs (10 Mbps). The desired period in nibble times minus 3 should be written to the register. |

---

### 3.5 IPGR1 (Non Back to Back Inter Packet Gap Register 1)

**Reset Value:** `0000000Ch`

| Bit # | Access | Description |
|-------|--------|-------------|
| 31–7 | | Reserved |
| 6–0 | RW | **IPGR1** – Non Back to Back Inter Packet Gap 1. When a carrier sense appears within the IPGR1 window, Tx MAC defers and the IPGR counter is reset. When a carrier sense appears later than the IPGR1 window, the IPGR counter continues counting. The recommended and default value for this register is 0xC. It must be within the range [0,IPGR2]. |

---

### 3.6 IPGR2 (Non Back to Back Inter Packet Gap Register 2)

**Reset Value:** `00000012h`

| Bit # | Access | Description |
|-------|--------|-------------|
| 31–7 | | Reserved |
| 6–0 | RW | **IPGR2** – Non Back to Back Inter Packet Gap 2. The recommended and default value is 0x12, which equals to 0.96 μs IPG (100 Mbit/s) or 9.6 μs (10 Mbit/s). |

---

### 3.7 PACKETLEN (Packet Length Register)

**Reset Value:** `00400600h`

| Bit # | Access | Description |
|-------|--------|-------------|
| 31–16 | RW | **MINFL** – Minimum Frame Length. The minimum Ethernet packet is 64 bytes long. If a reception of smaller frames is needed, assert the RECSMALL bit (in the mode register MODER) or change the value of this register. To transmit small packets, assert the PAD bit or the MINFL value (see the PAD bit description in the MODER register). |
| 15–0 | RW | **MAXFL** – Maximum Frame Length. The maximum Ethernet packet is 1518 bytes long. To support this and to leave some additional space for the tags, a default maximum packet length equals 1536 bytes (0x0600). If there is a need to support bigger packets, you can assert the HUGEN bit or increase the value of the MAXFL field (see the HUGEN bit description in the MODER). |

---

### 3.8 COLLCONF (Collision and Retry Configuration Register)

**Reset Value:** `000F003fh`

| Bit # | Access | Description |
|-------|--------|-------------|
| 31–20 | | Reserved |
| 19–16 | RW | **MAXRET** – Maximum Retry. This field specifies the maximum number of consequential retransmission attempts after the collision is detected. When the maximum number has been reached, the Tx MAC reports an error and stops transmitting the current packet. According to the Ethernet standard, the MAXRET default value is set to 0xf (15). |
| 15–6 | | Reserved |
| 5–0 | RW | **COLLVALID** – Collision Valid. This field specifies a collision time window. A collision that occurs later than the time window is reported as a »Late Collisions« and transmission of the current packet is aborted. The default value equals 0x3f (by default, a late collision is every collision that occurs 64 bytes (63 + 1) from the preamble). |

---

### 3.9 TX_BD_NUM (Transmit BD Number Register)

**Reset Value:** `00000040h`

| Bit # | Access | Description |
|-------|--------|-------------|
| 31–8 | | Reserved |
| 7–0 | RW | **Transmit Buffer Descriptor (Tx BD) Number.** Number of the Tx BD. Number of the Rx BD equals to the (0x80 – Tx BD number). Maximum number of the Tx BD is 0x80. Values greater then 0x80 cannot be written to this register (ignored). |

---

### 3.10 CTRLMODER (Control Module Mode Register)

**Reset Value:** `00000000h`

| Bit # | Access | Description |
|-------|--------|-------------|
| 31–3 | | Reserved |
| 2 | RW | **TXFLOW** – Transmit Flow Control. 0 = PAUSE control frames are blocked. 1 = PAUSE control frames are allowed to be sent. This bit enables the TXC bit in the INT_SOURCE register. |
| 1 | RW | **RXFLOW** – Receive Flow Control. 0 = Received PAUSE control frames are ignored. 1 = The transmit function (Tx MAC) is blocked when a PAUSE control frame is received. This bit enables the RXC bit in the INT_SOURCE register. |
| 0 | RW | **PASSALL** – Pass All Receive Frames. 0 = Control frames are not passed to the host. RXFLOW must be set to 1 in order to use PAUSE control frames. 1 = All received frames are passed to the host. |

#### PASSALL and RXFLOW Operation

| PASSALL | RXFLOW | Description |
|---------|--------|-------------|
| 0 | 0 | When a PAUSE control frame is received, nothing happens. The control frame is not stored to the memory. |
| 0 | 1 | When a PAUSE control frame is received, RXC interrupt is set and pause timer is updated. The control frame is not stored to the memory. |
| 1 | 0 | When a PAUSE control frame is received, it is stored to the memory as a normal data frame. RXB interrupt is set (if the related buffer descriptor has an IRQ bit set to 1). RXC interrupt is not set and pause timer is not updated. |
| 1 | 1 | When a PAUSE control frame is received, RXC interrupt is set and pause timer is updated. Besides that the control frame is also stored to the memory as a normal data frame. |

---

### 3.11 MIIMODER (MII Mode Register)

**Reset Value:** `00000064h`

| Bit # | Access | Description |
|-------|--------|-------------|
| 31–9 | | Reserved |
| 8 | RW | **MIINOPRE** – No Preamble. 0 = 32-bit preamble sent. 1 = No preamble send. |
| 7–0 | RW | **CLKDIV** – Clock Divider. The field is a host clock divider factor. The host clock can be divided by an even number, greater then 1. The default value is 0x64 (100). |

---

### 3.12 MIICOMMAND (MII Command Register)

**Reset Value:** `00000000h`

| Bit # | Access | Description |
|-------|--------|-------------|
| 31–3 | | Reserved |
| 2 | RW | **WCTRLDATA** – Write Control Data |
| 1 | RW | **RSTAT** – Read Status |
| 0 | RW | **SCANSTAT** – Scan Status |

> **NOTE:** While one operation is in progress, BUSY signal (see section 3.16) is set. Next operation can be started after the previous one is finished (and BUSY signal cleared to zero).

---

### 3.13 MIIADDRESS (MII Address Register)

**Reset Value:** `00000000h`

| Bit # | Access | Description |
|-------|--------|-------------|
| 31–13 | | Reserved |
| 12–8 | RW | **RGAD** – Register Address (within the PHY selected by the FIAD[4:0]). |
| 7–5 | | Reserved |
| 4–0 | RW | **FIAD** – PHY Address. |

---

### 3.14 MIITX_DATA (MII Transmit Data)

**Reset Value:** `00000000h`

| Bit # | Access | Description |
|-------|--------|-------------|
| 31–16 | | Reserved |
| 15–0 | RW | **CTRLDATA** – Control Data (data to be written to the PHY). |

---

### 3.15 MIIRX_DATA (MII Receive Data)

**Reset Value:** `00000000h`

| Bit # | Access | Description |
|-------|--------|-------------|
| 31–16 | | Reserved |
| 15–0 | R | **PRSD** – Received Data (data read from the PHY). |

---

### 3.16 MIISTATUS (MII Status Register)

**Reset Value:** `00000000h`

| Bit # | Access | Description |
|-------|--------|-------------|
| 31–3 | | Reserved |
| 2 | R | **NVALID** – Invalid. 0 = The data in the MIISTATUS register is valid. 1 = The data in the MIISTATUS register is invalid. This bit is only valid when the scan status operation is active. |
| 1 | R | **BUSY**. 0 = The MII is ready. 1 = The MII is busy (operation in progress). |
| 0 | R | **LINKFAIL**. 0 = The link is OK. 1 = The link failed. The Link fail condition occurred (now the link might be OK). Another status read gets a new status. |

---

### 3.17 MAC_ADDR0 (MAC Address Register 0)

**Reset Value:** `00000000h`

| Bit # | Access | Description |
|-------|--------|-------------|
| 31–24 | RW | Byte 2 of the Ethernet MAC address (individual address) |
| 23–16 | RW | Byte 3 of the Ethernet MAC address (individual address) |
| 15–8 | RW | Byte 4 of the Ethernet MAC address (individual address) |
| 7–0 | RW | Byte 5 of the Ethernet MAC address (individual address) |

> **Note:** When an address is transmitted, byte 0 is sent first and byte 5 last.

---

### 3.18 MAC_ADDR1 (MAC Address Register 1)

**Reset Value:** `00000000h`

| Bit # | Access | Description |
|-------|--------|-------------|
| 31–16 | | Reserved |
| 15–8 | RW | Byte 0 of the Ethernet MAC address (individual address) |
| 7–0 | RW | Byte 1 of the Ethernet MAC address (individual address) |

> **Note:** When an address is transmitted, byte 0 is sent first and byte 5 last.

---

### 3.19 HASH0 (HASH Register 0)

**Reset Value:** `00000000h`

| Bit # | Access | Description |
|-------|--------|-------------|
| 31–0 | RW | Hash0 value |

---

### 3.20 HASH1 (HASH Register 1)

**Reset Value:** `00000000h`

| Bit # | Access | Description |
|-------|--------|-------------|
| 31–0 | RW | Hash1 value |

---

### 3.21 TXCTRL (TX Control Register)

**Reset Value:** `00000000h`

| Bit # | Access | Description |
|-------|--------|-------------|
| 31–17 | | Reserved |
| 16 | RW | **TXPAUSERQ** – TX Pause Request. Writing 1 to this bit starts sending control frame procedure. Bit is automatically cleared to zero. |
| 15–0 | RW | **TXPAUSETV** – TX Pause Timer Value. The value that is send in the pause control frame. |

---

## 4. Operation

This section describes the Ethernet IP Core operation.

The core consists of five modules:

- **Host interface** – connects the Ethernet Core to the rest of the system via the WISHBONE (using DMA transfers). Registers are also part of the host interface.
- **TX Ethernet MAC** – performs transmit functions.
- **RX Ethernet MAC** – performs receive functions.
- **MAC Control Module** – performs full duplex flow control functions.
- **MII Management Module** – performs PHY control and gathers the status information from it.

All modules combined deliver full-function 10/100 Mbps Media Access Control. The Ethernet IP Core can operate in half- or full-duplex mode and is based on the CSMA/CD (Carrier Sense Multiple Access / Collision Detection) protocol.

When a station wants to transmit in half-duplex mode, it must observe the activity on the media (Carrier Sense). As soon as the media is idle (no transmission), any station can start transmitting (Multiple Access). If two or more stations are transmitting at the same time, a collision on the media is detected. All stations stop transmitting and back off for some random time. After the back-off time, the station checks the activity on the media again. If the media is idle, it starts transmitting. All other stations wait for the current transmission to end.

In full-duplex mode, the Carrier Sense and the Collision Detect signals are ignored. The MAC Control module takes care of sending and receiving the PAUSE control frame to achieve Flow control (see the TXFLOW and RXFLOW bit description in the CTRLMODER register for more information).

The MII Management module provides a media independent interface (MII) to the external PHY. This way, the configuration and status registers of the PHY can be read from/written to.

---

### 4.1 Resetting Ethernet Core

The RST_I signal is used for resetting all sub-modules except the MIIM module. Setting the MIIMRST bit in the MIIMODER register to 1 resets the MIIM module. To reset the PHY, assert its RESET signal either through the board's system control register or by writing an appropriate bit in the PHY register.

---

### 4.2 Host Interface Operation

The host interface connects the Ethernet IP Core to the rest of the system (RISC, memory) via the WISHBONE bus. The WISHBONE serves to access the configuration registers and the memory. Currently, only DMA transfers are supported for transferring the data from/to the memory.

#### 4.2.1 Configuration Registers

The function of the configuration registers is transparent and can be easily understood by reading the Registers section (Chapter 3).

#### 4.2.2 Buffer Descriptors (BD)

The transmission and the reception processes are based on the descriptors. The Transmit Descriptors (TxD) are used for transmission while the Receive Descriptors (RxD) are used for reception.

The buffer descriptors are 64 bits long. The first 32 bits are reserved for length and status while the last 32 bits contain the pointer to the associated buffer (where data is stored).

The Ethernet MAC core has an internal RAM that can store up to 128 BDs (for both Rx and Tx).

The internal memory saves all descriptors at addresses from 0x400 to 0x7ff (128 64-bit descriptors). The transmit descriptors are located between the start address (0x400) and the address that equals the value written in the TX_BD_NUM register (Chapter 3.9) multiplied by 8. This register holds the number of the used Tx buffer descriptors. The receive descriptors are located between the start address (0x400), plus the address number written in the TX_BD_NUM multiplied by 8, and the descriptor end address (0x7ff).

The transmit and receive status of the packet is written to the associated buffer descriptor once its transmission/reception is finished.

---

#### 4.2.2.1 TX Buffer Descriptors

The transmit descriptors contain information about associated buffers (length, status) and pointers to the buffers holding the relevant data.

```
ADDR = Offset + 0
  31 30 29 28 27 26 25 24 23 22 21 20 19 18 17 16
  |                    LEN                        |
  15 14 13 12 11 10  9  8  7  6  5  4  3  2  1  0
  |RD|IRQ|WR|PAD|CRC|Res|UR|  RTRY[3:0] |RL|LC|DF|CS|

ADDR = Offset + 4
  31 30 29 28 27 26 25 24 23 22 21 20 19 18 17 16
  |                   TXPNT                       |
  15 14 13 12 11 10  9  8  7  6  5  4  3  2  1  0
  |                   TXPNT                       |
```

| Bit # | Access | Description |
|-------|--------|-------------|
| 31–16 | RW | **LEN** – Length. Number of bytes associated with the BD to be transmitted. |
| 15 | RW | **RD** – TX BD Ready. 0 = The buffer associated with this buffer descriptor is not ready, and you are free to manipulate it. After the data from the associated buffer has been transmitted or after an error condition occurred, this bit is cleared to 0. 1 = The data buffer is ready for transmission or is currently being transmitted. You are not allowed to manipulate this descriptor once this bit is set. |
| 14 | RW | **IRQ** – Interrupt Request Enable. 0 = No interrupt is generated after the transmission. 1 = When data associated with this buffer descriptor is sent, a TXB or TXE interrupt will be asserted. |
| 13 | RW | **WR** – Wrap. 0 = This buffer descriptor is not the last descriptor in the buffer descriptor table. 1 = This buffer descriptor is the last descriptor in the buffer descriptor table. After this buffer descriptor was used, the first buffer descriptor in the table will be used again. |
| 12 | RW | **PAD** – Pad Enable. 0 = No pads will be add at the end of short packets. 1 = Pads will be added to the end of short packets. |
| 11 | RW | **CRC** – CRC Enable. 0 = CRC won't be added at the end of the packet. 1 = CRC will be added at the end of the packet. |
| 10–9 | | Reserved |
| 8 | RW | **UR** – Underrun. Underrun occurred while sending this buffer. |
| 7–4 | RW | **RTRY** – Retry Count. This bit indicates the number of retries before the frame was successfully sent. |
| 3 | RW | **RL** – Retransmission Limit. This bit is set when the transmitter fails. (Retry Limit + 1) attempts to successfully transmit a message due to repeated collisions on the medium. The Retry Limit is set in the COLLCONF register. |
| 2 | RW | **LC** – Late Collision. Late collision occurred while sending this buffer. The transmission is stopped and this bit is written. Late collision is defined in the COLLCONF register. |
| 1 | RW | **DF** – Defer Indication. The frame was deferred before being sent successfully, i.e. the transmitter had to wait for Carrier Sense before sending because the line was busy. This is not a collision indication. Collisions are indicated in RTRY. |
| 0 | RW | **CS** – Carrier Sense Lost. This bit is set when Carrier Sense is lost during a frame transmission. The Ethernet controller writes CS after it finishes sending the buffer. |

**TX Buffer Pointer:**

| Bit # | Access | Description |
|-------|--------|-------------|
| 31–0 | RW | **TXPNT** – Transmit Pointer. This is the buffer pointer when the associated frame is stored. |

---

#### 4.2.2.2 RX Buffer Descriptors

The receive BDs contain information about the received frames (length, status) and pointers to the buffers holding the relevant data.

```
ADDR = Offset + 0
  31 30 29 28 27 26 25 24 23 22 21 20 19 18 17 16
  |                    LEN                        |
  15 14 13 12 11 10  9  8  7  6  5  4  3  2  1  0
  |E |IRQ|WR |Res|CF|M |OR|IS|DN|TL|SF|CRC|LC|

ADDR = Offset + 4
  31 30 29 28 27 26 25 24 23 22 21 20 19 18 17 16
  |                   RXPNT                       |
  15 14 13 12 11 10  9  8  7  6  5  4  3  2  1  0
  |                   RXPNT                       |
```

| Bit # | Access | Description |
|-------|--------|-------------|
| 31–16 | RW | **LEN** – Number of the received bytes associated with this BD. |
| 15 | RW | **E** – Empty. 0 = The data buffer associated with this buffer descriptor has been filled with data or has stopped because an error occurred. The core can read or write this BD. As long as this bit is zero, this buffer descriptor won't be used. 1 = The data buffer is empty (and ready for receiving data) or currently receiving data. |
| 14 | RW | **IRQ** – Interrupt Request Enable. 0 = No interrupt is generated after the reception. 1 = When data is received (or error occurs), an RXF interrupt will be asserted. |
| 13 | RW | **WRAP** – Wrap. 0 = This buffer descriptor is not the last descriptor in the buffer descriptor table. 1 = This buffer descriptor is the last descriptor in the buffer descriptor table. After this buffer descriptor is used, the first Rx buffer descriptor in the table will be used again. |
| 12–9 | | Reserved |
| 8 | RW | **CF** – Control Frame. 0 = Normal data frame received. 1 = Control frame received. |
| 7 | RW | **M** – Miss. 0 = The frame is received because of an address recognition hit. 1 = The frame is received because of promiscuous mode. The Ethernet controller sets M for frames that are accepted in promiscuous mode but are tagged as a miss by internal address recognition. Thus, in promiscuous mode, M determines whether a frame is destined for this station. |
| 6 | RW | **OR** – Overrun. This bit is set when a receiver overrun occurs during frame reception. |
| 5 | RW | **IS** – Invalid Symbol. This bit is set when the reception of an invalid symbol is detected by the PHY. |
| 4 | RW | **DN** – Dribble Nibble. This bit is set when a received frame cannot be divided by 8 (one extra nibble has been received). |
| 3 | RW | **TL** – Too Long. This bit is set when a received frame is too long (bigger than the value set in the PACKETLEN register). |
| 2 | RW | **SF** – Short Frame. This bit is set when a frame that is smaller than the minimum length is received (minimum length is set in the PACKETLEN register). |
| 1 | RW | **CRC** – RX CRC Error. This bit is set when a received frame contains a CRC error. |
| 0 | RW | **LC** – Late Collision. This bit is set when a late collision occurred while receiving a frame. |

**RX Buffer Pointer:**

| Bit # | Access | Description |
|-------|--------|-------------|
| 31–0 | RW | **RXPNT** – Receive Pointer. This is the pointer to the buffer storing the associated frame. |

---

#### 4.2.3 Frame Transmission

To transmit the first frame, the RISC must do several things, namely:

- Store the frame to the memory.
- Associate the Tx BD in the Ethernet MAC core with the packet written to the memory (length, pad, crc, etc.).
- Enable the TX part of the Ethernet Core by setting the TXEN bit to 1.

As soon as the Ethernet IP Core is enabled, it continuously reads the first BD. Immediately when the descriptor is marked as ready, the core reads the pointer to the memory storing the associated data and starts then reading data to the internal FIFO. At the moment the FIFO is full, transmission begins.

At the end of the transmission, the transmit status is written to the buffer descriptor and an interrupt might be generated (when enabled). Next, two events might occur (according to the WR bit (wrap) in the descriptor):

- If the WR bit has not been set, the BD address is incremented, the next descriptor is loaded, and the process starts all over again (if next BD is marked as ready).
- If the WR bit has been set, the first BD address (base) is loaded again. As soon as the BD is marked as ready, transmission will start.

> **NOTE:** Only frames with length greater than 4 bytes are transmitted. Even if the BD is marked as ready, the frame is not transmitted if the length is too small.

---

#### 4.2.4 Frame Reception

To receive the first frame, the RISC must do several things, namely:

- Set the receive buffer descriptor to be associated with the received packet and mark it as empty.
- Enable the Ethernet receive function by setting the RXEN bit to 1.

The Ethernet IP Core reads the Rx BD. If it is marked as empty, it starts receiving frames. The Ethernet receive function receives an incoming frame nibble per nibble. After the whole frame has been received and stored to the memory, the receive status is written to the BD. An interrupt might be generated (if enabled). Then the BD address is incremented and the next BD loaded. If the new BD is marked as empty, another frame can be received; otherwise the operation stops.

> **NOTE:** Only frames with length greater than 4 bytes are received without an error. Smaller frames are received with a CRC error (CRC is 4 bytes long).

---

### 4.3 TX Ethernet MAC

The TX Ethernet MAC generates 10BASE-T/100BASE-TX transmit MII nibble data streams in response to the byte streams the transmit logic (host) supplies. It performs the required deferral and back-off algorithms, takes care of the inter-packet gap (IPG), computes the checksum (FCS), and monitors the physical media (by monitoring Carrier Sense and collision signals). The TX Ethernet MAC is divided into several modules that provide the following functionality:

- Generation of the signals connected to the Ethernet PHY during the transmission process
- Generation of the status signals the host uses to track the transmission process
- Random time generation used in the back-off process after a collision has been detected
- CRC generation and checking
- Pad generation
- Data nibble generation

---

### 4.4 RX Ethernet MAC

The RX Ethernet MAC transmits the data streams to the host in response to the 10BASE-T or 100BASE-TX received MII nibbles. The module is divided into several sub-modules providing the following functionality:

- Preamble removal
- Data assembly (from input nibble to output byte)
- CRC checking for all incoming packets
- Generation of the signal that can be used for address recognition (in the hash table)
- Generation of the status signals the host uses to track the reception process

---

### 4.5 MAC Control Module

The MAC Control Module performs a real-time flow control function for the full-duplex operation. The control opcode PAUSE is used for stopping the station transmitting the packets. The receive buffer (FIFO) starts filling up when the upper layer cannot continue accepting the incoming packets. Before an overflow happens, the upper layer sends a PAUSE control frame to the transmitting station. This control frame inhibits the transmission of the data frames for a specified period of time.

When the MAC Control module receives a PAUSE control frame, it loads the pause timer with the received value into the pause timer value field. The Tx MAC is stopped (paused) from transmitting the data frames for the "pause timer value" slot times. The pause timer decrements by one each time a slot time passes by. When the pause time number equals zero, the MAC transmitter resumes the transmit operation.

The MAC Control Module has the following functionality:

- Control frame detection
- Control frame generation
- TX/RX MAC Interface
- PAUSE Timer
- Slot Timer

---

#### 4.5.1 Control Frame Detection

The incoming data packets are passed from the receiver via the MAC Control Module to the upper layers while the control frames are usually dropped.

The RXFLOW bit in the CTRLMODER register defines whether the pause control frame causes the transmitter to break the transmission or not. If RXFLOW bit is set then the RXC interrupt is set in the INT_SOURCE register. The PASSALL bit in the CTRLMODER register defines whether the control frames are stored to the memory or not (regardless to the RXFLOW bit). If the PASSALL bit is set then the control frame is stored to the memory and related buffer descriptor has the control frame bit (CF) set to 1. RXB interrupt in the INT_SOURCE register is set to 1.

> **Note:** If both RXFLOW and PASSALL bits are set to 1, then only RXC interrupt is set in the INT_SOURCE register when a control frame is received.

A valid PAUSE control frame has the frame structure described below:

```
┌─────────────────────┬──────┬─────────┬────────┬────────┬────────┐
│ Dest. Address or    │ Src. │ Length/ │ Opcode │ Pause  │  CRC   │
│ reserved Multicast  │ Addr │  Type   │        │ Timer  │        │
│ address             │      │         │        │ Value  │        │
├─────────────────────┼──────┼─────────┼────────┼────────┼────────┤
│ 6 bytes             │ 6 byt│   2 byt │ 2 byt  │ 2 byt  │ 4 bytes│
└─────────────────────┴──────┴─────────┴────────┴────────┴────────┘
                                    Total: 64 Bytes
```

The destination address must be a reserved multicast address (01-80-c2-00-00-01) or a destination address equal to the Ethernet IP Core MAC address. The Length/Type field must be equal to 8808 and the opcode to 0001 for a PAUSE control frame.

When the receive flow control and the MAC Control Module are enabled (RXFLOW asserted and PASSALL deasserted), a PAUSE Timer Value from the PAUSE control frame is passed to the PAUSE timer.

---

#### 4.5.2 Control Frame Generation

When the host wants to send a PAUSE control frame, it asserts the Transmit Pause Request (TPAUSERQ). When a request is detected, the control module waits for the current transmission to end. It then starts transmitting the PAUSE control frame by asserting the Transmit Packet Start Frame (TxStartFrm) and providing the appropriate control data. Sending CtrlFrm is used to instruct the Transmit function (TX Ethernet MAC) to pad and append the FCS. The transmit Pause Frame End (TxEndFrm) is asserted at the end to inform the host that a Pause request was sent.

Asserting the TXFLOW bit in the CTRLMODER register enables the transmission of the PAUSE control frame.

When the control frame needs to be sent, the request is issued by writing the appropriate value to the TXCTRL register. The Transmit Pause Timer Value TPAUSETV[15:0] contains the value to be sent as a Pause Timer Value in the pause control frame. The TPAUSERQ signal (request) is latched internally in the MAC Control Generator and reset after the PAUSE control frame has been transmitted. This prevents issuing a new PAUSE request until the current request is sent.

---

#### 4.5.3 TX/RX MAC Interface

The MAC Control Module is connected between the host and the Tx and Rx modules. When enabled, its logic takes over the control of the following signals: TxData[7:0], TxStartFrm, TxEndFrm, TxUsedData, TxDone, and TxAbort. These signals are connected directly between the host and the MAC transmit and receive functions when data frames (not control frames) are transmitted or received.

On the other hand, when a host wants to send a PAUSE control frame, it asserts a TPauseRQ request signal. It is then up to the MAC Control Module to initiate the transmission. In this case, the above signals are not connected to the host any more. The MAC Control Module drives the appropriate control data signals and instructs the Tx module to transmit.

When a PAUSE control frame is received, the frame can be dropped or passed to the host, depending on the state of the PASSALL and RXFLOW bits. Again TxData[7:0], TxStartFrm, TxEndFrm, TxUsedData, TxDone, and TxAbort are not connected directly.

---

#### 4.5.4 PAUSE Timer

The 16-bit PAUSE timer is loaded with a pause timer value when a PAUSE control frame is received. The timer inhibits the data frame transmissions for the timer value time slots. This is done by:

- Preventing the Tx MAC module from seeing the signal TxStartFrm from the host
- Preventing the host from seeing the signal TxUsedData from the Tx module

The timer decrements by one each time a time slot passes by. A Slot Timer is used for counting the slot time.

---

#### 4.5.5 Slot Timer

The Slot Timer is activated when a PAUSE Timer is preloaded. It counts slot times and generates pulses to the PAUSE Timer for every slot time passed. Slot time is the time needed for transmission of 64 bytes.

---

### 4.6 MII Management Module

The MII Management Module is a simple two-wire interface between the host and an external PHY device. It is used for configuration and status read of the physical device. The physical interface consists of a management data line MDIO (Management Data Input/Output) and a clock line MDC (Management Data Clock). During the read/write operation, the most significant bit is shifted in/out first from/to the MDIO data signal. On each rising edge of the MDC, a Shift register is shifted to the left and a new value appears on the MDIO.

Internally the interface consists of four signals:

- MDC
- MDI
- MDO
- MDOEN (Management Data Output Enable)

The unidirectional lines MDI, MDO, and MDOEN are combined to make a bi-directional signal MDIO that is connected to the PHY.

The configuration and status data is written/read to/from the PHY via the MDIO signal. The MDC is a low frequency clock derived from dividing the host clock.

Three commands are supported for controlling the PHY:

- Write Control Data (writes the control data to the PHY Configuration registers)
- Read Status (reads the PHY Control and Status register)
- Scan Status (continuously reads the PHY Status register of one or more PHYs [link fail status])

The MII Management Module consists of four sub-modules:

- Operation Controller
- Shift Registers
- Output Control Module
- Clock Generator

---

#### 4.6.1 Operation Controller

The Operation Controller's task is to perform all supported commands: Write Control Data, Read Status, and Scan Status.

##### 4.6.1.1 Write Control Data

A host initiates a write operation by asserting the WCTRLDATA signal. This signal also indicates that the host data CTLD[15:0], the PHY address FIAD[4:0], and the PHY register address RGAD[4:0] are valid. As soon as the host asserts the WCTRLDATA signal, the MIIM module asserts the BUSY signal to inform the host that the write operation is in process. MDOEN is asserted to enable the output line MDO (MDIO) to the PHY. The MIIM module then clocks out the MIIM frame to the PHY on each rising edge of the MDC. The MIIM frame write format conforms to the IEEE 803.2u Specification:

- 32-bit long preamble (all ones) if the MIINOPRE bit is not asserted
- 2-bit long Start of frame pattern ST (zero followed by one)
- 2-bit Operation definition (zero-one for write or one-zero for read)
- 5-bit PHY address (FIAD[4:0])
- 5-bit PHY register address RGAD[4:0]
- 2-bit turnaround field TA (one-zero)
- 16-bit data

At the end of the write operation, the BUSY signal is deasserted.

##### 4.6.1.2 Read Status

A host initiates a read operation by asserting the RSTAT signal. This signal also indicates that the PHY address FIAD[4:0] and the PHY register address RGAD[4:0] are valid. As soon as the host asserts the RSTAT signal, the MIIM module asserts the BUSY signal to inform the host that the read operation is in process. MDOEN is asserted to enable the output line MDO (MDIO) to the PHY. The MIIM module then clocks out the MIIM frame to the PHY on each rising edge of the MDC and afterwards clocks in the requested data (status). The MIIM read frame format conforms to the IEEE 803.2u Specification:

- 32-bit long preamble (all ones) if the MIINOPRE bit is not asserted
- 2-bit long Start of frame pattern ST (zero followed by one)
- 2-bit Operation definition (zero-one for write or one-zero for read)
- 5-bit PHY address (FIAD[4:0])
- 5-bit PHY register address RGAD[4:0]
- 2-bit turnaround field TA (one-bit period in which the PHY stays in the high-Z state followed by a one-bit period during which the PHY drives a zero on the MDO)
- MIIM deasserts the MDOEN signal that enables the MDI (MDIO works as an input)
- PHY sends the data (status) back to the MIIM Module on the data lines PRSD[15:0]

At the end of the read operation, the MIIM deasserts the BUSY signal to indicate to the host that valid data is on the PRSD[15:0] lines.

##### 4.6.1.3 Scan Status

A host initiates the Scan Status Operation by asserting the SCANSTAT signal. The MIIM performs a continuous read operation of the PHY Status register. The PHY is selected by the FIAD[4:0] signals. The link status LinkFail signal is asserted/deasserted by the MIIM module and reflects the link status bit of the PHY Status register. The signal NVALID is used for qualifying the validity of the LinkFail signals and the status data PRSD[15:0]. These signals are invalid until the first scan status operation ends.

During the scan status operation, the BUSY signal is asserted until the last read is performed (the scan status operation is stopped).

---

#### 4.6.2 Shift Registers Operation

There are two shift registers in the MII Management Module. The Data Shift register is used for:

- Shifting out the data to the PHY during the Write Data Control operation
- Shifting in the data during the Read Status operation
- Shifting out the FIAD[4:0] and RGAD[4:0] addresses during all operations

The Status Shift register contains the data latched during the last Read Status Operation. Two additional status signals (LinkFail Status and Status Invalid NVALID) are latched separately from the Status Shift register.

When a Scan Operation is requested, the state of the PRSD[15:0] and a MIILF is constantly updated from the selected PHY register. NVALID is used to qualify the validity of the PRSD[15:0] and MIILS signals. These signals are invalid until the first Scan Status Operation ends.

---

#### 4.6.3 Output Control Module Operation

The Output Control Module combines the MDI, MDO, and MDOEN signals into a bi-directional MDIO signal that is connected to the external MII PHY. During the Write Control Data Operation, the MDIO operates as an output from the MIIM module. The signal is used for transferring data from the MIIM Module to the PHY. During the Read Status Operation, the MDIO first operates as an output (addressing the PHY and the PHY Internal register) and then as an input to the MIIM Module (reading the status data). In both cases the most significant bit of the data is shifted first. When no operation is performed, the MDIO is tri-stated.

---

#### 4.6.4 Clock Generator Operation

The Management Data Clock MDC is a divided host clock. The division factor is set in the MIIMODER register by setting the CLKDIV[7:0] field. (MDC depends on the PHY and can be 2.5 MHz or 12.5 MHz.)

---

## 5. Architecture

The Ethernet IP Core consists of 5 modules:

- Host Interface and the BD structure
- TX Ethernet MAC (transmit function)
- RX Ethernet MAC (receive function)
- MAC Control Module
- MII Management Module

### Architecture Overview

```
                                 ┌──────────────────────────────┐
                                 │   Ethernet IP Core           │
                                 ├──────────────────────────────┤
                                 │                              │
          ┌────────────────┼──────────────────┐           │
          │                │                  │           │
          │            ┌─────────────────┐    │           │
          │            │ Host Interface  │    │           │
          │            │ (Registers,     │◄───┼──┐        │
          │            │ WISHBONE iface, │    │  │        │
          │            │ DMA support)    │    │  │        │
          │            └─────────────────┘    │  │        │
          │                  │                │  │        │
          │       ┌──────────┼─────┐         │  │        │
          │       │          │     │         │  │        │
          │   ┌───▼──┐  ┌────▼──┐ ┌┴──────┐ │  │        │
          │   │ TX   │  │ MAC   │ │ RX    │ │  │        │
          │   │ MAC  │  │ Control│ │ MAC  │ │  │        │
          │   │      │  │Module │ │      │ │  │        │
          │   └──┬───┘  └───┬────┘ └──┬───┘ │  │        │
          │      │          │         │     │  │        │
          └─────┬┴──────────┴─────────┴─────┘  │        │
                  │                              │        │
                  └──────────────────┬───────────┼────────┘
                                            │           │
             ┌──────────────────────┘   ┌───────┴─────────┐
             │                          │                 │
      ┌────▼──────┐            ┌──────▼──────┐     ┌────▼────┐
      │  Ethernet │            │   MII       │     │ Ethernet │
      │  PHY      │            │ Management  │     │   Core   │
      │           │            │   Module    │     │          │
      └───────────┘            └─────────────┘     └──────────┘
          TX/RX Data,                 MDC, MDIO      Management Data
          PHY Control Signals
```

---

### 5.1 Host Interface

The host interface is connected to the RISC and the memory through the two Wishbone interfaces. The RISC writes the data for the configuration registers directly while the data frames are written to the memory. For writing data to configuration registers, Wishbone slave interface is used. Data in the memory is accessed through the Wishbone master interface.

---

### 5.2 TX Ethernet MAC

The TX Ethernet MAC generates 10BASE-T/100BASE-TX transmit MII nibble data streams in response to the byte streams supplied by the transmit logic (host). It performs the required deferral and back-off algorithms, takes care of the IPG, computes the checksum (FCS), and monitors the physical media (by monitoring Carrier Sense and collision signals).

---

### 5.3 RX Ethernet MAC

The RX Ethernet MAC interprets 10BASE-T/100BASE-TX MII receive data nibble streams and supplies correctly formed packet-byte streams to the host. It searches for the SFD (start frame delimiter) at the beginning of the packet, verifies the FCS, and detects any dribble nibbles or receive code violations.

---

### 5.4 MAC Control Module

The function of this module is to implement the full-duplex flow control.

The MAC Control Module consists of three sub-modules that provide the following functionality:

- Control frame detection
- Control frame generation
- TX/RX Ethernet MAC Interface
- PAUSE Timer
- Slot Timer

---

#### 5.4.1 Control Frame Detector

The control frame detector checks the incoming frames for control frames. Control frames can be discarded or passed to the host. When a PAUSE control frame is detected, it can stop the Tx module from transmitting for a certain period of time.

---

#### 5.4.2 Control Frame Generator

If the need arises to stop the transmitting station from transmitting (flow control in full-duplex mode), a PAUSE control frame can be sent.

---

#### 5.4.3 TX/RX Ethernet MAC Interface

The MAC Control Module is connected between the host interface, the Tx, and the Rx MAC modules. Signals from the host are passed to the Tx MAC in certain occasions and vice versa.

---

#### 5.4.4 PAUSE Timer

When a PAUSE control frame is received, the pause timer value is written to the PAUSE timer. This prevents the Tx module from transmitting for a "pause timer value" period of slot time.

---

#### 5.4.5 Slot Timer

The slot timer measures time slots and generates a pulse to the PAUSE timer for every slot time passed by.

---

### 5.5 MII Management Module

The function of the MII Management Module is to control the PHY and to gather information from it (status).

It consists of four sub-modules:

- Operation Control Module
- Output Control Module
- Shift Register
- Clock Generator

---

#### 5.5.1 Operation Control Module

The function of the Operation Control Module is to perform the following commands:

- Write control data
- Read status
- Scan status

---

#### 5.5.2 Output Control Module

The Output Control Module controls the signal appearance on the MDO, MCK, and MDOEN pins.

---

#### 5.5.3 Shift Register

The shift registers hold the status read from an external PHY.

---

#### 5.5.4 Clock Generator

The clock generator generates an appropriate output clock MCK according to the input host clock and the clock divider bits (CLKDIV[7:0] in the MIIMODER register).
