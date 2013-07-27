
from dpm.utils import log, programs, misc
import dpm.errors
import os
_logger = log.get_module_logger(__name__)

def solve_small_molecule(info, options={}):
    os.chdir(options.get('directory', '.'))
    _logger.info("Attempting to solve small-molecule structure ...")
    if not misc.file_requirements('%s-shelx.hkl' % info['name']):
        print "File not found %s-shelx.hkl" % info['name']
        return {'step': 'symmetry', 'success': False, 'reason': 'Required reflection files missing'}
    
    try:
        programs.shelx_sm(info['name'], info['unit_cell'], info['formula'])
    except (dpm.errors.ProcessError, dpm.errors.ParserError, IOError), e:
        return {'step': 'symmetry', 'success': False, 'reason': str(e)}
    
    
    _logger.info('Succeeded! Coordinates: %s.res, Phases: %s.fcf' % (
                                        os.path.join('shelx-sm', info['name']),
                                        os.path.join('shelx-sm', info['name']),
                                        ))


    return {'step':'smx_structure', 'success':True, 'data': None}   
