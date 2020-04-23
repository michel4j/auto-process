import os
import shutil

import autoprocess.errors
from autoprocess.parsers import best, xds
from autoprocess.utils import log, misc, programs, xdsio

_logger = log.get_module_logger(__name__)


def calc_strategy(data_info, options=None):
    options = options or {}
    os.chdir(data_info['working_directory'])

    # indicate overwritten parameters
    suffix = []
    if options.get('resolution'):
        suffix.append("res=%0.2f" % options.get('resolution'))
    if options.get('anomalous'):
        suffix.append("anomalous")

    if len(suffix) > 0:
        step_descr = "Calculating strategy [{}]".format(", ".join(suffix))
    else:
        step_descr = 'Calculating strategy'

    if not misc.file_requirements('CORRECT.LP', 'BKGPIX.cbf', 'XDS_ASCII.HKL', 'GXPARM.XDS'):
        return {'step': 'strategy', 'success': False, 'reason': 'Required files from integration missing'}

    if os.path.exists('GXPARM.XDS'):
        misc.backup_files('XPARM.XDS')
        shutil.copy('GXPARM.XDS', 'XPARM.XDS')
    run_info = {'mode': options.get('mode'), 'anomalous': options.get('anomalous', False)}
    run_info.update(data_info)
    xdsio.write_xds_input("XPLAN", run_info)

    try:
        programs.xds_par(step_descr)
        info = xds.parse_xplan()

        programs.best(data_info, options)
        info.update(best.parse_best())
    except autoprocess.errors.ProcessError as e:
        return {'step': 'strategy', 'success': True, 'reason': str(e), 'data': info}

    return {'step': 'strategy', 'success': True, 'data': info}
