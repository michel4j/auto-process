import sys
import os

from autoprocess.engine.process import Manager
from autoprocess.utils import log
from autoprocess.utils import misc

logger = log.get_module_logger('auto.scale')


def main(args):
    if args.dir:
        os.chdir(args.dir)

    try:
        checkpoint = misc.load_chkpt()
    except IOError:
        logger.error('Must be in, or provide a valid directory from previous session.')
        sys.exit(1)

    app = Manager(checkpoint=checkpoint)

    overwrite = {
        'backup': args.backup
    }
    if args.anom != app.options['anomalous']:
        overwrite['anomalous'] = args.anom
    if args.res:
        overwrite['resolution'] = args.res

    app.run(resume_from=(checkpoint['run_position'][0], 'scaling'), overwrite=overwrite)


def run(args):
    try:
        log.log_to_console()
        main(args)
    except KeyboardInterrupt:
        sys.exit(1)
