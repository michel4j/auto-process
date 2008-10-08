from twisted.internet import protocol, reactor, threads, defer
from twisted.application import internet, service
from twisted.spread import pb
from twisted.python import components
from twisted.manhole import telnet
from zope.interface import Interface, implements

import os, sys
sys.path.append(os.environ['DPM_PATH'])

import dpm.utils
from gnosis.xml import pickle

class IDPMService(Interface):
    
    def setUser(uid, gid):
        """Set the user as whom external programs will be executed"""
        
    def screenCrystal(img, directory):
        """Characterize a data set
        returns a deferred which returns the results of characterization
        """
        
    def analyseImage(img, directory):
        """Analyse an image
        returns a deferred which returns the results of analysis
        """
        
    def processDataset(img, directory):
        """Process a dataset
        returns a deferred which returns the results of analysis
        """

class IPerspectiveDPM(Interface):
    
    def remote_setUser(uid, gid):
        """Set the user as whom external programs will be executed"""
        
    def remote_screenCrystal(img, directory):
        """Characterize a data set"""
        
    def remote_analyseImage(img, directory):
        """Analyse an image"""
        
    def remote_processDataset(img, directory):
        """Process a dataset"""

class PerspectiveDPMFromService(pb.Root):
    implements(IPerspectiveDPM)
    def __init__(self, service):
        self.service = service
        
    def remote_setUser(self, uid, gid):
        return self.service.setUser(uid, gid)
        
    def remote_screenCrystal(self, img, directory):
        return self.service.screenCrystal(img, directory)
        
    def remote_analyseImage(self, img, directory):
        return self.service.analyseImage(img, directory)
        
    def remote_processDataset(self, img, directory):
        return self.service.processDataset(img, directory)

components.registerAdapter(PerspectiveDPMFromService,
    IDPMService,
    IPerspectiveDPM)
    
class DPMService(service.Service):
    implements(IDPMService)
    
    def __init__(self):
        self.settings = {}
        self.setUser(0,0)
        
    def setUser(self, uid, gid):
        self.settings['uid'] = uid
        self.settings['gid'] = gid
        return defer.succeed( [] )
        
    def screenCrystal(self, img, directory, anom=False):
        if anom:
            args = ['-a','-s', img]
        else:
            args = ['-s', img]
        return run_command(
            'autoprocess.py',
            args,
            directory,
            self.settings['uid'],
            self.settings['gid'])
        
    def analyseImage(self, img, directory):
        return run_command(
            'analyse_image',
            [img],
            directory,
            self.settings['uid'],
            self.settings['gid'])
        
    def processDataset(self, img, directory, anom=False):
        if anom:
            args = ['-a', img]
        else:
            args = [img]
        return run_command(
            'autoprocess.py',
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

def run_command(command, args, path, uid, gid):
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
    
application = service.Application('DPM')
f = DPMService()
tf = telnet.ShellFactory()
tf.setService(f)
serviceCollection = service.IServiceCollection(application)
internet.TCPServer(8889, pb.PBServerFactory(IPerspectiveDPM(f))).setServiceParent(serviceCollection)
internet.TCPServer(4040, tf).setServiceParent(serviceCollection)        
