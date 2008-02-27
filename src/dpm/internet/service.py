from twisted.internet import protocol, reactor, defer
from twisted.application import internet, service
from twisted.spread import pb
from twisted.python import components
from zope.interface import Interface, implements
import os

class IDPMService(Interface):
    def set_user(uid, gid):
        """Set the user as whom external programs will be executed"""
        
    def characterize(img, directory):
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
        
    def remote_characterize(img, directory):
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
        
    def remote_characterize(self, img, directory):
        return self.service.characterize(img, directory)
        
    def remote_analyse_image(self, img, directory):
        return self.service.analyse_image(img, directory)
        
    def remote_process_data(self, img, directory):
        return self.service.process_data(img, directory)

components.registerAdapter(PerspectiveDPMFromService,
    IDPMService,
    IPerspectiveDPM)
    
class LocalDPMService(service.Service):
    implements(IDPMService)
    
    def set_user(self, uid, gid):
        return defer.succeed( [] )
        
    def characterize(self, img, directory):
        return defer.succeed([])
        
    def analyse_image(self, img, directory):
         return defer.succeed([])
        
    def process_data(self, img, directory):
        return defer.succeed([])
    

def catchError(err):
    return "Internal error in server"
        
    
            

