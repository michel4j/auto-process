#!/usr/bin/env python


import sys
import os
import warnings
warnings.simplefilter("ignore") # ignore deprecation warnings
    
from autoprocess.engine.process import Manager
from autoprocess.utils import log
from autoprocess.utils.options import integrate_options
from autoprocess.utils import misc

_logger = log.get_module_logger('auto.integrate')

def main():
    # Parse options
    options = integrate_options(sys.argv[1:])
    try:
        chkpt = misc.load_chkpt()
    except IOError:
        _logger.error('This command must be run within a data processing directory.')
        sys.exit(1)
    app = Manager(checkpoint=chkpt)
    
    # update app and overwrite options
    ow = {}
    if options.get('anomalous') is not None:
        app.options['anomalous'] = options.get('anomalous')
    if options.get('frames'):
        ow.update(data_range=options.get('frames'), skip_frames=options.get('skip_frames'))
    if options.get('exclude'):
        ow.update(skip_range=options.get('exclude'))
    app.options['backup'] = options.get('backup', False)
    app.run(resume_from=(chkpt['run_position'][0],'integration'), overwrite=ow)
     
def run():
    try:
        log.log_to_console()
        main()
    except KeyboardInterrupt:
        sys.exit(1)
