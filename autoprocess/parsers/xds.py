"""
Parsers for XDS Files

"""
import os
import re
import shutil

import numpy

from autoprocess.utils import misc, xtal
from . import parser

(NO_FAILURE,
 SPOT_LIST_NOT_3D,
 INSUFFICIENT_INDEXED_SPOTS,
 INSUFFICIENT_SPOTS,
 POOR_SOLUTION,
 REFINE_ERROR,
 INDEX_ERROR,
 PROGRAM_ERROR) = list(range(8))

IDXREF_FAILURES = {
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
    info = parser.parse(filename, 'idxref')

    dimension_failures = [
        'CANNOT CONTINUE WITH A TWO-DIMENSIONAL',
        'DIMENSION OF DIFFERENCE VECTOR SET LESS THAN 3.',
        'DIMENSION OF DIFFERENCE VECTOR SET LESS THAN 2.',
    ]
    if info.get('failure_message') is None:
        if os.path.getsize(filename) < 15000:
            info['failure_code'] = 7
        else:
            info['failure_code'] = 0

    elif info['failure_message'] in dimension_failures:
        info['failure_code'] = 1
    elif re.match("^INSUFFICIENT PERCENTAGE .+ OF INDEXED REFLECTIONS", info['failure_message']):
        info['failure_code'] = 2
    elif info['failure_message'] == 'INSUFFICIENT NUMBER OF ACCEPTED SPOTS.':
        info['failure_code'] = 3
    elif info['failure_message'] == 'SOLUTION IS INACCURATE':
        info['failure_code'] = 4
    elif info['failure_message'] == 'RETURN CODE IS IER=           0':
        info['failure_code'] = 5
    elif info['failure_message'] == 'CANNOT INDEX REFLECTIONS':
        info['failure_code'] = 6
    else:
        info['failure_code'] = 7

    if misc.file_requirements(filename, 'XPARM.XDS'):
        info['parameters'] = parse_xparm('XPARM.XDS')
    info['failure'] = IDXREF_FAILURES[info['failure_code']]
    return info


def parse_correct(filename='CORRECT.LP'):

    if not os.path.exists(filename):
        return {'failure': 'Correction step failed'}

    info = parser.parse(filename, 'correct')
    info['summary'].update(info.pop('statistics_summary',{}))
    if len(info['statistics']) > 1:
        info['summary']['inner_shell'] = info['statistics'][0]
        info['summary']['outer_shell'] = info['statistics'][-1]

    if info['summary']['spacegroup'] == 1 and filename != 'CORRECT.LP.first':
        shutil.copy(filename, 'CORRECT.LP.first')

    for stats in info['standard_errors'][:-1]:
        if stats['i_sigma'] < 0.5:
            info['summary']['stderr_method'] = 'Resolution limit is based on I/Sigma(I) > 0.5'
            info['summary']['stderr_resolution'] = stats['resol_range'][-1]
            break
        else:
            info['summary']['stderr_method'] = 'Resolution limit is based on detector edge'
            info['summary']['stderr_resolution'] = stats['resol_range'][-1]

    # parse GXPARM.XDS and update with more accurate cell parameters
    xparm = parse_xparm('GXPARM.XDS')
    info['parameters'] = xparm
    info['summary']['unit_cell'] = xparm['unit_cell']
    info['summary']['ISa'] = info['correction_factors']['parameters'].get('ISa', -1)
    return info


def parse_xplan(filename='XPLAN.LP'):
    raw_info = parser.parse(filename, 'xplan')

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

    res_reason = correct_info['summary']['stderr_method']
    resolution = correct_info['summary']['stderr_resolution']
    mosaicity = correct_info['summary']['mosaicity']

    distance = round(xtal.resol_to_dist(
        resolution, correct_info['parameters']['pixel_size'][0], correct_info['parameters']['detector_size'][0],
        correct_info['parameters']['wavelength']
    ))

    osc = index_info['oscillation_ranges'][-1]
    for osc in index_info['oscillation_ranges']:
        if osc['resolution'] <= resolution:
            break
    delta = round(max(0.2, osc['delta_angle'] - mosaicity), 2)

    completeness = numpy.array([
        (v['start_angle'], v['end_angle'] - v['start_angle'], v['completeness'])
        for v in raw_info['completeness_statistics']
    ])
    starts = numpy.unique(completeness[:, 0])
    ranges = numpy.unique(completeness[:, 1])
    statistics = {
        str(tot): completeness[completeness[:, 1] == tot][:, 2].tolist() for tot in ranges
    }
    statistics['start_angle'] = starts.tolist()

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
            'number_of_images': int(180 / delta)
        }],
        'prediction_all': {
            'R_factor': correct_info['summary']['r_exp'],
            'average_error': -0.99,
            'average_i_over_sigma': correct_info['summary']['i_sigma'],
            'average_intensity': -99,
            'completeness': cmpl_plan.get('completeness', -99) / 100.,
            'fract_overload': 0.0,
            'max_resolution': resolution,
            'min_resolution': 50,
            'redundancy': cmpl_plan['multiplicity']
        },
        'prediction_hi': {
            'R_factor': correct_info['summary']['outer_shell']['r_exp'],
            'average_error': -0.99,
            'average_i_over_sigma': correct_info['summary']['outer_shell']['i_sigma'],
            'average_intensity': -99,
            'completeness': cmpl_plan.get('completeness', -99) / 100.,
            'fract_overload': 0.0,
            'max_resolution': resolution,
            'min_resolution': resolution - 0.03,
            'redundancy': cmpl_plan['multiplicity']
        },
        'details': {
            'completeness_statistics': statistics
        }
    }
    return info


def parse_xdsstat(filename='XDSSTAT.LP'):
    """
    Harvest XDSSTAT
    """
    return parser.parse(filename, 'xdsstat')


def parse_xparm(filename="XPARM.XDS"):
    """
    Harvest XPARMs
    """
    info = parser.parse(filename, 'xparm')
    return info['parameters']


def parse_xscale(filename='XSCALE.LP'):
    """
    Harvest data from XSCALE
    """
    if not os.path.exists(filename):
        return {'failure': 'Scaling step failed'}

    with open(filename, 'r') as handle:
        data = handle.read()

    # extract separate sections corresponding to different datasets
    header = re.compile(r'(CONTROL CARDS.+?CORRECTION FACTORS AS FUNCTION)', re.DOTALL)
    section = re.compile(
        r'(STATISTICS OF SCALED OUTPUT DATA SET : (?:\d+-)?([\w_]+)/?[\w]*?.HKL'
        r'.+?R-FACTORS FOR INTENSITIES OF DATA SET [^\n]+?\n)',
        re.DOTALL
    )

    header_text = "\n".join(header.findall(data))
    data_sections = {}
    for d, k in section.findall(data):
        data_sections[k] = header_text + "\n" + d
    info = {}
    for k, d in list(data_sections.items()):
        info[k] = parser.parse_text(d, 'xscale')
        if len(info[k]['statistics']) > 1:
            info[k]['summary']['inner_shell'] = info[k]['statistics'][0]
            info[k]['summary']['outer_shell'] = info[k]['statistics'][-1]
    return info


def parse_correlations(filename='XSCALE.LP'):
    """
    Harvest correlation data from XSCALE
    """
    if not os.path.exists(filename):
        return {'failure': 'Scaling step failed'}

    with open(filename, 'r') as handle:
        data = handle.read()

    # extract separate sections corresponding to different datasets
    header = re.compile(r'(CONTROL CARDS.+?CORRECTION FACTORS AS FUNCTION)', re.DOTALL)

    header_text = "\n".join(header.findall(data))
    return parser.parse_text(header, 'xscale')


def parse_integrate(filename='INTEGRATE.LP'):
    """
    Harvest data from INTEGRATE
    """
    if not os.path.exists(filename):
        return {'failure': 'Integration step failed'}
    info = parser.parse(filename, 'integrate')

    for batch, frames in zip(info.get('batches',[]), info.pop('batch_frames', [])):
        batch.update(frames)
    return info

