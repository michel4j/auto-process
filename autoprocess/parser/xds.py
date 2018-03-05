"""
Parsers for XDS Files

"""
import re
import numpy
import os
import utils
import shutil
from autoprocess.utils import misc, xtal

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
    1: 'Dimension of clusters not 3D',
    2: 'Percentage of indexed spots too low',
    3: 'Not enough spots to index',
    4: 'Solution is poor',
    5: 'Unable to refine solution',
    6: 'Unable to index reflections',
    7: 'Program died'
}
def parse_idxref(filename='IDXREF.LP'):
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
    
    if misc.file_requirements(filename,'XPARM.XDS'):
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
            
    if info['summary']['spacegroup'] == 1 and filename != 'CORRECT.LP.first':
        shutil.copy(filename, 'CORRECT.LP.first')
            
    # parse GXPARM.XDS and update with more accurate cell parameters
    xparm = parse_xparm('GXPARM.XDS')
    info['parameters'] = xparm
    info['summary']['unit_cell'] = xparm['unit_cell']   
    return info

def parse_xplan(filename='XPLAN.LP'):
    raw_info = utils.parse_file(filename, config='xplan.ini')
    index_info = parse_idxref()
    correct_info = parse_correct('CORRECT.LP.first')

    start_plan = {}
    for start_plan in raw_info['summary']:
        if start_plan['completeness'] > 90:
            break

    cmpl_plan = {}
    for cmpl_plan in raw_info['summary']:
        if cmpl_plan['total_angle'] >= 180.:
            break

    stats = correct_info['statistics'][-2]
    res_reason = 'N/A'
    for stats in correct_info['statistics'][:-1]:
        if stats['i_sigma'] < 0.5:
            res_reason = 'Resolution limit is based on I/Sigma(I) > 0.5'
            break
        res_reason = 'Resolution limit is based on detector edge'
    resolution = float(stats['shell'])
    mosaicity = correct_info['summary']['mosaicity']

    distance = round(xtal.resol_to_dist(
        resolution, correct_info['parameters']['pixel_size'][0], correct_info['parameters']['detector_size'][0],
        correct_info['parameters']['wavelength']
    ))

    osc = index_info['oscillation_ranges'][-1]
    for osc in  index_info['oscillation_ranges']:
        if osc['resolution'] <= resolution:
            break
    delta = round(max(0.2, osc['delta_angle'] - mosaicity), 2)
    info = {
        'distance': distance,
        'completeness': cmpl_plan.get('completeness', -99),
        'redundancy': cmpl_plan['multiplicity'],
        'i_sigma': correct_info['summary']['i_sigma'],
        'resolution': resolution,
        'resolution_reasoning': res_reason,
        'attenuation': 0,
        'runs': [{
            'name': 'Run 1',
            'number': 1,
            'distance': distance,
            'exposure_time': -1,
            'phi_start': start_plan.get('start_angle', 0),
            'phi_width': delta,
            'overlaps': {True: 'Yes', False: 'No'}[delta > osc['delta_angle']],
            'number_of_images': int(180/delta)
        }],
        'prediction_all': {
             'R_factor': correct_info['statistics'][-1]['r_exp'],
             'average_error': -0.99,
             'average_i_over_sigma': correct_info['statistics'][-1]['i_sigma'],
             'average_intensity': -99,
             'completeness': cmpl_plan.get('completeness', -99)/100.,
             'fract_overload': 0.0,
             'max_resolution': resolution,
             'min_resolution': 50,
             'redundancy': cmpl_plan['multiplicity']
        },
        'prediction_hi': {
            'R_factor': stats['r_exp'],
            'average_error': -0.99,
            'average_i_over_sigma': stats['i_sigma'],
            'average_intensity': -99,
            'completeness': cmpl_plan.get('completeness', -99) / 100.,
            'fract_overload': 0.0,
            'max_resolution': resolution,
            'min_resolution': resolution - 0.03,
            'redundancy': cmpl_plan['multiplicity']
        },
        'details': {
        }
    }
    return info

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

