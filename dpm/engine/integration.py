import os
import shutil
from dpm.parser import xds
from dpm.utils.progress import ProgDisplay, ProgChecker
from dpm.utils import log, misc, programs, xtal, io
import dpm.errors

_logger = log.get_module_logger(__name__)


def integrate(data_info, options={}):
    os.chdir(data_info['working_directory'])
    _logger.info('Integrating ...')
    run_info = {}
    run_info.update(data_info)
    if options.get('backup', False):
        misc.backup_files('INTEGRATE.LP', 'INTEGRATE.HKL')
    
    # if optimizing the integration, copy GXPARM
    if options.get('optimize', False) and os.path.exists('GXPARM.XDS'):
        misc.backup_files('XPARM.XDS')
        shutil.copy('GXPARM.XDS', 'XPARM.XDS')

    io.write_xds_input("DEFPIX INTEGRATE", run_info)
    if not misc.file_requirements('X-CORRECTIONS.cbf', 'Y-CORRECTIONS.cbf', 'XPARM.XDS'):
        return {'step': 'integration', 'success': False, 'reason': 'Required files missing'}
    _pc = ProgChecker(os.sysconf('SC_NPROCESSORS_ONLN'))
    _pd = ProgDisplay(data_info['data_range'], _pc.queue)
    _pd.start()
    _pc.start()
    try:
        programs.xds_par()
        info = xds.parse_integrate()
    except dpm.errors.ProcessError, e:
        return {'step': 'integration', 'success':False, 'reason': str(e)}
    _pd.stop()
    _pc.stop()
    
    if info.get('failure') is None:
        if data_info['working_directory'] == options.get('directory'):
            info['output_file'] = 'INTEGRATE.HKL'
        else:
            info['output_file'] = os.path.join(data_info['name'], 'INTEGRATE.HKL')
        return {'step': 'integration','success': True, 'data': info}
    else:
        return {'step': 'integration','success': False, 'reason': info['failure']}


def correct(data_info, options={}):
    os.chdir(data_info['working_directory'])
    _logger.info('Correcting ... ')
    run_info = {}
    run_info.update(data_info)

    if not misc.file_requirements('INTEGRATE.HKL','X-CORRECTIONS.cbf', 'Y-CORRECTIONS.cbf'):
        return {'step': 'correction', 'success': False, 'reason': 'Required files missing'}
    
    if options.get('backup', False):
        misc.backup_files('XDS_ASCII.HKL', 'CORRECT.LP')
    io.write_xds_input("CORRECT", run_info)
    
    try:
        programs.xds_par()
        info = xds.parse_correct()
    
        # enable correction factors if anomalous data and repeat correction   
        if info.get('correction_factors') is not None and options.get('anomalous', False):
            for f in info['correction_factors'].get('factors', []):
                if abs(f['chi_sq_fit']-1.0) > 0.25:
                    run_info.update({'strict_absorption': True})
                    io.write_xds_input("CORRECT", run_info)
                    programs.xds_par()
                    info = xds.parse_correct()
                    info['strict_absorption'] = True
                    break
    except dpm.errors.ProcessError, e:
        return {'step': 'correction', 'success': False, 'reason': str(e)}
                          
    if info.get('failure') is None:
        if info.get('statistics') is not None and len(info['statistics']) > 1:
            if info.get('summary') is not None:
                info['summary']['resolution'] = xtal.select_resolution(info['standard_errors'])
                info['summary'].update( info['statistics'][-1] )
                del info['summary']['shell']
        if data_info['working_directory'] == options.get('directory'):
            info['output_file'] = 'XDS_ASCII.HKL'
        else:
            info['output_file'] = os.path.join(data_info['name'], 'XDS_ASCII.HKL')
        
        return {'step': 'correction', 'success':True, 'data': info}
    else:
        return {'step': 'correction', 'success':False, 'reason': info['failure']}
