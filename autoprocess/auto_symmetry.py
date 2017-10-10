#!/usr/bin/env python


import sys
import warnings
warnings.simplefilter("ignore") # ignore deprecation warnings

import autoprocess.errors
from autoprocess.engine.process import Manager
from autoprocess.utils import log
from autoprocess.utils.options import symmetry_options
from autoprocess.utils import misc


_logger = log.get_module_logger('auto.symmetry')

def main():
    # Parse options
    try:
        options = symmetry_options(sys.argv[1:])
    except autoprocess.errors.InvalidOption, e:
        _logger.error(str(e))
        sys.exit(1)
        
    try:
        chkpt = misc.json.loads(file('checkpoint.json').read())
    except IOError:
        _logger.error('This command must be run within a data processing directory.')
        sys.exit(1)
    app = Manager(checkpoint=chkpt)
    app.run(resume_from=(chkpt['run_position'][0],'symmetry'), overwrite=options)      
     
def run():
    try:
        log.log_to_console()
        main()
    except KeyboardInterrupt:
        sys.exit(1)
