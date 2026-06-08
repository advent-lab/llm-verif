# Caesar Cipher RTL Module Documentation

## Overview

Implement the `caesar_cipher` module to perform Caesar cipher encryption or decryption on a set of ASCII characters. This RTL design processes characters in parallel, where each character receives an individual shift value through the `key` input. The module supports both uppercase and lowercase letters using wraparound logic, and also handles non-alphabetic characters using arithmetic shifting.

Use this design for hardware-based character transformation, simple encryption demonstrations, or logic design exercises involving modular arithmetic.

---

## Parameters

Define the following parameters to configure the module's behavior:

- `PHRASE_WIDTH` (Default: 8): Total bit-width of the input phrase. Each character occupies 8 bits.
- `PHRASE_LEN` (Derived): Number of characters in the phrase, automatically calculated as `PHRASE_WIDTH / 8`.

For example:
- If `PHRASE_WIDTH = 8`, then `PHRASE_LEN = 1` → one character
- If `PHRASE_WIDTH = 16`, then `PHRASE_LEN = 2` → two characters

---

## Port Descriptions

All signals are synchronous and operate combinationally under an `always @(*)` block.

- `input_char`  (Input, Width = `PHRASE_WIDTH`):  
  Use this to supply the input ASCII phrase. Each character is 8 bits. For example, with `PHRASE_WIDTH = 16`, the input may be `"ab"` as `8'h61_62`.

- `key` (Input, Width = `PHRASE_LEN * 5`):  
  Provide a 5-bit shift value for each 8-bit character in the input. For 2 characters, use 10 bits total: 5 bits per character.

- `decrypt` (Input, Width = 1):  
  Set to `1'b1` to perform decryption. Set to `1'b0` to perform encryption.

- `output_char` (Output, Width = `PHRASE_WIDTH`):  
  Get the transformed characters after Caesar cipher logic is applied.

---

## Internal Logic and Flow

1. **Initialize Output**:  
   Clear `output_char` to avoid latch inference.

2. **Iterate Through Each Character**:  
   Use a loop with index `idx` to process one character at a time.

3. **Extract Current Character and Shift Value**:  
   - Get an 8-bit character from `input_char[(idx*8)+:8]`.
   - Get the corresponding 5-bit `shift_val` from `key[(idx*5)+:5]`.

4. **Encrypt or Decrypt**:  
   - If `decrypt = 0`: apply Caesar encryption logic.
     - If character is between `'A'` and `'Z'`: shift within uppercase alphabet (`A` to `Z`) using modular arithmetic:  
       `(char - 'A' + shift_val) % 26 + 'A'`
     - If character is between `'a'` and `'z'`: shift within lowercase alphabet:  
       `(char - 'a' + shift_val) % 26 + 'a'`
     - For other characters, shift by adding the `shift_val` directly.
   - If `decrypt = 1`: apply Caesar decryption logic.
     - Reverse the Caesar cipher using:  
       `(char - base - shift_val + 26) % 26 + base`
     - For non-alphabetic characters, subtract the `shift_val` directly.

5. **Reassemble Result**:  
   Concatenate the processed 8-bit results into `output_char`.

---

## Example

Let’s encrypt and decrypt a 2-character phrase using the Caesar cipher.

### Configuration

- `PHRASE_WIDTH = 16` → Two characters (`PHRASE_LEN = 2`)
- `input_char = 8'h61_62` → This represents `"ab"`
- `key = 10'b00001_00010` → First shift = 1, second shift = 2
- `decrypt = 0` → Encrypt

### Encryption Output

- `'a'` + 1 = `'b'`
- `'b'` + 2 = `'d'`
- Result: `output_char = 8'h62_64` → `"bd"`

### Decryption

Use the same `key`, set `decrypt = 1`, and input `"bd"`:
- `'b'` - 1 = `'a'`
- `'d'` - 2 = `'b'`
- Result: `output_char = 8'h61_62` → `"ab"`

---

## Bit Width Calculation

- For `PHRASE_WIDTH = N` bits:
  - Each character = 8 bits → `PHRASE_LEN = N / 8`
  - `key` width = `PHRASE_LEN * 5` bits
  - `output_char` width = `PHRASE_WIDTH`

---

## Implementation Notes

- Use signed types (`reg signed [7:0]`) to safely manipulate ASCII characters.
- Use `$unsigned()` during decryption to prevent overflow/underflow issues.
- Modular arithmetic ensures alphabetic characters wrap around correctly.

---