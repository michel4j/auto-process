import os

import autoprocess.errors
from autoprocess.parsers import pointless
from autoprocess.utils import log, misc, programs, xtal

_logger = log.get_module_logger(__name__)


def get_symmetry_params(spacegroup, dset):
    sg_info = {}

    sg_info['character'] = xtal.get_character(spacegroup)
    sg_info['sg_number'] = spacegroup

    for lat in dset.results['correction']['symmetry']['lattices']:
        _, lat_type = lat['id']
        if sg_info['character'] == lat_type:
            sg_info['reindex_matrix'] = lat['reindex_matrix']
            sg_info['unit_cell'] = xtal.tidy_cell(lat['unit_cell'], sg_info['character'])
            break

    if not dset.results['correction']['symmetry']['lattices']:
        _logger.warning('Space group `%s` has a poor fit to the lattice' % xtal.SG_SYMBOLS[spacegroup])
    return sg_info


def determine_sg(data_info, dset, options=None):
    options = options or {}
    os.chdir(data_info['working_directory'])
    _logger.info("Automaticaly Determining Symmetry ...")
    if not misc.file_requirements('INTEGRATE.HKL'):
        return {'step': 'symmetry', 'success': False, 'reason': 'Required files from integration missing'}

    try:
        programs.pointless(chiral=options.get('chiral', True))
        sg_info = pointless.parse_pointless()
    except (autoprocess.errors.ProcessError, autoprocess.errors.ParserError, IOError) as e:
        return {'step': 'symmetry', 'success': False, 'reason': str(e)}

    xds_params = get_symmetry_params(sg_info['sg_number'], dset)
    sg_info.update(xds_params)
    _logger.info('Selected {}: {} , #{:d} '.format(sg_info['type'],
                                                   xtal.SG_SYMBOLS[sg_info['sg_number']],
                                                   sg_info['sg_number'], ))

    return {'step': 'symmetry', 'success': True, 'data': sg_info}
