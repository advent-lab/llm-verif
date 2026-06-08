module caesar_cipher_tb;
    reg [7:0] input_char;       // Input character (ASCII)
    reg [3:0] key;              // Shift key (4-bit)
    wire [7:0] output_char;     // Output character (shifted)
    integer i;

    // Test strings and phrases
    parameter PHRASE1_LEN = 5;
    parameter PHRASE2_LEN = 5;
    parameter PHRASE3_LEN = 6;
    reg [7:0] phrase1 [0:PHRASE1_LEN-1];  // Example word "hello"
    reg [7:0] phrase2 [0:PHRASE2_LEN-1];  // Example word "WORLD"
    reg [7:0] phrase3 [0:PHRASE3_LEN-1];  // Example word "Caesar"
    reg [7:0] output_phrase [0:31];       // Temporary storage for the output phrase

    // Instantiate the caesar_cipher module
    caesar_cipher uut (
        .input_char(input_char),
        .key(key),
        .output_char(output_char)
    );

    initial begin
        // Initialize phrases
        phrase1[0] = "h"; phrase1[1] = "e"; phrase1[2] = "l"; phrase1[3] = "l"; phrase1[4] = "o";
        phrase2[0] = "W"; phrase2[1] = "O"; phrase2[2] = "R"; phrase2[3] = "L"; phrase2[4] = "D";
        phrase3[0] = "C"; phrase3[1] = "a"; phrase3[2] = "e"; phrase3[3] = "s"; phrase3[4] = "a"; phrase3[5] = "r";

        // Test case 1: Phrase "hello" with key = 3
        key = 4'b0011; // key = 3
        $display("Test case 1: Phrase 'hello' with key = %d", key);
        for (i = 0; i < PHRASE1_LEN; i = i + 1) begin
            input_char = phrase1[i];
            #10;
            output_phrase[i] = output_char;
        end
        // Display the entire output phrase
        $write("Output: ");
        for (i = 0; i < PHRASE1_LEN; i = i + 1) begin
            $write("%c", output_phrase[i]);
        end
        $display("");

        // Test case 2: Phrase "WORLD" with key = 4
        key = 4'b0100; // key = 4
        $display("Test case 2: Phrase 'WORLD' with key = %d", key);
        for (i = 0; i < PHRASE2_LEN; i = i + 1) begin
            input_char = phrase2[i];
            #10;
            output_phrase[i] = output_char;
        end
        // Display the entire output phrase
        $write("Output: ");
        for (i = 0; i < PHRASE2_LEN; i = i + 1) begin
            $write("%c", output_phrase[i]);
        end
        $display("");

        // Test case 3: Phrase "Caesar" with key = 5
        key = 4'b0101; // key = 5
        $display("Test case 3: Phrase 'Caesar' with key = %d", key);
        for (i = 0; i < PHRASE3_LEN; i = i + 1) begin
            input_char = phrase3[i];
            #10;
            output_phrase[i] = output_char;
        end
        // Display the entire output phrase
        $write("Output: ");
        for (i = 0; i < PHRASE3_LEN; i = i + 1) begin
            $write("%c", output_phrase[i]);
        end
        $display("");

        $finish; // Stop simulation
    end
endmodule