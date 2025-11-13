# AMBA AXI Crossbar

[![GitHub license](https://img.shields.io/github/license/dpretet/axi-crossbar)](https://github.com/dpretet/axi-crossbar/blob/master/LICENSE)
![Github Actions](https://github.com/dpretet/axi-crossbar/actions/workflows/ci.yaml/badge.svg)
[![GitHub issues](https://img.shields.io/github/issues/dpretet/axi-crossbar)](https://github.com/dpretet/axi-crossbar/issues)
[![GitHub stars](https://img.shields.io/github/stars/dpretet/axi-crossbar)](https://github.com/dpretet/axi-crossbar/stargazers)
[![GitHub forks](https://img.shields.io/github/forks/dpretet/axi-crossbar)](https://github.com/dpretet/axi-crossbar/network)


## Overview

An AXI4 crossbar implemented in SystemVerilog to build the foundation of a SOC.

A crossbar is a circuit connecting multiple master and slave agents, mapped
across a memory space. The core consists of a collection of switches, routing
the master requests to the slaves and driving back completions to the agents.
A crossbar is a common piece of logic to connect in a SOC the
processor(s) with the peripherals like memories, IOs, co-processors...


```
    ┌─────────────┬───┬──────────────────────────┬───┬─────────────┐
    │             │ S │                          │ S │             │
    │             └───┘                          └───┘             │
    │ ┌───────────────────────────┐  ┌───────────────────────────┐ │
    │ │      Slave Interface      │  │      Slave Interface      │ │
    │ └───────────────────────────┘  └───────────────────────────┘ │
    │               │                              │               │
    │               ▼                              ▼               │
    │ ┌──────────────────────────────────────────────────────────┐ │
    │ │                         Crossbar                         │ │
    │ └──────────────────────────────────────────────────────────┘ │
    │               │                              │               │
    │               ▼                              ▼               │
    │ ┌───────────────────────────┐  ┌───────────────────────────┐ │
    │ │     Master Interface      │  │     Master Interface      │ │
    │ └───────────────────────────┘  └───────────────────────────┘ │
    │             ┌───┐                          ┌───┐             │
    │             │ M │                          │ M │             │
    └─────────────┴───┴──────────────────────────┴───┴─────────────┘
```


Features

- 4x4 master/slave interfaces
- Master/slave buffering capability, configurable per interface
    - Outstanding request number and payload configurable
    - Seamless support of AXI4 vs AXI4-lite
- CDC support in master & slave interface, to convert an agent clock domain
  from/to the fabric clock domain
- Round-robin arbitration
    - Non-blocking arbitration between requesters, with fait-share granting
    - Priority configurable per master interface, up to 4 different levels,
      for request and completion stages
- AXI or AXI4-Lite mode:
    - LITE mode: route all signals described in AXI4-lite specification
    - FULL mode: route all signals described by AXI4 specification
    - The selected mode applies to the global infrastructure
- Routing table can be defined to restrict slaves access
    - Easily create enclosed and secured memory map
    - Dedicate sensitive slaves only to trusted master agents
- USER signal support
    - Configurable for each channel (AW, AR, W, B, R)
    - Common to all master/slave interfaces if activated


## Implementation Details

- Interfaces share the same address / data / ID width
    - Address width configurable, any width
    - Data width configurable, any width
    - ID width configurable, any width
- Advanced clock/reset network
    - Support both asynchronous and synchronous reset policies
    - Can handle clock domain crossing if needed, the core being fueled by its
      own clock domain
- Route read/write requests by address decoding. All slave agents are mapped
  into the memory space across a start/end address range.
- Route read & write completion by ID decoding. All master agents have an ID
  mask used to identified the route to drive back a completion
- Configurable routing across the infrastructure
    - A master can be restricted to a memory map subset
    - An access to a forbidden area is completed by a `DECERR`
- Switching logic IO interfaces can be pipelined to achieve timing closure easier
- Don't garantee completion ordering when a master targets multiple slaves with the
  same AXI ID (!). A master should use different IDs and reorder the completion by itself

Further details can be found in:
- The architecture [chapter](doc/architecture.md)
- The IOs/parameters [chapter](doc/io_parameter.md)


## Verification environment

The core is verified with a testbench relying on pseudo-random driver and
monitor to inject some traffic and verify its correctness. Please refer to the
[dedicated chapter](./test/svut/README.md) for futher details and find hints
to integrate the core in your own development. The flow relies on:

- [Icarus Verilog 11](https://github.com/steveicarus/iverilog) as simulator
- [SVUT](https://github.com/dpretet/svut) to configure and execute Icarus


## Development plan

Core features:
- Full AXI ordering support: put in place multiple queues
  per ID and manage reordering to master interfaces
- Read-only or write-only master to save gate count
- Address translation service to connect multiple systems together
- Timeout support in switching logic
- Debug interface to steam out events like 4KB crossing or timeout
- New Checkers:
    - Check address overlap (start+end vs next slave start address)
    - ID overlap: mask ID + OR number supported up to next slave ID

Wizard:
- Number of master and slave agents configurable
- RTL generator

AXI Goodies:
- Interface datapath width conversion
- AXI4-to-AXI4-lite converter
    - split AXI4 to multiple AXI4-lite requests
    - gather AXI4-lite completion into a single AXI completion
- 4KB boundary crossing checking, supported by a splitting mechanism

Simulation:
- Support Verilator
- Error injection in the core and tesbench
- Implement statistics in testbench to track misrouting, address distribution,
  master granting, ...

## License

This IP core is licensed under MIT license. It grants nearly all rights to use,
modify and distribute these sources.

However, consider to contribute and provide updates to this core if you add
feature and fix, would be greatly appreciated :)
# Architecture

## Overview


```
                       ┌───────┐    ┌───────┐    ┌───────┐    ┌───────┐
                       │Slave 0│    │Slave 1│    │Slave 2│    │Slave 3│
                       └───────┘    └───────┘    └───────┘    └───────┘
                           ▲            ▲            ▲            ▲
                           │            │            │            │
                           │            │            │            │
    ┌──────────┐           │            │            │            │
    │ Master 0 │─────────▶( )──────────( )──────────( )──────────( )
    └──────────┘           │            │            │            │
                           │            │            │            │
                           │            │            │            │
    ┌──────────┐           │            │            │            │
    │ Master 1 │─────────▶( )──────────( )──────────( )──────────( )
    └──────────┘           │            │            │            │
                           │            │            │            │
                           │            │            │            │
    ┌──────────┐           │            │            │            │
    │ Master 2 │─────────▶( )──────────( )──────────( )──────────( )
    └──────────┘           │            │            │            │
                           │            │            │            │
                           │            │            │            │
    ┌──────────┐           │            │            │            │
    │ Master 3 │─────────▶( )──────────( )──────────( )──────────( )
    └──────────┘
```


A crossbar is a piece of logic aiming to connect any master to any
slave connected upon it. Its interconnect topology provides a low latency, high
bandwidth switching logic for a non-blocking, conflict-free communication flow.

The IP can be divided in three parts:
- the slave interface layer, receiving the requests to route
- the interconnect layer, routing the requests
- the master interface layer, driving the requests outside the core


```
    ┌─────────────┬───┬──────────────────────────┬───┬─────────────┐
    │             │ S │                          │ S │             │
    │             └───┘                          └───┘             │
    │ ┌───────────────────────────┐  ┌───────────────────────────┐ │
    │ │      Slave Interface      │  │      Slave Interface      │ │
    │ └───────────────────────────┘  └───────────────────────────┘ │
    │               │                              │               │
    │               ▼                              ▼               │
    │ ┌──────────────────────────────────────────────────────────┐ │
    │ │                       Interconnect                       │ │
    │ └──────────────────────────────────────────────────────────┘ │
    │               │                              │               │
    │               ▼                              ▼               │
    │ ┌───────────────────────────┐  ┌───────────────────────────┐ │
    │ │     Master Interface      │  │     Master Interface      │ │
    │ └───────────────────────────┘  └───────────────────────────┘ │
    │             ┌───┐                          ┌───┐             │
    │             │ M │                          │ M │             │
    └─────────────┴───┴──────────────────────────┴───┴─────────────┘
```

Master and slave interfaces are mainly responsible to support the oustanding
requests and prepare the AXI request to be transported through the switching
logic. The interconnect is the collection of switches routing the requests and
the the completions from/to the agent.


## Clock and Reset Network

### Clock

The core uses and needs a reference clock for the internal switching logic. The
higher the frequency is, the better will be the global bandwidth and latency
of the system.

Each interface can operate in its own clock domain, whatever the frequency and
the phase regarding the other clocks. The core proposes a CDC stage for each
interface to convert the clock to the interconnect clock domain. The CDC stage
is implemented with a [DC-FIFO](https://github.com/dpretet/async_fifo).


### Reset

The core fully supports both asynchronous and synchronous reset. The choice
between these two options depends to the technology targeted. Most of the time,
asynchronous reset policy is the prefered option. It is STRONGLY ADVICED TO
NOT MIX THESE TWO RESET TYPES, and choose for instance asynchronous reset only
for the core and ALL the interfaces. The available resets, named uniformly
across the interfaces, are:

- `aresetn`: active low reset, asynchronously asserted, synchronously deasserted
  to the clock, compliant with AMBA requirement.
- `srst`: active high reset, asserted and deasserted synchronously to the clock.

If not used, `srst` needs to remain low; if not used, `aresetn` needs to
remain high all the time.

Each reset input needs to be driven when the core is under reset. If not,
its behavior is not garanteed.

Asynchronous reset is the most common option, especially because it simplifies
the efforts of the PnR and timing analysis steps.

Further details can be found in this
[excellent document](http://www.sunburst-design.com/papers/CummingsSNUG2003Boston_Resets.pdf)
from the excellent Clifford Cummings.


### Clock Domain Crossing

The core provides a CDC stage for each master or slave interface if needed. The stage is 
activated with `MSTx_CDC` or `SLVx_CDC`. Internally, the switching fabric uses a specific
clock (`aclk`) to route the requests and the completions from/to the agents. The master
and slave interfaces must activate a CDC stage if they don't use the same clock than 
the fabric (same frequency & phase). If an agent uses the same clock than the fabric, the 
agent must also use the same reset to ensure a clean reset sequence.


### Boot time

In order to boot properly the interconnect infrastructure, the user must follow the following
sequence:
1. Drive low all the reset inputs
2. Source all the clocks of the active interface
3. Wait for several clock cycles, for each clock domain, to be sure the whole logic has been reset
4. Before releasing the resets, be sure all the domains has been completly reset (point 3). Some 
   clock can be very slower than another domain, be sure to take it in account.
5. Release the resets
6. Start to issue request in the core


## AXI4 / AXI4-lite support

The core supports both AXI4 and AXI4-lite protocol by a single parameter setup.
For both protocols, the user can configure:
- the address bus width
- the data bus width
- the ID bus width
- the USER width, per channel

The configurations apply to the whole infrastructure, including the agents.
An agent connected to the core must support for instance `32` bits addressing if
other ones do. All other sideband signals (APROT, ACACHE, AREGION, ...) are
described and transported as the AMBA specification defines them. No modification
is applied by the interconnect on any signal, including the ID fields. The
interconnect is only a pass-thru infrastructure which transmits from one point
to another the requests and their completions.

A protocol support applies to the global architecture, thus the agents connected.
The core doesn't support (yet) any protocol conversion. An AXI4-lite agent could
be easily connected as a master agent by mapping the extra AXI4 fields to `0`.
However, connecting it as a slave agent is more tricky and the user must ensure
the ALEN remains to `0` and no extra information as carried for instance by ACACHE
is needed.

Optionally, AMBA USER signals can be supported and transported (AUSER, WUSER,
BUSER and RUSER). These bus fields of the AMBA channels can be activated
individually, e.g. for address channel only and configured to any width. This
applies for both AXI4 and AXI4-lite configuration.

The core proposes a top level for [AXI4](../rtl/axicb_crossbar_top.sv), and a 
top level for [AXI4-lite](../rtl/axicb_crossbar_lite_top.sv). Each supports up 
to 4 masters and 4 slaves. If the user needs less than 4 agents, it can tied
to 0 the input signals of an interface, and leave unconnected the outputs.


### Ordering rules

The core supports outstanding requests, and so manages traffic queues for each master.

The core doesn't support ID reodering to enhance quality-of-service and so the user
can be sure the read or write requests will be issued to the master interface(s)
in the same order than received on a slave interface.

The core doesn't support read/write completion reodering, so a master issuing
with the same ID some requests to different slaves can't be sure the completions
will follow the original order if the slaves don't have the same pace to complete
a request. This concern will be addressed in a future release. Today, a user needs
to use different IDs to identify the completions' source and so the slave responding.

Read and write traffics are totally uncorrelated, no ordering can be garanteed
between the read / write channels.

The ordering rules mentioned above apply for device or memory regions.

### AXI4-lite specificities

AXI4-lite specifies the data bus width can be only `32` or `64` bits wide.
However, the core doesn't perform any checks neither prevent to use another
width. The user is responsible to configure his platform with values according
the specification.

AXI4-lite doesn't request USER fields but the core allows to activate this
feature support.

AXI4-lite doesn't request IDs support, but the core supports them natively.
The user can use them or not but they are all carried across the
infrastructure.  This can be helpfull to mix AXI4-lite and AXI4 agents
together. If not used, the user needs to tied them to `0` to ensure a correct
ordering model and select a width equals to `1` bit to save area resources.

AXI4-lite doesn't support `xRESP` with value equals to `EXOKAY` but the core
doesn't check that. The user is responsible to drive a completion with a
correct value according the specification.

AXI4-lite supports WSTRB and the core too. It doesn't manipulate this field and
the user is responsible to drive correctly this field according the
specification.

All other fields specified by AXI4 but not in AXI4-lite and not mentioned in
this section are not supported by the core when AXI4-lite mode is selected.
They are not used neither carried across the infrastructure and the user can
safely ignore them.


## Outstanding Requests Support

The core proposes internal buffering capability to serve outstanding requests
from/to the slaves. This can be configured easily for all master and slave
interfaces with two parameters:

- `MSTx_OSTDREQ_NUM` or `SLVx_OSTDREQ_NUM`: the maximum number of oustanding
  requests the core is capable to store
- `MSTx_OSTDREQ_SIZE` or `SLVx_OSTDREQ_SIZE`: the number of datpahases of an
  outstanding requets. Can be useful to save area if a system doesn't need to 
  use biggest AXI4 payload possible, i.e. if a processor only use [1,2,4,8,16] 
  dataphases maximum. Default should be `256` beats.

When an inteface enables the CDC support to cross its clock domain, the internal
buffering is managed with the [DC-FIFO](https://github.com/dpretet/async_fifo)
instanciated for CDC purpose. If no CDC is required, a simple synchronous FIFO
is used to buffer the requests.

## Routing Accross The Switching Matrix

To route a read/write request to a slave agent, and route back its completion
to a master agent, the core uses the request's address and its ID.

Each master is identified by an ID mask to route back completion to it. For
instance if we suppose the ID field is 8 bit wide, the master agent connected
to the slave interface 0 can be setup with the mask `0x10`. If the agent supports
up to 16 outstanding requests, they may span between `0x10` and `0x1F`. The next
agent could be identified with `0x20` and another one with `0x30`. The user must
takes care the ID generated for a request doesn't conflict with an ID from
another agent, thus the ID numbering rolls off. In the setup above, the agent 0
can't issue ID bigger than `0x1F` which will mis-route completion back to it and
route it to the agent 1. The core doesn't track such wrong configuration. The
must use a mask greater than 0.

Each slave is assigned into an address map (start & end address) across the
global memory map. To route a request, the switching logic decodes the address
to select the slave agent targeted and so the master interface to source. For
instance, slave agent 0 could be mapped over the addresses `0x000` up to
`0x0FF`. Next slave agent between `0x100` and `0x1FF`. In case the request
tries to target a memory space not mapped to a slave, the agent will receive a
`DECERR` completion. The user must ensure the address mapping can be covered
by the address bus width; the user needs to take care to configure correctly
the mapping and avoid any address overlap between slaves which will lead to
mis-routing. The core doesn't track such wrong configurations.


## Switching Logic Architecture

The foundation of the core is made of a switches, one dedicated per interface.
All slave switches can target any master switch to drive read/write requests,
while any master switch can drive back completions to any slave switch.

```
         │                           │
         │                           │
         ▼                           ▼
┌─────────────────────────────────────────────┐
│ ┌──────────────┐           ┌──────────────┐ │
│ │ slv0 switch  │           │ slv1 switch  │ │
│ └──────────────┘           └──────────────┘ │
│                                             │
│ ┌──────────────┐           ┌──────────────┐ │
│ │ mst0 switch  │           │ mst1 switch  │ │
│ └──────────────┘           └──────────────┘ │
└─────────────────────────────────────────────┘
         │                           │
         │                           │
         ▼                           ▼
```

A pipeline stage can be activated for input and output of the switch layer to
help timing closure.


### Switching Logic from Slave Interfaces

The figure below illustrates the switching logic dedicated to a slave interface.
Each slave interface is connected to such switch which sends requests to master
interface by decoding the address. Completion are routed back from the slave with
a fair-share round robin arbiter to ensure a fair traffic share. This architecture
doesn't ensure any ordering rule and the master is responsible to reorder its
completion if needed by its internal core.

```

                                     From slave interface


   AW Channel                 W Channel         B channel         AR Channel        R Channel

        │                         │                 ▲                  │                ▲
        │                         │                 │                  │                │
        ▼                         ▼                 │                  ▼                │
┌──────────────┐   ┌────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│decoder+router│──▶│FIFO│──│decoder+router│  │arbiter+switch│  │decoder+router│  │arbiter+switch│
└──────────────┘   └────┘  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘
   │        │                 │        │        ▲        ▲        │        │        ▲        ▲
   │        │                 │        │        │        │        │        │        │        │
   ▼        ▼                 ▼        ▼        │        │        ▼        ▼        │        │


                                    To master switches
```

### Switching Logic to Master Interfaces

The figure below illustrates the switching logic dedicated to a master interface.
A fair-share round robin arbitration ensures a fair traffic share from the master and the
completion are routed back to the requester by decoding the ID.

```
                                    From slave switches


   AW Channels       W Channels        B channels        AR Channels        R Channels

   │        │        │        │        ▲        ▲        │        │        ▲        ▲
   │        │        │        │        │        │        │        │        │        │
   ▼        ▼        ▼        ▼        │        │        ▼        ▼        │        │
┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│arbiter+switch│  │arbiter+switch│  │arbiter+switch│  │decoder+router│  │decoder+router│
└──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘
        │                 │                 ▲                │                 ▲
        │                 │                 │                │                 │
        ▼                 ▼                 │                ▼                 │


                                    To master interface

```

### Arbitration and Priority Management

Both the master and slave switches use the same arbitration mode, a non-blocking
round robin model. The behavior of this stage is the following, illustrated here
with four requesters. `req`, `mask` `grant` & `next mask` are 4 bits wide,
agent 0 is mapped on LSB, agent 3 on MSB.

If all requesters are enabled, it will grant the access from LSB to MSB,
thus from req 0 to req 3 and then restart from 0:

```
        req    mask  grant  next mask

t0      1111   1111   0001    1110
t1      1111   1110   0010    1100
t2      1111   1100   0100    1000
t3      1111   1000   1000    1111
t4      1111   1111   0001    1110
t++     ...
```

If the next requester allowed is not active, it passes to the next+2:

```
         req    mask   grant   next mask

t0       1101   1111    0001     1110
t1       1101   1110    0100     1000
t2       1101   1000    1000     1111
t3       1101   1111    0001     1110
t4       1111   1110    0010     1100
t++      1111   1100    0100     1000
      ...
```

If a lonely request doesn't match a mask, it passes anyway and reboot the
mask:

```
         req    mask  grant   next mask

t0       0011   1111   0001     1110
t1       0011   1110   0010     1100
t2       0011   1100   0001     1110
t3       0111   1110   0010     1100
t4       0111   1100   0100     1000
t++      ...
```

To balance granting, masters can be prioritzed (from 0 to 3). An activated
highest priority layer prevent computation of lowest priority layers (here,
priority 2 for req 2, 0 for others):

```
         req    mask   grant   next mask (p2) next mask (p0)

t0       1111   1111    0100      1000          1111
t1       1011   1111    0001      1100          1110
t2       1011   1110    0010      1100          1100
t3       1111   1000    0100      1111          1100
t4       1011   1100    1000      1111          1111
t++      ...
```


### Shareability & Routing Tables

Each master can be configured to use only specific routes across the crossbar
infrastructure. This feature if used can help to save gate count as will
restrict portion of the memory map to certain agents, for security reasons or
avoid any accidental memory corruption. **By default a master can access to any
slave**. The parameter `MSTx_ROUTES` of N bits enables or not a route. Bit `0`
enable to route to the slave agent 0 (master interface 0), bit `1` to the slave
agent 1 and so on. This setup physically isolates agents from each others and
can't be overridden once the core is implemented. If a master agent tries to
access a restricted zone of the memory map, its slave switch will handshake the
request, will not transmit it and then complete the request with a `DECERR`.

This option can be use to define memory region shareable or not between master
agents.
# AXI ID Usage in the crossbar

## AMBA Specification

Follow the AMBA AXI4 specification part related to the ordering model.


### Definition of the ordering model


The AXI4 protocol supports an ordering model based on the use of the AXI ID
transaction identifier.

The principles are that for transactions with the same ID:
- Transactions to any single peripheral device, must arrive at the peripheral
  in the order in which they are issued, regardless of the addresses of the
  transactions.
- Memory transactions that use the same, or overlapping, addresses must arrive
  at the memory in the order in which they are issued.

Note:

In an AXI system with multiple masters, the AXI IDs used for the ordering model
include the infrastructure IDs, that identify each master uniquely. This means
the ordering model applies independently to each master in the system.

The AXI ordering model also requires that all transactions with the same ID in
the same direction must provide their responses in the order in which they are
issued. Read and write address channels are independent and in this
specification, are defined to be in different directions. If an ordering
relationship is required between two transactions with the same ID that are in
different directions, then a master must wait to receive a response to the
first transaction before issuing the second transaction.  If a master issues a
transaction in one direction before it has received a response to an earlier
transaction in the opposite direction, then there are no ordering guarantees
between the two transactions.

Note:

Where guaranteed ordering requires a response to an earlier transaction, a
master must ensure it has received a response from an appropriate point in the
system. A response from an intermediate AXI component cannot guarantee ordering
with respect to components that are downstream of the intermediate buffer.


### Master Ordering

A master that issues multiple read or write transactions in the same direction
with the same ID has the following guarantees about the ordering of these
transactions:

- The order of response at the master to all transactions must be the same as
  the order of issue.
- For transactions to Device memory, the order of arrival at the slave must be
  the same as the order of issue.
- For Normal memory, the order of arrival at the slave of transactions to the
  same or overlapping addresses, must be the same as the order of issue. This
  also applies to transactions to cacheable memory and all valid transactions
  for which AxCACHE[3:1] is not 0b000.


### Interconnect Ordering

To meet the requirements of the ordering model, the interconnect must ensure that:

- The order of transactions in the same direction with the same ID to Device
  memory is preserved.
- The order of transactions in the same direction with the same ID to the same
  or overlapping addresses is preserved.
- The order of write responses with the same ID is preserved.
- The order of read responses with the same ID is preserved.
- Any manipulation of the AXI ID values associated with a transaction must
  ensure that the ordering requirements of the original ID values are
  maintained.
- Any component that gives a response to a transaction before the transaction
  reaches its final destination must ensure that the ordering requirements
  given in this section are maintained until the transaction reaches its final
  destination.



### Slave Ordering


To meet the requirements of the ordering model, a slave must ensure that:

- Any write transaction for which it has issued a response must be observed by
  any subsequent write or read transaction, regardless of the transaction IDs.
- Any write transaction to Device memory must be observed by any subsequent
  write to Device memory with the same ID, even if a response has not yet been
  issued.
- Any write transaction to Normal memory must be observed by any subsequent
  write to the same or an overlapping address with the same ID, even if a
  response has not yet been given. This also applies to transactions to
  cacheable memory and applies to all valid write transactions for which
  AWCACHE[3:1] is not 0b000.
- Responses to multiple write transactions with the same ID must be issued in
  the order in which the transactions arrived.
- Responses to multiple write transactions with different IDs can be issued in
  any order.
- Any read transaction for which it has issued a response must be observed by
  any subsequent write or read transaction, regardless of the transaction IDs.
- Any read transaction to Device memory must be observed by any subsequent read
  to Device memory with the same ID, even if a response has not yet been
  issued.
- Responses to multiple read transactions with the same ID must be issued in
  the order in which the transactions arrive.
- Responses to multiple read transactions with different IDs can be issued in
  any order.



### Personal note

Master:

The behavior is obvious in the above statements from the specfication: if
requests use the same ID, the completions are served in the same order, else
they may be served out-of-order.


Interconnect:

The ordering model applies independently to each master in the system.

The interconnect must ensure the response ordering remain the same than the order
the requests have been issued. It's allowed to manipulate the IDs routed to the
slaves if the completion flow respects the original ordering.

The difficulty for an interconnect circuit is to manage the responses in case
of out-of-order completion if a master require in-order completion. However, this
scenario would be a nice-to-have feature, not mandatory and could be useful for
instance in a bridge between two protocols.

Slave:

The difficulty for a slave is to support in-order completion. For instance,
if a slave implements algorithms which not execute in the same time, the slave
would need a reodering stage to serve the completion in-order. the number of
supported outstanding requests allowed would drasticaly increase the complexity
of such stage.
# Inputs/Outputs & Parameters

## Parameters

- AXI_ADDR_W
    - Address width for both read and write address channels
    - Any value from 1 bit
- AXI_ID_W
    - ID width for both read and write address/completion channels
    - Any value from 1 bit
- AXI_DATA_W
    - ID width for both read and write data channels
    - Any value from 1 bit
- MST_PIPELINE
    - Enable pipeline stage on switching logic inputs from the master agents
    - 1 = add the pipeline stage, otherwise 0
- SLV_PIPELINE
    - Enable pipeline stage on switching logic output to the slave agents
    - 1 = add the pipeline stage, otherwise 0
- AXI_SIGNALING
    - Specify the protocol supported by the core. Apply to the whole topology
    - 0 = AXI4-lite, 1 = AXI4
- USER_SUPPORT
    - Enable user specific sideband signal in all AXI channels. Apply to the whole topology
    - 1 = support sideband signals, 0 = no sideband signals
- AXI_AUSER_W
    - Specify in bit the width of address sideband signals
    - Apply to both read and write address channels
    - Any value from 1 bit
- AXI_WUSER_W
    - Specify in bit the width of write data sideband signals
    - Any value from 1 bit
- AXI_BUSER_W
    - Specify in bit the width of write response sideband signals
    - Any value from 1 bit
- AXI_RUSER_W
    - Specify in bit the width of read data sideband signals
    - Apply to both read and write address channels
    - Any value from 1 bit

Follow description of parameters common to all interfaces on which
a master agent is connected:

- MSTx_CDC
    - Implement a CDC stage for master x
    - 1 = activated, 0 = no CDC
- MSTx_OSTDREQ_NUM
    - Number of outstanding request supported for master x
    - Any value from 1
- MSTx_OSTDREQ_SIZE
    - Number of dataphase of an outstanding request for master x
    - Any from value between 1 and 256
- MSTx_PRIORITY
    - Priority a master will be garanteed in a switching
    - Value between 0 (low priority) and 3 (high priority)
- MSTx_ROUTES
    - The slave agent a master can target
    - 4 bits, one per slave. Bit0 is slave0, ..., bit3 is slave3
- MSTx_ID_MASK
    - A mask applied in slave completion channel to determine which master to route back the
      BRESP/RRESP completions.
    - Any value, width equal to `AXI_ID_W`

Follow description of parameters common to all interfaces on which a 
slave agent is connected:

- SLVx_CDC
    - Implement a CDC stage for slave x
    - 1 = activated, 0 = no CDC
- SLVx_OSTDREQ_NUM
    - Number of outstanding request supported for slave x
    - Any value from 1
- SLVx_OSTDREQ_SIZE
    - Number of dataphase of an outstanding request for slave x
    - Any from value between 1 and 256
- SLVx_START_ADDR
    - Memory address from which a slave agent can be targeted
    - Any value from 0 up to 2^`AXI_ADDR_W`/8
- SLVx_END_ADDR
    - Memory address up to which a slave agent can be targeted
    - Any value from 0 up to 2^`AXI_ADDR_W`/8
- SLVx_KEEP_BASE_ADDR
    - When a reqeust is issued to a slave agent, the base address `SLVx_START_ADDR` is
      is not removed from the `AxADDR` field

## Input / Output

### AXI4 / AXI4-lite

The core complies with AXI4 and AXI4-lite signal definition. The specification of the protocol
as well the signals list can be found on 
[ARM website](https://developer.arm.com/documentation/ihi0022/latest/).

### General Interface

The following signals are the clock and reset necessary to switching logic to be functional.
Only on reset must be driven, the other one needing to be tied to `0` for srst or `1` for aresetn.
Refer to the [architecture chapter](architecture.md#clock-and-reset-network) for explanation.

- aclk
    - The clock for the switching logic and the internal buffers
    - Any frequency
- aresetn
    - Active low, asynchronous reset. Must comply to AMBA specification, asynchronous assertion,
      synchronous deassertion
- srst
    - Fully synchronous reset
