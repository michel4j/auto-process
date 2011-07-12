import os

from dpm.parser import distl
from dpm.utils import log, misc, programs, io
import dpm.errors

_logger = log.get_module_logger(__name__)


def initialize(data_info, options={}):
    os.chdir(data_info['working_directory'])
    _logger.info('Creating correction tables ...')

    run_info = {}
    run_info.update(data_info)
    
    io.write_xds_input('XYCORR INIT', run_info)
    try:
        programs.xds_par()
    except dpm.errors.ProcessError, e:
        return {'step': 'initialize', 'success':False, 'reason': str(e)}
    
    if misc.file_requirements('X-CORRECTIONS.cbf', 'Y-CORRECTIONS.cbf',
        'BKGINIT.cbf', 'BLANK.cbf', 'GAIN.cbf'):
        return {'step': 'initialize', 'success':True}
    else:
        return {'step': 'initialize','success': False, 'reason': 'Could not create correction tables'}


def analyse_image(data_info, options={}):
    os.chdir(data_info['working_directory'])
    _logger.info('Analyzing reference image ...')

    try:
        programs.distl(data_info['reference_image'])
    except dpm.errors.ProcessError, e:
        return {'step': 'image_analysis', 'success':False, 'reason': str(e)}
    
    if not misc.file_requirements('distl.log'):
        return {'step': 'image_analysis', 'success': False, 'reason': 'Could not analyse reference image'}
    info = distl.parse_distl('distl.log')
    return {'step': 'image_analysis', 'success': True, 'data': info}
    

def find_spots(data_info, options={}):
    os.chdir(data_info['working_directory'])
    _logger.info('Searching for strong spots ...')

    run_info = {}
    run_info.update(data_info)
    
    io.write_xds_input('COLSPOT', run_info)
    try:
        programs.xds_par()
    except dpm.errors.ProcessError, e:
        return {'step': 'spot_search','success': False, 'reason': str(e)}

    if misc.file_requirements('SPOT.XDS'):
        return {'step': 'spot_search','success': True}
    else:
        return {'step': 'spot_search','success':False, 'reason': 'Could not find spots.'}