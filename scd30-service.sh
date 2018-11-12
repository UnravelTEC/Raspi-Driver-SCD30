#!/bin/zsh
# reads out scd30 co2 sensor periodically

buffer=/run/scd30
bin=/usr/local/bin/scd30.py

i2c_clk_tm_getter=/usr/local/bin/i2c1_get_clkt_tout
i2c_clk_tm_setter=/usr/local/bin/i2c1_set_clkt_tout

function finish {
  rm -rf ${buffer}
}

trap finish EXIT

touch ${buffer}
chown www-data ${buffer}

if [ "$($i2c_clk_tm_getter)" != "i2c1_get_clkt_tout: CLKT.TOUT = 20000" ]; then
  echo "setting i2c clock stretch timeout to 200ms"
  $i2c_clk_tm_setter 20000
fi

while true; do
  
  buffercontent=""
  buffercontent=$($bin)
  sleep 2

  echo "$buffercontent" > ${buffer}

done
