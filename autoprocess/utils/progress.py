# -*- coding: utf-8 -*-
'''
Created on Sep 13, 2009

@author: michel
'''
import Queue
import os
import re
import sys
import threading
import time

import numpy


class ProgressMeter(object):
    ESC = chr(27)

    def __init__(self, **kw):
        # What time do we start tracking our progress from?
        self.timestamp = kw.get('timestamp', time.time())
        # What kind of unit are we tracking?
        self.unit = str(kw.get('unit', ''))
        # Number of units to process
        self.total = int(kw.get('total', 100))
        # Number of units already processed
        self.count = int(kw.get('count', 0))
        # Refresh rate in seconds
        self.rate_refresh = float(kw.get('rate_refresh', .5))
        # Number of ticks in meter
        self.meter_ticks = int(kw.get('ticks', 60))
        self.meter_division = float(self.total) / self.meter_ticks
        self.meter_value = int(self.count / self.meter_division)
        self.last_update = None
        self.rate_history_idx = 0
        self.rate_history_len = 10
        self.rate_history = [None] * self.rate_history_len
        self.rate_current = 0.0
        self.last_refresh = 0
        self._cursor = False
        self.reset_cursor()

    def reset_cursor(self, first=False):
        if self._cursor:
            self.stream.write(self.ESC + '[u')
        self._cursor = True
        self.stream.write(self.ESC + '[s')

    def update(self, count, **kw):
        now = time.time()
        # Caclulate rate of progress
        rate = 0.0
        # Add count to Total
        self.count += count
        self.count = min(self.count, self.total)
        if self.last_update:
            delta = now - float(self.last_update)
            if delta:
                rate = count / delta
            else:
                rate = count
            self.rate_history[self.rate_history_idx] = rate
            self.rate_history_idx += 1
            self.rate_history_idx %= self.rate_history_len
            cnt = 0
            total = 0.0
            # Average rate history
            for rate in self.rate_history:
                if rate == None:
                    continue
                cnt += 1
                total += rate
            rate = total / cnt
        self.rate_current = rate
        self.last_update = now
        # Device Total by meter division
        value = int(self.count / self.meter_division)
        if value > self.meter_value:
            self.meter_value = value
        if self.last_refresh:
            if (now - self.last_refresh) > self.rate_refresh or (self.count >= self.total):
                self.refresh()
        else:
            self.refresh()

    def get_meter(self, **kw):
        bar = '-' * self.meter_value
        pad = ' ' * (self.meter_ticks - self.meter_value)
        perc = (float(self.count) / self.total) * 100
        return '[%s>%s] %d%%  %.1f/sec' % (bar, pad, perc, self.rate_current)

    def refresh(self, **kw):
        # Clear line
        self.stream.write(self.ESC + '[2K')
        self.reset_cursor()
        self.stream.write(self.get_meter(**kw))
        # Are we finished?
        if self.count >= self.total:
            self.stream.write('\n')
        self.stream.flush()
        # Timestamp
        self.last_refresh = time.time()


class ProgChecker(object):
    def __init__(self, num, queue=None):
        self.file_list = []
        self.file_objs = {}
        self.file_data = {}

        for i in range(num):
            fn = 'LP_%02d.tmp' % (i + 1)
            self.file_list.append(fn)
            self.file_data[fn] = ''

        if queue is None:
            self.queue = Queue.Queue(100)
        else:
            self.queue = queue
        self._stopped = False
        self._initialized = False
        self._chunk_pattern = re.compile('\s+PROCESSING OF IMAGES\s+(\d{1,5})\s+[.]{3}\s+(\d{1,5})\n [*]{78}',
                                         re.DOTALL)

    def stop(self):
        self._stopped = True

    def _process_chunks(self):
        for fn, chunk in self.file_data.items():
            batches = self._chunk_pattern.findall(chunk)
            if batches is not None:
                self.file_data[fn] = self._chunk_pattern.sub(chunk, '')
                for batch in batches:
                    self.queue.put(map(int, batch))

    def start(self):
        self._stopped = False
        worker_thread = threading.Thread(target=self._run)
        worker_thread.setDaemon(True)
        worker_thread.start()

    def _run(self):
        while not self._stopped:
            time.sleep(0.05)
            for fn in self.file_list:
                if os.path.exists(fn):
                    if fn not in self.file_objs.keys():
                        self.file_objs[fn] = open(fn)
                        self._initialized = True
                else:
                    if fn in self.file_objs.keys():
                        self.file_objs[fn].close()
                        del self.file_objs[fn]
            if self._initialized and len(self.file_objs.keys()) == 0:
                self._stopped = True
                self._initialized = False
                self.queue.put(None)
                break
            if self._initialized:
                for fn, fobj in self.file_objs.items():
                    # adjust for shrinkage
                    try:
                        if os.path.getsize(fn) < fobj.tell():
                            self.fileobj.seek(0, os.SEEK_END)
                        elif os.path.getsize(fn) > fobj.tell():
                            self.file_data[fn] += fobj.read()
                    except:
                        pass
                        # fstat = os.fstat(fobj.fileno())
                self._process_chunks()


# spinner="|/-\\"
# spinner=".o0O0o. "
# spinner="⇐⇖⇑⇗⇒⇘⇓⇙" #utf8
# spinner="◓◑◒◐" #utf8
# spinner="○◔◑◕●" #utf8
# spinner="◴◷◶◵" #utf8
# Note the following 2 look fine with misc fixed font,
# but under bitstream vera mono at least the characters
# vary between single and double width?
# spinner="▏▎▍▌▋▊▉█▉▊▌▍▎" #utf8
# spinner="▁▂▃▄▅▆▇█▇▆▅▄▃▂" #utf8
# spinner=".oO@*"
# spinner="⠁⠂⠄⡀⢀⠠⠐⠈"
class ProgDisplay(threading.Thread):
    ESC = chr(27)
    spinner = "|/-\\"

    def __init__(self, data_range, q, descr="", stream=sys.stdout):
        threading.Thread.__init__(self)
        self.queue = q
        self.total = (data_range[1] - data_range[0]) + 1
        self.data_range = data_range
        self.length = 65
        self._cursor = False
        self._stopped = False
        self.chars = [c.encode("utf-8") for c in unicode(self.spinner, "utf-8")]
        self.descr = descr
        self.stream = stream

    def reset_cursor(self, first=False):
        if self._cursor:
            self.stream.write(self.ESC + '[u')
        self._cursor = True
        self.stream.write(self.ESC + '[s')

    def refresh(self, txt, c='', force=False):
        # Clear line
        if not self.stream.isatty() and not force: return
        self.stream.write(self.ESC + '[2K')
        self.reset_cursor()
        self.stream.write(txt)
        self.stream.flush()

    def stop(self):
        self._stopped = True

    def run(self):
        prog = numpy.zeros(self.length)
        d = {1: '#', 0: '-'}
        obj = [self.data_range[0], self.data_range[0]]
        pos = 0
        txt2 = ' %4.1f%%' % (0.0)
        while not self._stopped:
            _t = time.strftime('%b%d %H:%M:%S')
            txt1 = '%s| %s ' % (_t, self.descr)
            if obj is not None:
                l = int((obj[0] - self.data_range[0]) * self.length / self.total)
                r = int((obj[1] - self.data_range[0] + 1) * self.length / self.total)
                prog[l:r] = 1
                bar = ''.join([d[v] for v in prog])
                frac = prog.mean()
                txt2 = ' %4.1f%%' % (frac * 100)
            txt = txt1 + self.chars[pos] + txt2
            self.refresh(txt)
            if self.queue.empty():
                obj = None
            else:
                obj = self.queue.get(block=True)
            pos += 1
            pos %= len(self.chars)
            if not self._stopped:
                time.sleep(0.1)

        bar = d[1] * self.length
        _t = time.strftime('%b/%d %H:%M:%S')
        txt = '%s %s. %4.1f%% done.\n' % (_t, self.descr, 100)
        self.refresh(txt, force=True)


class FileProgressDisplay(threading.Thread):
    ESC = chr(27)
    spinner = "|/-\\"

    def __init__(self, fname, descr="", stream=sys.stdout):
        threading.Thread.__init__(self)
        self.total = 100
        self.length = 65
        self._cursor = False
        self._stopped = False
        self.chars = [c.encode("utf-8") for c in unicode(self.spinner, "utf-8")]
        self.descr = descr
        self.stream = stream
        self.filename = fname

    def reset_cursor(self, first=False):
        if self._cursor:
            self.stream.write(self.ESC + '[u')
        self._cursor = True
        self.stream.write(self.ESC + '[s')

    def refresh(self, txt, c='', force=False):
        # Clear line
        if not self.stream.isatty() and not force: return
        self.stream.write(self.ESC + '[2K')
        self.reset_cursor()
        self.stream.write(txt)
        self.stream.flush()

    def stop(self):
        self._stopped = True

    def run(self):
        progress = 0.0
        pos = 0
        while not self._stopped:
            _t = time.strftime('%b%d %H:%M:%S')
            txt1 = '%s| %s ' % (_t, self.descr)
            if pos >= 20 and os.path.exists(self.filename): # Update every 1 seconds cycles
                pos = 0
                with open(self.filename, 'r') as progress_file:
                    progress_text = progress_file.read().strip()
                    if progress_text:
                        progress = float(progress_text) * 100
            txt2 = '{:4.1f}%'.format(progress)
            txt = txt1 + self.chars[pos % len(self.chars)] + txt2
            self.refresh(txt)
            pos += 1
            if not self._stopped:
                time.sleep(0.1)
        _t = time.strftime('%b%d %H:%M:%S')
        txt = '%s| %s. %4.1f%% done.\n' % (_t, self.descr, 100)
        self.refresh(txt, force=True)
