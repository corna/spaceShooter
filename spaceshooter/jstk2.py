#!/usr/bin/env python3

import serial
import threading
import struct
import time

from typing import Tuple

class jstk2:
    HEADER_CODE = 0xc0
    READ_CHUNK_SIZE = 4

    def __init__(self, serial_port: str, baud_rate: int, tx_period: int = 100, read_timeout: int = 50):
        self.serial = serial.Serial(serial_port, baud_rate, timeout=read_timeout)
        self.terminate = threading.Event()

        # TX resources
        self.tx_period = tx_period
        self.leds = (0, 0, 0)
        self.tx_lock = threading.Lock()
        self.tx_thread = threading.Thread(target=self._tx_th)
        self.tx_thread.start()

        # RX resources
        self.jstk = (0, 0)
        self.btn_trigger = False
        self.btn_jstk = False
        self.rx_data = bytearray()
        self.rx_lock = threading.Lock()
        self.rx_thread = threading.Thread(target=self._rx_th)
        self.rx_thread.start()

    def close(self):
        self.terminate.set()
        self.tx_thread.join()
        self.rx_thread.join()

    def __del__(self):
        self.close()

    def _tx_th(self):
        while True:
            with self.tx_lock:
                leds = self.leds
            self.serial.write(struct.pack("BBBB", self.HEADER_CODE, *leds))

            # Cancel requested
            if self.terminate.wait(self.tx_period / 1000):
                break

    def _rx_th(self):
        while not self.terminate.is_set():
            self.rx_data += self.serial.read(self.READ_CHUNK_SIZE)

            try:
                # Drop leading bytes until HEADER_CODE
                self.rx_data = self.rx_data[self.rx_data.index(self.HEADER_CODE):]
                
                if len(self.rx_data) < 4:
                    # Partial packet, do nothing
                    pass

                else:
                    # Got a packet: extract the data, remove its bytes from rx_data and save the content
                    jstk_x, jstk_y, buttons = struct.unpack("xBBB", self.rx_data[:4])
                    self.rx_data = self.rx_data[4:]

                    with self.rx_lock:
                        self.jstk = (jstk_x & 0x7f, jstk_y & 0x7f)
                        self.btn_trigger = bool(buttons & 0x02)
                        self.btn_jstk = bool(buttons & 0x01)
        
            except ValueError:
                # No header, drop all the data and do nothing
                self.rx_data = bytearray()

    def set_leds(self, leds: Tuple[int, int, int]) -> None:
        with self.tx_lock:
            self.leds = leds

    def get_jstk(self) -> Tuple[Tuple[int, int], bool, bool]:
        with self.rx_lock:
            return self.jstk, self.btn_trigger, self.btn_jstk


## Example:
#
#jstk_obj = jstk2('/dev/ttyUSB1', 115200)
#jstk_obj.set_leds((255, 0, 0))
#
#time.sleep(0.1)
#for i in range(2):
#   
#    print(jstk_obj.get_jstk())
#    time.sleep(1)
#
#jstk_obj.close()