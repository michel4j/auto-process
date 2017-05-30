import os
import shutil
import json

from dpm.parser import best, xds
from dpm.utils import log, misc, programs, io
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
    
    if not misc.file_requirements('CORRECT.LP',  'BKGPIX.cbf', 'XDS_ASCII.HKL', 'GXPARM.XDS'):
        return {'step': 'strategy', 'success': False, 'reason': 'Required files from integration missing'}

    if os.path.exists('GXPARM.XDS'):
        misc.backup_files('XPARM.XDS')
        shutil.copy('GXPARM.XDS', 'XPARM.XDS')

    run_info = {'mode': options.get('mode'), 'anomalous': options.get('anomalous', False)}
    run_info.update(data_info)
    io.write_xds_input("XPLAN", run_info)
    
    try:
        info = {
            'runs': [],
            'prediction_all': {},
            'prediction_hi': {},
            'details': {}
        }

        programs.xds_par()
        xplan = xds.parse_xplan()
        idxinfo = xds.parse_idxref()
        xplan['max_delta'] = {
            'resolution': [entry['resolution'] for entry in idxinfo['oscillation_ranges']],
            'delta': [entry['delta_angle'] - idxinfo['summary']['mosaicity'] for entry in idxinfo['oscillation_ranges']],
        }
        info['xplan'] = xplan

        programs.best(data_info, options)
        info.update(best.parse_best())
    except dpm.errors.ProcessError, e:
        return {'step': 'strategy', 'success': True, 'reason': str(e)}
    
    return {'step': 'strategy', 'success': True, 'data': info}