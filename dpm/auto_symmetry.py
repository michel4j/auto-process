#!/usr/bin/env python


import sys
import os
import warnings
warnings.simplefilter("ignore") # ignore deprecation warnings

import dpm.errors
from dpm.engine.process import Manager
from dpm.utils import log
from dpm.utils.options import symmetry_options
from dpm.utils import misc


_logger = log.get_module_logger('auto.symmetry')

def main():
    # Parse options
    try:
        options = symmetry_options(sys.argv[1:])
    except dpm.errors.InvalidOption, e:
        _logger.error(str(e))
        sys.exit(1)
        
    try:
        chkpt = misc.json.loads(file('checkpoint.json').read())
    except IOError:
        _logger.error('This command must be run within a data processing directory.')
        sys.exit(1)
    app = Manager(checkpoint=chkpt)
    app.run(resume_from=(chkpt['run_position'][0],'symmetry'), overwrite=options)      
     
if __name__ == "__main__":
    try:
        log.log_to_console()
        main()
    except KeyboardInterrupt:
        sys.exit(1)
