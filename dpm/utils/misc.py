'''
Created on Mar 24, 2011

@author: michel
'''
import pwd
import os
import shutil
import math

try:
    import json
except:
    import simplejson as json

# Physical Constants
_h = 4.13566733e-15 # eV.s
_c = 299792458e10   # A/s

def get_cpu_count():
    return os.sysconf('SC_NPROCESSORS_ONLN')


def energy_to_wavelength(energy): 
    """Convert energy in keV to wavelength in angstroms."""
    if energy == 0.0:
        return 0.0
    return (_h*_c)/(energy*1000.0)

def wavelength_to_energy(wavelength): 
    """Convert wavelength in angstroms to energy in keV."""
    if wavelength == 0.0:
        return 0.0
    return (_h*_c)/(wavelength*1000.0)

def air(e):
    p = [ 1.00000857e+00,  -3.10243288e-04,   3.01020914e+00]    
    return 1.0 - (p[0] * math.exp( p[1] * (e**p[2])))
   
def get_project_name():
    return pwd.getpwuid(os.geteuid())[0]

def get_home_dir():
    return pwd.getpwuid(os.geteuid())[5]
    
def backup_files(*args):
    for filename in args:
        if os.path.exists(filename):
            index = 0
            while os.path.exists('%s.%0d' % (filename, index)):
                index += 1
            shutil.copy(filename, '%s.%0d' % (filename, index))
    return

def file_requirements(*args):
    all_exist = True
    for f in args:
        if not os.path.exists(f):
            all_exist = False
            break
    return all_exist


import posixpath

def _relpath(path, base=os.curdir):
    """
    Return a relative path to the target from either the current dir or an optional base dir.
    Base can be a directory specified either as absolute or relative to current dir.
    """

    if not path:
        raise ValueError("no path specified")
    start_list = posixpath.abspath(base).split(posixpath.sep)
    path_list = posixpath.abspath(path).split(posixpath.sep)
    # Work out how much of the filepath is shared by start and path.
    i = len(posixpath.commonprefix([start_list, path_list]))
    rel_list = [posixpath.pardir] * (len(start_list)-i) + path_list[i:]
    if not rel_list:
        return posixpath.curdir
    return posixpath.join(*rel_list)



# custom relpath for python < 2.7
try:
    from os.path import relpath
except:
    relpath = _relpath

def prepare_dir(workdir, backup=False):
    """ 
    Creates a work dir for autoprocess to run. Increments run number if 
    directory already exists.
    
    """
    
    exists = os.path.isdir(workdir)
    if not exists:
        os.makedirs(workdir)
    elif backup:
        count = 0
        while exists:
            count += 1
            bkdir = "%s-bk%02d" % (workdir, count)
            exists = os.path.isdir(bkdir)
        shutil.move(workdir, bkdir)
        os.makedirs(workdir)
    