import os
import time

from dpm.parser import xds, ccp4
from dpm.utils import log, misc, programs, io, xtal
import dpm.errors

_logger = log.get_module_logger(__name__)

def _check_chisq(result):
    # check correction factors
    if result.get('correction_factors') is not None:
        for f in result['correction_factors'].get('factors', []):
            if (f['chi_sq_fit']-1.0) > 0.25:
                return False
    return True

  
def scale_datasets(dsets, options={}):
    os.chdir(options['directory'])
    
    # indicate overwritten parameters
    _suffix = []
    if options.get('resolution'):
        _suffix.append("res=%0.2f" % options.get('resolution'))
    if len(_suffix) > 0: 
        _logger.info("Re-scaling ... (%s)" % ",".join(_suffix))
    else:
        _logger.info("Scaling ... ")
    
      
    # Check Requirements
    for dset in dsets.values():
        if dset.results.get('correction') is None:
            return {'step': 'scaling', 'success': False, 'reason': 'Can only scale after successful correction'}
            
    mode = options.get('mode', 'simple')
    if mode == 'mad':
        sections = []
        for dset in dsets.values():
            dres = dset.results
            resol = options.get('resolution', dres['correction']['summary']['resolution'][0])
            in_file = dres['correction']['output_file']
            out_file = os.path.join(dset.name, "XSCALE.HKL")
            sections.append(
                {'anomalous': options.get('anomalous', False),
                 'strict_absorption': _check_chisq(dres['correction']),
                 'output_file': out_file,
                 'crystal': 'cryst1',
                 'inputs': [{'input_file': in_file, 'resolution': resol}],
                })
            if options.get('backup', False):
                misc.backup_files(out_file, 'XSCALE.LP')
            dset.results['scaling'] = {'output_file': out_file}
    else:
        inputs = []
        for dset in dsets.values():
            dres = dset.results
            resol = options.get('resolution', dres['correction']['summary']['resolution'][0])
            in_file = dres['correction']['output_file']
            inputs.append({'input_file': in_file, 'resolution': resol})
        sections = [{
            'anomalous': options.get('anomalous', False),
            'strict_absorption': _check_chisq(dres['correction']),
            'output_file': "XSCALE.HKL",
            'inputs': inputs,}]
        if options.get('backup', False):
            misc.backup_files('XSCALE.HKL', 'XSCALE.LP')


    xscale_options = {
        'sections': sections
        }
    
    io.write_xscale_input(xscale_options)
    try:
        programs.xscale_par()
        raw_info = xds.parse_xscale('XSCALE.LP')
    except dpm.errors.ProcessError, e:       
        for dset in dsets.values():
            dset.log.append((time.time(), 'scaling', False, e.value))
        return {'step': 'scaling', 'success': False, 'reason': e.value}

    if len(raw_info.keys()) == 1:
        info = raw_info.values()[0]
        info['output_file'] = 'XSCALE.HKL'
        for i, dset in enumerate(dsets.values()):           
            try:
                _logger.info("(%s) Calculating extra statistics ..." % dset.name)
                programs.xdsstat(dset.results['correction']['output_file'])
                stat_info = xds.parse_xdsstat()
                dset.results['correction'].update(stat_info)           
            except dpm.errors.ProcessError, e:
                dset.log.append((time.time(), 'frame_statistics', False, e.value))
                return {'step': 'scaling', 'success': False, 'reason': e.value}

            if i == 0:
                # Set resolution
                if options.get('resolution'):
                    resol = (options.get('resolution'), 4)
                else:
                    resol = xtal.select_resolution(info['statistics'])
                info['summary']['resolution'] = resol
                dset.results['scaling'] = info
                dset.log.append((time.time(), 'scaling', True, None))
    else:
        for name, info in raw_info.items():
            dset = dsets[name]
            # Set resolution
            if options.get('resolution'):
                resol = (options.get('resolution'), 4)
            else:
                resol = xtal.select_resolution(info['statistics'])
            info['summary']['resolution'] = resol
            try:
                _logger.info("(%s) Calculating extra statistics ..." % (name))
                programs.xdsstat(dset.results['correction']['output_file'])
                stat_info = xds.parse_xdsstat()
                dset.results['correction'].update(stat_info)
            except dpm.errors.ProcessError, e:
                dset.log.append((time.time(), 'frame_statistics', False, e.value))
                return {'step': 'scaling', 'success': False, 'reason': e.value}
            
            dsets[name].results['scaling'].update(info)
            dsets[name].log.append((time.time(), 'scaling', True, None))

    return {'step': 'scaling', 'success': True}


def data_quality(filename, options={}):
    os.chdir(options['directory'])
    _logger.info('Checking data quality ...')
        
    # Check Requirements
    if not misc.file_requirements(filename):
        return {'step': 'data_quality', 'success': False, 'reason': 'Required files missing'}
    
    try:
        programs.ccp4check(filename)
        info = ccp4.parse_ctruncate()
        sf_info = ccp4.parse_sfcheck()
        info.update(sf_info)
    except dpm.errors.ProcessError, e:
        return {'step': 'data_quality', 'success':False, 'reason': e.value}
    return {'step': 'data_quality','success': True, 'data': info}


    