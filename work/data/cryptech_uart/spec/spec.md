uart.v
------
Configuration registers for the uart core.

tb_uart.v
---------
Testbench for the UART core.

uart_core.v
-----------
A simple universal asynchronous receiver/transmitter (UART)
interface. The interface contains 16 byte wide transmit and
receivea buffers and can handle start and stop bits. But in
general is rather simple. The primary purpose is as host
interface for the coretest design. The core also has a
loopback mode to allow testing of a serial link.

Note that the UART has a separate API interface to allow
a control core to change settings such as speed. But the core
has default values to allow it to start operating directly
after reset. No config should be needed.

uart
====

A Universal asynchronous receiver/transmitter (UART) implemented in Verilog.

This UART used to be in coretest, but has been moved out as a separate
project.

The current implementation supports the ability to set the bit rate as
well as number of data- and stop bits by writing to control addresses
via the control interface.



