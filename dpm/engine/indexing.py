import os
import numpy
from dpm.utils.misc import Table
from dpm.parser import xds
from dpm.utils import log, misc, programs, io
import dpm.errors

_logger = log.get_module_logger(__name__)

PROBLEMS = misc.Choices(
    (1, 'index_origin', 'Detector origin not optimal.'),
    (2, 'multiple_subtrees', 'Indexed reflections belong to multiple subtrees.'),
    (4, 'poor_solution', 'Poor solution, indexing refinement problems.'),
    (8, 'non_integral', 'Indices deviate significantly from integers.'),
    (16, 'unindexed_spots', 'Too many un-indexed spots.'),
    (32, 'spot_accuracy', 'Spots deviate significantly from expected positions.'),
    (64, 'dimension_2d', 'Clusters are not 3-Dimensional.'),
    (128, 'few_spots', 'Insufficient spots available.'),
    (256, 'failed', 'Indexing failed for unknown reason.')
)

CODES = {
    xds.SPOT_LIST_NOT_3D: PROBLEMS.dimension_2d,
    xds.INSUFFICIENT_INDEXED_SPOTS: PROBLEMS.unindexed_spots,
    xds.INSUFFICIENT_SPOTS: PROBLEMS.few_spots,
    xds.POOR_SOLUTION: PROBLEMS.spot_accuracy,
    xds.REFINE_ERROR: PROBLEMS.poor_solution,
    xds.INDEX_ERROR: PROBLEMS.failed,
    256: PROBLEMS.failed
}

def diagnose_index(info):

    failure_code = info.get('failure_code', 256)
    problems = [CODES.get(failure_code, 0)]
    options = {}

    _refl = info.get('reflections')
    subtrees = info.get('subtrees')
    _local_spots = info.get('local_indexed_spots')

    # not enough spots
    if info.get('spots') and 'selected_spots' in info.get('spots', {}):
        if info['spots'].get('selected_spots', 0) < 300:
            problems.append(PROBLEMS.few_spots)

    # get number of subtrees
    distinct = 0
    satelites = 0
    for subtree in subtrees:
        pct = subtree['population']/float(_local_spots)
        if pct > 0.3:
            distinct += 1
        elif pct > 1:
            satelites += 1
        else:
            break

    if distinct > 1:
        problems.append(PROBLEMS.multiple_subtrees)
    elif distinct == 0:
        problems.append(PROBLEMS.poor_solution)


    # get max, std deviation of integral indices
    _indices = info.get('cluster_indices')
    if _indices is not None and len(_indices) > 0:
        t = Table(_indices)
        _index_array = numpy.array(t['hkl'])
        _index_err = abs(_index_array - _index_array.round())
        avg_error = _index_err.mean()
        if avg_error > 0.05:
            problems.append(PROBLEMS.non_integral)

    # get spot deviation
    if info.get('summary') is not None:
        if info['summary'].get('stdev_spot') > 3:
            problems.append(PROBLEMS.spot_accuracy)

    # get rejects
    if info.get('cluster_dimension', 0) < 3:
        problems.append(PROBLEMS.dimension_2d)

    # get quality of selected index origin
    _origins = info.get('index_origins')
    selected_quality = 0
    selected_deviation = 0
    best_quality = 999.
    best_deviation = 999.
    origin_deviation = _origins[0].get('position')

    for i, _org in enumerate(_origins):
        deviation = sum(_org.get('deviation',0))
        quality = _org.get('quality', 0)
        if deviation < best_deviation:
            selected_deviation = i
            best_deviation = deviation
            origin_deviation = _org.get('position')
        if quality < best_quality:
            selected_quality = i
            best_quality = i

    if best_quality != 0 or best_deviation != 0 or selected_quality != selected_deviation:
        problems.append(PROBLEMS.index_origin)
        options['beam_center'] = origin_deviation

    return {
        'problems': set(problems),
        'options': options
    }


def _diagnose_index(info):
    # quality_code is integer factors
    qcodes = {
        256 : "serious indexing failure",
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
    _st = info.get('subtrees')
    _local_spots = info.get('local_indexed_spots')
    
    # not enough spots
    if _refl:
        if _refl.get('selected_spots', 0) < 300:
            data['quality_code'] |= 128
        else:
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
    run_info = {'mode': options.get('mode')}
    info = {}
    run_info.update(data_info)
    if not misc.file_requirements('XDS.INP','SPOT.XDS'):
        return {'step': 'indexing', 'success':False, 'reason': "Required files not found"}
    try:

        io.write_xds_input(jobs, run_info)
        programs.xds_par()
        info = xds.parse_idxref()
        diagnosis = diagnose_index(info)
        
        _retries = 0
        sigma = 6
        spot_size = 3
        _aliens_removed = False
        _weak_removed = False
        _spot_adjusted = False
        
        while info.get('failure_code') > 0 and _retries < 8:
            _all_images = (run_info['spot_range'][0] == run_info['data_range'])
            _retries += 1
            _logger.warning('Indexing failed:')
            for prob in diagnosis['problems']:
                _logger.warning('... {0}'.format(PROBLEMS[prob]))
            
            if options.get('backup', False):
                misc.backup_files('SPOT.XDS', 'IDXREF.LP')

            if diagnosis['problems'] & {PROBLEMS.index_origin}:
                _logger.info('-> Adjusting detector origin ...')
                run_info['beam_center'] = diagnosis['options'].get('beam_center', run_info['beam_center'])
                io.write_xds_input('IDXREF', run_info)
                programs.xds_par()
                info = xds.parse_idxref()
                diagnosis = diagnose_index(info)
            elif (diagnosis['problems'] & {PROBLEMS.few_spots, PROBLEMS.dimension_2d}) and not _all_images:
                _logger.info('-> Expanding spot range ...')
                run_info.update(spot_range=[run_info['data_range']])
                io.write_xds_input('IDXREF', run_info)
                programs.xds_par()
                info = xds.parse_idxref()
                diagnosis = diagnose_index(info)
            elif (diagnosis['problems'] & {PROBLEMS.poor_solution, PROBLEMS.spot_accuracy, PROBLEMS.non_integral}) and not _spot_adjusted:
                spot_size *= 1.5
                sigma = 6
                new_params = {'sigma': sigma, 'min_spot_size': spot_size, 'refine_index': "CELL BEAM ORIENTATION AXIS"}
                if not _all_images:
                    new_params['spot_range'] = [run_info['data_range']]
                run_info.update(new_params)
                _logger.info('-> Adjusting spot size and refinement parameters ...')
                io.write_xds_input('COLSPOT IDXREF', run_info)
                programs.xds_par()
                info = xds.parse_idxref()
                diagnosis = diagnose_index(info)
                _spot_adjusted = spot_size > 12
            elif (diagnosis['problems'] & {PROBLEMS.unindexed_spots, PROBLEMS.multiple_subtrees}) and not _weak_removed:
                sigma += 3
                _logger.info('.. Removing weak spots (Sigma < %2.0f)...' % sigma)
                _filter_spots(sigma=sigma)
                run_info.update(sigma=sigma)
                io.write_xds_input('IDXREF', run_info)
                programs.xds_par()
                info = xds.parse_idxref()
                diagnosis = diagnose_index(info)
                _weak_removed = sigma >= 12
            elif (diagnosis['problems'] & {PROBLEMS.unindexed_spots, PROBLEMS.multiple_subtrees}) and not _aliens_removed:
                _logger.info('-> Removing all alien spots ...')
                _filter_spots(unindexed=True)
                io.write_xds_input(jobs, run_info)
                programs.xds_par()
                info = xds.parse_idxref()
                diagnosis = diagnose_index(info)
                _aliens_removed = True
            else:
                _logger.critical('.. Unable to proceed.')
                _retries = 999
                
    except dpm.errors.ProcessError, e:
        return {'step': 'indexing', 'success':False, 'reason': str(e)}
        
    if info.get('failure_code') == 0:
        return {'step': 'indexing', 'success':True, 'data': info}
    else:
        return {'step': 'indexing','success':False, 'reason': info['failure']}
    
