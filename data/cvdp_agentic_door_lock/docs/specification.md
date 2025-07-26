# Door Lock System Specification Document

## **Introduction**
The **Door Lock System** is a password-protected authentication module designed for **PIN-based access control** with a configurable password length. The module provides user authentication through password entry and verification while handling incorrect attempts with a lockout mechanism. Additionally, an **admin mode** allows for password updates and an override function to unlock the door when necessary.

---

## **Functional Overview**
The **door_lock** module is based on a **finite state machine (FSM)** and follows these primary operations:

1. **Password Entry:**  
   - The user enters a configurable length (`PASSWORD_LENGTH`) password.
   - Digits are entered sequentially via `key_input`, with `key_valid` indicating a valid input.

2. **Password Verification:**  
   - Upon entering all digits, the user presses `confirm` for 1 clock cycle to verify the password.
   - The module compares the entered password with the stored password.
   - If correct, the door unlocks by asserting the unlock signal for 1 clock cycle. It also reset the fail count, otherwise, the attempt count increments.

3. **Incorrect Attempts & Lockout:**  
   - If the password is entered incorrectly `MAX_TRIALS` times, the system locks out and stays locked out by continuously asserting `lockout` signal.
   - The system can only be reset using an `admin_override` or a full design reset.

4. **Admin Features:**  
   - `admin_override` is used to unlock the door during a lockout condition and also initiates password setting when combined with `admin_set_mode`.  
   - `admin_set_mode` enables the system to enter password-setting mode when first `admin_override` is used to unlock the door and then both `admin_override` and `admin_set_mode` are asserted in the `IDLE` state.  

---

## **Example Password Flow**
**Successful Authentication**

Stored Password: 1234 User Inputs: 1 → 2 → 3 → 4 → Confirm System: Door Unlocks.

**Incorrect Attempt**

Stored Password: 1234 User Inputs: 1 → 2 → 5 → 6 → Confirm System: Password Incorrect, 1 Attempt Used.

**Lockout Scenario**

User enters incorrect password 3 times System: Lockout Activated. Only Admin Override Can Unlock.


---

## **Module Interface**
The module should be implemented with the following interface:

```verilog
module door_lock #(
    parameter PASSWORD_LENGTH = 4,
    parameter MAX_TRIALS = 3
)(
    input  logic                         clk,
    input  logic                         srst, 
    input  logic [3:0]                   key_input,
    input  logic                         key_valid,
    input  logic                         confirm,
    input  logic                         admin_override,
    input  logic                         admin_set_mode,
    input  logic [PASSWORD_LENGTH*4-1:0] new_password,
    input  logic                         new_password_valid,
    output logic                         door_unlock,
    output logic                         lockout
);
```
---

## **Module Parameters**
The module supports the following **configurable parameters**:

| **Parameter**      | **Type** | **Description**                                                                                            |
|--------------------|----------|------------------------------------------------------------------------------------------------------------|
| `PASSWORD_LENGTH`  | Integer  | Defines the number of digits in the password.                                                              |
| `MAX_TRIALS`       | Integer  | Specifies the maximum number of incorrect password attempts before the system locks out.                   |

---

## **Port Description**

- **clk**: System clock, all operations are synchronous.  
- **srst**: Active-high synchronous reset.  
- **key_input**: 4-bit input representing a single digit (values 0–9) of the password.
- **key_valid**: Active-high. Indicates that `key_input` holds a valid digit of the password to be registered.  
- **confirm**: Active-high. Signals the module to compare the entered password with the stored one.  
- **admin_override**: Active-high. Unlocks the door during lockout or enables password update when used with `admin_set_mode`.  
- **admin_set_mode**: Active-high. Enables password update mode when used with `admin_override` and a `new_password_valid`.  
- **new_password**: New password input in admin mode.  
- **new_password_valid**: Active-high. Indicates that `new_password` contains a valid password to be stored.  
- **door_unlock**: Active-high. Asserted when the entered password is correct or admin override is triggered.  
- **lockout**: Active-high. Asserted after `MAX_TRIALS` failed password attempts.

---

## **FSM Design & States**

The FSM has the following states:

| **State**          | **Description**                                                                 |
|--------------------|---------------------------------------------------------------------------------|
| **IDLE**           | System is idle, waiting for user input or admin override.                       |
| **ENTER_PASS**     | Actively receiving password digits from the user via `key_input`.               |
| **CHECK_PASS**     | Verifies the entered password against the stored password.                      |
| **PASSWORD_OK**    | Password is correct or admin override is triggered; system grants access.       |
| **PASSWORD_FAIL**  | Password check failed; failure counter is incremented.                          |
| **LOCKED_OUT**     | System is locked due to reaching `MAX_TRIALS` failed attempts.                  |
| **ADMIN_MODE**     | Admin mode is active; system is ready to accept and store a new password.       |


---

## **State Transitions**


## **State Transitions**

- **IDLE → ENTER_PASS**: Triggered when the user initiates password entry by providing `key_valid`.  
- **ENTER_PASS → CHECK_PASS**: Triggered if the `confirm` signal is asserted and the number of digits of entered password is correct.
- **ENTER_PASS → PASSWORD_FAIL**: Triggered if the `confirm` signal is asserted and the number of digits of entered password is not correct.
- **CHECK_PASS → PASSWORD_OK**: Transition occurs if the entered password matches the stored password.  
- **CHECK_PASS → PASSWORD_FAIL**: Taken when the entered password does not match the stored password.  
- **PASSWORD_OK → IDLE**: The system resets to the idle state without any condition after a successful unlock sequence.  
- **PASSWORD_FAIL → LOCKED_OUT**: Activated when the number of consecutive failed attempts reaches the configured maximum.  
- **LOCKED_OUT → PASSWORD_OK**: When `admin_override` is asserted. It resets the lockout and grants access.  
- **IDLE → PASSWORD_OK**: When `admin_override` is asserted and `admin_set_mode` is not set in the same cycle.
- **IDLE → ADMIN_MODE**: When `admin_override` is asserted and `admin_set_mode` is also set in the same cycle. 
- **ADMIN_MODE → IDLE**: Triggered when a valid new password is submitted for storage.

---

## **Timing & Latency**

- The system is **synchronous**, with all operations occurring on the **rising clock edge**.
- `door_unlock` is asserted **1 clock cycle** after entering the `PASSWORD_OK` state.
- The attempt count (`fail_count`) is incremented **1 clock cycle** after entering the `PASSWORD_FAIL` state and resets when `admin_override` is asserted.
- `lockout` is asserted **1 clock cycle** after `fail_count` reaches `MAX_TRIALS-1` and FSM is in the `PASSWORD_FAIL` state. It resets when `admin_override` is asserted.
- `lockout` is deasserted **2 clock cycle** after `admin_override`.
---

## **Edge Cases & Constraints**

- **Incorrect password handling:**  
  - Fails should increment `fail_count` and eventually lead to lockout.  
- **Valid digit input range:**  
  - `key_input` values outside `0-9` are ignored.  
- **Admin mode precedence:**  
  - If `admin_set_mode` is active, normal password verification is bypassed.  
- **Reset Behavior:**  
  - `srst` resets the system to **IDLE**, clears `entered_password` and `fail_count`.
- **Default password initialization:**  
  - On reset, the stored password is initialized to a right-aligned value of 1, with all higher digits set to 0. The number of digits depends on `PASSWORD_LENGTH`.
    