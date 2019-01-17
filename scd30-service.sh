#!/bin/bash
# reads out scd30 co2 sensor periodically

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

datadir=/run/sensors/scd30
buffer=$datadir/last

bin=/usr/local/bin/scd30.py

i2c_clk_tm_getter=/usr/local/bin/i2c1_get_clkt_tout
i2c_clk_tm_setter=/usr/local/bin/i2c1_set_clkt_tout

function finish {
  rm -rf ${buffer}
}

trap finish EXIT

result=$(i2cset -y 1 0x61 0x02 0x02)
if [[ "$?" == "1" ]]; then
  echo "error: Sensor not found on i2c bus, exiting"
  exit 1
fi


mkdir -p $datadir

if [ "$($i2c_clk_tm_getter)" != "i2c1_get_clkt_tout: CLKT.TOUT = 20000" ]; then
  echo "setting i2c clock stretch timeout to 200ms"
  $i2c_clk_tm_setter 20000
fi

errorcounter=0

while true; do
  
  buffercontent=""
  buffercontent=$($bin)
  if [[ "$?" == "1" ]]; then
    let errorcounter=errorcounter+1
    echo "readout of sensorval failed"
  else
    errorcounter=0
  fi

  if [[ "$errorcounter" = "3" ]]; then
    echo "read value 3 times failed, sleep 1m"
    errorcounter=0
    sleep 60
  fi

  if [[ "$buffercontent" ]]; then
    echo "$buffercontent" > ${buffer}
  else
    rm -rf ${buffer}
  fi

  sleep 2

done
