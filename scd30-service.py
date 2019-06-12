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
import math
import crcmod # aptitude install python-crcmod
import os, signal
from subprocess import call


def eprint(*args, **kwargs):
  print(*args, file=sys.stderr, **kwargs)
  sys.stderr.flush()

def flprint(*args, **kwargs):
  print(*args, **kwargs)
  sys.stdout.flush()

SENSOR_FOLDER = '/run/sensors/'
SENSOR_NAME = 'scd30'
LOGFILE = SENSOR_FOLDER + SENSOR_NAME + '/last'
PRESSURE_SENSORS = ['bme280', 'bme680']
MEAS_INTERVAL = 2 # integer between 1 and 255 (if longer needed, change code below)

PIGPIO_HOST = '127.0.0.1'
I2C_SLAVE = 0x61
I2C_BUS = 1

DEBUG = True
DEBUG = False

def exit_gracefully(a,b):
  flprint("exiting gracefully...")
  stop_measurement()
  flprint("measurement stopped")
  os.path.isfile(LOGFILE) and os.access(LOGFILE, os.W_OK) and os.remove(LOGFILE)
  flprint("sensor value files cleared")
  pi.i2c_close(h)
  flprint("i2c handle closed, exit 0")
  exit(0)

def exit_hard():
  flprint("exiting hard...")
  reset()
  flprint("resetted")
  os.path.isfile(LOGFILE) and os.access(LOGFILE, os.W_OK) and os.remove(LOGFILE)
  flprint("sensor value files cleared")
  pi.i2c_close(h)
  flprint("i2c handle closed, exit 1")
  exit(1)

signal.signal(signal.SIGINT, exit_gracefully)
signal.signal(signal.SIGTERM, exit_gracefully)


deviceOnI2C = call("i2cdetect -y 1 0x61 0x61|grep '\--' -q", shell=True) # grep exits 0 if match found
if deviceOnI2C:
  flprint("I2Cdetect found " + SENSOR_NAME)
else:
  flprint(SENSOR_NAME + " (0x61) not found on I2C bus")
  exit(1)

pi = pigpio.pi(PIGPIO_HOST)
if not pi.connected:
  flprint("no connection to pigpio daemon at " + PIGPIO_HOST + ".")
  exit(1)

try:
  pi.i2c_close(0)
except:
  if sys.exc_value and str(sys.exc_value) != "'unknown handle'":
    eprint("Unknown error: ", sys.exc_type, ":", sys.exc_value)

try:
  h = pi.i2c_open(I2C_BUS, I2C_SLAVE)
except:
  eprint("i2c open failed") and sys.stdout.flush()
  exit(1)

flprint("connected to pigpio daemon at " + PIGPIO_HOST + ".")

f_crc8 = crcmod.mkCrcFun(0x131, 0xFF, False, 0x00)
def calcCRC(TwoBdataArray):
  byteData = ''.join(chr(x) for x in TwoBdataArray)
  return f_crc8(byteData)

def calcFloat(sixBArray):
  struct_float = struct.pack('>BBBB', sixBArray[0], sixBArray[1], sixBArray[3], sixBArray[4])
  float_values = struct.unpack('>f', struct_float)
  first = float_values[0]
  return first

def read_n_bytes(n):
  try:
    (count, data) = pi.i2c_read_device(h, n)
  except:
    eprint("error: i2c_read failed")
    exit_hard()

  time.sleep(0.02)

  if count == n:
    DEBUG and flprint("read_n_bytes(" + str(n) + ") successful")
    if n % 3 == 0:
      DEBUG and flprint("multiple of 3 bytes read, calc checksum")
      for i in range(int(n / 3)):
        offset = i * 3
        sent_crc = data[offset + 2]
        calc_crc = calcCRC([data[offset + 0], data[offset + 1]])
        if sent_crc == calc_crc:
          DEBUG and flprint(str(i) + ": crc " + hex(sent_crc) + " of " + hex(data[offset + 0]) +" "+ hex(data[offset + 1]) + " OK")
        else:
          eprint(str(i) + ": crc " + hex(sent_crc) + " of " + hex(data[offset + 0]) +" "+ hex(data[offset + 1]) + " NOK, should be " + hex(calc_crc))
          return False
    return data
  else:
    eprint("error: read bytes didnt return " + str(n) + " B, but " + str(count) + " B")
    return False

# takes an array of bytes (integer-array)
def i2cWrite(data):
  try:
    pi.i2c_write_device(h, data)
  except:
    eprint("error: i2c_write failed")
    time.sleep(0.5)
    return -1
  time.sleep(0.02)
  return True

def read_firmware_version():
  ret = i2cWrite([0xD1,0x00])
  if ret == -1:
    eprint("error: sending 'read firmware' unsuccessful")
    return False
  if ret == True:
    firmware_version = read_n_bytes(3)
    if firmware_version != False:
      flprint("firmware version: " + hex(firmware_version[0]) + hex(firmware_version[1]))
      return True
  eprint("error: read firmware version unsuccessful")
  return False

def read_meas_interval():
  ret = i2cWrite([0x46, 0x00])
  if ret == -1:
    eprint("error: sending 'read measurement interval' unsuccessful")
    return -1
  ret = read_n_bytes(3)
  if ret != False:
    interval = ret[0] * 256 + ret[1]
    flprint("current measurement interval: " + str(interval))
    return interval
  eprint("error: read measurement interval unsuccessful")
  return -1

def read_asc_status():
  ret = i2cWrite([0x53,0x06])
  if ret == -1:
    eprint("error: sending 'read acs status' unsuccessful")
    return -1

  data = read_n_bytes(3)
  if data == False:
    flprint("read asc unsuccessful")
    return -1

  DEBUG and flprint("answer: " + hex(data[0]) + " " + hex(data[1]) + " " + hex(data[2]) + ".")

  if data[1] == 1:
    flprint("asc enabled")
    return 1

  if data[1] == 0:
    flprint("asc disabled")
    return 0

  flprint("asc status unknown, values returned: " + hex(data[0]) + " " + hex(data[1]) + " " + hex(data[2]) + ".")
  return -1

def stop_measurement():
  ret = i2cWrite([0x01, 0x04])
  if ret == -1:
    eprint("error: sending stop measurement command unsuccessful")

def reset():
  flprint("reset")
  ret = i2cWrite([0xD3,0x04])
  if ret == -1:
    flprint("reset unsuccessful")
    return
  time.sleep(0.5)

def set_forced_cal(ppm):
  LSB = 0xFF & ppm
  MSB = 0xFF & (ppm >> 8)
  ret = i2cWrite([0x52, 0x04, MSB, LSB, calcCRC([MSB,LSB])])
  if ret == -1:
    print("setting cal to "+str(ppm)+" unsuccessful")
    exit_hard()
  print("setting cal to "+str(ppm)+" successful")

def get_forced_cal():
  ret = i2cWrite([0x52, 0x04])
  if ret == -1:
    eprint("getting frc value unsuccessful")
    return
  ret = read_n_bytes(3)
  if ret != False:
    value = ret[0] * 256 + ret[1]
    flprint("current frc value: " + str(value))
    return
  eprint("error: read frc value unsuccessful")
  return

def get_temp_offset():
  ret = i2cWrite([0x54, 0x03])
  if ret == -1:
    eprint("getting temp offset value unsuccessful")
    return -1
  ret = read_n_bytes(3)
  if ret != False:
    value = (ret[0] * 256 + ret[1])
    flprint("current temp offset value: " + str(value))
    return value
  eprint("error: read temp offset value unsuccessful")
  return -1

def get_pressure(last_pressure):
  for sensor in PRESSURE_SENSORS:
    pressure_mbar = last_pressure
    pressure_filename = SENSOR_FOLDER + sensor + '/last'
    current_pressure = 0
    if os.path.isfile(pressure_filename):
      pressure_file = open(pressure_filename,'r')
      DEBUG and flprint("read from " + pressure_filename)
      for line in pressure_file:
        if line.startswith('pressure_hPa'):
          line_array = line.split()
          # print(line_array)
          if len(line_array) > 1:
            float_val = float(line_array[1])
            if(isinstance(float_val,float)):
              current_pressure = int(float_val)
              if current_pressure > 300:
                DEBUG and flprint("got pressure from " + pressure_filename)
                break
      if current_pressure > 300:
        if last_pressure != current_pressure:
          flprint('pressure compensation changed from', last_pressure, 'to', current_pressure)
          pressure_mbar = current_pressure
        break
  return pressure_mbar

def start_cont_measurement(pressure_mbar):
  LSB = 0xFF & pressure_mbar
  MSB = 0xFF & (pressure_mbar >> 8)
  ret = i2cWrite([0x00, 0x10, MSB, LSB, calcCRC([MSB,LSB])])
  if ret == -1:
    print("start_cont_measurement unsuccessful")
    exit_hard()
  print('started cont measurement with ' + str(pressure_mbar) + 'mbar')

read_firmware_version() or exit_hard()

read_meas_result = read_meas_interval()
if read_meas_result != MEAS_INTERVAL:
# if not every default, set it
  flprint("setting interval to " + str(MEAS_INTERVAL))
  ret = i2cWrite([0x46, 0x00, 0x00, MEAS_INTERVAL, calcCRC([0x00, MEAS_INTERVAL])])
  if ret == -1:
    exit_hard()
  read_meas_result = read_meas_interval()
  if read_meas_result != MEAS_INTERVAL:
    eprint("setting measurement interval unsuccessful, returned " + str(read_meas_result))
    exit_hard()

asc_status = read_asc_status()
if asc_status == 0:
  #activating ASC
  flprint("enabling asc...")
  i2cWrite([0x53, 0x06, 0x00, 0x01, calcCRC([0x00,0x01])])
  time.sleep(MEAS_INTERVAL+1)
  asc_status = read_asc_status()

get_forced_cal()

get_temp_offset()

call(["mkdir", "-p", SENSOR_FOLDER + SENSOR_NAME])

extra_log_interval = 120 #seconds
extra_log_count = extra_log_interval / MEAS_INTERVAL
extra_log_i = extra_log_count

pressure_mbar = 972 # 300 metres above sea level
last_pressure = pressure_mbar
start_cont_measurement(last_pressure)
log_once = True
while True:
  if extra_log_i == 0:
    get_forced_cal()
    get_temp_offset()
    extra_log_i = extra_log_count
    log_once = True
  extra_log_i -= 1

  new_pressure = get_pressure(last_pressure)
  if new_pressure != last_pressure:
    start_cont_measurement(new_pressure)
    last_pressure = new_pressure

  time.sleep(-0.1 + MEAS_INTERVAL)

  # read ready status
  deadmancounter = 20 * MEAS_INTERVAL
  attempts = deadmancounter
  while True:
    if deadmancounter == 0:
      flprint(str(attempts) + " attempts to get data unsuccessful, exiting")
      get_forced_cal()
      exit_hard()
    ret = i2cWrite([0x02, 0x02])
    if ret == -1:
      exit_hard()

    data = read_n_bytes(3)
    if data == False:
      flprint("read data ready unsuccessful")
      time.sleep(0.1)
      deadmancounter -= 1
      continue

    if data[1] == 1:
      #print "data ready"
      break
    else:
      #eprint(".")
      time.sleep(0.1)
      deadmancounter -= 1

  #read measurement
  i2cWrite([0x03, 0x00])
  data = read_n_bytes(18)

  if data == False:
    flprint("read data unsuccessful")
    log_once = True
    continue

  float_co2 = calcFloat(data[0:5])
  float_T = calcFloat(data[6:11])
  float_rH = calcFloat(data[12:17])

  if log_once:
    flprint("CO₂: " + str(float_co2) + ", rH: " + str(float_rH) + ", T: " + str(float_T))
    log_once = False

  if math.isnan(float_co2) or math.isnan(float_rH) or math.isnan(float_T) or float_co2 <= 0.0 or float_rH <= 0.0:
    flprint("read wrong, co2: " + str(float_co2) + ", rH: " + str(float_rH) + ", T: " + str(float_T))
    get_forced_cal()
    log_once = True
    continue

  output_string =  'gas_ppm{{sensor="SCD30",gas="CO2"}} {0:.8f}\n'.format( float_co2 )
  output_string += 'temperature_degC{{sensor="SCD30"}} {0:.8f}\n'.format( float_T )
  output_string += 'humidity_rel_percent{{sensor="SCD30"}} {0:.8f}\n'.format( float_rH )

  logfilehandle = open(LOGFILE, "w",1)
  logfilehandle.write(output_string)
  logfilehandle.close()

pi.i2c_close(h)
