# SCD30

Software to read out [Sensirion SCD30](https://www.sensirion.com/en/environmental-sensors/carbon-dioxide-sensors-co2/) CO2 Sensor values on Raspberry Pi.

This software is licenced under GPLv3 by [UnravelTEC OG](https://unraveltec.com) (https://unraveltec.com), 2018.

## Prerequsites 

### Python 

Install the following python-libraries:

```
aptitude install python-crcmod
```

### Pigpiod

As the SCD30 needs complex i2c-commands, the Linux standard i2c-dev doesn't work. A working alternative is pigpiod.

```
aptitude install pigpio python-pigpio
```

Atm, IPv6 doesn't work on Raspbian correctly with pigpiod, so:

```
sed -i "s|^ExecStart=.*|ExecStart=/usr/bin/pigpiod -l -n 127.0.0.1|" /lib/systemd/system/pigpiod.service
systemctl restart pigpiod
# Test (should return an int)
pigs hwver
```

### I2C Clock stretching

Master needs to support Clock Stretching up to 150ms. The default in Raspbian is too low, we have to increase it:

To set it, download from here:

```
https://github.com/raspihats/raspihats/tree/master/clk_stretch
```

Compile:
```
gcc -o i2c1_set_clkt_tout i2c1_set_clkt_tout.c
gcc -o i2c1_get_clkt_tout i2c1_get_clkt_tout.c
```

execute (add to /etc/rc.local to run on every boot):

```
./i2c1_set_clkt_tout 20000 for 200ms
```

Remember: Maximum I2C speed for SCD30 is 100kHz.

# Run program

```
python scd30.py
```

## installing as a service

```
cp scd30.py /usr/local/bin
cp scd30-service.sh /usr/local/bin
cp scd30.service /etc/systemd/system/
systemctl enable scd30.service
systemctl start scd30.service
```
the service writes a file /run/scd30 (which resides in RAM) - it is meant to be read out by prometheus.


## Todos

pressure value for pressure compensation is currently  done via a constant (972mbar ~ altitude of 300m)
