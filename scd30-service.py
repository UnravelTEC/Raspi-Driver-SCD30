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
import os, signal
from subprocess import call


def eprint(*args, **kwargs):
  print(*args, file=sys.stderr, **kwargs)

SENSOR_FOLDER = '/run/sensors/'
SENSOR_NAME = 'scd30'
LOGFILE = SENSOR_FOLDER + SENSOR_NAME + '/last'
PRESSURE_SENSORS = ['bme280', 'bme680']

PIGPIO_HOST = '127.0.0.1'
I2C_SLAVE = 0x61
I2C_BUS = 1

def exit_gracefully(a,b):
  print("exit")
  os.path.isfile(LOGFILE) and os.access(LOGFILE, os.W_OK) and os.remove(LOGFILE)
  pi.i2c_close(h)
  exit(0)

signal.signal(signal.SIGINT, exit_gracefully)
signal.signal(signal.SIGTERM, exit_gracefully)


deviceOnI2C = call("i2cdetect -y 1 0x61 0x61|grep '\--' -q", shell=True) # grep exits 0 if match found
if deviceOnI2C:
  print("I2Cdetect found " + SENSOR_NAME)
else:
  print(SENSOR_NAME + " (0x61) not found on I2C bus")
  exit(1)

pi = pigpio.pi(PIGPIO_HOST)
if not pi.connected:
  print("no connection to pigpio daemon at " + PIGPIO_HOST + ".")
  exit(1)

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

call(["mkdir", "-p", SENSOR_FOLDER + SENSOR_NAME])

f_crc8 = crcmod.mkCrcFun(0x131, 0xFF, False, 0x00)
def calcCRC(TwoBdataArray):
  byteData = ''.join(chr(x) for x in TwoBdataArray)
  return f_crc8(byteData)

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

# takes an array of bytes (integer-array)
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
    eprint("error: read measurement interval didnt return 3B")
  
  return -1

read_meas_result = read_meas_interval()
if read_meas_result == -1:
  eprint("read_meas_interval unsuccessful")
  exit(1)

if read_meas_result != 1:
# if not every 1s, set it
  print("setting interval to 1")
  ret = i2cWrite([0x46, 0x00, 0x00, 0x01, calcCRC([0x00, 0x01])])
  if ret == -1:
    exit(1)
  read_meas_interval()


def calcFloat(sixBArray):
  struct_float = struct.pack('>BBBB', sixBArray[0], sixBArray[1], sixBArray[3], sixBArray[4])
  float_values = struct.unpack('>f', struct_float)
  first = float_values[0]
  return first

pressure_mbar = 972 # 300 metres above sea level
while True:
  for sensor in PRESSURE_SENSORS: 
    pressure_filename = SENSOR_FOLDER + sensor + '/last'
    current_pressure = 0
    if os.path.isfile(pressure_filename):
      pressure_file = open(pressure_filename,'r')
      for line in pressure_file:
        if line.startswith('pressure_hPa'):
          line_array = line.split()
          if len(line_array) > 1:
            current_pressure = int(float(line_array[1]))
            if current_pressure > 300:
              break
      if current_pressure > 300:
        if pressure_mbar != current_pressure:
          print('pressure compensation changed from', pressure_mbar,'to', current_pressure)
          pressure_mbar = current_pressure
        break

  LSB = 0xFF & pressure_mbar
  MSB = 0xFF & (pressure_mbar >> 8)

  i2cWrite([0x00, 0x10, MSB, LSB, calcCRC([MSB,LSB])])

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

  float_co2 = calcFloat(data[0:5])
  float_T = calcFloat(data[6:11])
  float_rH = calcFloat(data[12:17])

  if float_co2 <= 0.0 or float_rH <= 0.0:
    continue

  output_string =  'gas_ppm{{sensor="SCD30",gas="CO2"}} {0:.8f}\n'.format( float_co2 )
  output_string += 'temperature_degC{{sensor="SCD30"}} {0:.8f}\n'.format( float_T )
  output_string += 'humidity_rel_percent{{sensor="SCD30"}} {0:.8f}\n'.format( float_rH )

  logfilehandle = open(LOGFILE, "w",1)
  logfilehandle.write(output_string)
  logfilehandle.close()

  time.sleep(0.9)

pi.i2c_close(h)
