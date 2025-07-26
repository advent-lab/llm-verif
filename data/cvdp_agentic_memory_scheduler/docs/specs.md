# Memory Scheduler Module Description

This module implements a multi‐request memory scheduler that grants one of four possible memory requests each cycle based on **rotating priority** and **round‐robin fallback**. It selects the next request to serve by first looking for a request matching a 2‐bit priority level (which decrements each time a request is serviced) and, if none match, it falls back to a round‐robin mechanism. The chosen request is marked by a single‐hot grant signal, and the corresponding address is driven onto the memory interface outputs.

---

## Parameterization

This design is primarily fixed at four requesters, each with a 2‐bit QoS level. Key fixed aspects include:

- **Number of Requesters:** Exactly 4.  
- **QoS Bit‐Width:** 2 bits per request, allowing 4 levels of priority (0..3).  
- **Memory Address Width:** 32 bits for each request’s address.

No additional compile‐time parameters are provided, so the design is specialized for four requesters.

---

## Interfaces

### 1. Clock and Reset

- **clk:** The primary clock input.  
- **reset:** An active‐high reset that reinitializes the scheduler to its default state.

When `reset` is asserted, the module clears any internal state and sets outputs to default values.

### 2. Request and QoS Inputs

- **request [3:0]:** A one‐bit “request” signal for each of the four clients.  
  - `request[i] = 1` indicates that client *i* has an active request.  
- **qos [7:0]:** Four 2‐bit QoS fields, one for each requester.  
  - `qos[1:0]`   => QoS for requester 0  
  - `qos[3:2]`   => QoS for requester 1  
  - `qos[5:4]`   => QoS for requester 2  
  - `qos[7:6]`   => QoS for requester 3  
  Higher QoS values (3) imply higher priority; lower values (0) imply lower priority.

### 3. Address Inputs

- **address0, address1, address2, address3 (32 bits each):**  
  The 32‐bit memory addresses associated with each of the four requesters.

### 4. Memory Interface Outputs

- **mem_address [31:0]:** The selected address for the granted request.  
- **mem_cmd_valid:** A control signal indicating when the scheduler has a valid memory command.  
- **mem_cmd_type [1:0]:** The command type (e.g., `00` for READ, `01` for WRITE). In this design, it is always set to `READ` (2’b00).

### 5. Handshake and Grant

- **mem_ack:** An input from the memory interface acknowledging that the current command has been accepted.  
- **grant [3:0]:** A one‐hot vector indicating which request is currently granted. For example, `grant = 4'b0100` means request 2 is being serviced.

---

## Detailed Functionality

### 1. Rotating Priority Logic

The module maintains a 2‐bit `current_priority` register, which starts at `3` (binary `11`) after reset. Each time a request is successfully issued (indicated by `mem_ack` going high) or when no request is currently valid, it **rotates** by decrementing this value (`3 → 2 → 1 → 0 → 3 → ...`).

### 2. Priority‐Based Selection

On each cycle, if a new request can be chosen (i.e., either `mem_cmd_valid == 0` or `mem_ack == 1`):

1. **Priority Pass**: The scheduler loops over the four request lines (from highest index to lowest) to find any requester whose 2‐bit QoS matches the `current_priority`. The highest‐indexed matching requester is selected.  
2. **Round‐Robin Fallback**: If no requester matched the current priority, the scheduler performs a round‐robin search among all four request lines, starting from `round_robin_index`. It picks the first active requester it finds and then increments `round_robin_index`.

In this manner, the design ensures that:

- Higher QoS requests (matching `current_priority`) are served first.  
- If no request matches that QoS, the system avoids starvation by falling back to a round‐robin selection among all active requesters.

### 3. Single‐Hot Grant and Memory Address

Once a request is selected:

- The scheduler asserts `mem_cmd_valid` and drives the corresponding 32‐bit address onto `mem_address`.  
- A single‐hot `grant` vector is generated, e.g. `4'b1000` for requester 3.  
- The 2‐bit `mem_cmd_type` is set to `READ` (`00` in this example).

The module holds these signals stable until `mem_ack` indicates that the memory interface has accepted the request, allowing a new arbitration cycle to begin.

### 4. Internal Registers and State

- **current_priority:** Tracks which QoS level (0..3) the scheduler is trying to service first.  
- **round_robin_index:** Tracks where the fallback round‐robin search starts.  
- **granted_request [3:0]:** Stores which requester was chosen in the current cycle (single‐hot).

All updates occur synchronously on the rising edge of `clk` unless `reset` is asserted, which clears the module to default states (`mem_cmd_valid=0`, etc.).

---

## Summary

This **memory scheduler** module arbitrates up to four simultaneous requesters, each with a 2‐bit QoS level. It implements a **rotating QoS priority** (3 → 2 → 1 → 0 → 3 → …) to ensure that higher‐priority requests are serviced first in each cycle. If no request matches the current priority, a **round‐robin** fallback ensures fairness among all active requests. The chosen request is granted exclusively via a one‐hot `grant` signal, and its address is driven on the `mem_address` output.

This architecture provides a **flexible yet compact** scheduling design for systems needing QoS priority control plus a backup fairness mechanism.
