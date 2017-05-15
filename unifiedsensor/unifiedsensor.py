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
import logging
import multiprocessing as mp
from yanh.airtime import AirtimeCalculator
from athspectralscan import AthSpectralScanner, AthSpectralScanDecoder, DataHub
from .feature_extraction import PulseExtractorProcess
logger = logging.getLogger(__name__)


class UnifiedSensor(object):

    def __init__(self, interface, output_queue):
        self.athss_queue = mp.Queue()
        self.airtime_queue = mp.Queue()
        self.output_queue = output_queue
        self.scanner = AthSpectralScanner(interface=interface)
        self.scanner.set_spectral_short_repeat(0)
        self.scanner.set_mode("background")
        self.scanner.set_channel(1)
        self.airtimecalc = AirtimeCalculator(monitor_interface=sys.argv[1], output_queue=self.airtime_queue)
        self.decoder = AthSpectralScanDecoder()
        self.decoder.set_number_of_processes(1)
        self.decoder.set_output_queue(self.athss_queue)
        self.hub = DataHub(scanner=self.scanner, decoder=self.decoder)
        self.pulse_extractor_process = mp.Process(
            target=PulseExtractorProcess.run_pulse_extractor,
            args=(self.athss_queue, self.airtime_queue, self.output_queue,)
        )

    def start(self):
        self.decoder.start()
        self.hub.start()
        self.airtimecalc.start()
        self.scanner.start()
        # start read+process process
        #self.pulse_extractor_process.start()
        #logger.info("started pulse extractor process with PID=%d" % self.pulse_extractor_process.pid)

    def stop(self):
        self.scanner.stop()
        self.airtimecalc.stop()
        self.decoder.stop()
        self.hub.stop()
        #self.pulse_extractor_process.terminate()

