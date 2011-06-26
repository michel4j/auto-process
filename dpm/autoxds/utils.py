"""
Generic Utiltites for AutoXDS

"""

    
import os
import sys
import re
import math
from math import exp
import fnmatch
import shutil
import commands
from bcm.utils.imageio import read_header
from dpm.parser.utils import Table
from dpm.utils import magic
from dpm.utils import fitting
from dpm.utils import peaks
import numpy
from dpm.utils.prettytable import PrettyTable
from dpm.utils.odict import SortedDict
import textwrap
   
from dpm.utils.log import get_module_logger
_logger = get_module_logger('AutoXDS')

DEBUG = False

    

def print_table(info, multiple=False):
    txt = '*** Auto-indexing Diagnostics ***\n'
    
    if not multiple:
        length = max([len(v) for v in info.keys()])
        format = "%%%ds: %%s\n" % length
        for k, v in info.items():
            txt += format % (k, v)
    else:
        formats = {}
        _t = Table(info)
        for k in info[0].keys():
            length = max([ len(str(v)) for v in _t[k] ])
            length = max(length, len(k))
            formats[k] = "%%%ds " % length
        for k, f in formats.items():
            txt += f % (k),
        txt += '\n'
        for l in info:
            for k, v in l.items():
                txt += f % (v),
            txt += '\n'
    return txt
    

def update_xparm():
    if os.path.exists('GXPARM.XDS'):
        backup_file('XPARM.XDS')
        shutil.copy('GXPARM.XDS', 'XPARM.XDS')
    
def get_xplan_strategy(info):
    plan = {}
    xplan = info['strategy'].get('xplan')
    res = info['scaling']['resolution'][0]
    osc = Table(info['indexing']['oscillation_ranges'])
    x = numpy.array(osc['resolution'])
    y = numpy.array(osc['delta_angle'])
    p1 = fitting.linear_fit(x, y)
    plan['resolution'] = res
    plan['delta_angle'] = fitting.line_func(res, p1)
    
    _scens = info['strategy']['xplan'].get('summary')
    pos = len(_scens)
    _sel = _scens[-1]
    while pos > 0:
        pos -=1
        if (_scens[pos]['completeness'] - _sel['completeness']) > -0.5:
            _sel = _scens[pos]
            
    plan.update(_sel)
    plan['number_of_images'] = int(plan['total_angle']/plan['delta_angle'])
    return plan    

def match_code(src, tgt):
    # bitwise compare two integers
    return src|tgt == src

def match_none(src, tgts):
    for tgt in tgts:
        if src|tgt == src:
            return False
    return True

def match_any(src, tgts):
    for tgt in tgts:
        if src|tgt == src:
            return True
    return False 

def text_heading(txt, level=1):
    if level in [1,2]:
        _pad = ' '*((78 - len(txt))//2)
        txt = '%s%s%s' % (_pad, txt, _pad)
        if level == 2:
            _banner = '-'*78
        else:
            _banner = '*'*78
            txt = txt.upper()
        _out = '\n%s\n%s\n%s\n\n' % (_banner, txt, _banner)
    elif level == 3:
        _pad = '*'*((74 - len(txt))//2)
        _out = '\n%s  %s  %s\n\n' % (_pad, txt, _pad)
    elif level == 4:
        _out = '\n%s:\n' % (txt.upper(),)
    else:
        _out = txt
    return _out

def add_margin(txt, size=1):
    _margin = ' '*size
    return '\n'.join([_margin+s for s in txt.split('\n')]) 


def format_section(section, level=1, invert=False, fields=[], show_title=True):
    _section = section
    if show_title:
        file_text = text_heading(_section['title'], level)
    else:
        file_text = ''
        
    if _section.get('table') is not None:
        _key = 'table'
    elif _section.get('table+plot') is not None:
        _key = 'table+plot'
    else:
        return ''
    pt = PrettyTable()
    if not invert:
        for i, d in enumerate(_section[_key]):
            dd = SortedDict(d)
            values = dd.values()
            if i == 0:
                keys = dd.keys()
                pt.add_column(keys[0], keys[1:],'l')
            pt.add_column(values[0], values[1:], 'r')
    else:
        for i, d in enumerate(_section[_key]):
            dd = SortedDict(d)
            values = dd.values()
            if i == 0:
                keys = dd.keys()
                pt.field_names = keys
            pt.add_row(values)
        pt.align = "r"
    if len(fields) == 0:
        file_text += pt.get_string()
    else:
        file_text += pt.get_string(fields=fields)
    file_text +='\n'
    if _section.get('notes'):
        all_notes = _section.get('notes').split('\n')
        notes = []
        for note in all_notes:
            notes += textwrap.wrap( note, width=60, subsequent_indent="    ")
        file_text += '\n'.join(notes)
    file_text += '\n'
    return file_text
    
def shorten_path(path, start):
    start = os.path.abspath(start)+os.path.sep
    return path.replace(start,'')
