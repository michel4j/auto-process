#!/usr/bin/env python


import sys
import warnings

warnings.simplefilter("ignore")  # ignore deprecation warnings

from autoprocess.engine.process import Manager
from autoprocess.utils import log
from autoprocess.utils.options import scale_options
from autoprocess.utils import misc

_logger = log.get_module_logger('auto.scale')


def main():
    # Parse options
    options = scale_options(sys.argv[1:])
    try:
        chkpt = misc.load_chkpt()
    except IOError:
        _logger.error('This command must be run within a data processing directory.')
        sys.exit(1)
    app = Manager(checkpoint=chkpt)

    # update app options
    if options.get('anomalous') is not None:
        app.options['anomalous'] = options.get('anomalous')
    app.options['backup'] = options.get('backup', False)
    app.run(resume_from=(chkpt['run_position'][0], 'scaling'), overwrite=options)


def run():
    try:
        log.log_to_console()
        main()
    except KeyboardInterrupt:
        sys.exit(1)
