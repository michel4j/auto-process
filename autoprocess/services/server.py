#!/usr/bin/env python

import json
import logging
import os
import pwd
import subprocess

from distutils.spawn import find_executable
from twisted.application import service, internet
from twisted.internet import protocol, reactor, defer
from twisted.python import log as twistedlog
from twisted.python.failure import Failure
from twisted.spread import pb
from twisted.python import components

from zope.interface import implementer, Interface

from autoprocess.utils import log, mdns
from autoprocess.parsers.distl import parse_distl_string

logger = log.get_module_logger(__name__)


class TwistedLogger(logging.StreamHandler):
    def emit(self, record):
        msg = self.format(record)
        if record.levelno == logging.WARNING:
            twistedlog.msg(msg)
        elif record.levelno > logging.WARNING:
            twistedlog.err(msg)
        else:
            twistedlog.msg(msg)
        self.flush()


def log_to_twisted(level=logging.DEBUG):
    """
    Add a log handler which logs to the twisted logger.
    """
    console = TwistedLogger()
    console.setLevel(level)
    logging.getLogger('').addHandler(console)


def demote(user_name):
    """Pass the function 'set_user' to preexec_fn, rather than just calling
    setuid and setgid. This will change the ids for that subprocess only"""

    def set_user():
        pwdb = pwd.getpwnam(user_name)
        os.setgid(pwdb.pw_gid)
        os.setuid(pwdb.pw_uid)

    return set_user


class CommandProtocol(protocol.ProcessProtocol):
    """
    Twisted Protocol for running commands asynchronously
    """

    def __init__(self, command, directory, json_file=None, json_out=False, parser=None):
        """
        :param command: name of command
        :param directory: directory to run command
        :param json_file: output file name for reading json output from the command
        :param json_out: bool, interpret standard output as json for output
        :param parser: function, optional parser to converting command output into return value
        """
        self.output = ''
        self.errors = ''
        self.parser = parser
        self.command = command
        self.json_file = json_file if not json_file else os.path.join(directory, json_file)
        self.json_out = json_out
        self.directory = directory

    def outReceived(self, output):
        self.output += output.decode('utf8')

    def errReceived(self, error):
        self.errors += error.decode('utf8')

    def outConnectionLost(self):
        pass

    def errConnectionLost(self):
        pass

    def processEnded(self, reason):
        rc = reason.value.exitCode
        if rc == 0:
            try:
                if self.json_file:
                    with open(self.json_file, 'r') as handle:
                        self.deferred.callback(json.load(handle))
                elif self.json_out:
                    self.deferred.callback(json.loads(self.output))
                elif self.parser:
                    self.deferred.callback(self.parser(self.output))
                else:
                    self.deferred.callback(self.output)
            except Exception as e:
                logger.error(e)
                self.deferred.errback(Failure(e))
            if self.errors:
                logger.error(self.errors)
        else:
            failure = Failure(
                RuntimeError('Command {} died [code {}]: {}, {}'.format(self.command, rc, self.output, self.errors))
            )
            logger.error('Error:')
            logger.error(self.errors)
            self.deferred.errback(failure)


def async_command(command, args, directory='/tmp', user_name='root', json_file=None, json_output=False, parser=None):
    """
    Run a command asynchronously as a given user and return a deferred. The final result can be
    either read from a json file or json formatted standard output, or regular text output

    :param command: name of command to execute
    :param args: list of arguments to pass
    :param directory: directory in which to run the command
    :param user_name: User name
    :param json_file: File name of file to read output from, or None
    :param json_output: Bool, whether to pParse standard output as json instead of reading from file
    :param parser: function, optional parser to converting command output into return value
    :return: [str|list|dict]
    """

    try:
        pwdb = pwd.getpwnam(user_name)
        uid = pwdb.pw_uid
        gid = pwdb.pw_gid
        if not os.path.exists(directory):
            subprocess.check_call(['mkdir', '-p', directory], preexec_fn=demote(user_name))
        impersonate = True
    except:
        uid = os.getuid()
        gid = os.getgid()
        if not os.path.exists(directory):
            os.makedirs(directory)
        impersonate = False

    prot = CommandProtocol(command, directory, json_file=json_file, json_out=json_output, parser=parser)
    prot.deferred = defer.Deferred()
    args = [find_executable(command)] + args

    if impersonate:
        reactor.spawnProcess(prot, args[0], args, env=os.environ, path=directory, uid=uid, gid=gid, usePTY=True)
    else:
        reactor.spawnProcess(prot, args[0], args, env=os.environ, path=directory, usePTY=True)
    return prot.deferred


class IDPService(Interface):
    def analyse_frame(frame_path, user_name, rastering=False):
        """
        Analyse diffraction frame

        :param frame_path: full path to frame
        :param user_name: user name to run as
        :params rastering: If True, perform scoring for rastering
        :return:
        """

    def process_mx(info, directory, user_name):
        """
        Process an MX dataset

        :param info: dictionary containing parameters
        :param directory: directory for output
        :param user_name: user name to run as
        :return:
        """

    def process_misc(info, directory, user_name):
        """
        Process an MX dataset

        :param info: dictionary containing parameters
        :param directory: directory for output
        :param user_name: user name to run as
        :return:
        """

    def process_xrd(info, directory, user_name):
        """
        Process an XRD dataset

        :param info: dictionary containing parameters
        :param directory: directory for output
        :param user_name: user name to run as
        :return:
        """


class IDPSPerspective(Interface):
    def remote_analyse_frame(*args, **kwargs):
        """analyse_frame adaptor"""

    def remote_process_mx(*args, **kwargs):
        """analyse_mx adaptor"""

    def remote_process_misc(*args, **kwargs):
        """analyse_mx adaptor"""

    def remote_process_xrd(*args, **kwargs):
        """analyse_xrd adaptor"""


@implementer(IDPSPerspective)
class DPSPerspective2Service(pb.Root):

    def __init__(self, service):
        self.service = service

    def remote_analyse_frame(self, *args, **kwargs):
        return self.service.analyse_frame(*args, **kwargs)

    def remote_process_mx(self, *args, **kwargs):
        return self.service.process_mx(*args, **kwargs)

    def remote_process_misc(self, *args, **kwargs):
        return self.service.process_misc(*args, **kwargs)

    def remote_process_xrd(self, *args, **kwargs):
        return self.service.process_xrd(*args, **kwargs)


def _distl_output(text):
    out = parse_distl_string(text)
    return out['summary']


@implementer(IDPService)
class DPService(service.Service):
    """
    Data Processing Service using Twisted Perspective Broker.

    """
    def __init__(self):
        super().__init__()
        reactor.callLater(2, self.publishService)

    def publishService(self):
        self.provider = mdns.Provider('AutoProcess Server', '_autoprocess._tcp.local.', 9991)
        reactor.addSystemEventTrigger('before', 'shutdown', self.stopService)

    def stopService(self):
        del self.provider
        super().stopService()

    @log.log_call
    def analyse_frame(self, frame_path, user_name, rastering=False):
        """
        Analyse diffraction frame

        :param frame_path: full path to frame
        :param user_name: user name to run as
        :params rastering: If True, perform scoring for rastering
        :return: a dictionary representing the processing report
        """

        directory = os.path.dirname(frame_path)
        args = [
            'distl.res.outer={}'.format(3.0 if rastering else 1.0),
            'distl.res.inner=10.0',
            frame_path,
        ]
        return async_command('distl.signal_strength', args, directory, user_name=user_name, parser=_distl_output)

    @log.log_call
    def process_mx(self, info, directory, user_name):
        """
        Process an MX dataset

        :param info: dictionary containing parameters
        :param directory: directory for output
        :param user_name: user name to run as
        :return: dictionary containing the report
        """

        args = [
            '--dir={}'.format(directory)
        ]
        args += ['--screen'] if info.get('screen') else []
        args += ['--anom'] if info.get('anomalous') else []
        args += ['--mad'] if info.get('mad') else []
        args += info['file_names']
        return async_command('auto.process', args, directory, user_name=user_name, json_file='report.json')

    @log.log_call
    def process_misc(self, info, directory, user_name):
        args = [
            '-d',
            directory,
            info['file_names'][0]
        ]
        return async_command('msg', args, directory, user_name=user_name, json_file='report.json')

    @log.log_call
    def process_xrd(self, info, directory, user_name):
        """
        Process an XRD dataset

        :param info: dictionary containing parameters
        :param directory: directory for output
        :param user_name: user name to run as
        :return: a dictionary of the report
        """

        args = []
        args += ['--calib'] if info.get('calib') else []
        args += info['file_names']
        return async_command('auto.powder', args, directory, user_name=user_name, json_file='report.json')


components.registerAdapter(DPSPerspective2Service, IDPService, IDPSPerspective)


def get_service():
    """
    Return a service suitable for creating an application object.
    """
    log_to_twisted()
    dps_server = DPService()
    return internet.TCPServer(9991, pb.PBServerFactory(IDPSPerspective(dps_server)))