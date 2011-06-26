import os

from dpm.parser import best
from dpm.utils import log, misc, programs
import dpm.errors

_logger = log.get_module_logger(__name__)


def calc_strategy(data_info, options={}):
    os.chdir(data_info['working_directory'])

    # indicate overwritten parameters
    _suffix = []
    if options.get('resolution'):
        _suffix.append("res=%0.2f" % options.get('resolution'))
    if options.get('anomalous', None) is not None:
        _suffix.append("anom=%s" % options.get('anomalous'))
    if len(_suffix) > 0: 
        _logger.info("Calculating strategy ... (%s)" % ",".join(_suffix))
    else:
        _logger.info('Calculating strategy ...')
    
    if not misc.file_requirements('CORRECT.LP',  'BKGPIX.cbf', 'XDS_ASCII.HKL'):
        return {'step': 'strategy', 'success': False, 'reason': 'Required files from integration missing'}
    
    try:
        programs.best(data_info, options)
        info = best.parse_best()
    except dpm.errors.ProcessError, e:
        return {'step': 'strategy', 'success': False, 'reason': e.value}
    
    return {'step': 'strategy', 'success': True, 'data': info}