import os

import autoprocess.errors
from autoprocess.utils import log, programs, misc

_logger = log.get_module_logger(__name__)


def solve_small_molecule(info, options=None):
    options = options or {}
    os.chdir(options.get('directory', '.'))
    _logger.info("Solving small-molecule structure ...")
    if not misc.file_requirements('%s-shelx.hkl' % info['name']):
        print(("File not found %s-shelx.hkl" % info['name']))
        return {'step': 'symmetry', 'success': False, 'reason': 'Required reflection files missing'}

    try:
        programs.shelx_sm(info['name'], info['unit_cell'], info['formula'])
    except (autoprocess.errors.ProcessError, autoprocess.errors.ParserError, IOError) as e:
        return {'step': 'symmetry', 'success': False, 'reason': str(e)}

    _smx_dir = os.path.relpath(
        os.path.join(options.get('directory', '.'), 'shelx-sm', info['name']),
        options.get('command_dir'))
    _logger.info('Coordinates: %s.res, Phases: %s.fcf' % (_smx_dir, _smx_dir))

    return {'step': 'smx_structure', 'success': True, 'data': None}
