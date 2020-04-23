import sys
import os

from autoprocess.engine.process import Manager
from autoprocess.utils import log
from autoprocess.utils import misc

logger = log.get_module_logger('auto.strategy')


def main(args):
    if args.dir:
        os.chdir(args.dir)

    try:
        chkpt = misc.load_chkpt()
    except IOError:
        logger.error('This command must be run within a data processing directory.')
        sys.exit(1)
    app = Manager(checkpoint=chkpt)

    overwrite = {
        'backup': args.backup
    }
    if args.anom != app.options['anomalous']:
        overwrite['anomalous'] = args.anom
    if args.res:
        overwrite['resolution'] = args.res
    app.run(resume_from=(chkpt['run_position'][0], 'strategy'), overwrite=overwrite)


def run(args):
    try:
        log.log_to_console()
        main(args)
    except KeyboardInterrupt:
        sys.exit(1)

