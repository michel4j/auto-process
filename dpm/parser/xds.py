"""
Parsers for XDS Files

"""
import re, numpy
import os
import utils

def parse_idxref(filename='IDXREF.LP'):
    info = utils.parse_file(filename, config='idxref.ini')
    if os.path.getsize(filename) < 15000 and info.get('failure') is None:
        info['failure'] = 'Indexing did not complete!'
    return info
        

def parse_correct(filename='CORRECT.LP'):
    return utils.parse_file(filename, config='correct.ini')

def parse_xplan(filename='XPLAN.LP'):
    return utils.parse_file(filename, config='xplan.ini')


def parse_xscale(filename='XSCALE.LP'):
    data = file(filename).read()
    # extract separate sections corresponding to different datasets
    _st_p = re.compile('(STATISTICS OF SCALED OUTPUT DATA SET : ([\w-]*)/?XSCALE.HKL.+?STATISTICS OF INPUT DATA SET [=\s]*)', re.DOTALL)
    _wl_p = re.compile('(WILSON STATISTICS OF SCALED DATA SET: ([\w-]*)/?XSCALE.HKL\s+[*]{78}.+?(?:List of|\s+[*]{78}|cpu time))', re.DOTALL)
    data_sections = {}
    for d,k in _st_p.findall(data):
        data_sections[k] = d
    for d,k in _wl_p.findall(data):
        data_sections[k] += d
    info = {}
    for k, d in data_sections.items():
        info[k] = utils.parse_data(d, config='xscale.ini')
        if info[k].get('statistics') is not None:
            if len(info[k]['statistics']) > 1:
                info[k]['summary'] = info[k]['statistics'][-1]             
    return info

def parse_integrate(filename='INTEGRATE.LP'):
     return utils.parse_file(filename, config='integrate.ini')

def get_profile(raw_data):
    def _str2arr(s):
        l = [int(v) for v in re.findall('.{3}', s)]
        a = numpy.array(l).reshape((9,9))
        return a
    data = []

    for line in raw_data:
        if len(line) > 2:
            l = line[3:-1]
            data.append(l)

    slice_str = ['']*9

    for i in range(27):
        section = data[i].split('   ')
        sl =  i//9 * 3
        for j in range(3):
            slice_str[sl+j] += section[j]
    
    return numpy.array(map(_str2arr, slice_str))
