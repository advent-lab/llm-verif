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