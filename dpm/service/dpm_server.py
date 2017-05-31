from twisted.internet import glib2reactor
glib2reactor.install()

from twisted.internet import protocol, reactor, threads, defer
from twisted.application import internet, service
from twisted.spread import pb
from twisted.python import components
from twisted.cred import portal, checkers
from twisted.python import log
from twisted.python.failure import Failure, DefaultException
from zope.interface import Interface, implements

from dpm.service.interfaces import *
from dpm.utils.misc import json
from dpm.utils import mdns
from dpm.service.common import *
import os, sys
from dpm.utils.which import which
import pwd
from dpm.service.common import *


log.FileLogObserver(sys.stdout).start()


def log_call(f):
    def new_f(*args, **kwargs):
        params = ['%s' % repr(a) for a in args[1:] ]
        params.extend(['%s=%s' % (p[0], repr(p[1])) for p in kwargs.items()])
        params = ', '.join(params)
        log.msg('<%s(%s)>' % (f.__name__, params))
        return f(*args,**kwargs)
    new_f.__name__ = f.__name__
    return new_f


def get_user_properties(user_name):
    try:
        pwdb = pwd.getpwnam(user_name)
        uid = pwdb.pw_uid
        gid = pwdb.pw_gid
    except:
        raise InvalidUser('Unknown user `%s`' % user_name)
    return uid, gid
    
    
class PerspectiveDPMFromService(pb.Root):
    implements(IPerspectiveDPM)
    def __init__(self, service):
        self.service = service
        
    def remote_screenDataset(self, info, directory, uname=None):
        return self.service.screenDataset(info, directory, uname)
        
    def remote_analyseImage(self, img, directory, uname=None):
        return self.service.analyseImage(img, directory, uname)
        
    def remote_processDataset(self, info, directory, uname=None):
        return self.service.processDataset(info, directory, uname)

components.registerAdapter(PerspectiveDPMFromService,
    IDPMService,
    IPerspectiveDPM)
    
class DPMService(service.Service):
    implements(IDPMService)
    
    def __init__(self):
        self.settings = {}        
        
    @log_call
    def screenDataset(self, info, directory, uname=None):
        if isinstance(info['file_names'], (list, tuple)):
            info['file_names'] = ' '.join(info['file_names']) 
        args = ['--screen', info['file_names'], '--dir=%s' % (directory)]
        if info.get('anomalous', False):
            args.append('--anom')
        
        if uname is not None:
            try:
                uid, gid = get_user_properties(uname)
                self.settings['uid'] = uid
                self.settings['gid'] = gid
            except InvalidUser, e:
                return defer.fail(Failure(e))
        else:
            uid = self.settings['uid']
            gid = self.settings['gid']
        
        return run_command_output(
            'auto.process',
            args,
            directory,
            uid,
            gid,
            output='process.json')
        
    
    @log_call
    def analyseImage(self, img, directory, uname=None):
        if uname is not None:
            try:
                uid, gid = get_user_properties(uname)
                self.settings['uid'] = uid
                self.settings['gid'] = gid
            except InvalidUser, e:
                return defer.fail(Failure(e))
        else:
            uid = self.settings['uid']
            gid = self.settings['gid']
        _output_file = '%s-distl.json' % (os.path.splitext(os.path.basename(img))[0])
        return run_command_output(
            'auto.analyse',
            [img, directory, _output_file],
            directory,
            uid,
            gid,
            output=_output_file,
            )
    
    @log_call
    def processDataset(self, info, directory, uname=None):
            
        if uname is not None:
            try:
                uid, gid = get_user_properties(uname)
                self.settings['uid'] = uid
                self.settings['gid'] = gid
            except InvalidUser, e:
                return defer.fail(Failure(e))
        else:
            uid = self.settings['uid']
            gid = self.settings['gid']
        
        # prepare arguments for autoprocess
        args = list(info['file_names']) + ['--dir=%s' % (directory)]
        if info.get('anomalous', False):
            args.append('--anom')
        if info.get('mad', False):
            args.append('--mad')
            
        return run_command_output(
            'auto.process',
            args,
            directory,
            uid,
            gid,
            output='process.json')

def catchError(err):
    return "Internal error in DPM service"
        
class CommandProtocol(protocol.ProcessProtocol):
    
    def __init__(self, path, command, output_file=None, use_json=True):
        self.output = ''
        self.errors = ''
        self.command = command
        if output_file is not None:
            self.output_file = os.path.join(path, output_file)
        else:
            self.output_file = None
        self.use_json = use_json
        self.path = path
    
    def outReceived(self, output):
        self.output += output
    
    def errReceived(self, error):
        self.errors += error

    def outConnectionLost(self):
        pass
    
    def errConnectionLost(self):
        pass
    
    def processEnded(self, reason):
        rc = reason.value.exitCode
        if rc == 0:
            if self.output_file is not None:
                if self.errors == '':
                    self.errors = None
                data = file(self.output_file).read()
            else:
                data = self.output    
            if self.use_json:
                data = json.loads(data)
                if data.get('error', None) is None and data.get('result', None) is not None:
                    self.deferred.callback(data['result'])
                elif data.get('error', None) is not None:
                    msg = data['error']['message']
                    f = Failure(CommandFailed('Command `%s` failed with error: \n%s.' % (self.command, msg)))
                    self.deferred.errback(f)
            else:
                self.deferred.callback(data)
            log.msg(self.errors)
        else:
            f = Failure(CommandFailed('Command `%s` died with code `%d`.' % (self.command, rc)))
            log.msg(self.output)
            log.msg(self.errors)
            self.deferred.errback(f)
            
            
def run_command(command, args, path='/tmp', uid=0, gid=0):
    prot = CommandProtocol(path, command)
    prot.deferred = defer.Deferred()
    args = [which(command)] + args
    reactor.spawnProcess(
        prot,
        args[0],
        args,
        env=os.environ, path=path,
        uid=uid, gid=gid, usePTY=True
        )
    return prot.deferred

def run_command_output(command, args, path='/tmp', uid=0, gid=0, output=None):
    """Run a command and return the output from the specified file in given path"""
    output = os.path.join(path, output)
    prot = CommandProtocol(path, command, output_file=output)
    prot.deferred = defer.Deferred()
    args = [which(command)] + args
    reactor.spawnProcess(
        prot,
        args[0],
        args,
        env=os.environ,
        uid=uid, gid=gid, usePTY=True
        )
    return prot.deferred



application = service.Application('DPM')
f = DPMService()

# publish DPM service on network
dpm_provider = mdns.Provider('Data Processing Module', '_cmcf_dpm._tcp', 8881, {})

serviceCollection = service.IServiceCollection(application)
internet.TCPServer(8881, pb.PBServerFactory(IPerspectiveDPM(f))).setServiceParent(serviceCollection)


