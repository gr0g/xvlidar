#!/usr/bin/env python

'''
    xvlidar.py - Python class for reading from GetSurreal's XV Lidar Controller

    Adapted from lidar.py downloaded from 

      http://www.getsurreal.com/products/xv-lidar-controller/xv-lidar-controller-visual-test

    Copyright (C) 2015 Simon D. Levy
    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU Lesser General Public License as 
    published by the Free Software Foundation, either version 3 of the 
    License, or (at your option) any later version.
    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.
'''

COM_PORT = "/dev/ttyACM0"

import threading, time, serial, sys

class XVLidar(object):

    def __init__(self, port):

        self.ser = serial.Serial(port, 115200)
        self.thread = threading.Thread(target=self._read_lidar, args=())
        self.thread.daemon = True
        self.state = 0
        self.index = 0
        self.lidarData = [[] for i in range(360)] #A list of 360 elements Angle, Distance , quality
        self.speed_rpm = 0

    def start(self):

        self.thread.start()
     
    def _read_lidar(self):

        nb_errors = 0

        while True:

            try:

                time.sleep(0.001) # do not hog the processor power

                if self.state == 0 :
                    b = ord(self.ser.read(1))
                    # start byte
                    if b == 0xFA :
                        self.state = 1
                    else:
                        self.state = 0
                elif self.state == 1:
                    # position index
                    b = ord(self.ser.read(1))
                    if b >= 0xA0 and b <= 0xF9 :
                        self.index = b - 0xA0
                        self.state = 2
                    elif b != 0xFA:
                        self.state = 0
                elif self.state == 2 :
                    # speed
                    b_speed = [ ord(b) for b in self.ser.read(2)]
                    
                    # data
                    b_data0 = [ ord(b) for b in self.ser.read(4)]
                    b_data1 = [ ord(b) for b in self.ser.read(4)]
                    b_data2 = [ ord(b) for b in self.ser.read(4)]
                    b_data3 = [ ord(b) for b in self.ser.read(4)]

                    # for the checksum, we need all the data of the packet...
                    # this could be collected in a more elegent fashion...
                    all_data = [ 0xFA, self.index+0xA0 ] + b_speed + b_data0 + b_data1 + b_data2 + b_data3

                    # checksum
                    b_checksum = [ ord(b) for b in self.ser.read(2) ]
                    incoming_checksum = int(b_checksum[0]) + (int(b_checksum[1]) << 8)

                    # verify that the received checksum is equal to the one computed from the data
                    if self._checksum(all_data) == incoming_checksum:

                        self.speed_rpm = self._compute_speed(b_speed)
                        
                        self._update(self.index * 4 + 0, b_data0)
                        self._update(self.index * 4 + 1, b_data1)
                        self._update(self.index * 4 + 2, b_data2)
                        self._update(self.index * 4 + 3, b_data3)
                    else:
                        # the checksum does not match, something went wrong...
                        nb_errors +=1
                        
                        # display the samples in an error state
                        self._update(self.index * 4 + 0, [0, 0x80, 0, 0])
                        self._update(self.index * 4 + 1, [0, 0x80, 0, 0])
                        self._update(self.index * 4 + 2, [0, 0x80, 0, 0])
                        self._update(self.index * 4 + 3, [0, 0x80, 0, 0])
                        
                    self.state = 0 # reset and wait for the next packet
                    
                else: # default, should never happen...
                    self.state = 0
            except:
                print(sys.exc_info())
                exit(0)

    def _update(self, angle, data ):
        """Updates the view of a sample.
           Takes the angle (an int, from 0 to 359) and the list of four bytes of data in the order they arrived.
         """

        #unpack data using the denomination used during the discussions
        x = data[0]
        x1= data[1]
        x2= data[2]
        x3= data[3]
        
        dist_mm = x | (( x1 & 0x3f) << 8) # distance is coded on 13 bits ? 14 bits ?
        print(angle, dist_mm)
        quality = x2 | (x3 << 8) # quality is on 16 bits
        self.lidarData[angle] = [dist_mm,quality]

    def _checksum(self, data):
        """Compute and return the checksum as an int.
           data -- list of 20 bytes (as ints), in the order they arrived in.
        """
        # group the data by word, little-endian
        data_list = []
        for t in range(10):
            data_list.append( data[2*t] + (data[2*t+1]<<8) )
        
        # compute the checksum on 32 bits
        chk32 = 0
        for d in data_list:
            chk32 = (chk32 << 1) + d

        # return a value wrapped around on 15bits, and truncated to still fit into 15 bits
        checksum = (chk32 & 0x7FFF) + ( chk32 >> 15 ) # wrap around to fit into 15 bits
        checksum = checksum & 0x7FFF # truncate to 15 bits
        return int( checksum )


    def _compute_speed(self, data):

        speed_rpm = float( data[0] | (data[1] << 8) ) / 64.0
        return speed_rpm

if __name__ == '__main__':

    lidar = XVLidar(COM_PORT)
    lidar.start()

    while True:
        try:
            pass
        except KeyboardInterrupt:
            exit(0)

