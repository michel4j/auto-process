import os
import sys

from autoprocess.engine.process import Manager
from autoprocess.utils import log
from autoprocess.utils import misc

logger = log.get_module_logger('auto.process')


def main(args):
    if len(args.images) >= 1:
        options = {
            'images': args.images,
            'anomalous': bool(args.anom),
            'mode': 'simple',
            'backup': args.backup,
            'chiral': (not args.nonchiral),
            'solve-small': args.formula,
            'directory': args.dir,
            'prefix': [] if not args.prefix else args.prefix.split(',')
        }
        if args.screen:
            options['mode'] = 'screen'
        elif args.mad:
            options['mode'] = 'mad'
            options['anomalous'] = True
        elif len(args.images) > 1:
            options['mode'] = 'merge'

        if len(options['prefix']) != len(args.images):
            del options['prefix']

        app = Manager(options=options)
        app.run()

    else:
        if args.dir:
            os.chdir(args.dir)

        try:
            if args.load:
                chkpt = None
            else:
                chkpt = misc.load_chkpt()

            options = {
                'anomalous': bool(args.anom),
                'mode': 'simple',
                'backup': args.backup,
                'directory': args.dir,
                'zap': args.zap,
                'import': args.load,
            }

            if args.load:
                options['directory'] = args.dir or os.getcwd()

            app = Manager(checkpoint=chkpt, options=options)
            if args.zap or args.load:
                app.run(colonize=args.load)
            else:
                app.run(resume_from=chkpt['run_position'])
        except IOError:
            logger.error('Either specify a dataset, or run within a data processing directory.')
            sys.exit(1)


def run(args):
    try:
        log.log_to_console()
        main(args)
    except KeyboardInterrupt:
        sys.exit(1)
