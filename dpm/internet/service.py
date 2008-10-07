from twisted.internet import protocol, reactor, defer
from twisted.application import internet, service
from twisted.spread import pb
from twisted.python import components
from zope.interface import Interface, implements
import os
from dpm.parser.distl import parse_distl_string
import dpm.utils
from gnosis.xml import pickle

class IDPMService(Interface):
    def set_user(uid, gid):
        """Set the user as whom external programs will be executed"""
        
    def screen(img, directory):
        """Characterize a data set
        returns a deferred which returns the results of characterization
        """
        
    def analyse_image(img, directory):
        """Analyse an image
        returns a deferred which returns the results of analysis
        """
        
    def process_data(img, directory):
        """Process a dataset
        returns a deferred which returns the results of analysis
        """

class IPerspectiveDPM(Interface):
    def remote_set_user(uid, gid):
        """Set the user as whom external programs will be executed"""
        
    def remote_screen(img, directory):
        """Characterize a data set"""
        
    def remote_analyse_image(img, directory):
        """Analyse an image"""
        
    def remote_process_data(img, directory):
        """Process a dataset"""

class PerspectiveDPMFromService(pb.Root):
    implements(IPerspectiveDPM)
    def __init__(self, service):
        self.service = service
        
    def remote_set_user(self, uid, gid):
        return self.service.set_user(gid, uid)
        
    def remote_screen(self, img, directory):
        return self.service.screen(img, directory)
        
    def remote_analyse_image(self, img, directory):
        return self.service.analyse_image(img, directory)
        
    def remote_process_data(self, img, directory):
        return self.service.process_data(img, directory)

components.registerAdapter(PerspectiveDPMFromService,
    IDPMService,
    IPerspectiveDPM)
    
class LocalDPMService(service.Service):
    implements(IDPMService)
    def __init__(self):
        self.settings = {}
        self.set_user(0,0)
        
    def set_user(self, uid, gid):
        self.settings['uid'] = uid
        self.settings['gid'] = gid
        return defer.succeed( [] )
        
    def screen(self, img, directory):
        return defer.succeed([])
        
    def analyse_image(self, img, directory):
        return run_command(
            'analyse_image',
            [img],
            directory,
            self.settings['uid'],
            self.settings['gid'])
        
    def process_data(self, img, directory):
        return run_command(
            'autoprocess',
            [img],
            directory,
            self.settings['uid'],
            self.settings['gid'])

def catchError(err):
    return "Internal error in DPM service"
        
class CommandProtocol(protocol.ProcessProtocol):
    deferred = defer.Deferred()
    
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
    prot = CommandProtocol()
    args = [dpm.utils.which(command)] + args
    p = reactor.spawnProcess(
        prot,
        args[0],
        args,
        env=os.environ, path=path,
        uid=uid, gid=gid,
        )
    return prot.deferred

        
