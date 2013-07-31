
from dpm.utils import log, programs, misc
import dpm.errors
import os
_logger = log.get_module_logger(__name__)

def solve_small_molecule(info, options={}):
    os.chdir(options.get('directory', '.'))
    _logger.info("Solving small-molecule structure ...")
    if not misc.file_requirements('%s-shelx.hkl' % info['name']):
        print "File not found %s-shelx.hkl" % info['name']
        return {'step': 'symmetry', 'success': False, 'reason': 'Required reflection files missing'}
    
    try:
        programs.shelx_sm(info['name'], info['unit_cell'], info['formula'])
    except (dpm.errors.ProcessError, dpm.errors.ParserError, IOError), e:
        return {'step': 'symmetry', 'success': False, 'reason': str(e)}
    
    _smx_dir = misc.relpath(
                    os.path.join(options.get('directory', '.'), 'shelx-sm', info['name']), 
                    options.get('command_dir'))
    _logger.info('Coordinates: %s.res, Phases: %s.fcf' % (_smx_dir, _smx_dir))


    return {'step':'smx_structure', 'success':True, 'data': None}   
