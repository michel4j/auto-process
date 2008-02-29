"""
DISTL Parser functions

"""
import utils

class _ParseInfo: pass

_distl = _ParseInfo()
_distl.summary = """
                     File : %s
               Spot Total : %6d
      In-Resolution Total : %6d
    Good Bragg Candidates : %6d
                Ice Rings : %6d
      Method 1 Resolution : %6f
      Method 2 Resolution : %6f
        Maximum unit cell : %6f
%Saturation, Top %d Peaks : %6f
"""
_distl.summary_vars = [
    ('file',1),
    ('total_spots',1),
    ('resolution_spots',1),
    ('bragg_spots',1),
    ('ice_rings',1),
    ('alt_resolution',1),
    ('resolution',1),
    ('max_cell',1),
    ('peaks',1),
    ('saturation',1),
    ]

def parse_distl(filename):
    """
    Parse DISTL log file and return dictionary of values
    
    """
    
    info = None
    data = utils.load_file(filename)
    
    sum_vals, pos = utils.scanf(_distl.summary, data)
    if sum_vals:
        info = utilscast_params(_distl.summary_vars, sum_vals)
    
    return info
