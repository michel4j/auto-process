#!/usr/bin/env python

import argparse
import json
import os
import pwd
import subprocess
import sys

import rpyc

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from autoprocess.utils import mdns, log, misc
from autoprocess.utils.rpc import expose, expose_service
from autoprocess.parser.distl import parse_distl_string

logger = log.get_module_logger(__name__)


def demote(user_name):
    """Pass the function 'set_user' to preexec_fn, rather than just calling
    setuid and setgid. This will change the ids for that subprocess only"""

    def set_user():
        pwdb = pwd.getpwnam(user_name)
        os.setgid(pwdb.pw_gid)
        os.setuid(pwdb.pw_uid)

    return set_user


def get_user(user_name):
    try:
        pwdb = pwd.getpwnam(user_name)
        uid = pwdb.pw_uid
        gid = pwdb.pw_gid
    except:
        raise ValueError('Invalid User "{}"'.format(user_name))
    return uid, gid


@expose_service
class DataProcessorService(rpyc.Service):
    @expose
    def analyse_frame(self, frame_path, user_name):
        args = [
            'labelit.distl',
            frame_path,
        ]
        try:
            out = subprocess.check_output(args, preexec_fn=demote(user_name))
            #subprocess.check_output(['labelit.reset'])
            results = parse_distl_string(out)
            info = results['summary']
        except subprocess.CalledProcessError as e:
            logger.error('Error analysing frame: {}'.format(e.output))
            return {'error': 'Error analysing frame: {}'.format(e.output)}
        else:
            return info

    @expose
    def process_mx(self, info, directory, user_name):
        args = [
            'auto.process',
            '--dir={}'.format(directory)
        ]
        args += ['--screen'] if 'screen' in info and info['screen'] else []
        args += ['--anom'] if 'anomalous' in info and info['anomalous'] else []
        args += ['--mad'] if 'mad' in info and info['mad'] else []
        args += info['file_names']
        subprocess.check_call(args, preexec_fn=demote(user_name))

        with open('process.json', 'r') as handle:
            result = json.load(handle)
        return result

    @expose
    def process_xrd(self, info, directory, user_name):
        args = [
            'auto.xrd',
            '--dir={}'.format(directory)
        ]
        args += ['--calib'] if 'calib' in info and info['calibrate'] else []
        args += info['file_names']
        subprocess.check_call(args, preexec_fn=demote(user_name))

        with open('process.json', 'r') as handle:
            result = json.load(handle)
        return result

    def __str__(self):
        return '{}:{}'.format(*self._conn._channel.stream.sock.getpeername())


if __name__ == '__main__':
    from rpyc.utils.server import ThreadedServer
    import rpyc.lib

    rpyc.lib.setup_logger()

    parser = argparse.ArgumentParser(description='Run a Data Processing Server')
    parser.add_argument('--log', metavar='/path/to/logfile.log', type=str, nargs='?', help='full path to log file')
    parser.add_argument('--pid', metavar='/path/to/pidfile.pid', type=str, nargs='?', help='full path to pid file')

    args = parser.parse_args()
    if args.log:
        log.log_to_file(args.log)
    else:
        log.log_to_console()

    if args.pid:
        misc.save_pid(args.pid)

    s = ThreadedServer(DataProcessorService, port=8881)
    provider = mdns.Provider('Data Processing Server', '_dpm_rpc._tcp', 8881, unique=True)
    s.start()
