import os

from autoprocess.parser import distl
from autoprocess.utils import log, misc, programs, xdsio
import autoprocess.errors

_logger = log.get_module_logger(__name__)


def initialize(data_info, options={}):
    os.chdir(data_info['working_directory'])

    run_info = {'mode': options.get('mode')}
    run_info.update(data_info)
    
    xdsio.write_xds_input('XYCORR INIT', run_info)
    try:
        programs.xds_par()
    except autoprocess.errors.ProcessError as e:
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
    except autoprocess.errors.ProcessError as e:
        return {'step': 'image_analysis', 'success':False, 'reason': str(e)}
    
    if not misc.file_requirements('distl.log'):
        return {'step': 'image_analysis', 'success': False, 'reason': 'Could not analyse reference image'}
    info = distl.parse_distl('distl.log')
    return {'step': 'image_analysis', 'success': True, 'data': info}
    

def find_spots(data_info, options={}):
    os.chdir(data_info['working_directory'])
    _logger.info('Searching for strong spots ...')

    run_info = {'mode': options.get('mode')}
    run_info.update(data_info)
    
    xdsio.write_xds_input('COLSPOT', run_info)
    try:
        programs.xds_par()
    except autoprocess.errors.ProcessError as e:
        return {'step': 'spot_search','success': False, 'reason': str(e)}

    if misc.file_requirements('SPOT.XDS'):
        return {'step': 'spot_search','success': True}
    else:
        return {'step': 'spot_search','success':False, 'reason': 'Could not find spots.'}