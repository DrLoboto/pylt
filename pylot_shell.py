#!/usr/bin/env python
#
#    License: GNU GPLv3
#
#    This file is part of Pylot.
#    
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.  See the GNU General Public License 
#    for more details.
#


import sys
import time
import xmlparse
from threading import Thread
from pylot_engine import LoadManager



# flag is set if the script is run on windows
is_windows = sys.platform.startswith('win')

class ProgressBar:
    def __init__(self, duration, min_value=0, max_value=100, total_width=40):
        self.prog_bar = '[]'  # holds the progress bar string
        self.duration = duration
        self.min = min_value
        self.max = max_value
        self.span = max_value - min_value
        self.width = total_width
        self.amount = 0  # when amount == max, we are 100% done
        self.update_amount(0)  # build progress bar string
    
    
    def update_amount(self, new_amount=0):
        if new_amount < self.min: new_amount = self.min
        if new_amount > self.max: new_amount = self.max
        self.amount = new_amount
        
        # figure out the new percent done, round to an integer
        diff_from_min = float(self.amount - self.min)
        percent_done = (diff_from_min / float(self.span)) * 100.0
        percent_done = round(percent_done)
        percent_done = int(percent_done)
        
        # figure out how many hash bars the percentage should be
        all_full = self.width - 2
        num_hashes = (percent_done / 100.0) * all_full
        num_hashes = int(round(num_hashes))
        
        # build a progress bar with hashes and spaces
        self.prog_bar = '[' + '#' * num_hashes + ' ' * (all_full - num_hashes) + ']'
        
        # figure out where to put the percentage, roughly centered
        percent_place = (len(self.prog_bar) / 2) - len(str(percent_done))
        percent_string = str(percent_done) + '%'

        # slice the percentage into the bar
        self.prog_bar = self.prog_bar[0:percent_place] + (percent_string + self.prog_bar[percent_place + len(percent_string):])
                    
    
    def update_line(self, time_running, agg_count, agg_avg, agg_error_count, avg_throughput, cur_throughput):
        self.time_running = time.time()
        self.update_amount((time_running / self.duration) * 100)
        self.prog_bar += '  %ds/%ss   Reqs: %d  AvgResp: %.3f  Errs: %d  AvgTp: %.2f  CurTp: %d' % (
            time_running, self.duration, agg_count, agg_avg, agg_error_count, avg_throughput, cur_throughput)
        # this is for the Windows cmd prompt    
        if is_windows:      
            sys.stdout.write(chr(0x08) * len(self.prog_bar) + self.prog_bar)
        # on POSIX terminals we need to work with ascii control sequences
        else:  
            sys.stdout.write(chr(27) + '[G')
            sys.stdout.write(self.prog_bar)
            sys.stdout.flush()
        
        
    def __str__(self):
        return str(self.prog_bar)



def start(num_agents, rampup, interval, duration, log_resps):
    runtime_stats = {}
    error_queue = []
    interval = interval / 1000.0  # convert from millisecs to secs
    
    # create a load manager
    lm = LoadManager(num_agents, interval, rampup, log_resps, runtime_stats, error_queue)
    
    # load the test cases
    try:
        cases = xmlparse.load_xml_cases()
        for req in cases:
            lm.add_req(req)
    except:  # if there was a problem getting cases from the xml file
        sys.stderr.write('Error opening testcase file.\n')
        sys.exit(1)
    
    start_time = time.time()
    
    # start the load manager
    lm.setDaemon(True)
    lm.start()
    
    pb = ProgressBar(duration)
    last_count = 0 
    while (time.time() < start_time + duration):         
        
        refresh_rate = 1.0
        time.sleep(refresh_rate)
        
        # when all agents are started start displaying the progress bar and stats
        if lm.agents_started:
            elapsed_secs = time.time() - start_time
            ids = runtime_stats.keys()
            agg_count = sum([runtime_stats[id].count for id in ids])  # total req count
            agg_total_latency = sum([runtime_stats[id].total_latency for id in ids])
            agg_error_count = sum([runtime_stats[id].error_count for id in ids])
            if agg_count > 0 and elapsed_secs > 0:
                agg_avg = agg_total_latency / agg_count  # total avg response time
                avg_throughput = float(agg_count) / elapsed_secs  # avg throughput since start
            
                interval_count = agg_count - last_count  # requests since last refresh
                cur_throughput = float(interval_count) / refresh_rate  # throughput since last refresh
                last_count = agg_count  # reset for next time
                pb.update_line(elapsed_secs, agg_count, agg_avg, agg_error_count, avg_throughput, cur_throughput)       
    sys.stdout.write('\n')
    lm.stop()
    print 'Generating results...'
    # wait until the result generator is finished
    while lm.results_gen.isAlive():
        time.sleep(.05)
    print 'Done.'
    
