"""
Generic Utiltites for AutoXDS

"""

    
import os
import re
import math
from math import exp
import fnmatch
import shutil
import tempfile
import commands
from dpm.imageio import marccd


# each rule is a list of 9 boolean values representing
# a=a, a=c, b=c, a=b=c, alpha=90, beta=90, gamma=90, alpha=120, beta=120, gamma=120
_lattice_rules = {
    'a':[False, False, False, False, False, False, False, False, False, False],
    'm':[False, False, False, False, True, False, True, False, False, False],
    'o':[False, False, False, False, True, True, True, False, False, False],
    't':[True, False, False, False, True, True, True, False, False, False],
    'h':[True, False, False, False, True, True, False, False, False, True],
    'c':[True, True, True, True, True, True, True, False, False, False]
    }

SPACE_GROUP_NAMES = {
    1:'P1', 3:'P2', 4:'P2(1)', 5:'C2', 16:'P222', 
    17:'P222(1)', 18:'P2(1)2(1)2',
    19:'P2(1)2(1)2(1)', 21:'C222', 20:'C222(1)', 22:'F222', 23:'I222',
    24:'I2(1)2(1)2(1)', 75:'P4', 76:'P4(1)', 77:'P4(2)', 78:'P4(3)', 89:'P422',
    90:'P42(1)2', 91:'P4(1)22', 92:'P4(1)2(1)2', 93:'P4(2)22', 94:'P4(2)2(1)2',
    95:'P4(3)22', 96:'P4(3)2(1)2', 79:'I4', 80:'I4(1)', 97:'I422', 98:'I4(1)22',
    143:'P3', 144:'P3(1)', 145:'P3(2)', 149:'P312', 150:'P321', 151:'P3(1)12',
    152:'P3(1)21', 153:'P3(2)12', 154:'P3(2)21', 168:'P6', 169:'P6(1)',
    170:'P6(5)', 171:'P6(2)', 172:'P6(4)', 173:'P6(3)', 177:'P622', 178:'P6(1)22',
    179:'P6(5)22', 180:'P6(2)22', 181:'P6(4)22', 182:'P6(3)22', 146:'R3',
    155:'R32', 195:'P23', 198:'P2(1)3', 207:'P432', 208:'P4(2)32', 212:'P4(3)32',
    213:'P4(1)32', 196:'F23', 209:'F432', 210:'F4(1)32', 197:'I23', 199:'I2(1)3',
    211:'I432', 214:'I4(1)32'             
    }

POINT_GROUPS = {
    'cI':[197, 199, 211, 214],
    'cF':[196, 209, 210],
    'cP':[195, 198, 207, 208, 212, 213],
    'hR':[146, 155],
    'hP':[143, 144, 145, 149, 150, 151, 152, 153, 154, 168, 
          169, 170, 171, 172, 173, 177, 178, 179, 180, 181, 182],
    'tI':[79, 80, 97, 98],
    'tP':[75, 76, 77, 78, 89, 90, 91, 92, 93, 94, 95, 96],
    'oI':[23, 24],
    'oF':[22],
    'oC':[21, 20],
    'oP':[16, 17, 18, 19],
    'mC':[5],
    'mI':[5],
    'mP':[3, 4],
    'aP':[1]            
    }

CRYSTAL_SYSTEMS = {
    'a':'triclinic',
    'm':'monoclinic',
    'o':'orthorombic',
    't':'tetragonal',
    'h':'rhombohedral',
    'c':'cubic'
    }                    
def get_character(sg_number=1):
    return [k for k, v in POINT_GROUPS.items() if sg_number in v][0]
    
def _all_files(root, patterns='*'):
    """ 
    Return a list of all the files in a directory matching the pattern
    
    """
    patterns = patterns.split(';')
    path, subdirs, files = os.walk(root).next()
    sfiles = []
    for name in files:
        for pattern in patterns:
            if fnmatch.fnmatch(name,pattern):
                sfiles.append(name)
    sfiles.sort()
    return sfiles

def get_cpu_count():
    return os.sysconf('SC_NPROCESSORS_ONLN')

def prepare_work_dir(work_dir_parent, prefix='xds'):
    """ 
    Creates a work dir for AutoXDS to run. Increments run number if 
    directory already exists.
    
    """
    
    count = 0
    workdir = "%s/%s-%d" % (work_dir_parent, prefix, count)
    exists = os.path.isdir(workdir)
    
    while exists:
        count += 1
        workdir = "%s/%s-%d" % (work_dir_parent, prefix, count)
        exists = os.path.isdir(workdir)

    os.makedirs(workdir)
    return workdir
    
def get_dataset_params(img_file, screen=False):
    """ 
    Determine parameters for the data set 
    returns a dictionary of results
    
    """
    reference_image = os.path.abspath(img_file)
    directory, filename = os.path.split(reference_image)

    file_pattern = re.compile('^(.*)([_.])(\d+)(\..+)?$')
    fm = file_pattern.search(filename)
    parts = fm.groups()
    if len(parts) == 4:
        prefix = parts[0] + parts[1]
        if parts[3]:
            file_extension = parts[3]
        else:
            file_extension = ""
    filler = '?' * len(parts[2])

    file_template = "%s%s0%dd%s" % (prefix, '%', len(parts[2]), file_extension)
    xds_template = "%s%s%s" % (prefix, filler, file_extension)

    file_list = list( _all_files(directory, xds_template) )
    fm = file_pattern.search(file_list[0])
    parts = fm.groups()
    first_frame = int (parts[2])
    if first_frame == 0: first_frame = 1
    frame_count = len(file_list)
    
    info = marccd.read_header(img_file)
    info['file_template'] = "%s/%s" % (directory, xds_template)
    
    # if template is longer create symlink
    if len(info['file_template']) + len(info['file_format']) > 49:
        tmp_dir = tempfile.mktemp('','xds-')
        os.symlink(directory, tmp_dir)
        info['file_template'] = "%s/%s" % (tmp_dir, xds_template)
        
    
    #determine spot range
    spot_range = []
    # up to 5 deg at the beginning
    r_s = first_frame
    r_e = first_frame
    while r_e < (first_frame + frame_count) and (r_e - r_s)*info['oscillation_range'] <= 5.0:
        r_e += 1
    spot_range.append( (r_s, r_e) )
    
    # up to 5 deg starting at 90 deg
    r_s = first_frame + int(90.0 / info['oscillation_range'])
    if r_s < (first_frame + frame_count):
        r_e = r_s
        while r_e < (first_frame + frame_count) and (r_e - r_s)*info['oscillation_range'] <= 5.0:
            r_e += 1
        spot_range.append( (r_s, r_e) )
    info['spot_range'] = spot_range
    if screen:
        info['data_range'] = spot_range[0]
    else:
        info['data_range'] = (first_frame, first_frame + frame_count - 1)
    
    # initialize default dummy values for other parameters
    info['reindex_matrix'] = None
    info['unit_cell'] = (0,0,0,0,0,0)
    info['space_group'] = 0
    info['cpu_count'] = get_cpu_count()
    info['reference_image'] = reference_image
    
    return info

def tidy_cell(unit_cell, character):
    """
    Tidies the given unit cell parameters given as a list/tuple of 6 values
    according to the rules of the lattice character
    
    """
    
    new_cell = [0.,0.,0.,0.,0.,0]
    rule = _lattice_rules[ character[0] ]
    
    def same_value_cleaner(v, rule=False):
        if rule:
            vi = sum(v)/len(v)
            v = (vi,)*len(v)
        return v

    def equality_cleaner(v1, c1, rule=False):
        if rule:
            v1 = c1
        return v1
    new_cell[0:4] = unit_cell[0:4]
    new_cell[0:2] = same_value_cleaner( new_cell[0:2], rule[0] )
    new_cell[1:3] = same_value_cleaner( new_cell[1:3], rule[1] )
    new_cell[2:4] = same_value_cleaner( new_cell[2:4], rule[2] )
    new_cell[0:4] = same_value_cleaner( new_cell[0:4], rule[3] )

    for i in range(3):
        new_cell[3+i] = equality_cleaner( unit_cell[3+i], 90, rule[4+i] )
    for i in range(3):
        new_cell[3+i] = equality_cleaner( new_cell[3+i], 120, rule[7+i] )

    return tuple(new_cell)
     

def cell_volume(unit_cell):
    """
    Calculate the unit cell volume from the cell parameters given as a list/tuple of 6 values
    
    """
    a, b, c, alpha, beta, gamma = unit_cell
    alpha, beta, gamma = alpha*math.pi/180.0, beta*math.pi/180.0, gamma*math.pi/180.0
    v = a * b * c * ((1- math.cos(alpha)**2 - math.cos(beta)**2 - math.cos(gamma)**2) + 2*math.cos(alpha)*math.cos(beta)*math.cos(gamma))**0.5
    
    return v 


def select_resolution(table):
    """
    Takes a table of statistics and determines the optimal resolution
    The table is a list of dictionaries each with at least the following fields
    record = {
        'shell': float
        'r_meas': float
        'i_sigma' : float
    }
    
    """
    resol = table[-1]['shell']
    pos = 0
    while  pos < len(table) and table[pos]['i_sigma'] >= 1.5:
        resol = table[pos]['shell']
        pos +=1
    if pos < len(table) and table[pos]['i_sigma'] <= -99.0:
        resol = table[-1]['shell']
    
    return resol

def select_lattices(table):
    """
    Takes a table of lattice statistics and returns the sorted short-list 
    The table is a list of dictionaries each with at least the following fields
    record = {
        'type': str
        'quality': float
        'unit_cell' : tuple of 6 float
        'reindex_matrix': tuple of 12 ints
    }
    
    """
    
    split_point = 10
    while table[split_point]['quality'] < 30:
        split_point += 1
    result = table[:split_point]

    def _cmp(x,y):
        a,b = x['character'], y['character']
        return cmp(POINT_GROUPS[b], POINT_GROUPS[a])
    
    result.sort(_cmp)
    return result
    

def execute_xds():
    sts, output = commands.getstatusoutput('xds >> xds.log')
    return sts==0

def execute_xds_par():
    sts, output = commands.getstatusoutput('xds_par >> xds.log')
    return sts==0


def execute_xscale():
    sts, output = commands.getstatusoutput('xscale_par >> xds.log')
    return sts==0

def execute_xdsconv():
    sts, output = commands.getstatusoutput('xdsconv >> xds.log')
    return sts==0

def execute_f2mtz():
    sts, output = commands.getstatusoutput('sh f2mtz.com >> xds.log')
    return sts==0
       
def execute_pointless():
    sts, output = commands.getstatusoutput('pointless xdsin INTEGRATE.HKL xmlout pointless.xml >> xds.log')
    return sts==0

def execute_best(time, anomalous=False):
    anom_flag = ''
    if anomalous:
        anom_flag = '-a'       
    command  = "best -t %f -i2s 1.5 -q -pl best.plan" % time
    command += " -e none -M 1 -w 0.2 %s -dna best.xml" % anom_flag
    command += " -xds CORRECT.LP BKGPIX.pck XDS_ASCII.HKL >> best.log" 
    
    sts, output = commands.getstatusoutput(command)
    return sts==0

def execute_distl(filename):
    sts, output = commands.getstatusoutput('labelit.distl %s > distl.log' % filename)
    return sts==0

def save_files(prefix):
    os.mkdir(prefix)
    shutil.copy('XDS.INP',prefix)
    shutil.copy('CORRECT.LP',prefix)
    shutil.copy('INTEGRATE.LP',prefix)
    shutil.copy('XDS_ASCII.HKL', prefix)
    shutil.copy('INTEGRATE.HKL', prefix)
    shutil.copy('GXPARM.XDS', prefix)
    files = {
        'correct': '%s/XDS_ASCII.HKL' % prefix,
        'integrate': '%s/XDS_ASCII.HKL' % prefix,
        'prefix': prefix
        }
    return files

def score_crystal(resolution, mosaicity, r_meas, i_sigma, std_spot, std_spindle, subtree_skew, ice_rings):
    score = [ 1.0,
        -0.7 * math.exp(-4.0 / resolution),
        -0.2 * std_spindle ,
        -0.05 * std_spot ,
        -0.2 * mosaicity,
        -0.01 * abs(r_meas),
        -0.2 * 2.0 / i_sigma,
        -0.05 * ice_rings,
        -0.5 * subtree_skew]
    
    names = ['Root', 'Resolution', 'Spindle', 'Spot', 'Mosaicity','R_meas', 'I/Sigma', 'Ice','Satellites']
    #for name, contrib in zip(names,score):
    #    print '\t\t%s : %0.3f' % (name, contrib)
        
    return sum(score)


# Physical Constats
h = 4.13566733e-15 # eV.s
c = 299792458e10   # A/s
S111_a_rt   = 5.4310209 # A at RT
S111_a_ln2  = 5.4297575 # A at LN2 

def energy_to_wavelength(energy): #Angstroms
	return (h*c)/(energy)

def air(e):
    p = [  1.00000857e+00,  -3.10243288e-04,   3.01020914e+00]    
    return 1.0 - (p[0] * exp( p[1] * (e**p[2])))
