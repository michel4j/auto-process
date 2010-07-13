from twisted.internet import glib2reactor
glib2reactor.install()

from twisted.internet import protocol, reactor, threads, defer
from twisted.application import internet, service
from twisted.spread import pb
from twisted.python import components
from twisted.conch import manhole, manhole_ssh
from twisted.cred import portal, checkers
from twisted.python import log
from twisted.python import log
from zope.interface import Interface, implements

from dpm.service.interfaces import *
from bcm.service.utils import log_call
from bcm.utils import mdns

import os, sys
import dpm.utils


class PerspectiveDPMFromService(pb.Root):
    implements(IPerspectiveDPM)
    def __init__(self, service):
        self.service = service

    def remote_setUser(self, uid, gid):
        return self.service.setUser(uid, gid)
        
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
        self.setUser(0,0)
    
    @log_call
    def setUser(self, uid, gid):
        self.settings['uid'] = uid
        self.settings['gid'] = gid
        return defer.succeed( [] )
        
    @log_call
    def screenDataset(self, info, directory):
        if info['anomalous']:
            args = ['-sa', info['file_name']]
        else:
            args = ['-s', info['file_name']]
        return run_command(
            'autoprocess',
            args,
            directory,
            self.settings['uid'],
            self.settings['gid'])
    
    @log_call   
    def analyseImage(self, img, directory):
        return run_command(
            'analyse_image',
            [img],
            directory,
            self.settings['uid'],
            self.settings['gid'])
    
    @log_call
    def processDataset(self, info, directory, anom=False):
        if anom:
            args = ['-a', info['file_name']]
        else:
            args = [info['file_name']]
        return run_command(
            'autoprocess',
            args,
            directory,
            self.settings['uid'],
            self.settings['gid'])

def catchError(err):
    return "Internal error in DPM service"
        
class CommandProtocol(protocol.ProcessProtocol):
    
    def __init__(self, path):
        self.output = ''
        self.errors = ''
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
            self.deferred.callback(self.output)
        else:
            self.deferred.errback(rc)

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
