'''
Created on Oct 25, 2010

@author: michel
'''
import pwd
import os
from twisted.spread import pb

class DPMError(pb.Error):
    pass
    
class InvalidParameters(DPMError):
    pass

class InvalidUser(DPMError):
    pass

class InvalidDirectory(DPMError):
    pass

class ServiceUnavailable(DPMError):
    pass

class CommandFailed(DPMError):
    pass

def get_user_properties(user_name):
    try:
        pwdb = pwd.getpwnam(user_name)
        uid = pwdb.pw_uid
        gid = pwdb.pw_gid
        dir = pwdb.pw_dir
    except:
        raise InvalidUser('Unknown user `%s`' % user_name)
    return uid, gid, dir


def validate_directory(dir):
    if not os.path.exists(dir):
        raise InvalidDirectory('Directory `%s` does not exist.' % dir)
    if not os.access(dir, os.W_OK):
        raise InvalidDirectory('Permission denied for directory `%s`.' % dir)
