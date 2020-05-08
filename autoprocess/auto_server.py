import os
import sys


SHARE_DIR = os.path.join(os.path.dirname(__file__), 'share')
TAC_FILE = os.path.join(SHARE_DIR, 'autoprocess.tac')


def main(args):
    if args.nodaemon:
        sys.argv = ['', '-ny', TAC_FILE, '--umask=022']
    else:
        sys.argv = ['', '-y', TAC_FILE, '--umask=022']

    if args.pidfile:
        sys.argv.append(f'--pidfile={args.pidfile}')

    if args.logfile:
        sys.argv.append(f'--logfile={args.logfile}')

    from twisted.application import app
    from twisted.scripts._twistd_unix import ServerOptions, UnixApplicationRunner

    def runApp(config):
        runner = UnixApplicationRunner(config)
        runner.run()
        if runner._exitSignal is not None:
            app._exitWithSignal(runner._exitSignal)

    app.run(runApp, ServerOptions)


