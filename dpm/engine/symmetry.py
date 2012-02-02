import os

from dpm.parser import pointless
from dpm.utils import log, misc, programs, xtal
import dpm.errors

_logger = log.get_module_logger(__name__)


def determine_sg(data_info, dset, options={}):
    os.chdir(data_info['working_directory'])
    
    if data_info.get('sg_overwrite') is not None:
        _logger.info("Manually Setting SpaceGroup ...")
        sg_info = {}
        if dset.results.get('symmetry') is None:
            return {'step': 'symmetry', 'success': False, 'reason': 'Must run auto symmetry before manual symmetry'}
        else:
            sg_info.update(dset.results.get('symmetry'))
            sg_info['character'] = xtal.get_character(data_info['sg_overwrite'])
            sg_info['sg_number'] = data_info['sg_overwrite']
            sg_info['type'] = "SpaceGroup"      
    else:
        _logger.info("Automaticaly Determining Symmetry ...")
        if not misc.file_requirements('INTEGRATE.HKL'):
            return {'step': 'symmetry', 'success': False, 'reason': 'Required files from integration missing'}
        
        try:
            programs.pointless()
            sg_info = pointless.parse_pointless()
        except (dpm.errors.ProcessError, dpm.errors.ParserError, IOError), e:
            return {'step': 'symmetry', 'success': False, 'reason': str(e)}
    
    # Overwrite sg_info parameters with XDS friendly ones if present:
    # fetches xds reindex matrix and cell constants based on lattice,
    # character
    _lat_compatible = False
    for _lat in dset.results['correction']['symmetry']['lattices']:
        id, lat_type = _lat['id']
        if sg_info['character'] == lat_type:
            _lat_compatible = (_lat['star'] == '*')
            sg_info['reindex_matrix'] = _lat['reindex_matrix']
            sg_info['unit_cell'] = _lat['unit_cell']
            break
            
    dset.parameters.update({'unit_cell': xtal.tidy_cell(sg_info['unit_cell'], sg_info['character']),
                            'space_group': sg_info['sg_number']
                            })
    
    cell_str = "%0.1f %0.1f %0.1f %0.1f %0.1f %0.1f" % tuple(dset.parameters['unit_cell'])
    _logger.info('%s: %s (#%d) - %s' % (sg_info['type'], 
                                        xtal.SPACE_GROUP_NAMES[dset.parameters['space_group']], 
                                        dset.parameters['space_group'],
                                        cell_str))     
    if not _lat_compatible:
        _logger.warning('Selected SpaceGroup has a poor fit to the lattice')
        #return {'step': 'symmetry', 'success': False, 'reason': 'Selected SpaceGroup incompatible with lattice'}
        
    if data_info.get('reference_data') is None:
        dset.parameters.update({'reindex_matrix': sg_info['reindex_matrix']})        
    else:
        _ref_sgn = dset.parameters['reference_sginfo']['sg_number']
        _ref_type = dset.parameters['reference_sginfo']['type']
        if sg_info['sg_number'] != _ref_sgn:
            _logger.warning('Space group differs from reference data set!')                          
            _logger.info('Proceeding with %s: %s (#%d) instead.' % (_ref_type, 
                                                                    xtal.SPACE_GROUP_NAMES[_ref_sgn], _ref_sgn))
            _ref_sginfo = dset.parameters['reference_sginfo']
            dset.parameters.update({'unit_cell' : xtal.tidy_cell(_ref_sginfo['unit_cell'], _ref_sginfo['character']),
                                    'space_group': _ref_sgn,
                                    })

    return {'step':'symmetry', 'success':True, 'data': sg_info}   

