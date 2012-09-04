import os
import numpy

from dpm.utils.misc import Table
from dpm.parser import xds
from dpm.utils import log, misc, programs, io
import dpm.errors

_logger = log.get_module_logger(__name__)


def _diagnose_index(info):
    # quality_code is integer factors
    # 256 = irrecoverable failure 
    # 128 = not enough spots 
    #  64 = cluster dimension < 3 
    #  32 = spot deviation > 3.0
    #  16 = percent indexed < 70
    #   8 = cluster index error > 0.05
    #   4 = no distinct subtree
    #   2 = more than one distinct subtree
    #   1 = index origin delta > 6
    data = {}
    data['quality_code'] = 0
    if info['failure_code'] == 1:
        data['quality_code'] |=  64
    elif info['failure_code'] == 2:
        data['quality_code'] |=  16
    elif info['failure_code'] == 3:
        data['quality_code'] |=  128
    elif info['failure_code'] == 4:
        data['quality_code'] |=  32
    elif info['failure_code'] in [5,6]:
        data['quality_code'] |=  256
        
    _refl = _spots = None
    _st = info.get('subtrees')
    _local_spots = info.get('local_indexed_spots')

    _reflx = info.get('reflections')
    if _reflx is not None:
        _spots = _reflx.get('selected_spots')
        _refl = _reflx.get('indexed_spots')
        data['indexed_spots'] = _refl
        data['percent_overlap'] = 100.0 * _reflx.get('rejects_overlap')/_refl
        data['percent_too_far'] = 100.0 * _reflx.get('rejects_far')/_refl

    # get percent of indexed reflections
    data['percent_indexed'] = 0.0
    data['primary_subtree'] = 0.0
    if _refl is not None and _st is not None and len(_st)>0:
        data['primary_subtree'] = 100.0 * _st[0].get('population')/float(_local_spots)
    
    if _spots is not None:
        data['percent_indexed'] = 100.0 * _spots/_refl
    if data['percent_indexed'] < 70 : data['quality_code'] |= 16
    
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
        for _org in _origins:
            if _org['index_origin'] == _sel_org:
                data['index_origin_delta'] = _org.get('delta')
                data['new_origin'] = _org.get('position')
                #data['index_deviation'] = _org.get('deviation')
                break    
    if data['index_origin_delta'] > 6 : data['quality_code'] |= 1
    data['failure_code'] = info['failure_code']
    
    return data

def _match_code(src, tgt):
    # bitwise compare two integers
    return src|tgt == src


def _filter_spots(sigma=0, unindexed=False, filename='SPOT.XDS'):
    new_list = numpy.loadtxt(filename)
    def _indexed(a):
        if len(a) < 5:
            return False
        elif sum([abs(v) for v in a[4:]])>0.01:
            return True
        else:
            return False
            
    if sigma > 0:
        new_list = [sp for sp in new_list if sp[3] > sigma ]
    if unindexed:
        new_list = [sp for sp in new_list if _indexed(sp)]
    f = open(filename, 'w')
    for spot in new_list:
        if len(spot)>4:
            txt = '%10.2f%10.2f%10.2f%9.0f.%8d%8d%8d\n' % tuple(spot)
        else:
            txt = '%10.2f%10.2f%10.2f%9.0f.\n' % tuple(spot)
        f.write(txt)
    f.close()
    

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
        sigma = 3
        spot_size = 6
        _all_images = False
        _aliens_tried = False
        _sigma_tried = False

        while info.get('failure_code') > 0 and _retries < 8:
            _logger.warning(info.get('failure'))
            #_logger.debug('Indexing Quality [%04d]' % (data['quality_code']))
            #_logger.debug(utils.print_table(data))
            if run_info['spot_range'][0] == run_info['data_range']:
                _all_images = True
            else:
                _all_images = False
            _retries += 1
            if options.get('backup', False):
                misc.backup_files('SPOT.XDS', 'IDXREF.LP')
    
            if info.get('failure_code') == xds.POOR_SOLUTION:
                if not _aliens_tried:
                    _logger.info('...Removing alien spots...')
                    _filter_spots(unindexed=True)
                    io.write_xds_input(jobs, run_info)
                    programs.xds_par()
                    info = xds.parse_idxref()
                    data = _diagnose_index(info)
                    _aliens_tried = True
                elif sigma < 48:
                    sigma *= 2
                    _logger.info('...Removing weak spots (Sigma < %2.0f)...' % sigma)
                    _filter_spots(sigma=sigma)
                    io.write_xds_input(jobs, run_info)
                    programs.xds_par()
                    info = xds.parse_idxref()
                    data = _diagnose_index(info)
                else:
                    _logger.critical('...Unable to proceed...')
                    _retries = 999
            elif info.get('failure_code') == xds.INSUFFICIENT_INDEXED_SPOTS:
                if data['distinct_subtrees'] == 1:
                    _logger.info('...Removing alien spots ...')
                    _filter_spots(unindexed=True)
                    io.write_xds_input(jobs, run_info)
                    programs.xds_par()
                    info = xds.parse_idxref()
                    data = _diagnose_index(info)
                elif sigma < 48 and data['index_origin_delta'] <= 6:
                    sigma *= 2
                    _logger.info('...Removing weak spots (Sigma < %2.0f)...' % sigma)
                    _filter_spots(sigma=sigma)
                    io.write_xds_input(jobs, run_info)
                    programs.xds_par()
                    info = xds.parse_idxref()
                    data = _diagnose_index(info)
                elif data['quality_code'] in [19]:
                    run_info['beam_center'] = data['new_origin']
                    _logger.info('...Adjusting beam origin to (%0.0f %0.0f)...'% run_info['beam_center'])
                    io.write_xds_input(jobs, run_info)
                    programs.xds_par()
                    info = xds.parse_idxref()
                    data = _diagnose_index(info)
                elif not _aliens_tried:
                    _filter_spots(unindexed=True)
                    io.write_xds_input(jobs, run_info)
                    programs.xds_par()
                    info = xds.parse_idxref()
                    data = _diagnose_index(info)
                    _aliens_tried = True                    
                else:
                    _logger.critical('...Unable to proceed...')
                    _retries = 999
            elif info.get('failure_code') == xds.INSUFFICIENT_SPOTS or info.get('failure_code') == xds.SPOT_LIST_NOT_3D:
                if not _all_images:
                    run_info['spot_range'] = [run_info['data_range']]
                    _logger.info('Increasing spot search range to [%d..%d] ...' % tuple(run_info['spot_range'][0]))
                    io.write_xds_input('COLSPOT IDXREF', run_info)
                    programs.xds_par()
                    info = xds.parse_idxref()
                    data = _diagnose_index(info)
                elif sigma > 3:
                    sigma /= 2
                    _logger.info('...Including weaker spots (Sigma > %2.0f)...' % sigma)
                    io.write_xds_input('COLSPOT IDXREF', run_info)
                    programs.xds_par()
                    info = xds.parse_idxref()
                    data = _diagnose_index(info)
                else:
                    _logger.critical('...Unable to proceed...')
                    _retries = 999   
            elif _match_code(data['quality_code'], 512) :
                _logger.info('Adjusting spot parameters ...')
                spot_size *= 1.5
                new_params = {'min_spot_size':spot_size}
                run_info.update(new_params)
                io.write_xds_input('COLSPOT IDXREF', run_info)
                programs.xds_par()
                info = xds.parse_idxref()
                data = _diagnose_index(info)                    
            else:
                _logger.critical('...Unable to proceed...')
                _retries = 999
    except dpm.errors.ProcessError, e:
        return {'step': 'indexing', 'success':False, 'reason': str(e)}
        
    if info.get('failure_code') == 0:
        return {'step': 'indexing', 'success':True, 'data': info}
    else:
        return {'step': 'indexing','success':False, 'reason': info['failure']}
    