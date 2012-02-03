'''
Created on Mar 24, 2011

@author: michel
'''
import pwd
import os
import shutil
import math
import numpy
import posixpath


try:
    import json
except:
    import simplejson as json

# Physical Constants
_h = 4.13566733e-15 # eV.s
_c = 299792458e10   # A/s

#direction vector of kappa axis on 08B1-1 when omega is at 0.0 deg
KAPPA_AXIS = numpy.array([ 0.91354546,  0.3468    ,  0.21251931])

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

def backup_special_file(filename, suffix):
    if os.path.exists(filename):
        shutil.copy(filename, '%s.%s' % (filename, suffix))
    return

def file_requirements(*args):
    all_exist = True
    for f in args:
        if not os.path.exists(f):
            all_exist = False
            break
    return all_exist

def rad2deg(r):
    return r*180.0/numpy.pi


def deg2rad(d):
    return r*numpy.pi/180.0


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

def calc_angle(v1, v2):
    v1 = numpy.array(v1, dtype=numpy.float64)/numpy.linalg.norm(v1)
    v2 = numpy.array(v2, dtype=numpy.float64)/numpy.linalg.norm(v2)
    cs = numpy.dot(v1,v2)
    sn = numpy.linalg.norm(numpy.cross(v1,v2))
    a = numpy.arctan2(sn,cs)
    if a > numpy.pi/2.0:
        a = a - numpy.pi
    return a
    
def make_rot_matrix(direction, angle):
    """
    Create a rotation matrix corresponding to the rotation around a general
    axis by a specified angle.

    R = dd^T + cos(a) (I - dd^T) + sin(a) skew(d)

    Parameters:

        angle : float a
        direction : array d
    """
    angle = angle * numpy.pi/180.0
    
    d = numpy.array(direction, dtype=numpy.float64)
    d /= numpy.linalg.norm(d)

    eye = numpy.eye(3, dtype=numpy.float64)
    ddt = numpy.outer(d, d)
    skew = numpy.array([[    0,  d[2],  -d[1]],
                     [-d[2],     0,  d[0]],
                     [ d[1], -d[0],    0]], dtype=numpy.float64)

    mtx = ddt + numpy.cos(angle) * (eye - ddt) + numpy.sin(angle) * skew
    return mtx    

def rotate_vector(vec, mtxa):
    mtx = numpy.matrix(mtxa, dtype=numpy.float64)
    vec = numpy.matrix(vec, dtype=numpy.float64)
    nvec = mtx * vec.getT()

    if vec.shape == (1,3):
        return nvec.getT().getA1()
    else:
        return nvec.getT().getA()

def optimize_xtal_offset(info, kappa_axis=KAPPA_AXIS):
    """Optimize the kappa and Phi rotations required to align the 
    longest cell axis closest to the spindle axis
    
    input:
        - info is a dictionary produced by parser.xds.parse_xparm
        - kappa_axis is the direction vector of the kappa axis at zero spindle rotation
    """
    
    axis_names = ['cell_a_axis', 'cell_b_axis', 'cell_c_axis']
    longest_axis = max(zip(info['unit_cell'], axis_names))[1]
    kmat = make_rot_matrix(kappa_axis, 1.0)
    orig_offset = abs(calc_angle(info[longest_axis], info['rotation_axis']))*180.0/numpy.pi
    offsets = []
    axis = info[longest_axis]
    phi_axis = info['rotation_axis']
    for kappa in range(180):
        naxis = axis
        pmat = make_rot_matrix(phi_axis, 1.0)
        for phi in range(360):
            offset = abs(calc_angle(naxis, info['rotation_axis']))
            offsets.append((offset, kappa, phi))
            naxis = rotate_vector(naxis, pmat)
        phi_axis = rotate_vector(phi_axis, kmat)
        axis = rotate_vector(axis, kmat)
    
    opt_offset, opt_kappa, opt_phi = min(offsets)
    _out = {
        'kappa': opt_kappa,
        'phi': opt_phi,
        'longest_axis': axis_names.index(longest_axis),
        'offset': orig_offset,
        'best_offset': opt_offset,
        'data': numpy.array(offsets),  
    }
    return _out
