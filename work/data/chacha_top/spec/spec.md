chacha.v
--------
Top level wrapper for the ChaCha stream, cipher core providing
a simple memory like interface with 32 bit data access.

chacha_core.v
--------------
Verilog 2001 implementation of the stream cipher ChaCha.
This is the internal core with wide interfaces.

chacha_qr.v
-----------
Verilog 2001 implementation of the stream cipher ChaCha.
This is the combinational QR logic as a separade module to allow
us to build versions of the cipher with 1, 2, 4 and even 8
parallel qr functions.

tb_chacha_qr.v
--------------
Testbench for the Chacha stream cipher quarerround (QR) module.

tb_chacha.v
-----------
Testbench for the Chacha top level wrapper.

tb_chacha_core.v
-----------------
Testbench for the Chacha stream cipher core.

chacha
========

Verilog 2001 implementation of the ChaCha stream cipher.

## Functionality ##
This core implements ChaCha with support for 128 and 256 bit keys. The
number of rounds can be set from two to 32 rounds in steps of two. The
default number of rounds is eight.

The core contains an internal 64-bit block counter that is automatically
updated for each data block.


## Performance ##
Each quarterround takes one cycle which means that the mininum latency
will be 4*rounds. When the core is functionally correct we will add two
more version with 2 and 4 parallel quarterrounds respectively. The four
quarterounds version will achieve 1 cycle/round.


