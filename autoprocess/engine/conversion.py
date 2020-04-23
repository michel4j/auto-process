import os

import autoprocess.errors
from autoprocess.utils import programs, misc, log, xdsio

logger = log.get_module_logger(__name__)


def convert_formats(dataset, options=None):
    options = options or {}
    os.chdir(options['directory'])

    # GENERATE MTZ and CNS output files
    infile = dataset.results['scaling'].get('output_file')
    out_file_dir = os.path.dirname(infile)
    out_file_base = os.path.basename(infile)
    out_file_root = os.path.join(out_file_dir, options.get('file_root', dataset.name))
    output_files = []

    logger.info('Generating MTZ, SHELX & CNS files from {} ...'.format(out_file_base))
    if not misc.file_requirements(dataset.results['scaling'].get('output_file')):
        return {'step': 'conversion', 'success': False, 'reason': 'Required files missing'}

    # Create convertion options
    conv_options = [
        {
            'resolution': 0,
            'format': 'CNS',
            'anomalous': options.get('anomalous', False),
            'input_file': infile,
            'output_file': out_file_root + ".cns",
            'freeR_fraction': 0.05
        }, {
            'resolution': 0,
            'format': 'SHELX',
            'anomalous': options.get('anomalous', False),
            'input_file': infile,
            'output_file': out_file_root + "-shelx.hkl",
            'freeR_fraction': 0,
        }, {
            'resolution': 0,
            'format': 'CCP4_I',
            'anomalous': True,
            'input_file': infile,
            'output_file': out_file_root + ".ccp4i",
            'freeR_fraction': 0.05,
        }
    ]

    for opt in conv_options:
        try:
            if opt['format'] == 'CCP4_I':
                out_file = out_file_root + ".mtz"
                out_format = 'MTZ'
            else:
                out_file = opt['output_file']
                out_format = opt['format']

            xdsio.write_xdsconv_input(opt)
            label = f'Preparing {out_format} output file'
            programs.xdsconv(label=f'{label:<27}', final=log.TermColor.bold(out_file))

            # Special formatting for MTZ
            if opt['format'] == 'CCP4_I':
                mtz_file = out_file_root + ".mtz"
                programs.f2mtz(mtz_file)
                output_files.append(mtz_file)
            else:
                output_files.append(opt['output_file'])

        except autoprocess.errors.ProcessError as e:
            logger.warning(f'Error creating {opt["format"]} file: {e}')

    if len(output_files) == 0:
        return {'step': 'conversion', 'success': False, 'reason': 'No output files generated'}
    else:
        return {'step': 'conversion', 'success': True, 'data': output_files}
