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


def parse_xscale(filename='XSCALE.LP', output_file='XSCALE.HKL'):
    info = utils.parse_file(filename, config='xscale.ini')
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
