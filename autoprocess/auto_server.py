import os
import sys


SHARE_DIR = os.path.join(os.path.dirname(__file__), 'share')
TAC_FILE = os.path.join(SHARE_DIR, 'autoprocess.tac')

# inject command line args
sys.argv = ['', '-noy', TAC_FILE, '--umask=022']


def main():
    from twisted.application import app
    from twisted.scripts._twistd_unix import ServerOptions, UnixApplicationRunner

    def runApp(config):
        runner = UnixApplicationRunner(config)
        runner.run()
        if runner._exitSignal is not None:
            app._exitWithSignal(runner._exitSignal)

    app.run(runApp, ServerOptions)


