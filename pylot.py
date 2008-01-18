#!/usr/bin/env python
#
#    Copyright (c) 2007-2008 Corey Goldberg (corey@goldb.org)
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


version = '.02_beta'


import time
import sys
import wx
from wx.lib.mixins.listctrl import ListCtrlAutoWidthMixin
from threading import Thread
import xml.etree.ElementTree as etree
from pylot_engine import *
import results
    
    
    
class Application(wx.Frame):
    def __init__(self, parent):
        wx.Frame.__init__(self, parent, -1, 'Pylot - Web Performance  |  Version ' + version, size=(680, 710))
    
        self.runtime_stats = {}  # shared runtime stats dictionary
        self.error_queue = []  # shared error list
        
        self.SetIcon(wx.Icon('ui/icon.ico', wx.BITMAP_TYPE_ICO))  # set window icon
        self.CreateStatusBar()  # enable bottom status bar
        
        # menus
        file_menu = wx.Menu()
        file_menu.Append(101, '&About', 'About Pylot')
        wx.EVT_MENU(self, 101, self.on_about)
        file_menu.Append(102, '&Exit', 'Exit Pylot')
        wx.EVT_MENU(self, 102, self.on_exit)
        tools_menu = wx.Menu()
        tools_menu.Append(103, '&Regenerate Results', 'Regenerate Results')
        wx.EVT_MENU(self, 103, self.on_results)
        menuBar = wx.MenuBar()
        menuBar.Append(file_menu, '&File')
        menuBar.Append(tools_menu, '&Tools')
        self.SetMenuBar(menuBar)

        # main panel
        panel = wx.Panel(self)
        
        # workload controls
        self.num_agents_spin = wx.SpinCtrl(panel, -1, size=(75, -1))
        self.num_agents_spin.SetRange(1, 1000000)
        self.num_agents_spin.SetValue(1)
        self.interval_spin = wx.SpinCtrl(panel, -1, size=(75, -1))
        self.interval_spin.SetRange(0, 1000000)
        self.interval_spin.SetValue(1000)
        self.rampup_spin = wx.SpinCtrl(panel, -1, size=(75, -1))
        self.rampup_spin.SetRange(0, 1000000)
        self.rampup_spin.SetValue(0)
        self.duration_spin = wx.SpinCtrl(panel, -1, size=(75, -1))
        self.duration_spin.SetRange(1, 1000000)
        self.duration_spin.SetValue(60)
        controls_sizer = wx.GridSizer(0, 4, 0, 0)
        controls_sizer.Add(wx.StaticText(panel, -1, 'Agents (count)'), 0, wx.TOP|wx.LEFT, 8)
        controls_sizer.Add(self.num_agents_spin, 0, wx.ALL, 2)
        controls_sizer.Add(wx.StaticText(panel, -1, 'Interval (ms)'), 0, wx.TOP|wx.LEFT, 8)
        controls_sizer.Add(self.interval_spin, 0, wx.ALL, 2)
        controls_sizer.Add(wx.StaticText(panel, -1, 'Rampup (s)'), 0, wx.TOP|wx.LEFT, 8)
        controls_sizer.Add(self.rampup_spin, 0, wx.ALL, 2)
        controls_sizer.Add(wx.StaticText(panel, -1, 'Duration (s)'), 0, wx.TOP|wx.LEFT, 8)
        controls_sizer.Add(self.duration_spin, 0, wx.ALL, 2)
        
        # run controls
        self.run_btn = wx.Button(panel, -1, 'Run')
        self.stop_btn = wx.Button(panel, -1, 'Stop')
        self.busy_gauge = wx.Gauge(panel, -1, 0, size=(60, 12))
        self.busy_timer = wx.Timer(self)  # timer for gauge pulsing
        runcontrols_sizer = wx.BoxSizer(wx.HORIZONTAL)
        runcontrols_sizer.Add(self.run_btn, 0, wx.ALL, 3)
        runcontrols_sizer.Add(self.stop_btn, 0, wx.ALL, 3)
        runcontrols_sizer.Add(controls_sizer, 0, wx.LEFT, 55)
        runcontrols_sizer.Add(self.busy_gauge, 0, wx.LEFT, 60)
        
        # run options
        runopts_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.logresp_checkbox = wx.CheckBox(panel, -1, 'Log Responses')
        runopts_sizer.Add(self.logresp_checkbox, wx.LEFT, 0)
        
        # monitor
        summary_monitor_text = wx.StaticText(panel, -1, 'Summary')
        summary_monitor_text.SetFont(wx.Font(8, wx.DEFAULT, wx.NORMAL, wx.NORMAL))
        self.total_statlist = AutoWidthListCtrl(panel, height=45)
        self.total_statlist.InsertColumn(0, 'Run Time', width=85)
        self.total_statlist.InsertColumn(1, 'Agents', width=80)
        self.total_statlist.InsertColumn(2, 'Requests', width=75)
        self.total_statlist.InsertColumn(3, 'Errors', width=75)
        self.total_statlist.InsertColumn(4, 'Avg Resp Time', width=95)
        self.total_statlist.InsertColumn(5, 'Avg Throughput', width=95)
        self.total_statlist.InsertColumn(6, 'Cur Throughput', width=95) 
        agent_monitor_text = wx.StaticText(panel, -1, 'Agent Monitor')
        agent_monitor_text.SetFont(wx.Font(8, wx.DEFAULT, wx.NORMAL, wx.NORMAL))
        
        self.agents_statlist = AutoWidthListCtrl(panel, height=300)
        self.agents_statlist.InsertColumn(0, 'Agent Num', width=80)
        self.agents_statlist.InsertColumn(1, 'Status', width=100)
        self.agents_statlist.InsertColumn(2, 'Requests', width=100)
        self.agents_statlist.InsertColumn(3, 'Last Resp Time', width=100)
        self.agents_statlist.InsertColumn(4, 'Avg Resp Time', width=100)
        self.agents_statlist.InsertColumn(5, 'Bytes Received', width=100)
        self.agents_statlist.resizeLastColumn(90)
                
        error_text = wx.StaticText(panel, -1, 'Errors')
        error_text.SetFont(wx.Font(8, wx.DEFAULT, wx.NORMAL, wx.NORMAL))
        self.error_list = wx.TextCtrl(panel, -1, style=wx.TE_MULTILINE, size=(0, 100))
        self.error_list.SetOwnForegroundColour(wx.RED)
        self.pause_btn = wx.Button(panel, -1, 'Pause Monitoring')
        self.resume_btn = wx.Button(panel, -1, 'Resume Monitoring')
        pause_resume_sizer = wx.BoxSizer(wx.HORIZONTAL)
        pause_resume_sizer.Add(self.pause_btn, 0, wx.ALL, 3)
        pause_resume_sizer.Add(self.resume_btn, 0, wx.ALL, 3)
        monitor_sizer = wx.BoxSizer(wx.VERTICAL)
        monitor_sizer.Add(summary_monitor_text, 0, wx.ALL, 3)
        monitor_sizer.Add(self.total_statlist, 0, wx.EXPAND, 0)
        monitor_sizer.Add(agent_monitor_text, 0, wx.ALL, 3)
        monitor_sizer.Add(self.agents_statlist, 0, wx.EXPAND, 0)
        monitor_sizer.Add(error_text, 0, wx.ALL, 3)
        monitor_sizer.Add(self.error_list, 0, wx.EXPAND, 0)
        monitor_sizer.Add(pause_resume_sizer, 0, wx.ALL, 3)
        
        # main layout
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(runcontrols_sizer, 0, wx.ALL, 3)
        sizer.Add(runopts_sizer, 0, wx.LEFT, 465)
        sizer.Add(monitor_sizer, 0, wx.LEFT, 33)
        
        # bind the events to handlers
        self.Bind(wx.EVT_BUTTON, self.on_run, self.run_btn)
        self.Bind(wx.EVT_BUTTON, self.on_stop, self.stop_btn)
        self.Bind(wx.EVT_BUTTON, self.on_pause, self.pause_btn)
        self.Bind(wx.EVT_BUTTON, self.on_resume, self.resume_btn)
        self.Bind(wx.EVT_TIMER, self.timer_handler)
                
        self.switch_status(False)
        panel.SetSizer(sizer)        
        self.Centre()
        self.Show(True)
        

    def on_about(self, evt):
        info = wx.AboutDialogInfo()
        info.SetName('Pylot')
        info.SetCopyright('Copyright %s 2007 Corey Goldberg\ncorey@goldb.org' % u'\u00A9')
        info.SetDescription('\nPylot is Free Open Source Software\nLicense:  GNU GPL')
        wx.AboutBox(info)


    def stop(self):
        self.lm.stop()
        self.rt_mon.stop()
        self.stopper.stop()
        self.switch_status(False)

        
    def on_exit(self, evt):    
        sys.exit(0)
        
        
    def timer_handler(self, evt):
        self.busy_gauge.Pulse()
        
        
    def on_run(self, evt):
        # reset stats and errors in case there was a previous run since startup
        self.runtime_stats = {}
        self.error_queue = []
        
        # get values from UI controls
        num_agents = self.num_agents_spin.GetValue()
        interval = self.interval_spin.GetValue() / 1000.0  # convert from millisecs to secs
        rampup = self.rampup_spin.GetValue()
        duration = self.duration_spin.GetValue()
        log_resps = self.logresp_checkbox.GetValue()
        
        # create a load manager
        self.lm = LoadManager(num_agents, interval, rampup, log_resps, self.runtime_stats, self.error_queue)
        
        # load the test cases
        try:
            cases = self.load_xml_cases()
            for req in cases:
                self.lm.add_req(req)
        except:
            # if there was a problem getting cases from the xml file
            dial = wx.MessageDialog(None, 'invalid testcase file', 'Error', wx.OK | wx.ICON_ERROR)
            dial.ShowModal()
            cases = None
        
        if cases != None:  # only run if we have valid cases
            self.start_time = time.time()    
            
            # start the load manager
            self.lm.setDaemon(True)
            self.lm.start()
            
            # start a thread to stop execution when the test duration lapses
            self.stopper = Stopper(self, duration)
            self.stopper.setDaemon(True)
            self.stopper.start()
            
            self.rt_mon = RTMonitor(self.start_time, self.runtime_stats, self.error_queue, self.agents_statlist, self.total_statlist, self.error_list)
            self.rt_mon.error_list.Clear()
            
            self.rt_mon.setDaemon(True)
            self.rt_mon.start()
            
            self.switch_status(True)
        
        
    def on_stop(self, evt):
        self.stop()
        
        
    def on_pause(self, evt):
        self.pause_btn.Disable()
        self.resume_btn.Enable()
        self.rt_mon.stop()
        
        
    def on_resume(self, evt):
        self.pause_btn.Enable()
        self.resume_btn.Disable()
        
        self.rt_mon = RTMonitor(self.start_time, self.runtime_stats, self.error_queue, self.agents_statlist, self.total_statlist, self.error_list)
        self.rt_mon.setDaemon(True)
        self.rt_mon.start()
        
        
    def on_results(self, evt):
        dir_dlg = wx.DirDialog(self, message='Choose Results Directory', defaultPath=os.getcwd(), style=wx.DD_DIR_MUST_EXIST)
        if dir_dlg.ShowModal() == wx.ID_OK:
            dirname = dir_dlg.GetPath()
            results_gen = results.ResultsGenerator(dirname)
            results_gen.setDaemon(True)
            results_gen.start()
            msg = 'Generating HTML report in:\n%s' % dirname
            gen_dlg = wx.MessageDialog(None, msg, 'Info', wx.OK)
            gen_dlg.ShowModal()
        dir_dlg.Destroy()
            

    def load_xml_cases(self):
        # parse xml and load request queue
        dom = etree.parse('testcases.xml')
        cases = []
        for child in dom.getiterator():
            if child.tag != dom.getroot().tag and child.tag == 'case':
                req = Request()
                repeat = child.attrib.get('repeat')
                if repeat:
                    req.repeat = int(repeat)
                else:
                    repeat = 1
                int(req.repeat)
                #print int()
                for element in child:
                    if element.tag == 'url':
                        req.url = element.text
                    if element.tag == 'method': 
                        req.method = element.text
                    if element.tag == 'body': 
                        req.body = element.text
                    if element.tag == 'verify': 
                        req.verify = element.text
                    if element.tag == 'verify_negative': 
                        req.verify_negative = element.text
                    if element.tag == 'add_header':
                        splat = element.text.split(':')
                        req.add_header(splat[0].strip(), splat[1].strip())
                if 'Content-type' not in req.headers:
                    req.add_header('Content-type', 'text/xml')  # default if no type specified
                    #req.add_header('Content-type', 'application/x-www-form-urlencoded')  # default if no type specified
                cases.append(req)
        return cases
   
        
    def switch_status(self, is_on):
        # change the status gauge and swap run/stop buttons, turn off workload controls
        if is_on:
            self.run_btn.Disable()
            self.stop_btn.Enable()
            self.pause_btn.Enable()
            self.resume_btn.Disable()
            self.num_agents_spin.Disable()
            self.interval_spin.Disable()
            self.rampup_spin.Disable()
            self.duration_spin.Disable()
            self.logresp_checkbox.Disable()
            self.busy_timer.Start(75)
        else:
            self.run_btn.Enable()
            self.stop_btn.Disable()
            self.pause_btn.Disable()
            self.resume_btn.Disable()
            self.num_agents_spin.Enable()
            self.interval_spin.Enable()
            self.rampup_spin.Enable()
            self.duration_spin.Enable()
            self.logresp_checkbox.Enable()
            self.busy_timer.Stop()




class Stopper(Thread):  # timer thread for stopping execution once duration lapses
    def __init__(self, root, duration):
        Thread.__init__(self)
        self.root = root
        self.duration = duration
        self.start_time = time.time()
        self.running = True
        
    def stop(self):
        self.running = False        
        
    def run(self):
        while (time.time() < self.start_time + self.duration) and self.running:
            time.sleep(.75)
        if self.running:  # if stop() was already called explicitly, don't stop again
            self.root.stop()




class AutoWidthListCtrl(wx.ListCtrl, ListCtrlAutoWidthMixin):
    def __init__(self, parent, height=100, width=605):
        wx.ListCtrl.__init__(self, parent, -1, size=(width, height), style=wx.LC_REPORT|wx.LC_HRULES)
        ListCtrlAutoWidthMixin.__init__(self)
        



class RTMonitor(Thread):  # real time monitor.  runs in its own thread so we don't block UI events 
    def __init__(self, start_time, runtime_stats, error_queue, agents_statlist, total_statlist, error_list):
        Thread.__init__(self)
        
        # references to shared data stores         
        self.runtime_stats = runtime_stats
        self.error_queue = error_queue
        
        # references to list widgets
        self.agents_statlist = agents_statlist  
        self.total_statlist = total_statlist
        self.error_list = error_list
        
        self.start_time = start_time
        self.refresh_rate = 3.0
        
        
    def run(self):
        self.running = True
        self.last_count = 0  # to calc current throughput
        while self.running:
            self.refresh()
            # sleep until next refresh    
            time.sleep(self.refresh_rate)
    
    
    def refresh(self):
        # refresh total monitor
        elapsed_secs = int(time.time() - self.start_time)  # running time in secs
        ids = self.runtime_stats.keys()
        
        agents_running = '%d/%d' % (len([self.runtime_stats[id].count for id in ids if self.runtime_stats[id].count > 0]), len(ids))
        agg_count = sum([self.runtime_stats[id].count for id in ids])  # total req count
        agg_total_latency = sum([self.runtime_stats[id].total_latency for id in ids])
        agg_error_count = sum([self.runtime_stats[id].error_count for id in ids])
        if agg_count > 0 and elapsed_secs > 0:
            agg_avg = agg_total_latency / agg_count  # total avg response time
            throughput = float(agg_count) / elapsed_secs  # avg throughput since start
            interval_count = agg_count - self.last_count  # requests since last refresh
            cur_throughput = float(interval_count) / self.refresh_rate  # throughput since last refresh
            self.last_count = agg_count  # reset for next time
        else: 
            agg_avg = 0
            throughput = 0
            cur_throughput = 0
        self.total_statlist.DeleteAllItems()       
        index = self.total_statlist.InsertStringItem(sys.maxint, self.humanize_time(elapsed_secs))
        self.total_statlist.SetStringItem(index, 1, '%s' % agents_running)
        self.total_statlist.SetStringItem(index, 2, '%d' % agg_count)
        self.total_statlist.SetStringItem(index, 3, '%d' % agg_error_count)
        self.total_statlist.SetStringItem(index, 4, '%.3f' % agg_avg)
        self.total_statlist.SetStringItem(index, 5, '%.3f' % throughput)
        self.total_statlist.SetStringItem(index, 6, '%.3f' % cur_throughput)
        
        # refresh agents monitor
        self.agents_statlist.DeleteAllItems()       
        for id in self.runtime_stats.keys():
            count = self.runtime_stats[id].count
            index = self.agents_statlist.InsertStringItem(sys.maxint, '%d' % (id + 1))
            self.agents_statlist.SetStringItem(index, 2, '%d' % count)
            if count == 0:
                self.agents_statlist.SetStringItem(index, 1, 'waiting')
                self.agents_statlist.SetStringItem(index, 3, '-')
                self.agents_statlist.SetStringItem(index, 4, '-')
                self.agents_statlist.SetStringItem(index, 5, '-')
            else:
                self.agents_statlist.SetStringItem(index, 1, 'running')
                self.agents_statlist.SetStringItem(index, 3, '%.3f' % self.runtime_stats[id].latency)
                self.agents_statlist.SetStringItem(index, 4, '%.3f' % self.runtime_stats[id].avg_latency)
                self.agents_statlist.SetStringItem(index, 5, '%d' % self.runtime_stats[id].total_bytes)
        self.agents_statlist.resizeLastColumn(80)  # avoid horizontal scrollbar
        
        
        # refresh error monitor            
        for error in self.error_queue:
            # pop error strings off the queue and render them in the monitor
            self.error_list.AppendText('%s\n' % self.error_queue.pop(0))
        self.error_list.ShowPosition(self.error_list.GetLastPosition()) # scroll to end 
        
        
    def stop(self):
        self.refresh()
        for id in self.runtime_stats.keys():
            self.agents_statlist.SetStringItem(id, 1, 'stopped')
        self.running = False
        
    
    def humanize_time(self, secs):
        # convert secs (int) into a human readable time string:  hh:mm:ss
        mins, secs = divmod(secs, 60)
        hours, mins = divmod(mins, 60)
        if hours < 10:
            hours = '0%d' % hours
        else:
            hours = str(hours)
        if mins < 10:
            mins = '0%d' % mins
        else:
            mins = str(mins)
        if secs < 10:
            secs = '0%d' % secs
        else:
            secs = str(secs)
        return '%s:%s:%s' % (hours, mins, secs)
            
        
        
        
class AboutFrame(wx.Frame):
    def __init__(self, parent, ID, title):
        wx.Frame.__init__(self, parent, -1, title, pos=(0, 0), size=(320, 240))
        self.SetIcon(wx.Icon('ui/icon.ico', wx.BITMAP_TYPE_ICO))
        panel = wx.Panel(self, -1)
        
        content = """\
Pylot - Web Performance
Copyright (c) 2007-2008 Corey Goldberg
Pylot is Free Open Source Software
License:  GNU GPL
        """
        text = wx.StaticText(panel, -1, content, wx.Point(10, 10))
        text.SetFont(wx.Font(8, wx.DEFAULT, wx.NORMAL, wx.NORMAL))
        
            


def main():
    app = wx.App(0)
    Application(None)
    app.MainLoop()            


if __name__ == '__main__':
    main()
