"""
Parsers for XDS Files

"""
import re
import numpy
import os
import utils
import shutil
from dpm.utils import misc

(NO_FAILURE,
SPOT_LIST_NOT_3D,
INSUFFICIENT_INDEXED_SPOTS,
INSUFFICIENT_SPOTS,
POOR_SOLUTION,
REFINE_ERROR,
INDEX_ERROR,
PROGRAM_ERROR ) = range(8)

_IDXREF_FAILURES = {
    0: None,
    1: 'Dimension of difference vector set too low',
    2: 'Insufficient percentage of spots indexed',
    3: 'Insufficient number of spots',
    4: 'Solution is not good enough',
    5: 'Could not refine solution',
    6: 'Could not index reflections',
    7: 'Program died prematurely'
}
def parse_idxref(filename='IDXREF.LP'):
    if not misc.file_requirements(filename,'XPARM.XDS'):
        return {'failure': 'Indexing step failed'}
    info = utils.parse_file(filename, config='idxref.ini')
    
    if info['failure_message'] is None:
        if os.path.getsize(filename) < 15000:
            info['failure_code'] = 7
        else:
            info['failure_code'] = 0
    
    elif info['failure_message'] in ['CANNOT CONTINUE WITH A TWO-DIMENSIONAL',
                           'DIMENSION OF DIFFERENCE VECTOR SET LESS THAN 3.',
                           'DIMENSION OF DIFFERENCE VECTOR SET LESS THAN 2.',
                           ]:
        info['failure_code'] = 1
    elif re.match("^INSUFFICIENT PERCENTAGE .+ OF INDEXED REFLECTIONS", info['failure_message']):
        info['failure_code'] = 2
    elif info['failure_message'] == 'INSUFFICIENT NUMBER OF ACCEPTED SPOTS.':
        info['failure_code'] = 3
    elif info['failure_message'] == 'SOLUTION IS INACCURATE':
        info['failure_code'] = 4
    elif  info['failure_message'] == 'RETURN CODE IS IER=           0':
        info['failure_code'] = 5
    elif  info['failure_message'] =='CANNOT INDEX REFLECTIONS':
        info['failure_code'] = 6
    else:
        info['failure_code'] = 7
        
    info['parameters'] = parse_xparm('XPARM.XDS')
    info['failure'] = _IDXREF_FAILURES[info['failure_code']]
    return info
        

def parse_correct(filename='CORRECT.LP'):
    if not os.path.exists(filename):
        return {'failure': 'Correction step failed'}
    info = utils.parse_file(filename, config='correct.ini')

    if info.get('statistics') is not None:
        if len(info['statistics']) > 1:
            info['summary'].update( info['statistics'][-1] )
            del info['summary']['shell']
            
    if info['summary']['spacegroup'] == 1:
        shutil.copy(filename, 'CORRECT.LP.first')
            
    # parse GXPARM.XDS and update with more accurate cell parameters
    xparm = parse_xparm('GXPARM.XDS')
    info['parameters'] = xparm
    info['summary']['unit_cell'] = xparm['unit_cell']   
    return info

def parse_xplan(filename='XPLAN.LP'):
    return utils.parse_file(filename, config='xplan.ini')

def parse_xdsstat(filename='XDSSTAT.LP'):
    return utils.parse_file(filename, config='xdsstat.ini')

def parse_xparm(filename="XPARM.XDS"):
    info = utils.parse_file(filename, config='xparm.ini')
    return info['parameters']

def parse_xscale(filename='XSCALE.LP'):
    if not os.path.exists(filename):
        return {'failure': 'Scaling step failed'}
    data = file(filename).read()
    # extract separate sections corresponding to different datasets
    
    _header = utils.cut_section("CONTROL CARDS", "CORRECTION FACTORS AS FUNCTION", data)[0]
    _st_p = re.compile('(STATISTICS OF SCALED OUTPUT DATA SET : ([\w-]*)/?[\w]+.HKL.+?STATISTICS OF INPUT DATA SET [=\s]*)', re.DOTALL)
    _wl_p = re.compile('(WILSON STATISTICS OF SCALED DATA SET: ([\w-]*)/?[\w]+.HKL\s+[*]{78}.+?(?:List of|\s+[*]{78}|cpu time))', re.DOTALL)

    data_sections = {}
    for d,k in _st_p.findall(data):
        data_sections[k] = _header + d
    for d,k in _wl_p.findall(data):
        data_sections[k] += d
    info = {}
    for k, d in data_sections.items():
        info[k] = utils.parse_data(d, config='xscale.ini')
        if info[k].get('statistics') is not None:
            if len(info[k]['statistics']) > 1:
                info[k]['summary'] = {}
                info[k]['summary'].update(info[k]['statistics'][-1])       
                del info[k]['summary']['shell']
    return info

def parse_correlations(filename='XSCALE.LP'):
    if not os.path.exists(filename):
        return {'failure': 'File not found'}
    data = file(filename).read()
    # extract separate sections corresponding to different datasets
    
    _header = utils.cut_section("CONTROL CARDS", "CORRECTION FACTORS AS FUNCTION", data)[0]
    return utils.parse_data(_header, config='xscale.ini')


def parse_integrate(filename='INTEGRATE.LP'):
    if not os.path.exists(filename):
        return {'failure': 'Integration step failed'}
    info = utils.parse_file(filename, config='integrate.ini')
    if info.get('profiles') is not None:
        profiles = []
        for i in range(9):
            profile = {}
            if i == 0:
                x_max = info['profiles']['detector_regions'][0]['positions'][i]*2
                y_max = info['profiles']['detector_regions'][1]['positions'][i]*2
            profile['x'] = 9 * info['profiles']['detector_regions'][0]['positions'][i]/x_max
            profile['y'] = 9* info['profiles']['detector_regions'][1]['positions'][i]/y_max
            profile['spots'] = []
            for j in range(9):
                spot = tuple()
                idx = j+(i*9)
                x = idx%3
                y = idx//3
                sx, ex = x*9, (x+1)*9
                sy, ey = y*9, (y+1)*9
                for v in info['profiles']['averages'][sy:ey]:
                    spot += v['pixels'][sx:ex]
                profile['spots'].append(spot)
            profiles.append(profile)
        info['profiles'] = profiles
    return info

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
