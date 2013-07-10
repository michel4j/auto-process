#!/usr/bin/env python


import sys
import warnings
warnings.simplefilter("ignore") # ignore deprecation warnings
    
from dpm.engine.process import DataSet
from dpm.utils import options, log, io

_logger = log.get_module_logger('auto.process')

def main():
    # Parse options
    opt = options.process_options(sys.argv[1:], options.INPUTS_USAGE)
    
    if len(opt['images']) >= 1:
        dset = DataSet(filename=opt['images'][0])
        _logger.info('Creating XDS.INP ...')
        io.write_xds_input('ALL !XYCORR INIT COLSPOT IDXREF DEFPIX INTEGRATE CORRECT', dset.parameters)
    else:
        _logger.error('No image specified.')
        print options.INPUTS_USAGE
        sys.exit(1)
          
def run():
    try:
        log.log_to_console()
        main()
    except KeyboardInterrupt:
        sys.exit(1)
