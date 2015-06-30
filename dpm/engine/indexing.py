import os
import numpy

from dpm.utils.misc import Table
from dpm.parser import xds
from dpm.utils import log, misc, programs, io
import dpm.errors

_logger = log.get_module_logger(__name__)


def _diagnose_index(info):
    # quality_code is integer factors
    qcodes = {
        256 : "irrecoverable failure",
        128: "not enough spots",
        64: "cluster dimension is not 3D ",
        32: "spot positions not predicted accurately",
        16: "insufficient percent of spots indexed",
        8: "indices deviate significantly from integers",
        4: "no distinct subtree",
        2: "more than one distinct subtree",
        1: "index origin not optimal",
    }

    data = {}
    data['quality_code'] = 0
    failure_code = info.get('failure_code', 256)
    if failure_code == xds.SPOT_LIST_NOT_3D:
        data['quality_code'] |=  64
    elif failure_code == xds.INSUFFICIENT_INDEXED_SPOTS:
        data['quality_code'] |=  16
    elif failure_code == xds.INSUFFICIENT_SPOTS:
        data['quality_code'] |=  128
    elif failure_code == xds.POOR_SOLUTION:
        data['quality_code'] |=  32
    elif failure_code in [xds.REFINE_ERROR,xds.INDEX_ERROR]:
        data['quality_code'] |=  256
       
    _refl = info.get('reflections')
    _spots = info.get('spots')
    _st = info.get('subtrees')
    _local_spots = info.get('local_indexed_spots')
    
    # not enough spots
    if _spots['selected_spots'] < 300:
        data['quality_code'] |= 128
            
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
    if info.get('summary')  is not None:
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
        _origins.sort(key=lambda k: k['delta_angle'])
        for _org in _origins:
            if _org['index_origin'] == _sel_org:
                data['index_origin_delta'] = _org.get('delta')
                data['index_origin_quality'] = _org.get('quality')
                data['new_origin'] = _org.get('position')  
                break
        if data['index_origin_delta'] > 6 or data['index_origin_quality'] > 10: 
            data['quality_code'] |= 1
    data['failure_code'] = failure_code
    data['messages'] = [v for k,v in qcodes.items() if (data['quality_code']|k == data['quality_code'])]
    
    return data


def _filter_spots(sigma=0, unindexed=False, filename='SPOT.XDS'):
    
    new_list = numpy.loadtxt(filename)
    if new_list.shape[1] < 5:
        return
    fmt = [" %0.2f"] + ["%0.2f"]*2 + ["%0.0f."]
    if new_list.shape[1] > 7:
        fmt += ["%d"]*4
    else:
        fmt += ["%d"]*3
        
    new_sel = (new_list[:,3] > sigma)
    if unindexed:
        new_sel = new_sel & (new_list[:,-3] != 0) & (new_list[:,-3] != 0) & (new_list[:,-3] != 0)

    numpy.savetxt(filename, new_list[new_sel,:], fmt=fmt)
    
def auto_index(data_info, options={}):
    os.chdir(data_info['working_directory'])
    _logger.info('Determining lattice orientation and parameters ...')
    jobs = 'IDXREF'
    run_info = {}
    info = {}
    run_info.update(data_info)
    if not misc.file_requirements('XDS.INP','SPOT.XDS'):
        return {'step': 'indexing', 'success':False, 'reason': "Required files not found"}
    try:
        io.write_xds_input(jobs, run_info)
        programs.xds_par()
        info = xds.parse_idxref()
        data = _diagnose_index(info)

        _retries = 0
        sigma = 6
        spot_size = 3
        _all_images = False
        _aliens_removed = False
        _weak_removed = False
        _refined_dist = False
        _weak_added = False 
        _spot_adjusted = False
        
        while info.get('failure_code') > 0 and _retries < 8:
            _logger.warning('Indexing failed:')
            for msg in data['messages']: _logger.warning('... {0}'.format(msg))
            #if run_info['spot_range'][0] == run_info['data_range']:
            _all_images = True
            _retries += 1
            
            if options.get('backup', False):
                misc.backup_files('SPOT.XDS', 'IDXREF.LP')
            
            if misc.code_matches_any(data['quality_code'], 2,4,8,32) and not _spot_adjusted:
                run_info.update(min_spot_size=3, spot_range=[run_info['data_range']])
                _logger.info('-> Adjusting spot size and range parameters ...')
                io.write_xds_input('COLSPOT IDXREF', run_info)
                programs.xds_par()
                info = xds.parse_idxref()
                data = _diagnose_index(info)
                _spot_adjusted = True
            elif misc.code_matches_all(data['quality_code'], 16) and not _weak_removed:
                sigma += 3
                _weak_removed = sigma >= 12
                _logger.info('.. Removing weak spots (Sigma < %2.0f)...' % sigma)
                _filter_spots(sigma=sigma)
                run_info.update(sigma=sigma)
                io.write_xds_input('IDXREF', run_info)
                programs.xds_par()
                info = xds.parse_idxref()
                data = _diagnose_index(info)
            elif misc.code_matches_all(data['quality_code'], 16) and not _aliens_removed:
                _logger.info('-> Removing alien spots ...')
                _filter_spots(unindexed=True)
                io.write_xds_input(jobs, run_info)
                programs.xds_par()
                info = xds.parse_idxref()
                data = _diagnose_index(info)
                _aliens_removed = True                    
            elif misc.code_matches_all(data['quality_code'], 19):
                run_info['beam_center'] = data['new_origin']
                _logger.info('-> Adjusting beam origin to (%0.0f %0.0f) ...'% run_info['beam_center'])
                io.write_xds_input(jobs, run_info)
                programs.xds_par()
                info = xds.parse_idxref()
                data = _diagnose_index(info)
            elif misc.code_matches_all(data['quality_code'], 8) :
                _logger.info('Adjusting spot parameters ...')
                spot_size *= 1.5
                sigma = 6
                new_params = {'sigma': sigma, 'min_spot_size':spot_size, 'refine_index': "ORIENTATION BEAM"}
                run_info.update(new_params)
                io.write_xds_input('COLSPOT IDXREF', run_info)
                programs.xds_par()
                info = xds.parse_idxref()
                data = _diagnose_index(info)                    
            else:
                _logger.critical('.. Unable to proceed.')
                _retries = 999
                
    except dpm.errors.ProcessError, e:
        return {'step': 'indexing', 'success':False, 'reason': str(e)}
        
    if info.get('failure_code') == 0:
        return {'step': 'indexing', 'success':True, 'data': info}
    else:
        return {'step': 'indexing','success':False, 'reason': info['failure']}
    