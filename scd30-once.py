#!/usr/bin/env python
# coding=utf-8
#
# Copyright © 2018 UnravelTEC
# Michael Maier <michael.maier+github@unraveltec.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
#
# If you want to relicense this code under another license, please contact info+github@unraveltec.com.

# hints from https://www.raspberrypi.org/forums/viewtopic.php?p=600515#p600515

from __future__ import print_function

# This module uses the services of the C pigpio library. pigpio must be running on the Pi(s) whose GPIO are to be manipulated. 
# cmd ref: http://abyz.me.uk/rpi/pigpio/python.html#i2c_write_byte_data
import pigpio # aptitude install python-pigpio
import time
import struct
import sys
import crcmod # aptitude install python-crcmod


def eprint(*args, **kwargs):
  print(*args, file=sys.stderr, **kwargs)

PIGPIO_HOST = '::1'
PIGPIO_HOST = '127.0.0.1'

pi = pigpio.pi(PIGPIO_HOST)
if not pi.connected:
  eprint("no connection to pigpio daemon at " + PIGPIO_HOST + ".")
  exit(1)

I2C_SLAVE = 0x61
I2C_BUS = 1

try:
  pi.i2c_close(0)
except:
  if sys.exc_value and str(sys.exc_value) != "'unknown handle'":
    eprint("Unknown error: ", sys.exc_type, ":", sys.exc_value)

try:
	h = pi.i2c_open(I2C_BUS, I2C_SLAVE)
except:
	eprint("i2c open failed")
	exit(1)

# read meas interval (not documented, but works)

def read_n_bytes(n):

  try:
		(count, data) = pi.i2c_read_device(h, n)
  except:
    eprint("error: i2c_read failed")
    exit(1)

  if count == n:
    return data
  else:
    eprint("error: read measurement interval didnt return " + str(n) + "B")
    return False

def i2cWrite(data):
  try:
    pi.i2c_write_device(h, data)
  except:
    eprint("error: i2c_write failed")
    return -1
  return True


def read_meas_interval():
  ret = i2cWrite([0x46, 0x00])
  if ret == -1:
    return -1

  try:
    (count, data) = pi.i2c_read_device(h, 3)
  except:
    eprint("error: i2c_read failed")
    exit(1)

  if count == 3:
    if len(data) == 3:
      interval = int(data[0])*256 + int(data[1])
      #print "measurement interval: " + str(interval) + "s, checksum " + str(data[2])
      return interval
    else:
      eprint("error: no array len 3 returned, instead " + str(len(data)) + "type: " + str(type(data)))
  else:
    "error: read measurement interval didnt return 3B"
  
  return -1

read_meas_result = read_meas_interval()
if read_meas_result == -1:
  exit(1)

if read_meas_result != 2:
# if not every 2s, set it
  eprint("setting interval to 2")
  ret = i2cWrite([0x46, 0x00, 0x00, 0x02, 0xE3])
  if ret == -1:
    exit(1)
  read_meas_interval()


#trigger cont meas
# TODO read out current pressure value
pressure_mbar = 972
LSB = 0xFF & pressure_mbar
MSB = 0xFF & (pressure_mbar >> 8)
#print ("MSB: " + hex(MSB) + " LSB: " + hex(LSB))
#pressure_re = LSB + (MSB * 256)
#print("press " + str(pressure_re))
pressure = [MSB, LSB]

pressure_array = ''.join(chr(x) for x in [pressure[0], pressure[1]])
#pressure_array = ''.join(chr(x) for x in [0xBE, 0xEF]) # use for testing crc, should be 0x92
#print pressure_array

f_crc8 = crcmod.mkCrcFun(0x131, 0xFF, False, 0x00)

crc8 = f_crc8(pressure_array) # for pressure 0, should be 0x81
# print "CRC: " + hex(crc8)
i2cWrite([0x00, 0x10, pressure[0], pressure[1], crc8])

# read ready status
while True:
  ret = i2cWrite([0x02, 0x02])
  if ret == -1:
    exit(1)

  data = read_n_bytes(3)
  if data == False:
    time.sleep(0.1)
    continue

  if data[1] == 1:
    #print "data ready"
    break
  else:
    #eprint(".")
    time.sleep(0.1)

#read measurement
i2cWrite([0x03, 0x00])
data = read_n_bytes(18)
  
#print "CO2: "  + str(data[0]) +" "+ str(data[1]) +" "+ str(data[3]) +" "+ str(data[4])

if data == False:
  exit(1)
struct_co2 = struct.pack('>BBBB', data[0], data[1], data[3], data[4])
float_co2 = struct.unpack('>f', struct_co2)

struct_T = struct.pack('>BBBB', data[6], data[7], data[9], data[10])
float_T = struct.unpack('>f', struct_T)

struct_rH = struct.pack('>BBBB', data[12], data[13], data[15], data[16])
float_rH = struct.unpack('>f', struct_rH)

if float_co2 > 0.0:
  print("gas_ppm{sensor=\"SCD30\",gas=\"CO2\"} %f" % float_co2)

print("temperature_degC{sensor=\"SCD30\"} %f" % float_T)

if float_rH > 0.0:
  print("humidity_rel_percent{sensor=\"SCD30\"} %f" % float_rH)

pi.i2c_close(h)
