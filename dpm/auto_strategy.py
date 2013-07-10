#!/usr/bin/env python


import sys
import warnings
warnings.simplefilter("ignore") # ignore deprecation warnings
    
from dpm.engine.process import Manager
from dpm.utils import log
from dpm.utils.options import strategy_options
from dpm.utils import misc

_logger = log.get_module_logger('auto.strategy')

def main():
    # Parse options
    options = strategy_options(sys.argv[1:])
    try:
        chkpt = misc.json.loads(file('checkpoint.json').read())
    except IOError:
        _logger.error('This command must be run within a data processing directory.')
        sys.exit(1)
    app = Manager(checkpoint=chkpt)
    
    # update app options
    if options.get('anomalous') is not None:
        app.options['anomalous'] = options.get('anomalous')
    app.options['backup'] = options.get('backup', False)
    app.run( resume_from=(chkpt['run_position'][0],'strategy'), overwrite=options)

def run():
    try:
        log.log_to_console()
        main()
    except KeyboardInterrupt:
        sys.exit(1)
         
if __name__ == "__main__":
    run()
