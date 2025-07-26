module door_lock #(
    parameter PASSWORD_LENGTH = 4, // Number of digits in the password
    parameter MAX_TRIALS      = 4  // Maximum allowed incorrect attempts
) (
    input  logic                         clk               , // Clock signal
    input  logic                         srst              , // Active High Synchronous Reset
    input  logic [                  3:0] key_input         , // 4-bit digit input (0-9)
    input  logic                         key_valid         , // Signal to register a key input
    input  logic                         confirm           , // Confirm button for password check
    input  logic                         admin_override    , // Admin override to unlock the door
    input  logic                         admin_set_mode    , // Admin mode activation for setting password
    input  logic [PASSWORD_LENGTH*4-1:0] new_password      , // New password input
    input  logic                         new_password_valid, // Valid signal for new password
    output logic                         door_unlock       , // Door unlock signal
    output logic                         lockout             // Lockout due to multiple failed attempts
);

    // FSM States
    typedef enum logic [2:0] {
        IDLE,          // Waiting for input
        ENTER_PASS,    // Entering password
        CHECK_PASS,    // Checking password
        PASSWORD_OK,   // Password is correct
        PASSWORD_FAIL, // Password is incorrect
        LOCKED_OUT,    // System locked due to max failed attempts
        ADMIN_MODE     // Admin sets a new password
    } state_t;

    state_t current_state, next_state;

    // Internal registers
    logic [    PASSWORD_LENGTH*4-1:0] stored_password ; // Stored password
    logic [    PASSWORD_LENGTH*4-1:0] entered_password; // Entered password
    logic [$clog2(PASSWORD_LENGTH):0] entered_count   ; // Number of entered digits
    logic [     $clog2(MAX_TRIALS):0] fail_count      ; // Track number of failed attempts
    logic                             match           ; // Password match flag

    // Sequential logic - State transition
    always_ff @(posedge clk or posedge srst) begin
        if (srst) begin
            current_state <= IDLE;
        end else begin
            current_state <= next_state;
        end
    end

    // Password entry logic
    always_ff @(posedge clk or posedge srst) begin
        if (srst) begin
            entered_password <= 0;
        end else if (key_valid && entered_count < PASSWORD_LENGTH) begin
            entered_password <= {entered_password[PASSWORD_LENGTH*4-5:0], key_input};
        end
    end

    // Counter for entered digits
    always_ff @(posedge clk or posedge srst) begin
        if (srst) begin
            entered_count <= 0;
        end else if (key_valid) begin
            entered_count <= entered_count + 1;
        end else if (current_state == CHECK_PASS) begin
            entered_count <= 0; // Reset after confirmation
        end
    end

    // Password comparison logic
    assign match = (entered_password == stored_password);

    // Next state logic
    always_comb begin
        next_state = current_state; // Default hold state
        case (current_state)
            IDLE : begin
                if (!admin_set_mode && admin_override)
                    next_state = PASSWORD_OK; // Admin override unlocks
                else if (key_valid)
                    next_state = ENTER_PASS;
                else if (admin_set_mode && admin_override) // Admin enters password setting mode
                    next_state = ADMIN_MODE;
            end
            ENTER_PASS : begin
                if (entered_count == PASSWORD_LENGTH && confirm)
                    next_state = CHECK_PASS;
                else if (confirm)
                    next_state = PASSWORD_FAIL;

            end
            CHECK_PASS : begin
                if (match)
                    next_state = PASSWORD_OK; // Password correct
                else
                    next_state = PASSWORD_FAIL; // Password incorrect
            end
            PASSWORD_OK : begin
                next_state = IDLE;
            end
            PASSWORD_FAIL : begin
                if (fail_count >= MAX_TRIALS - 1)
                    next_state = LOCKED_OUT; // Lockout if max trials exceeded
                else
                    next_state = IDLE;
            end
            LOCKED_OUT : begin
                if (admin_override)
                    next_state = PASSWORD_OK; // Admin reset
            end
            ADMIN_MODE : begin
                if (new_password_valid)
                    next_state = IDLE; // Exit admin mode after password update
            end
            default: begin
                next_state = IDLE;
            end
        endcase
    end

    // Unlock and lockout logic
    always_ff @(posedge clk or posedge srst) begin
        if (srst) begin
            door_unlock <= 0;
            lockout     <= 0;
            fail_count  <= 0;
        end else begin
            case (current_state)
                PASSWORD_OK : begin
                    door_unlock <= 1;
                    fail_count <= 0; // Reset failed attempts
                    lockout    <= 0;
                end
                PASSWORD_FAIL : begin
                    door_unlock <= 0;
                    fail_count <= fail_count + 1;
                    lockout    <= (fail_count == MAX_TRIALS-1) ? 1 : 0;
                end
                LOCKED_OUT    : begin
                    lockout    <= 1;
                    if (admin_override)
                        fail_count <= 0;
                end
                default : begin
                    door_unlock <= 0;
                    lockout     <= 0;
                end
            endcase
        end
    end

    // Password setting logic (only by admin)
    always_ff @(posedge clk or posedge srst) begin
        if (srst) begin
            stored_password <= '0 | 1; // Default password: 0001
        end else if (current_state == ADMIN_MODE && new_password_valid) begin
            stored_password <= new_password; // Update password
        end
    end

endmodule