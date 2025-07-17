trng_csprng.v
-------------
CSPRNG for the TRNG.

trng.v
--------
Top level wrapper for the True Random Number Generator.

trng_csprng_fifo.v
------------------
Output FIFO for the CSPRNG in the TRNG.

trng_mixer.v
------------
Mixer for the TRNG.

tb_trng.v
-----------
Testbench for the trng module in the trng.

tb_csprng.v
-----------
Testbench for the csprng module in the trng.

tb_mixer.v
-----------
Testbench for the mixer module in the trng.

tb_csprng_fifo.v
----------------
Testbench for the csprng fifo module in the trng.


trng
====

True Random Number Generator core implemented in Verilog.

## Design inspiration, ideas and principles ##

The TRNG **MUST** be a really good one. Furthermore it must be trustable
by its users. That means it should not do wild and crazy stuff. And
users should be able to verify that the TRNG works as expected.

* Follow best practice
* Be conservative - No big untested ideas.
* Support transparency - The parts should be testable.


Some of our inspiration comes from:

* The Yarrow implementation in FreeBSD

* The Fortuna RNG by Ferguson and Schneier as described in Cryptography
Engineering.

* /dev/random in OpenBSD


## System description ##

The TRNG consists of a chain with three main subsystems

* Entropy generation
* Entropy accumulation
* Random generation


### Entropy generation ###

The entropy generation subsystems consists of at least two separate entropy
generators. Each generator collects entropy from an independent physical
process. The entropy sources MUST be of different types. For example
avalance noise from a reversed bias P/N junction as one source and RSSI
LSB from a receiver.

The reason for having multiple entropy sources is both to provide
reduncancy as well as making it harder for an attacker to affect the
entropy collection by forcing the attacker to try and affect different
physical processes simultaneously.

A given entropy generator is responsible for collecting the entropy
(possibly including A/D conversion.). The entropy generator MUST
implement some on-line testing of the physical entropy source based on
the entropy collected. The tests shall be described in detail here but
will at least include tests for:

* No long run lengths in generated values.
* Variance that exceeds a given threshhold.
* Mean value that don't deviate from expected mean.
* Frequency for all possible values are within expected variance.

If the tests fails over a period of generated values the entropy source
MUST raise an error flag. And MAY also block access to the entropy it
otherwise provides.

There shall also be possible to read out the raw entropy collected from
a given entropy generator. This MUST ONLY be possible in a specific
debug mode when no random generation is allowed. Also the entropy
provided in debug mode MUST NOT be used for later random number
generation.

The entropy generator SHALL perform whitening on the collected entropy
before providing it as 32-bit values to the entropy accumulator.



### Entropy accumulation ###

The entropy acculumation subsystems reads 32-bit words from the entropy
generators. The 32-bit words are combined and mixed by a simple
XOR-mixer into 32-bit words accumulated.

(TODO: We need a mechanism for mixing that supports generators with
different rates, capacity.)

When 1024 bits of mixed entropy has been collected the entropy is used
as a message block fed into a hash function.

The hash function used is SHA-512 (NIST FIPS 180-4).

When at least 256 blocks have been processed the current 512 bit digest
from SHA-512 is possible to extract from the entropy accumulator as seed
for the random generator. When a seed value has been extracted the
entropy message is discarded and a new message shall be started. This
means that no entropy collected is allowed to affect more than one seed
value.

Note that the number of 256 bit blocks used to generate the digest can
and probably will be much higher. The 256 block limit is the lower
warm-up bound. This lower bound may be increased as needed to provide
more trust. The complete TRNG MUST NOT be able to generate any random
numbers before the warm-up bound has been met and the random generator
has been seeded.


### Random generation ###

The random generation consists of a symmetric cipher that generates a
stream of values based on an intial state from the seed provived by the
entropy accumulator.

Our proposal is to use the ChaCha stream cipher with 256 bit key and 96
bit IV. The key and IV are taken from the seed. This means that there
will be a 32 bit counter and thus the maximum number of keystream blocks
is (2**32 - 1). The cipher must then be reseeded and the counter be
reset. We propose that it will be possible to configure the maximum
number of blocks to generate. From 2**16 to (2**31 - 1).

The number of rounds used in ChaCha should be conservatively
selected. We propose that the number of rounds shall be at least 24
rounds. Possibly 32 rounds. Given the performance in HW for ChaCha and
the size of the keystream block, the TRNG should be able to generate
plentiful of random values even with 32 rounds.

The random generator shall support the ability to test its functionality
by seeding it with a user supplied value and then generate a number of
values in a specific debug mode. The normal access to generated random
values MUST NOT be allowed during the debug mode. The random generator
MUST also set an error flag during debug mode. Finally, when exiting the
debug mode, reseeding MUST be done.

Finally the random generator provides random numbers as 32-bit
values. the 512 bit keystream blocks from ChaCha are divided into 16
32-bit words and provided in sequence.


## Implementation details ##

The core supports multpiple entropy sources as well as a CSPRNG. For
each entropy source there are some estimators that checks that the
sources are not broken.

There are also an ability to extract raw entropy as well as inject test
data into the CSPRNG to verify the functionality.

The core will include one FPGA based entropy source but expects the
other entropy source(s) to be connected on external ports. It is up to
the user/system implementer to provide physical entropy souces. We will
suggest and provide info on how to design at least one such source.

# Introduction to the Cryptech True Random Number Generator #
The Cryptech HSM project is designing an open HSM (Hardware Security or
High Security Module).

A critical part of any HSM is the ability to generate high quality
random numbers. These numbers are used to generate cryptographic keys,
initial vectors, IDs and many other things.

In this introduction to the Cryptech True Random Number Generator (TRNG)
we will look at the design goals for the TRNG and how the design meets
these goals [1].


## Design Goals ##
The Cryptech TRNG shall meet the following design Goals

1. High performance and Scaleable. Even a compact, low cost
implementation shall be able to generate 10-100 Mbps rate of random
number data. The design shall also be scaleable to basically arbitrarily
high capacity demands. A data rate of 100 Gbps for example shall be
possibe to reach, albeit not in a low cost implementation.


2. Secure and Conservative. Secure defaults. Following best practices
and don't invent new things that breaks with known besr practice. Very
high quality of the generated number. Resistance against attepmts at
manipulation. Use of big seed state. On-line testing of entropy souces.


3. Flexible and Modular. The architecture and the parameters controlling
the functionality shall be under control of the application. The major
functionaloties are in separate modules.


4. Open, Testable and Auditable.


Combining (4) with (2) and (3) is probably what sets the Cryptech TRNG
apart from many other designs.


## High level architecture ##

The Cryptech TRNG is a hybrid design with entropy providers connected to
physical entropy sources are used to seed a cryptographically safe
pseudor random number generator (CSPRNG). In order to combine the
entropy from the providers, the TRNG contains a mixer stage between the
providers and the CSPRNG. Figure XYZ shows the high level architecture.

Besides the three stages of the datapath, the TRNG contains a control
part that provides the functionality needed to test and debug the TRNG
in a secure manner, even in a running system.

The followin sub chapters will give a detailed description of each of
the parts of the TRNG.


### Entropy Providers ###

Entropy providers can be seen as the HW equivalent to drivers in an
operating system. The entropy provider is responsible for hiding the
functionality needed to control and extract data from a given entropy
source and to provide it as 32-bit data in a uniform way to the mixer.

The entropy provider must observe the behaviour of its noise source and
perform

Fast total failure tests and more comprehensive online test.


For debugging purposes the entropy providers must provide access to the
raw digital noise.



### Mixer ###

The mixer also decouples the random number generation from the entropy
collection. This means that the TRNG can collect entropy for the next
seed operation while the random generatio part keeps generating random
numbers.

The mixer is based around a cryptographic hash function. The current
implementation uses SHA-512 [5] but can be replaced with any other
cryptographic hash function.

Using a cryptographic hash function as a mixer makes it very hard
(infeasible) to determine the entropy from the seed. This makes it very
hard from an attacker to determine how an attempt at manipulating a
entropy source affected the seed and thus how effective the manipulatio
was.

Entropy is provided to the Mixer as 32-bit data words. The words are
accepted by the mixer in strict round robin order. This means that in an
implementation with a high capacity entropy provider and a lowe capacity
entropy provider, the rate of accepted data words from the high capacity
provider will be limited to the capacity of the low capacit
provider. The high capacity provider is simply not allowed to dominate
the input to the mixer.

Unless the TRNG state is reset, the hash function is never
reinitialized. Instead all entropy are added as new blocks of the same
message and the extracted seeds are intermediate digests generated for
each block added.

This means that the state of the hash function between seed data blocks
are based not only on the new entropy data, but also on previous hash
operations.

Each hash block is 1024 bits of new entropy, which are needed when
calculating one digest. A reseed requires two separate digests which
means that we need two blocks for a total of 2048 bits of entropy is
needd to reseed the CSPRNG.

The seeds are provided to the CSPRNG as 512 bit data words.


### CSPRNG ###

The CSPRNG is responsible for generating the random numbers provided to
applications by the TRNG.

The Cryptech CSPRNG is based on the stream cipher ChaCha. The key length
is 256 bits and the default number of rounds is 20. Users that want to
trade performance against security can adjust the numver of rounds by
setting the appropriate control registers.

The number of 512 bit blocks of random numbers generated is set to
64'h1000000000000000, or 2**60. This means that 2**64 32-bit words will
be generated between reseeds. The number of blocks between reseeds can
be adjusted by writing the the appropriate control register. It is also
possible to write to a control register that forces a reseed directly.

The CSPRNG requires two 512 bit words from the mixer to seed the
CSPRNG. These bits are used for:

- 512 bits block
- 256 bits key
- 64 bits IV
- 64 bits initial counter value.

In total 896 bits are used to seed the PRNG.

The current implementation of the CSPRNG contains one instance of the
ChaCha stream cipher. For higher performance more instances ca be added
to allow interleaved generation of random number blocks.

The CSPRNG contains a random number FIFO that provides the generated
32-bit numbers to applications. This allows the CSPRNG to generate
blocks of data fairly independently of the application consumption, and
ensure a steady rate of random numbers.


### Test and Debug ###

Each of the entropy sources are responsible for implementing on-line
testing.
