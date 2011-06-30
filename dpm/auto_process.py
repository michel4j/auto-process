#!/usr/bin/env python


import sys
import os
import warnings
warnings.simplefilter("ignore") # ignore deprecation warnings
    
from dpm.engine.process import Manager
from dpm.utils import log
from dpm.utils import options
from dpm.utils import misc
import dpm.errors

_logger = log.get_module_logger('auto.process')

def main():
    # Parse options
    opt = options.process_options(sys.argv[1:])
    if len(opt['images']) >= 1:
        app = Manager(options=opt)
        app.run()      
    else:
        try:
            chkpt = misc.json.loads(file('checkpoint.json').read())
            app = Manager(checkpoint=chkpt, options=opt)
            app.run(resume_from=chkpt['run_position'])
        except IOError:
            _logger.error('Either specify a dataset, or run within a data processing directory.')
            print options.PROCESS_USAGE
            sys.exit(1)
          
if __name__ == "__main__":
    try:
        log.log_to_console()
        main()
    except KeyboardInterrupt:
        sys.exit(1)