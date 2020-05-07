import bisect
import gzip
import math
import os
import itertools

import json
import numpy
from collections import defaultdict
from autoprocess.utils.misc import Table

DEBUG = False
XTAL_TABLE_FILE = os.path.join(os.path.dirname(__file__), 'data', 'xtal_tables.jsonz')
with gzip.open(XTAL_TABLE_FILE, 'rb') as handle:
    XTAL_TABLES = json.load(handle)

SG_SYMBOLS = {int(k): v['name'] for k, v in list(XTAL_TABLES.items())}
SG_NAMES = {int(k): v['symbol'] for k, v in list(XTAL_TABLES.items())}
SG_NUMBERS = {v['name']: int(k) for k, v in list(XTAL_TABLES.items())}
CHIRAL_SPACE_GROUPS = [int(k) for k, v in list(XTAL_TABLES.items()) if v['chiral']]
CENTRO_SYMETRIC = {int(k): '-X,-Y,-Z' in v['symmetry'] for k, v in list(XTAL_TABLES.items())}

# each rule is a list of 9 boolean values representing
# a=b, a=c, b=c, a=b=c, alpha=90, beta=90, gamma=90, alpha=120, beta=120, gamma=120
_lattice_rules = {
    'a': [False, False, False, False, False, False, False, False, False, False],
    'm': [False, False, False, False, True, False, True, False, False, False],
    'o': [False, False, False, False, True, True, True, False, False, False],
    't': [True, False, False, False, True, True, True, False, False, False],
    'h': [True, False, False, False, True, True, False, False, False, True],
    'c': [False, False, False, True, True, True, True, False, False, False]
}


def resolution_shells(resolution, num=12):
    def _angle(resol):
        return 2 * numpy.arcsin(0.5 * 1.0 / resol)

    def _resol(angl):
        return round(0.5 * 1.0 / numpy.sin(0.5 * angl), 2)

    max_angle = _angle(resolution)
    min_angle = _angle(5.0)
    angles = numpy.linspace(min_angle, max_angle, num)
    return list(map(_resol, angles))


def get_character(sg_number=1):
    return XTAL_TABLES[str(sg_number)]['lattice_character']


def get_number(sg_name):
    return SG_NUMBERS[sg_name]


def get_pg_list(lattices, chiral=True):
    """
    Takes a list of lattice characters and returns a unique list of the
    names of the lowest symmetry pointgroup.
    """

    pgset = set(
        [SG_NUMBERS[v['point_group']] for v in list(XTAL_TABLES.values()) if v['lattice_character'] in lattices])
    if chiral:
        pgset = pgset.intersection(set(CHIRAL_SPACE_GROUPS))
    pgnums = sorted(pgset)
    return [SG_SYMBOLS[n] for n in pgnums]


def get_sg_table(chiral=True):
    """Generate a table of all spacegroups for each given crystal system."""
    tab = defaultdict(list)
    for k, v in list(XTAL_TABLES.items()):
        if (chiral and not v['chiral']): continue
        tab[v['lattice_character']].append(f"{v['symbol']}(#{k})")

    txt = 'Space group numbers for Bravais lattice types:\n\n'
    for k in ['aP', 'mP', 'mC', 'oP', 'oC', 'oA', 'oF', 'oI', 'tP', 'tI', 'hP', 'hR', 'cP', 'cF', 'cI']:
        if k in tab:
            v = tab[k]
            chunks = [v[i:i + 5] for i in range(0, len(v), 5)]
            sg_text = '\n\t'.join(', '.join(sg for sg in chunk) for chunk in chunks)


            txt += f':{k}:\n\t{sg_text}\n\n'
    return txt


def tidy_cell(unit_cell, character):
    """
    Tidies the given unit cell parameters given as a list/tuple of 6 values
    according to the rules of the lattice character
    
    """

    new_cell = list(unit_cell)
    rules = _lattice_rules[character[0]]

    def same_value_cleaner(v):
        vi = sum(v) / len(v)
        v = (vi,) * len(v)
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
        if i in [4, 5, 6]:
            new_cell[i - 1] = equality_cleaner(unit_cell[i - 1], 90.)
        if i in [7, 8, 9]:
            new_cell[i - 4] = equality_cleaner(new_cell[i - 4], 120.)

    return tuple(new_cell)


def cell_volume(unit_cell):
    """
    Calculate the unit cell volume from the cell parameters given as a list/tuple of 6 values
    
    """
    a, b, c, alpha, beta, gamma = unit_cell
    alpha, beta, gamma = alpha * math.pi / 180.0, beta * math.pi / 180.0, gamma * math.pi / 180.0
    v = a * b * c * ((1 - math.cos(alpha) ** 2 - math.cos(beta) ** 2 - math.cos(gamma) ** 2) + 2 * math.cos(
        alpha) * math.cos(beta) * math.cos(gamma)) ** 0.5

    return v


def select_resolution(table, method=2, optimistic=False):
    """
    Takes a table of statistics and determines the optimal resolutions
    The table is a list of dictionaries each with at least the following fields
    record = {
        'shell': string convertible to float
            or  'resol_range': a pair of floats
        'r_meas': float
        'cc_half': float
        'i_sigma' : float
        'signif' : '*' or ' '
    }
    
    returns a tuple the first value of which is the selected resolution,
    and the second value of which is the selectio method where:
    0 : Detector edge
    1 : I/sigma > 0.5
    2 : cc_half == '*'
    3 : DISTL 
    4 : Manualy chosen    
    """

    data = Table(table[:-1])
    if 'shell' in list(data.keys()):
        resol = [float(v) for v in data['shell']]
    else:
        resol = [float(v[1]) for v in data['resol_range']]

    idx = len(resol) - 1

    if method == 1:
        idx = bisect.bisect_left(data['i_sigma'], 0.5)

    if method == 2 and data['signif'].count('*') > 0:
        idx = len(data['signif']) - data['signif'][::-1].index("*") - 1
    elif method == 2:
        idx = len(data['signif']) - 1

    if optimistic and idx < len(resol) - 1:
        idx += 1

    if idx == len(resol) - 1:
        method = 0

    return (resol[idx], method)


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

    x = (x - worst) / float(best - worst)
    return numpy.sqrt(1 - x * x)


def logistic_score(x, best=1, fair=0.5):
    t = 3 * (x - fair) / (best - fair)
    return 1 / (1 + numpy.exp(-t))


def logistic(x, x0=0.0, weight=1.0, width=1.0, invert=False):
    mult = 1 if invert else -1
    return weight / (1 + numpy.exp(mult * width * (x - x0)))


def score_crystal(resolution, completeness, r_meas, i_sigma, mosaicity, std_spot, std_spindle, rejected_fraction):
    scores = numpy.array([
        logistic(resolution, x0=2.0, weight=0.2, width=6, invert=True),
        logistic(completeness, x0=75, weight=0.2, width=0.25),
        logistic(r_meas, x0=6, weight=0.2, width=1, invert=True),
        logistic(i_sigma, x0=30, weight=0.1, width=0.1),
        logistic(mosaicity, x0=0.3, weight=0.1, width=30, invert=True),
        logistic(std_spindle, x0=1.0, weight=0.05, width=2, invert=True),
        logistic(std_spot, x0=2.0, weight=0.05, width=2, invert=True),
        logistic(rejected_fraction, x0=0.1, weight=0.1, width=6, invert=True),
    ])
    weights = numpy.array([0.2, 0.2, 0.2, 0.1, 0.1, 0.05, 0.05, 0.1])
    names = ['Resolution', 'Completeness', 'R_meas', 'I/Sigma', 'Mosaicity', 'Std_spindle', 'Std_spot', 'Rejected']
    values = [resolution, completeness, r_meas, i_sigma, mosaicity, std_spot, std_spindle, rejected_fraction]
    return scores.sum(), list(zip(names, scores / weights, values))


def average_cell(cell_and_weights):
    """Average a series of cell parameters together with weights and return the average cell and standard deviations
        input should be of the form [(cell1, weight), (cell2, weight), ...]
        where cell1 is a container with 6 floats for a,b,c alpha, beta, gamma
    """

    cells = numpy.zeros((len(cell_and_weights), 6))
    weights = numpy.zeros((len(cell_and_weights)))
    for i, cw in enumerate(cell_and_weights):
        cell, weight = cw
        cells[i] = numpy.array(cell)
        weights[i] = weight

    new_cell = (cells.transpose() * weights).sum(1) / weights.sum()
    cell_esd = numpy.sqrt(numpy.dot(weights, (cells - new_cell) ** 2) / weights.sum())
    return (new_cell, cell_esd)


def dist_to_resol(distance, pixel_size, detector_size, wavelength, two_theta=0):
    """Convert from distance in mm to resolution in angstroms.

    Arguments:
    pixel_size      --  pixel size of detector
    detector_size   --  width of detector
    distance   -- detector distance
    energy          --  X-ray energy

    """

    theta = 0.5 * math.atan(0.5 * pixel_size * detector_size / distance)
    theta = theta + two_theta
    return 0.5 * wavelength / math.sin(theta)


def resol_to_dist(resolution, pixel_size, detector_size, wavelength, two_theta=0):
    """Convert from resolution in angstroms to distance in mm.

    Arguments:
    resolution    -- desired resolution
    pixel_size      --  pixel size of detector
    detector_size   --  width of detector
    energy          --  X-ray energy

    """

    theta = math.asin(0.5 * wavelength / resolution)
    theta = max(0, (theta - two_theta))
    return 0.5 * pixel_size * detector_size / math.tan(2 * theta)
