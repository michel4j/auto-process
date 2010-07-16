from twisted.internet import glib2reactor
glib2reactor.install()

from twisted.internet import protocol, reactor, threads, defer
from twisted.application import internet, service
from twisted.spread import pb
from twisted.python import components
from twisted.conch import manhole, manhole_ssh
from twisted.cred import portal, checkers
from twisted.python import log
from zope.interface import Interface, implements

from dpm.service.interfaces import *
from bcm.service.utils import log_call
from bcm.utils import mdns
from bcm.utils.misc import get_short_uuid

import os, sys
import dpm.utils
import pwd

try:
    import json
except:
    import simplejson as json

class PerspectiveDPMFromService(pb.Root):
    implements(IPerspectiveDPM)
    def __init__(self, service):
        self.service = service

    def remote_setUser(self, uname):
        return self.service.setUser(uname)
        
    def remote_screenDataset(self, info, directory):
        return self.service.screenDataset(info, directory)
        
    def remote_analyseImage(self, img, directory):
        return self.service.analyseImage(img, directory)
        
    def remote_processDataset(self, info, directory):
        return self.service.processDataset(info, directory)

components.registerAdapter(PerspectiveDPMFromService,
    IDPMService,
    IPerspectiveDPM)
    
class DPMService(service.Service):
    implements(IDPMService)
    
    def __init__(self):
        self.settings = {}
        self.setUser('root')
    
    @log_call
    def setUser(self, uname):
        pwdb = pwd.getpwnam(uname)
        self.settings['uid'] = pwdb.pw_uid
        self.settings['gid'] = pwdb.pw_gid
        return defer.succeed( [] )
        
    @log_call
    def screenDataset(self, info, directory):
        if isinstance(info['file_names'], (list, tuple)):
            info['file_names'] = ' '.join(info['file_names']) 
        args = ['--screen', info['file_names'], '--dir=%s' % (directory)]
        if info.get('anomalous', False):
            args.append('--anom')
        
        if info.get('user', None) is not None:
            pwdb = pwd.getpwnam(info.get('user'))
            uid = pwdb.pw_uid
            gid = pwdb.pw_gid
        else:
            uid = self.settings['uid'],
            gid = self.settings['gid'],
            
        return run_command_output(
            'autoprocess',
            args,
            directory,
            uid,
            gid,
            output='process.json')
    
    @log_call   
    def analyseImage(self, img, directory):
        return run_command_output(
            'analyse_image',
            [img, directory],
            directory,
            self.settings['uid'],
            self.settings['gid'],
            output='distl.json')
    
    @log_call
    def processDataset(self, info, directory):
        if isinstance(info['file_names'], (list, tuple)):
            info['file_names'] = ' '.join(info['file_names'])
        args = [info['file_names'], '--dir=%s' % (directory)]
        if info.get('anomalous', False):
            args.append('--anom')
        if info.get('mad', False):
            args.append('--mad')
        if info.get('user', None) is not None:
            pwdb = pwd.getpwnam(info.get('user'))
            uid = pwdb.pw_uid
            gid = pwdb.pw_gid
        else:
            uid = self.settings['uid'],
            gid = self.settings['gid'],
            
        return run_command_output(
            'autoprocess',
            args,
            directory,
            uid,
            gid,
            output='process.json')

def catchError(err):
    return "Internal error in DPM service"
        
class CommandProtocol(protocol.ProcessProtocol):
    
    def __init__(self, path, output_file=None, use_json=False):
        self.output = ''
        self.errors = ''
        self.output_file = output_file
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
                self.output = file(self.output_file).read()
            if self.use_json:
                self.output = json.loads(self.output)
            self.deferred.callback(self.output)
        else:
            self.deferred.callback(self.errors)

def run_command(command, args, path='/tmp', uid=0, gid=0):
    prot = CommandProtocol(path)
    prot.deferred = defer.Deferred()
    args = [dpm.utils.which(command)] + args
    p = reactor.spawnProcess(
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
    prot = CommandProtocol(path, output_file=output)
    prot.deferred = defer.Deferred()
    args = [dpm.utils.which(command)] + args
    p = reactor.spawnProcess(
        prot,
        args[0],
        args,
        env=os.environ,
        uid=uid, gid=gid, usePTY=True
        )
    return prot.deferred

    
# generate ssh factory which points to a given service
def getShellFactory(service, **passwords):
    realm = manhole_ssh.TerminalRealm()
    def getManhole(_):
        namespace = {'service': service, '_': None }
        fac = manhole.Manhole(namespace)
        fac.namespace['factory'] = fac
        return fac
    realm.chainedProtocolFactory.protocolFactory = getManhole
    p = portal.Portal(realm)
    p.registerChecker(
        checkers.InMemoryUsernamePasswordDatabaseDontUse(**passwords))
    f = manhole_ssh.ConchFactory(p)
    return f



application = service.Application('DPM')
f = DPMService()
sf = getShellFactory(f, admin='admin')

# publish DPM service on network
bcm_provider = mdns.Provider('Data Analsys Module', '_cmcf_dpm._tcp', 8881, {})
bcm_ssh_provider = mdns.Provider('Data Analysis Module Console', '_cmcf_dpm_ssh._tcp', 2221, {})

serviceCollection = service.IServiceCollection(application)
internet.TCPServer(8881, pb.PBServerFactory(IPerspectiveDPM(f))).setServiceParent(serviceCollection)
internet.TCPServer(2221, sf).setServiceParent(serviceCollection)        
