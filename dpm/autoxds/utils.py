"""
Generic Utiltites for AutoXDS

"""

    
import os
import sys
import re
import math
from math import exp
import fnmatch
import shutil
import commands
from dpm.imageio import read_header
from dpm.parser.utils import Table
from dpm.utils import magic
from dpm.utils import fitting
import numpy
from dpm.utils.prettytable import PrettyTable, MSWORD_FRIENDLY
from dpm.utils.odict import SortedDict
import textwrap


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

def resolution_shells(resolution, num=10.0):
    
    def _angle(resol):
        return numpy.arcsin( 0.5 * 1.0 / resol )
        
    def _resol(angl):
        return round(0.5 * 1.0 / numpy.sin (angl),2)
                 
    max_angle = _angle( resolution )
    min_angle = _angle( 25.0)
    angles = numpy.linspace(min_angle, max_angle, num)
    return map(_resol, angles)


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

def prepare_work_dir(work_dir_parent, prefix='xds', backup=False):
    """ 
    Creates a work dir for AutoXDS to run. Increments run number if 
    directory already exists.
    
    """
    
    workdir = "%s/%s" % (work_dir_parent, prefix)
    exists = os.path.isdir(workdir)
    
    if not exists:
        os.makedirs(workdir)
    elif backup:
        count = 0
        while exists:
            count += 1
            bkdir = "%s/%s.%02d" % (work_dir_parent, prefix, count)
            exists = os.path.isdir(bkdir)
        shutil.move(workdir, bkdir)
        os.makedirs(workdir)

    return workdir

    
def get_dataset_params(img_file, screen=False):
    """ 
    Determine parameters for the data set 
    returns a dictionary of results
    
    """
    directory, filename = os.path.split(os.path.abspath(img_file))

    file_pattern = re.compile('^(.*)([_.])(\d+)(\..+)?$')
    fm = file_pattern.search(filename)
    parts = fm.groups()
    _dataset_name = parts[0]
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

    reference_image = os.path.join(directory, file_list[0])
    
    parts = fm.groups()
    first_frame = int (parts[2])
    if first_frame == 0: first_frame = 1
    frame_count = len(file_list)
    if frame_count < 4:
        print 'AutoXDS ERROR: You need at least 4 frames in the set! Only %d found' % frame_count
        sys.exit(1)
        
    info = read_header(reference_image)
    info['frame_count'] = frame_count
    info['dataset_name'] = _dataset_name
    info['file_template'] = "%s/%s" % (directory, xds_template)        
    info['file_format'] = magic.from_file(reference_image)
    #determine spot range
    spot_range = []
    # up to 5 deg at the beginning
    r_s = first_frame
    r_e = first_frame
    while r_e < (first_frame + frame_count) and (r_e - r_s)*info['oscillation_range'] <= 5.0:
        r_e += 1
    spot_range.append( (r_s, r_e-1) )
    
    # up to 5 deg starting at 90 deg
    r_s = first_frame + int(90.0 / info['oscillation_range'])
    if r_s < (first_frame + frame_count):
        r_e = r_s
        while r_e < (first_frame + frame_count) and (r_e - r_s)*info['oscillation_range'] <= 5.0:
            r_e += 1
        spot_range.append( (r_s, r_e-1) )
    info['spot_range'] = spot_range
    if screen:
        info['data_range'] = spot_range[0]
    else:
        info['data_range'] = (first_frame, first_frame + frame_count-1)
    
    #info['spot_range'] = [info['data_range']]
    
    # initialize default dummy values for other parameters
    info['reindex_matrix'] = None
    info['unit_cell'] = (0,0,0,0,0,0)
    info['space_group'] = 0
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
    Takes a table of statistics and determines the optimal resolutions
    The table is a list of dictionaries each with at least the following fields
    record = {
        'shell': string convertible to float
        'r_meas': float
        'r_mrgdf': float
        'i_sigma' : float
    }
    
    """
    shells = table[:-1]
    resol_i = float(shells[0]['shell'])
    resol_r = float(shells[0]['shell'])
    pos = 0
    while pos < len(shells):
        if shells[pos]['i_sigma'] >= 1.0:
            resol_i = float(shells[pos]['shell'])
        elif shells[pos]['i_sigma'] == -99.0:
            resol_i = float(shells[pos]['shell'])
        else:
            break
        pos += 1
    pos = 0   
    while pos < len(shells):
        if abs(shells[pos]['r_mrgdf']) <= 40.0:
            resol_r = float(shells[pos]['shell'])
        elif shells[pos]['r_mrgdf'] == -99.0:
            resol_r = float(shells[pos]['shell'])
        else:
            break
        pos += 1

    return (float(resol_i), float(resol_r))

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

def execute_pointless_retry():
    f = open('pointless.com', 'w')
    cmd = """pointless << eof
xdsin INTEGRATE.HKL
xmlout pointless.xml
choose solution 1
eof
"""
    f.write(cmd)
    f.close()
    sts, output = commands.getstatusoutput('sh pointless.com >> xds.log')
    return sts==0     

def execute_best(time, anomalous=False):
    anom_flag = ''
    if anomalous:
        anom_flag = '-a'
    command  = "best -t %f -q " % time
    command += " -e none -M 1 -w 0.2 %s -dna best.xml" % anom_flag
    command += " -xds CORRECT.LP BKGPIX.cbf XDS_ASCII.HKL >> best.log"
    sts, output = commands.getstatusoutput(command)
    return sts==0

def execute_distl(filename):
    sts, output = commands.getstatusoutput('labelit.distl %s > distl.log' % filename)
    return sts==0

def score_crystal(resolution, mosaicity, r_meas, i_sigma, std_spot, std_spindle, subtree_skew, ice_rings):
#    score = [ 1.0,
#        -0.7 * math.exp(-4.0/resolution),
#        -0.2 * std_spindle ,
#        -0.05 * std_spot ,
#        -0.2 * mosaicity,
#        -0.01 * abs(r_meas),
#        -0.2 * 2.0 / i_sigma,
#        -0.05 * ice_rings,
#        ]
    score = [ 1.0,
        -0.45 * max(0.0, min(1.0, math.exp(-4.0 + resolution))),
        -0.2 * max(0.0, min(1.0, math.exp(-3.0 + std_spot))),
        -0.05 * max(0.0, min(1.0, math.exp(-1.0 + std_spindle))),
        -0.1 * max(0.0, min(1.0, math.exp(-0.5 + mosaicity))),
        -0.1 * max(0.0, min(1.0, math.exp(-5.0 + abs(r_meas)))),
        -0.05 * max(0.0, min(1.0, math.exp(1.0 - abs(i_sigma)))),
        -0.05 * max(0.0, min(1.0, math.exp(ice_rings))),
        ]
    
    #names = ['Root', 'Resolution', 'Spindle', 'Spot', 'Mosaicity','R_meas', 'I/Sigma', 'Ice', 'Satellites']
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
    p = [ 1.00000857e+00,  -3.10243288e-04,   3.01020914e+00]    
    return 1.0 - (p[0] * exp( p[1] * (e**p[2])))

def _files_exist(file_list):
    for f in file_list:
        if not os.path.exists(f):
            return False
    return True

def print_table(info, multiple=False):
    txt = '*** Auto-indexing Diagnostics ***\n'
    
    if not multiple:
        length = max([len(v) for v in info.keys()])
        format = "%%%ds: %%s\n" % length
        for k, v in info.items():
            txt += format % (k, v)
    else:
        formats = {}
        _t = Table(info)
        for k in info[0].keys():
            length = max([ len(str(v)) for v in _t[k] ])
            length = max(length, len(k))
            formats[k] = "%%%ds " % length
        for k, f in formats.items():
            txt += f % (k),
        txt += '\n'
        for l in info:
            for k, v in l.items():
                txt += f % (v),
            txt += '\n'
    return txt
    

def check_init():
    file_list = ['XYCORR.LP','X-CORRECTIONS.cbf', 'Y-CORRECTIONS.cbf',
        'INIT.LP', 'BKGINIT.cbf', 'BLANK.cbf', 'GAIN.cbf']
    return _files_exist(file_list)

def check_spots():
    file_list = ['COLSPOT.LP','SPOT.XDS']
    return _files_exist(file_list)
    
def check_index():
    file_list = ['XPARM.XDS','SPOT.XDS', 'IDXREF.LP']
    return _files_exist(file_list)

def update_xparm():
    if os.path.exists('GXPARM.XDS'):
        backup_file('XPARM.XDS')
        shutil.copy('GXPARM.XDS', 'XPARM.XDS')
    
def diagnose_index(info):
    # quality_code is integer factors
    # 256 = irrecoverable failure 
    # 128 = not enough spots 
    #  64 = cluster dimension < 3 
    #  32 = spot deviation > 3.0
    #  16 = percent indexed < 70
    #   8 = cluster index error > 0.05
    #   4 = no distinct subtree
    #   2 = more than one distinct subtree
    #   1 = index origin delta > 6
    data = {}
    data['quality_code'] = 0
    if info['failure_code'] == 1:
        data['quality_code'] |=  64
    elif info['failure_code'] == 2:
        data['quality_code'] |=  16
    elif info['failure_code'] == 3:
        data['quality_code'] |=  128
    elif info['failure_code'] == 4:
        data['quality_code'] |=  32
    elif info['failure_code'] in [5,6]:
        data['quality_code'] |=  256
        
    _refl = _spots = None
    _st = info.get('subtrees')
    _local_spots = info.get('local_indexed_spots')
    _summary = info.get('summary')
    if _summary is not None:
        _spots = _summary.get('selected_spots')
        _refl = _summary.get('indexed_spots')
        data['indexed_spots'] = _refl
        data['percent_overlap'] = 100.0 * _summary.get('rejects_overlap')/_refl
        data['percent_too_far'] = 100.0 * _summary.get('rejects_far')/_refl

    # get percent of indexed reflections
    data['percent_indexed'] = 0.0
    data['primary_subtree'] = 0.0
    if _refl is not None and _st is not None and len(_st)>0:
        data['primary_subtree'] = 100.0 * _st[0].get('population')/float(_local_spots)
    
    if _spots is not None:
        data['percent_indexed'] = 100.0 * _spots/_refl
    if data['percent_indexed'] < 70 : data['quality_code'] |= 16
    
    # get number of subtrees
    data['distinct_subtrees'] = 0
    data['satellites'] = 0
    if _st is not None and len(_st) > 0 and _refl is not None:
        data['distinct_subtrees'] = 0
        data['satellites'] = 0
        for item in _st:
            _percent = 100.0 * item.get('population')/float(_local_spots)
            if _percent >= 30.0:
                data['distinct_subtrees'] += 1
            elif _percent > 1:
                data['satellites']  += 1
            else:
                break
    if data['distinct_subtrees'] > 1 :
        data['quality_code'] |= 2
    elif data['distinct_subtrees'] == 0 :
        data['quality_code'] |= 4
        
    # get max, std deviation of integral indices
    _indices = info.get('cluster_indices')
    data['index_error_max'] = 999.
    data['index_error_mean'] = 999. 
    if _indices is not None and len(_indices) > 0:
        t = Table(_indices)
        _index_array = numpy.array(t['hkl'])
        _index_err = abs(_index_array - _index_array.round())
        data['index_error_max'] = _index_err.max()
        data['index_error_mean'] = _index_err.mean()
    if data['index_error_mean'] > 0.05 : data['quality_code'] |= 8
    
    # get spot deviation 
    data['spot_deviation'] = 999.
    if _summary  is not None:
        data['spot_deviation'] = info['summary'].get('stdev_spot')
    if data['spot_deviation'] > 3 : data['quality_code'] |= 32
    
    # get rejects     
    data['cluster_dimension'] = info.get('cluster_dimension', 0)
    if data['cluster_dimension'] < 3 : data['quality_code'] |= 64
    
    # get quality of selected index origin
    _origins = info.get('index_origins')
    _sel_org = info.get('selected_origin')
    data['index_origin_delta'] = 999.
    data['new_origin'] = None
    if _sel_org is not None and _origins is not None and len(_origins)>0:
        for _org in _origins:
            if _org['index_origin'] == _sel_org:
                data['index_origin_delta'] = _org.get('delta')
                data['new_origin'] = _org.get('position')
                #data['index_deviation'] = _org.get('deviation')
                break    
    if data['index_origin_delta'] > 6 : data['quality_code'] |= 1
    data['failure_code'] = info['failure_code']
    
    return data

def load_spots(filename='SPOT.XDS'):
    try:
        spot_list = numpy.loadtxt(filename)
    except:
        from pylab import load
        spot_list = load(filename, comments='!')
    return spot_list

def save_spots(spot_list, filename='SPOT.XDS'):
    f = open(filename, 'w')
    for spot in spot_list:
        if len(spot)>4:
            txt = '%10.2f%10.2f%10.2f%9.0f.%8d%8d%8d\n' % tuple(spot)
        else:
            txt = '%10.2f%10.2f%10.2f%9.0f.\n' % tuple(spot)
        f.write(txt)
    f.close()

def filter_spots(spot_list, sigma=0, unindexed=False):
    new_list = spot_list
    def _indexed(a):
        for v in a:
            if abs(v)>0.01:
                return True
        return False
            
    if sigma > 0:
        new_list = [sp for sp in new_list if sp[3] > sigma ]
    if unindexed and len(new_list[0]) > 4:
        new_list = [sp for sp in new_list if _indexed(sp[4:])]
    return new_list

def get_xplan_strategy(info):
    plan = {}
    xplan = info['strategy'].get('xplan')
    res = info['scaling']['resolution'][0]
    osc = Table(info['indexing']['oscillation_ranges'])
    x = numpy.array(osc['resolution'])
    y = numpy.array(osc['angle'])
    p1 = fitting.linear_fit(x, y)
    plan['resolution'] = res
    plan['delta_angle'] = fitting.line_func(res, p1)
    
    _scens = info['strategy']['xplan'].get('summary')
    pos = len(_scens)
    _sel = _scens[-1]
    while pos > 0:
        pos -=1
        if _scens[pos]['completeness'] >= min(99.0, _sel['completeness']):
            _sel = _scens[pos]
            
    plan.update(_sel)
    plan['number_of_images'] = int(plan['total_angle']/plan['delta_angle'])
    return plan    

def backup_file(filename):
    if os.path.exists(filename):
        index = 0
        while os.path.exists('%s.%0d' % (filename, index)):
            index += 1
        shutil.copy(filename, '%s.%0d' % (filename, index))
    return

def match_code(src, tgt):
    # bitwise compare two integers
    return src|tgt == src

def match_none(src, tgts):
    for tgt in tgts:
        if src|tgt == src:
            return False
    return True

def match_any(src, tgts):
    for tgt in tgts:
        if src|tgt == src:
            return True
    return False 

def text_heading(txt, level=1):
    if level in [1,2]:
        _pad = ' '*((78 - len(txt))//2)
        txt = '%s%s%s' % (_pad, txt, _pad)
        if level == 2:
            _banner = '-'*78
        else:
            _banner = '*'*78
            txt = txt.upper()
        _out = '\n%s\n%s\n%s\n\n' % (_banner, txt, _banner)
    elif level == 3:
        _pad = '*'*((74 - len(txt))//2)
        _out = '\n%s  %s  %s\n\n' % (_pad, txt, _pad)
    elif level == 4:
        _out = '\n%s:\n' % (txt.upper(),)
    else:
        _out = txt
    return _out

def add_margin(txt, size=1):
    _margin = ' '*size
    return '\n'.join([_margin+s for s in txt.split('\n')]) 


def format_section(section, level=1, invert=False, fields=[], show_title=True):
    _section = section
    if show_title:
        file_text = text_heading(_section['title'], level)
    else:
        file_text = ''
        
    if _section.get('table') is not None:
        _key = 'table'
    elif _section.get('table+plot') is not None:
        _key = 'table+plot'
    else:
        return str(section)
    pt = PrettyTable()
    if not invert:
        for i, d in enumerate(_section[_key]):
            dd = SortedDict(d)
            values = dd.values()
            if i == 0:
                keys = dd.keys()
                pt.add_column(keys[0], keys[1:],'l')
            pt.add_column(values[0], values[1:], 'r')
    else:
        for i, d in enumerate(_section[_key]):
            dd = SortedDict(d)
            values = dd.values()
            if i == 0:
                keys = dd.keys()
                pt.field_names = keys
            pt.add_row(values)
        pt.align = "r"
    if len(fields) == 0:
        file_text += pt.get_string()
    else:
        file_text += pt.get_string(fields=fields)
    file_text +='\n'
    if _section.get('notes'):
        all_notes = _section.get('notes').split('\n')
        notes = []
        for note in all_notes:
            notes += textwrap.wrap( note, width=60, subsequent_indent="    ")
        file_text += '\n'.join(notes)
    file_text += '\n'
    return file_text
    
