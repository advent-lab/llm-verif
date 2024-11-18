# Washing machine
this a multiclock washing machine microcontroller(FSM) done using verilog implemented into main blocks and one top module the main blocks are :
1- FSM 
2- counter 

# FSM
the finite state machine is used as a main controller for the washing machine and determines in which state the machine are in, the states are as in the following :
1-IDLE
2-Filling water(2 min)
3-Washing(5 min) 
4-Rinsing(2 min) 
5-Spining(1 min) 
and for each state besides the idle state the washing machine spends a time calculated with the help of the counter 
  
  localparam IDLE       = 3'b000,
  Filing_Water          = 3'b001,
  Washing               = 3'b011,
  Rinsing               = 3'b010,
  spining               = 3'b110,
  pause                 = 3'b111;

# counter
the counter is used to calculate seconds, minutes while a 10 us is emulating the 1s for the sake of the simulating, and for the different clock frequencies,
the counter calculates different number of clocks to reach on second, the washing machine can have the following clock frequencies :
1-1 Mhz
2-2 Mhz
3-4 Mhz
4-8 Mhz
