import os

import autoprocess.errors
from autoprocess.parsers import distl
from autoprocess.utils import log, misc, programs, xdsio

_logger = log.get_module_logger(__name__)


def harvest_initialize():
    if misc.file_requirements('X-CORRECTIONS.cbf', 'Y-CORRECTIONS.cbf', 'BKGINIT.cbf', 'BLANK.cbf', 'GAIN.cbf'):
        return {'step': 'initialize', 'success': True}
    else:
        return {'step': 'initialize', 'success': False, 'reason': 'Initialization unsuccessful!'}


def initialize(data_info, options=None):
    options = options or {}
    os.chdir(data_info['working_directory'])

    run_info = {'mode': options.get('mode')}
    run_info.update(data_info)

    xdsio.write_xds_input('XYCORR INIT', run_info)
    try:
        programs.xds_par('Initializing')
    except autoprocess.errors.ProcessError as e:
        return {'step': 'initialize', 'success': False, 'reason': str(e)}

    return harvest_initialize()


def analyse_image(data_info, options=None):
    options = options or {}
    os.chdir(data_info['working_directory'])
    _logger.info('Analyzing reference image ...')

    try:
        programs.distl(data_info['reference_image'])
    except autoprocess.errors.ProcessError as e:
        return {'step': 'image_analysis', 'success': False, 'reason': str(e)}

    if not misc.file_requirements('distl.log'):
        return {'step': 'image_analysis', 'success': False, 'reason': 'Could not analyse reference image'}
    info = distl.parse_distl('distl.log')
    return {'step': 'image_analysis', 'success': True, 'data': info}


def harvest_spots():
    if misc.file_requirements('SPOT.XDS'):
        return {'step': 'spot_search', 'success': True}
    else:
        return {'step': 'spot_search', 'success': False, 'reason': 'Could not find spots.'}


def find_spots(data_info, options=None):
    options = options or {}
    os.chdir(data_info['working_directory'])

    run_info = {'mode': options.get('mode')}
    run_info.update(data_info)

    xdsio.write_xds_input('COLSPOT', run_info)
    try:
        programs.xds_par('Searching for strong spots')
    except autoprocess.errors.ProcessError as e:
        return {'step': 'spot_search', 'success': False, 'reason': str(e)}

    return harvest_spots()
