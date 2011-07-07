import numpy
import math

DEBUG = False

# each rule is a list of 9 boolean values representing
# a=b, a=c, b=c, a=b=c, alpha=90, beta=90, gamma=90, alpha=120, beta=120, gamma=120
_lattice_rules = {
    'a':[False, False, False, False, False, False, False, False, False, False],
    'm':[False, False, False, False, True, False, True, False, False, False],
    'o':[False, False, False, False, True, True, True, False, False, False],
    't':[True, False, False, False, True, True, True, False, False, False],
    'h':[True, False, False, False, True, True, False, False, False, True],
    'c':[False, False, False, True, True, True, True, False, False, False]
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

     
def tidy_cell(unit_cell, character):
    """
    Tidies the given unit cell parameters given as a list/tuple of 6 values
    according to the rules of the lattice character
    
    """
    
    new_cell = list(unit_cell)
    rules = _lattice_rules[ character[0] ]
    
    def same_value_cleaner(v):
        vi = sum(v)/len(v)
        v = (vi,)*len(v)
        return v

    def equality_cleaner(v1, c1):
        v1 = c1
        return v1
    
    for i, rule in enumerate(rules):
        if not rule: continue
        # clean cell axis lengths
        if i == 0:           
            new_cell[0:2] = same_value_cleaner(unit_cell[0:2])
        if i == 1:
            new_cell[0], new_cell[2] = same_value_cleaner([unit_cell[0], unit_cell[2]])
        if i == 2:
            new_cell[1], new_cell[2] = same_value_cleaner([unit_cell[1], unit_cell[2]])
        if i == 3:
            new_cell[0:3] = same_value_cleaner(unit_cell[0:3])
        
        # clean angles
        if i in [4,5,6]: 
            new_cell[i-1] = equality_cleaner( unit_cell[i-1], 90.)
        if i in [7,8,9]:
            new_cell[i-4] = equality_cleaner( new_cell[i-4], 120.)

    return tuple(new_cell)

def cell_volume(unit_cell):
    """
    Calculate the unit cell volume from the cell parameters given as a list/tuple of 6 values
    
    """
    a, b, c, alpha, beta, gamma = unit_cell
    alpha, beta, gamma = alpha*math.pi/180.0, beta*math.pi/180.0, gamma*math.pi/180.0
    v = a * b * c * ((1- math.cos(alpha)**2 - math.cos(beta)**2 - math.cos(gamma)**2) + 2*math.cos(alpha)*math.cos(beta)*math.cos(gamma))**0.5
    
    return v 


def select_resolution(table, method=1):
    """
    Takes a table of statistics and determines the optimal resolutions
    The table is a list of dictionaries each with at least the following fields
    record = {
        'shell': string convertible to float
            or  'resol_range': a pair of floats
        'r_meas': float
        'r_mrgdf': float
        'i_sigma' : float
    }
    
    returns a tuple the first value of which is the selected resolution,
    and the second value of which is the selectio method where:
    0 : Detector edge
    1 : I/sigma > 1
    2 : R-mrgdF < 40
    3 : DISTL 
    4 : Manualy chosen    
    """

    shells = table[:-1]
    _rmet = 0
    for shell in shells:
        if 'shell' in shell:
            res = float(shell['shell'])
        elif 'resol_range' in shell:
            res = shell['resol_range'][1]
        i_sigma = shell['i_sigma']
        r_mgdf = shell.get('r_mrgdf', -99)
        resol_i = res
        if (method == 1) and i_sigma < 1.0:
            _rmet = method
            break
        elif (method == 2) and r_mgdf > 40.0:
            _rmet = method
            break
            
    return (resol_i, _rmet)


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
    

    

def score_penalty(x, best=1, worst=0):
    """Calculate an exponential score penalty for any value given the limits [best, worst]
    so that values close to the best are penalized least but easily distinguishable from each other
    while those far away from best but close to worst are penalized most but not that easily distinguishable.
    
    Any value better than or equal to best is not penalized and any value worse than worst, is penalized maximally
    """
    
    # clip the values so they stay in the range
    if best > worst:
        x = min(best, max(worst, x))
    else:
        x = max(best, min(worst, x))
    
    x = (x-worst)/float(best-worst)
    return numpy.sqrt(1 - x*x)

    
def score_crystal(resolution, completeness, r_meas, i_sigma, mosaicity, std_spot, std_spindle, ice_rings):
            
    score = [ 1.0,
        -0.20 * score_penalty(resolution, 1.0, 6.0),
        -0.20 * score_penalty(completeness, 100, 70),
        -0.10 * score_penalty(r_meas, 1, 50),
        -0.10 * score_penalty(i_sigma, 20, 1),
        -0.10 * score_penalty(mosaicity, 0.1, 4),
        -0.10 * score_penalty(std_spindle, 0.01, 2),
        -0.05 * score_penalty(std_spot, 1, 4),
        -0.05 * score_penalty(ice_rings, 0, 8),
        ]
    
    if DEBUG:
        names = ['Root', 'Resolution', 'Completeness', 'R_meas', 'I/Sigma', 'Mosaicity', 'Std_spindle', 'Std_spot', 'Ice']
        vals = [1, resolution, completeness, r_meas, i_sigma, mosaicity, std_spindle, std_spot, ice_rings]
        for name, contrib, val in zip(names,score, vals):
            print '\t\t%s : %0.3f (%0.3f)' % (name, contrib, val)
        
    return sum(score)
