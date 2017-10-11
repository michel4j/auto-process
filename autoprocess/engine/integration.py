import multiprocessing
import os
import shutil

import autoprocess.errors
from autoprocess.parser import xds
from autoprocess.utils import log, misc, programs, xtal, xdsio
from autoprocess.utils.progress import FileProgressDisplay, ProgDisplay, ProgChecker

_logger = log.get_module_logger(__name__)


def integrate(data_info, options={}):
    os.chdir(data_info['working_directory'])
    run_info = {'mode': options.get('mode')}
    run_info.update(data_info)
    if options.get('backup', False):
        misc.backup_files('INTEGRATE.LP', 'INTEGRATE.HKL')

    # if optimizing the integration, copy GXPARM
    # Calculate actual number of frames
    full_range = range(run_info['data_range'][0], run_info['data_range'][1] + 1)
    skip_ranges = []
    for r_s, r_e in run_info['skip_range']:
        skip_ranges.extend(range(r_s, r_e + 1))
    num_frames = len(set(full_range) - set(skip_ranges))

    if options.get('optimize', False) and os.path.exists('GXPARM.XDS'):
        misc.backup_files('XPARM.XDS')
        shutil.copy('GXPARM.XDS', 'XPARM.XDS')
        step_descr = 'Optimizing %d frames of `%s` ...' % (num_frames, data_info['name'])
    else:
        step_descr = 'Integrating %d frames of `%s` ...' % (num_frames, data_info['name'])

    # check if we are screening
    _screening = options.get('mode') == 'screen'

    xdsio.write_xds_input("DEFPIX INTEGRATE", run_info)
    if not misc.file_requirements('X-CORRECTIONS.cbf', 'Y-CORRECTIONS.cbf', 'XPARM.XDS'):
        return {'step': 'integration', 'success': False, 'reason': 'Required files missing'}

    _pd = FileProgressDisplay('PROGRESS', descr=step_descr)

    try:
        _pd.start()
        programs.xds_par()
        info = xds.parse_integrate()
    except autoprocess.errors.ProcessError, e:
        _pd.stop()

        return {'step': 'integration', 'success': False, 'reason': str(e)}
    except:
        _pd.stop()

        return {'step': 'integration', 'success': False, 'reason': "Could not parse integrate output file"}
    else:
        _pd.stop()

    _pd.join()

    if info.get('failure') is None:
        if data_info['working_directory'] == options.get('directory'):
            info['output_file'] = 'INTEGRATE.HKL'
        else:
            info['output_file'] = os.path.join(data_info['name'], 'INTEGRATE.HKL')
        return {'step': 'integration', 'success': True, 'data': info}
    else:
        return {'step': 'integration', 'success': False, 'reason': info['failure']}


def correct(data_info, options={}):
    os.chdir(data_info['working_directory'])
    message = options.get('message', "Applying corrections to")
    _logger.info(
        '%s `%s` in `%s` ... ' % (message, data_info['name'], xtal.SPACE_GROUP_NAMES[data_info['space_group']]))
    run_info = {'mode': options.get('mode')}
    run_info.update(data_info)

    if not misc.file_requirements('INTEGRATE.HKL', 'X-CORRECTIONS.cbf', 'Y-CORRECTIONS.cbf'):
        return {'step': 'correction', 'success': False, 'reason': 'Required files missing'}

    if options.get('backup', False):
        misc.backup_files('XDS_ASCII.HKL', 'CORRECT.LP')
    xdsio.write_xds_input("CORRECT", run_info)

    try:
        programs.xds_par()
        info = xds.parse_correct()

        # enable correction factors if anomalous data and repeat correction
        if info.get('correction_factors') is not None and options.get('anomalous', False):
            for f in info['correction_factors'].get('factors', []):
                if abs(f['chi_sq_fit'] - 1.0) > 0.25:
                    run_info.update({'strict_absorption': True})
                    xdsio.write_xds_input("CORRECT", run_info)
                    programs.xds_par()
                    info = xds.parse_correct()
                    info['strict_absorption'] = True
                    break

        # Extra statistics
        if data_info['working_directory'] == options.get('directory'):
            info['output_file'] = 'XDS_ASCII.HKL'
        else:
            info['output_file'] = os.path.join(data_info['name'], 'XDS_ASCII.HKL')

        programs.xdsstat('XDS_ASCII.HKL')
        stat_info = xds.parse_xdsstat()
        info.update(stat_info)

    except autoprocess.errors.ProcessError, e:
        return {'step': 'correction', 'success': False, 'reason': str(e)}

    if info.get('failure') is None:
        if len(info.get('statistics', [])) > 1 and info.get('summary') is not None:
            info['summary']['resolution'] = xtal.select_resolution(info['statistics'])

        return {'step': 'correction', 'success': True, 'data': info}
    else:
        return {'step': 'correction', 'success': False, 'reason': info['failure']}
