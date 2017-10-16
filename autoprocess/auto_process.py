#!/usr/bin/env python


import sys
import os
import warnings
warnings.simplefilter("ignore") # ignore deprecation warnings
    
from autoprocess.engine.process import Manager
from autoprocess.utils import log
from autoprocess.utils import options
from autoprocess.utils import misc
import autoprocess.errors

_logger = log.get_module_logger('auto.process')

def main():
    # Parse options
    opt = options.process_options(sys.argv[1:])
    if len(opt['images']) >= 1:
        app = Manager(options=opt)
        app.run()      
    else:
        try:
            chkpt = misc.load_chkpt()
            app = Manager(checkpoint=chkpt, options=opt)
            if opt.get('zap', False):
                app.run()
            else:                
                app.run(resume_from=opt.get('resume_from', chkpt['run_position']))
        except IOError:
            _logger.error('Either specify a dataset, or run within a data processing directory.')
            print options.PROCESS_USAGE
            sys.exit(1)
          
def run():
    try:
        log.log_to_console()
        main()
    except KeyboardInterrupt:
        sys.exit(1)
