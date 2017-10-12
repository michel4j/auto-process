import os

import autoprocess.errors
from autoprocess.utils import programs, misc, log, xdsio

_logger = log.get_module_logger(__name__)

def convert_formats(dset, options={}):
    os.chdir(options['directory'])
    
    # GENERATE MTZ and CNS output files    

    infile = dset.results['scaling'].get('output_file')
    out_file_dir = os.path.dirname(infile)
    out_file_base = os.path.basename(infile)
    out_file_root = os.path.join(out_file_dir, options.get('file_root', dset.name))
    output_files = []

    _logger.info('Generating MTZ, SHELX & CNS files for `%s` ...' % out_file_base)
    if not misc.file_requirements(dset.results['scaling'].get('output_file')):
        return {'step': 'conversion', 'success': False, 'reason': 'Required files missing'}
    

    # Create convertion options
    conv_options = []
    conv_options.append({
        'resolution': 0,
        'format': 'CNS',
        'anomalous': options.get('anomalous', False),
        'input_file': infile,
        'output_file': out_file_root + ".cns",
        'freeR_fraction': 0.05}) # CNS
    conv_options.append({
        'resolution': 0,
        'format': 'SHELX',
        'anomalous': options.get('anomalous', False),
        'input_file': infile,
        'output_file': out_file_root + "-shelx.hkl",
        'freeR_fraction': 0,}) # SHELX
    conv_options.append({
        'resolution': 0,
        'format': 'CCP4_F',
        'anomalous': True,
        'input_file': infile,
        'output_file': out_file_root + ".ccp4f",
        'freeR_fraction': 0.05,}) # CCP4F for MTZ
    
    for opt in conv_options:
        try:
            xdsio.write_xdsconv_input(opt)
            programs.xdsconv()
            
            # Special formatting for MTZ
            if opt['format'] == 'CCP4_F':     
                mtz_file =   out_file_root + ".mtz"        
                programs.f2mtz(mtz_file)
                output_files.append(mtz_file)
            else:
                output_files.append(opt['output_file'])
                
        except autoprocess.errors.ProcessError, e:
            _logger.warning('Error creating %s file: %s' % (opt['format'], e))
   
    if len(output_files) == 0:
        return {'step': 'conversion', 'success': False, 'reason': 'No output files generated'}
    else:
        return {'step': 'conversion', 'success': True, 'data': output_files}