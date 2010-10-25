'''
Created on Oct 25, 2010

@author: michel
'''

class DPMError(Exception):
    pass
    
class InvalidParameters(DPMError):
    pass

class InvalidUser(DPMError):
    pass

class ServiceUnavailable(DPMError):
    pass

class CommandFailed(DPMError):
    pass