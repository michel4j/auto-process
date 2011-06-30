
from zope.interface import Interface

class IDPMService(Interface):
    
    def setUser(uid, gid):
        """Set the user as whom external programs will be executed"""
        
    def screenDataset(info, directory):
        """Characterize a data set
        returns a deferred which returns the results of characterization
        """
        
    def analyseImage(img, directory):
        """Analyse an image
        returns a deferred which returns the results of analysis
        """
        
    def processDataset(info, directory):
        """Process a dataset
        returns a deferred which returns the results of analysis
        """

class IPerspectiveDPM(Interface):
    
    def remote_setUser(uid, gid):
        """Set the user as whom external programs will be executed"""
        
    def remote_screenDataset(img, directory):
        """Characterize a data set"""
        
    def remote_analyseImage(img, directory):
        """Analyse an image"""
        
    def remote_processDataset(img, directory):
        """Process a dataset"""


__all__ = [ 'IPerspectiveDPM', 'IDPMService']