import sys
import os

from autoprocess.engine.process import Manager
from autoprocess.utils import log
from autoprocess.utils import misc
from autoprocess.utils import xtal

logger = log.get_module_logger('auto.symmetry')


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
        'backup': args.backup,
        'chiral': (not args.nonchiral)
    }
    if args.anom != app.options['anomalous']:
        overwrite['anomalous'] = args.anom
    if args.res:
        overwrite['resolution'] = args.res

    if args.spacegroup:
        if args.spacegroup in xtal.SG_SYMBOLS:
            overwrite['sg_overwrite'] = args.spacegroup
        else:
            logger.error(f'Invalid Space-Group: {args.spacegroup}')
            print(xtal.get_sg_table(False))

    app.run(resume_from=(checkpoint['run_position'][0], 'symmetry'), overwrite=overwrite)


def run(args):
    try:
        log.log_to_console()
        main(args)
    except KeyboardInterrupt:
        sys.exit(1)
