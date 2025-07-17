# Stop Watch

It is a repository in which stop watch is made using Verilog HDL. After that, this stop watch can support centi-seconds, seconds, minutes and hours. 

Moreover, it only uses only counter in it. i.e., FPGA is having clock of 100MHz and we cannot see anything on this so high frequency, so we must have to reduce this frequency. 

To reduce the frequency of FPGA and give it to stop watch, we use a counter to decrease the freqeuncy. The counter which I refer that I have used only one counter, is the counter of time. We can use multiple counters for time that counter of centi-seconds, counter of seconds, counter of minutes and counter for hours but I have used just one counter. 
There is another counter which is used to decreament the clock.



## How to decrease the clock using counter?

We can decrease the clock using counter by just a little bit of thinking.

As You can see that the 1Hz (1 second tick) clock is on for half of the time (1s) and off for another half of the time. 

It means that we can have the 1 second tick clock using the standard FPGA clock (100MHz) when we divide such a number by standard clock and we get an half. And the number is 50,000000 (50MHz).

50,000000 is the value of the counter which can give us clock of 1 second with the FPGA clock of 100MHz. 

But goal is to find the number which can take us to clock of 1 centi-second tick. To get it, we already have number for 1 second, which is 50,000000. To get for 1 centi-second, we multiply this number with 10 raised to the power negative 2 (which is centi simply). 

So, 50,000000 * (10 raised to negative 2) = 50,0000

So, 50,0000 is the number for the counter which can take to the clock of 1 centi-second (See line # 33 of stopWatch.v). After each of its positive of negative edge, we will increament the counter, after each increament, we say that 1 centi-second has elapsed. 
Now begins the formula by which we can convert centi-seconds to seconds, minutes and hours. 

100 centi-seconds make 1 second. 60 seconds make 1 minutes and 60 minutes make 1 hour. So simple.

% we have to used just not to exceed the number from its limit. For example, we cannot have centi-seconds greater than 100. We cannot have seconds greater than 60. We cannot have minutes greater than 60. And at last but not least, we cannot have hours greater than 24. 

That's all. Now concept is cleared remaining things you will understand yourself becasue they are quite easy and understandable.



## Putting it all together

Finally, to run all Verilog files in QuestaSim (I prefer this), add all Verilog (.v) file in the new project of QuestaSim, then simulate the file tb_RISC.v

