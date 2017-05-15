#!/usr/bin/env python3
# -*- coding: utf-8 -*-

#   This file is part of the unifiedsensor project.
#
#   Copyright (C) 2017 Robert Felten - https://github.com/rfelten/
#
#   This program is free software; you can redistribute it and/or modify
#   it under the terms of the GNU General Public License as published by
#   the Free Software Foundation; either version 3 of the License, or
#   (at your option) any later version.
#
#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU General Public License for more details.
#
#   You should have received a copy of the GNU General Public License
#   along with this program; if not, write to the Free Software Foundation,
#   Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301  USA

import sys
import time
import multiprocessing as mp
from unifiedsensor.unifiedsensor import UnifiedSensor

if __name__ == '__main__':
    wifi_interface = sys.argv[1]
    pulse_signatures = mp.Queue()
    unifiedsensor = UnifiedSensor(interface=wifi_interface, output_queue=pulse_signatures)
    unifiedsensor.start()
    time.sleep(10)
    unifiedsensor.stop()
    while True:
        try:
            pulse = pulse_signatures.get()
            print(pulse)
        except:
            break
