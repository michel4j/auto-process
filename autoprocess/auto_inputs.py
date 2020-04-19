#!/usr/bin/env python


import sys
import warnings

warnings.simplefilter("ignore")  # ignore deprecation warnings

from autoprocess.engine.process import DataSet
from autoprocess.utils import options, log, xdsio

_logger = log.get_module_logger('auto.process')


def main():
    # Parse options
    opt = options.process_options(sys.argv[1:], options.INPUTS_USAGE)

    if len(opt['images']) >= 1:
        dataset = DataSet(filename=opt['images'][0])
        _logger.info('Creating XDS.INP ...')
        xdsio.write_xds_input('ALL !XYCORR INIT COLSPOT IDXREF DEFPIX INTEGRATE CORRECT', dataset.parameters)
    else:
        _logger.error('No image specified.')
        print(options.INPUTS_USAGE)
        sys.exit(1)


def run():
    try:
        log.log_to_console()
        main()
    except KeyboardInterrupt:
        sys.exit(1)
