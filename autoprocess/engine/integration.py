import os
import shutil

import autoprocess.errors
from autoprocess.parsers import xds
from autoprocess.utils import log, misc, programs, xtal, xdsio

logger = log.get_module_logger(__name__)


def harvest_integrate():
    if not misc.file_requirements('INTEGRATE.LP', 'CORRECT.LP'):
        return {'step': 'integration', 'success': False, 'reason': 'Required files missing'}
    else:
        info = xds.parse_integrate()
        info['statistics'] = xds.parse_correct()

    if info.get('failure') is None:
        info['output_file'] = 'INTEGRATE.HKL'
        return {'step': 'integration', 'success': True, 'data': info}
    else:
        return {'step': 'integration', 'success': False, 'reason': info['failure']}


def integrate(data_info, options=None):
    options = {} if options is None else options
    os.chdir(data_info['working_directory'])
    run_info = {'mode': options.get('mode')}
    run_info.update(data_info)
    if options.get('backup', False):
        misc.backup_files('INTEGRATE.LP', 'INTEGRATE.HKL')

    # if optimizing the integration, copy GXPARM
    # Calculate actual number of frames
    full_range = list(range(run_info['data_range'][0], run_info['data_range'][1] + 1))
    skip_ranges = []
    for r_s, r_e in run_info['skip_range']:
        skip_ranges.extend(list(range(r_s, r_e + 1)))
    num_frames = len(set(full_range) - set(skip_ranges))

    if options.get('optimize', False) and os.path.exists('GXPARM.XDS'):
        misc.backup_files('XPARM.XDS')
        shutil.copy('GXPARM.XDS', 'XPARM.XDS')
        step_descr = 'Optimizing {:d} frames of dataset {}'.format(
            num_frames, log.TermColor.italics(data_info['name'])
        )
    else:
        step_descr = 'Integrating {:d} frames of dataset {}'.format(
            num_frames, log.TermColor.italics(data_info['name'])
        )

    # check if we are screening
    screening = options.get('mode') == 'screen'

    xdsio.write_xds_input("DEFPIX INTEGRATE", run_info)
    if not misc.file_requirements('X-CORRECTIONS.cbf', 'Y-CORRECTIONS.cbf', 'XPARM.XDS'):
        return {'step': 'integration', 'success': False, 'reason': 'Required files missing'}


    try:
        programs.xds_par(step_descr)
        info = xds.parse_integrate()
    except autoprocess.errors.ProcessError as e:
        return {'step': 'integration', 'success': False, 'reason': str(e)}
    except:
        return {'step': 'integration', 'success': False, 'reason': "Could not parse integrate output file"}
    else:
        pass

    if info.get('failure') is None:
        if data_info['working_directory'] == options.get('directory'):
            info['output_file'] = 'INTEGRATE.HKL'
        else:
            info['output_file'] = os.path.join(data_info['name'], 'INTEGRATE.HKL')
        return {'step': 'integration', 'success': True, 'data': info}
    else:
        return {'step': 'integration', 'success': False, 'reason': info['failure']}


def harvest_correct():
    if not misc.file_requirements('CORRECT.LP', 'GXPARM.XDS', 'XDS_ASCII.HKL'):
        return {'step': 'integration', 'success': False, 'reason': 'Required files missing'}
    else:
        info = xds.parse_integrate()
        programs.xdsstat('XDS_ASCII.HKL')
        stat_info = xds.parse_xdsstat()
        info.update(stat_info)

    if info.get('failure') is None:
        info['output_file'] = 'XDS_ASCII.HKL'
        if len(info.get('statistics', [])) > 1 and info.get('summary') is not None:
            info['summary']['resolution'] = xtal.select_resolution(info['statistics'])

        return {'step': 'correction', 'success': True, 'data': info}
    else:
        return {'step': 'correction', 'success': False, 'reason': info['failure']}


def correct(data_info, options=None):
    options = options or {}
    os.chdir(data_info['working_directory'])
    message = options.get('message', "Applying corrections to")
    step_descr = '{} dataset "{}" for space-group {}'.format(
        message,
        data_info['name'],
        xtal.SG_SYMBOLS[data_info['space_group']]
    )
    run_info = {'mode': options.get('mode')}
    run_info.update(data_info)

    if not misc.file_requirements('INTEGRATE.HKL', 'X-CORRECTIONS.cbf', 'Y-CORRECTIONS.cbf'):
        return {'step': 'correction', 'success': False, 'reason': 'Required files missing'}

    if options.get('backup', False):
        misc.backup_files('XDS_ASCII.HKL', 'CORRECT.LP')
    xdsio.write_xds_input("CORRECT", run_info)

    try:
        programs.xds_par(step_descr)
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
            sub_dir = os.path.relpath(data_info['working_directory'], options.get('directory', ''))
            info['output_file'] = os.path.join(sub_dir, 'XDS_ASCII.HKL')

        programs.xdsstat('XDS_ASCII.HKL')
        stat_info = xds.parse_xdsstat()
        info.update(stat_info)

    except autoprocess.errors.ProcessError as e:
        return {'step': 'correction', 'success': False, 'reason': str(e)}

    if info.get('failure') is None:
        if len(info.get('statistics', [])) > 1 and info.get('summary') is not None:
            info['summary']['resolution'] = xtal.select_resolution(info['statistics'])

        return {'step': 'correction', 'success': True, 'data': info}
    else:
        return {'step': 'correction', 'success': False, 'reason': info['failure']}
