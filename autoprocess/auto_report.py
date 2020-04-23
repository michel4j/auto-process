
import os
import sys
from autoprocess.utils import log, misc
from autoprocess.engine import reporting

logger = log.get_module_logger('auto.report')


def main(args):

    if args.dir:
        os.chdir(args.dir)

    try:
        data = misc.load_chkpt()
        reporting.save_report(data['datasets'], data['options'])
    except IOError:
        logger.error('Must be in, or provide a valid directory from previous session.')


def run(args):
    try:
        log.log_to_console()
        main(args)
    except KeyboardInterrupt:
        sys.exit(1)
