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

import time
import logging
import array
import copy
from queue import Empty
from collections import deque
from math import floor, log10

logger = logging.getLogger(__name__)


class PulseExtractor(object):

    def __init__(self):
        self.active_peaks_center = []

    @staticmethod
    def calc_peak_signature(peak, nf):
        # peak: [(freq, value), ...]:
        nf = abs(nf)
        signature = dict()
        signature['bandwidth'] = len(peak) * 0.3125  # IEEE802.11 subcarrier freq in MHz
        signature['peak_value'] = max([value for (_, value) in peak])
        power = PulseExtractor.sum_log10([value for (_, value) in peak])
        #print power, [value for (_, value) in peak]
        mass = sum([value for (_, value) in peak])
        if mass == 0:
            logger.error("Power (Mass) of zero detected. Please check your data!")
            center_of_mass = peak[0][0]  # 1st freq of peak
        else:
            center_of_mass = sum([freq*value for (freq, value) in peak]) / mass
        signature['center'] = center_of_mass
        signature['power'] = power
        return signature

    @staticmethod
    def _pulse_stats_new(start_time, peak_signature):
        return dict(
            start_time=start_time, duration=0,
            center=peak_signature['center'], bandwidth=peak_signature['bandwidth'],
            peak_power=peak_signature['peak_value'], power=peak_signature['power']
        )

    @staticmethod
    def _pulse_stats_update(pulse_stats, peak_signature, timestamp):
        pulse_stats['duration'] = timestamp - pulse_stats['start_time']
        pulse_stats['center'] = 0.9 * peak_signature['center'] + 0.1 * pulse_stats['center']  # alpha for EWMA should be uncritical
        if peak_signature['bandwidth'] > pulse_stats['bandwidth']:
            pulse_stats['bandwidth'] = peak_signature['bandwidth']
        if peak_signature['peak_value'] > pulse_stats['peak_power']:
            pulse_stats['peak_power'] = peak_signature['peak_value']
        pulse_stats['power'] = PulseExtractor.sum_log10([pulse_stats['power'], peak_signature['power']])
        return pulse_stats

    @staticmethod
    def extract_pulses_from_sample_row(pwr, noise_threshold):
        pulses = []
        # convert pwr-dict to sortable array and add numeric index
        #pwr_samples = sorted([(k, v) for k, v in pwr.iteritems()])
        pwr_samples = sorted([(k, v) for k, v in pwr.items()])
        # [(2413.09375, -108.65116457474159), (2413.40625, -131.64238880507423), ...
        pwr_samples = [(i, val) for i, val in enumerate(pwr_samples)]
        # sort samples via power: [ (1, (2403.40625, -112.37572698782097)), ...
        samples_sorted = sorted(pwr_samples, key=lambda x:x[1][1])  # largest power value at the end
        # [(0, (2413.09375, -108.65116457474159)), ... (index, (freq, value)), ...
        while len(samples_sorted) > 0:
            pulse = []
            (index, (freq, value)) = samples_sorted.pop()  # get last (=larges) value
            if value < noise_threshold:
                break  # only noise samples left
            pulse.append((freq, value))
            # go left downwards
            i = index
            while True:
                i -= 1
                if i <= 0:
                    break  # lower end of sample row
                (_, (freq_neighbor, value_neighbor)) = pwr_samples[i]  # use the unsorted order here
                if value_neighbor < noise_threshold:
                    break  # left end of peak hit
                #store result
                pulse.append((freq_neighbor, value_neighbor))
                # remove processed elements from sorted list
                for i_remove, (i_tmp, _) in enumerate(samples_sorted):
                    if i_tmp == i:
                        del samples_sorted[i_remove]
                        break
            # go right downwards
            i = index
            while True:
                i += 1
                if i >= len(pwr_samples):
                    break  # lower end of sample row
                (_, (freq_neighbor, value_neighbor)) = pwr_samples[i]  # use the unsorted order here
                if value_neighbor < noise_threshold:
                    break  # left end of peak hit
                # store result
                pulse.append((freq_neighbor, value_neighbor))
                # remove processed elements from sorted list
                for i_remove, (i_tmp, _) in enumerate(samples_sorted):
                    if i_tmp == i:
                        del samples_sorted[i_remove]
                        break

            pulses.append(pulse)
        return pulses

    @staticmethod
    def create_pulse_from_airtime(data, nf):
        # FIXME: differentiate between bad and sane frames !
        #(tsf, airtime, pwr, freq, is_fcs_bad) = data
        tsf, airtime, pwr, freq, is_fcs_bad, _, _ = data
        bw = 20  # FIXME
        power = pwr * bw * airtime
        pulse_stats = dict(
            start_time=tsf, duration=airtime,
            center=freq, bandwidth=bw,
            peak_power=pwr, power=power
        )
        return pulse_stats

    def detect_pulses(self, peaks_over_freq, timestamp, FREQ_JITTER_THRESHOLD, NOISE_FLOOR):
        active_peaks_center_updated = []
        for peak in peaks_over_freq:
            sig = PulseExtractor.calc_peak_signature(peak, NOISE_FLOOR)
            # test if peak is still active
            peak_already_classified = False
            for i, (apc, pulse_stats) in enumerate(self.active_peaks_center):
                if (sig['center'] > apc - FREQ_JITTER_THRESHOLD) and \
                   (sig['center'] < apc + FREQ_JITTER_THRESHOLD):
                    # FIXME: maybe also match bandwidth here?
                    #print "still active: ", apc, sig
                    pulse_stats = PulseExtractor._pulse_stats_update(pulse_stats, sig, timestamp)
                    active_peaks_center_updated.append((pulse_stats['center'], pulse_stats))
                    del self.active_peaks_center[i]
                    peak_already_classified = True

            # peak is new
            if not peak_already_classified:
                #print "new active:", sig
                pulse_stats = PulseExtractor._pulse_stats_new(peak_signature=sig, start_time=timestamp)
                active_peaks_center_updated.append((pulse_stats['center'], pulse_stats))

        peaks_finished = list(self.active_peaks_center)
        # update list of active peaks
        self.active_peaks_center = active_peaks_center_updated
        return peaks_finished

    @staticmethod
    def sum_log10(log_values):
        sum = 0
        for v in log_values:
            sum += 10 ** (v / 10)
        if sum == 0:
            return 0
        else:
            return 10 * log10(sum)


class PulseExtractorProcess(object):

    @staticmethod
    def run_pulse_extractor(input_queue_ath, input_queue_pcap, output_queue=None, snr=10):
        pe = PulseExtractor()
        # nf_detector_hist = HistogramBasedNoiseFloorDetector()
        nf_detector_avg = AvgBasedNoiseFloorDetector()
        signal_floor_h = float('-inf')
        # signal_floor_a = float('-inf')
        while True:
            empty_queues = 0
            try:
                # print "input queue size: ", input_queue.qsize()  # FIXME: add overflow checks to all queues
                (ts, (tsf, freq, noise, rssi, pwr)) = input_queue_ath.get(block=False)
                # update noise floor
                # nf_detector_hist.update_noise_floor(pwr)
                #signal_floor = nf_detector_hist.get_noise_floor() + snr  # signal needs to be SNR above noise
                signal_floor = nf_detector_avg.get_noise_floor() + snr  # signal needs to be SNR above noise
                #print "%.2f,%d,%d,%d" % (PulseExtractorProcess.avg_pwr(pwr), signal_floor_h, signal_floor_a, signal_floor_h-signal_floor_a)

                # extract pulses
                pulses = PulseExtractor.extract_pulses_from_sample_row(pwr, signal_floor)
                if len(pulses) > 0:
                    pulses = pe.detect_pulses(
                            peaks_over_freq=pulses, timestamp=tsf,
                            FREQ_JITTER_THRESHOLD=0.05, NOISE_FLOOR=signal_floor)
                    for _, p in pulses:
                        #if p['bandwidth'] > 0.3125 and p['duration'] > 0:
                        #   print p
                        if output_queue is not None:
                            output_queue.put(p)
            except Empty:  # input queue was empty
                empty_queues += 1

            data_from_pcap = None
            try:
                data_from_pcap = input_queue_pcap.get(block=False)
            except Empty:
                empty_queues += 1

            if data_from_pcap is not None:
                # FIXME: stop ongoing pulses here
                puls = PulseExtractor.create_pulse_from_airtime(data_from_pcap, signal_floor_h)
                # print puls
                if output_queue is not None:
                    output_queue.append(puls)
            # only sleep is both input queues are empty
            if empty_queues == 2:
                try:
                    time.sleep(0.1)
                except KeyboardInterrupt:  # user stops program
                    break

    @staticmethod
    def avg_pwr(pwr_dict):
            avg_noise = 0
            for freq, value in pwr_dict.iteritems():
                avg_noise += value
            avg_noise /= len(pwr_dict)
            return avg_noise


class HistogramBasedNoiseFloorDetector(object):

    def __init__(self, WINDOW_SIZE=10*1000, POWER_MIN_dBm=-200, POWER_MAX_dBm=20, UPDATE_CYCLE=200, calc_signal_histo=False):

        self.dbm_max = POWER_MAX_dBm
        self.dbm_min = POWER_MIN_dBm
        self.update_cycle = UPDATE_CYCLE
        self.update_cycle_cnt = 0
        self.calc_signal_histo = calc_signal_histo
        # initialize histogram, bin size = 1dBm
        # histogram array is indexed from 0 and have the size max-min#
        self.histo_size = float(self.dbm_max-self.dbm_min)
        self.noise_histogram = array.array('i')
        self.signal_histogram = array.array('i')
        for i in range(0, int(self.histo_size)):
            self.noise_histogram.append(0)
            self.signal_histogram.append(0)
        self.samples_window = deque()
        # initialize samples window with default noise floor
        for i in range(0, WINDOW_SIZE):
            self.samples_window.append(-95)
        assert (self.dbm_min < -95)
        self.noise_histogram[-95 + abs(self.dbm_min)] = WINDOW_SIZE  # at start, histogram contains WINDOW_SIZE times the default noise floor
        self.noise_floor = -95

    def get_noise_floor(self):
        return self.noise_floor

    def update_noise_floor(self, pwr_dict):
        # this should lower the cpu amount...
        self.update_cycle_cnt -= 1
        if self.update_cycle_cnt > 0:
            return
        self.update_cycle_cnt = self.update_cycle
        for freq, value in pwr_dict.iteritems():
            value_new = int(floor(value))
            # check limits, otherwise histogram array access will fail
            if value_new < self.dbm_min or value_new > self.dbm_max:
                logging.error("Power value of %.2f dBm is outside the limits (%d dBm - %d dBm)" % (value, self.dbm_min, self.dbm_max))
                continue
            else:
                # update histogram: keep track of values to remove them later from window
                self.samples_window.append(value_new)
                self.noise_histogram[value_new + abs(self.dbm_min)] += 1
                value_old = self.samples_window.popleft()
                self.noise_histogram[value_old + abs(self.dbm_min)] -= 1
        # update noise floor (once per sample row, = bad idea?)
        self.noise_floor = self.noise_histogram.index(max(self.noise_histogram)) - abs(self.dbm_min)

        if not self.calc_signal_histo:
            return  # signal_histogram not used yet

        # update the signal histogram: use left part of the nf bell to extract signal levels
        self.signal_histogram = copy.deepcopy(self.noise_histogram)
        idx_offset = 0
        while True:
            idx_offset += 1
            idx_right = abs(self.dbm_min) + self.noise_floor + idx_offset
            idx_left = abs(self.dbm_min) + self.noise_floor - idx_offset
            if idx_left < 0 or idx_right > self.histo_size:
                break
            left_bin = self.noise_histogram[idx_left]
            self.signal_histogram[idx_left] = 0  # below nf, everythin is noise
            self.signal_histogram[idx_right] -= left_bin  # substract left part of the bell from right part

        self.signal_histogram[abs(self.dbm_min) + self.noise_floor] = 0  # per definiton, the nf contains zero signal information
        # print "nf:", self.noise_histogram  # debug (to compare with signal_histogram)
        # print "s :", self.signal_histogram  # the residual levels contain only signal


class AvgBasedNoiseFloorDetector(object):

    def __init__(self, avg_alpha=0.125):
        self.noise_floor = -95
        self.avg_alpha = avg_alpha
        self.one_minus_avg_alpha = 1 - avg_alpha  # calculate once (nstead of once per sample)

    def get_noise_floor(self):
        return int(floor(self.noise_floor))

    def update_noise_floor(self, pwr_dict):
            new_noise = 0
            for freq, value in pwr_dict.iteritems():
                new_noise += value
            new_noise /= len(pwr_dict)
            self.noise_floor = self.avg_alpha * new_noise + self.one_minus_avg_alpha * self.noise_floor
