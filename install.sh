#!/bin/bash
# installs scd30 co2 sensor daemon and start it

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

rsync -ravxbc scd30.py /usr/local/bin/ 
rsync -ravxbc scd30-service.sh /usr/local/bin/ 

rsync -ravxbc scd30.service /etc/systemd/system/

systemctl enable scd30
systemctl restart scd30
