import os

import numpy

import autoprocess.errors
from autoprocess.parsers import xds
from autoprocess.utils import log, misc, programs, xdsio
from autoprocess.utils.choices import Choices
from autoprocess.utils.misc import Table

_logger = log.get_module_logger(__name__)

PROBLEMS = Choices(
    (1, 'index_origin', 'Detector origin not optimal.'),
    (2, 'multiple_subtrees', 'Indexed reflections belong to multiple subtrees.'),
    (3, 'poor_solution', 'Poor solution, indexing refinement problems.'),
    (4, 'non_integral', 'Indices deviate significantly from integers.'),
    (5, 'unindexed_spots', 'Too many un-indexed spots.'),
    (6, 'spot_accuracy', 'Spots deviate significantly from expected positions.'),
    (7, 'dimension_2d', 'Clusters are not 3-Dimensional.'),
    (8, 'few_spots', 'Insufficient spots available.'),
    (9, 'failed', 'Indexing failed for unknown reason.')
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
    failure_prob = CODES.get(failure_code, 0)
    problems = [failure_prob] if failure_prob else []

    options = {}

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
        pct = subtree['population'] / float(_local_spots)
        if pct > 0.2:
            distinct += 1
        elif pct > .05:
            satelites += 1
        else:
            break

    if distinct > 1:
        problems.append(PROBLEMS.multiple_subtrees)
    elif satelites > 2:
        problems.append(PROBLEMS.poor_solution)
    else:
        problems.append(PROBLEMS.unindexed_spots)

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
        if 'stdev_spot' in info['summary']:
            if info['summary'].get('stdev_spot') > 3:
                problems.append(PROBLEMS.spot_accuracy)
        else:
            problems.append(PROBLEMS.poor_solution)
    else:
        problems.append(PROBLEMS.failed)

    # get rejects
    if info.get('cluster_dimension', 0) < 3:
        problems.append(PROBLEMS.dimension_2d)

    # get quality of selected index origin
    _origins = info.get('index_origins', [])
    selected_deviation = 0
    best_deviation = 999.

    for i, _org in enumerate(_origins):
        if i == 0:
            origin_deviation = _org.get('position')
        deviation = sum(_org.get('deviation', [0]))
        if deviation < best_deviation:
            selected_deviation = i
            best_deviation = deviation
            origin_deviation = _org.get('position')

    if selected_deviation != 0:
        problems.append(PROBLEMS.index_origin)
        options['beam_center'] = origin_deviation

    return {
        'problems': set(problems),
        'options': options
    }


def _filter_spots(sigma=0, unindexed=False, filename='SPOT.XDS'):
    new_list = numpy.loadtxt(filename)
    if new_list.shape[1] < 5:
        return
    fmt = [" %0.2f"] + ["%0.2f"] * 2 + ["%0.0f."]
    if new_list.shape[1] > 7:
        fmt += ["%d"] * 4
    else:
        fmt += ["%d"] * 3

    new_sel = (new_list[:, 3] > sigma)
    if unindexed:
        new_sel = new_sel & (new_list[:, -3] != 0) & (new_list[:, -3] != 0) & (new_list[:, -3] != 0)

    numpy.savetxt(filename, new_list[new_sel, :], fmt=fmt)


def harvest_index():
    info = xds.parse_idxref()
    if info.get('failure_code') == 0:
        return {'step': 'indexing', 'success': True, 'data': info}
    else:
        return {'step': 'indexing', 'success': False, 'reason': info['failure']}


def auto_index(data_info, options=None):
    options = options or {}
    os.chdir(data_info['working_directory'])
    step_descr = 'Determining lattice orientation and parameters'
    jobs = 'IDXREF'
    run_info = {'mode': options.get('mode')}
    run_info.update(data_info)
    if not misc.file_requirements('XDS.INP', 'SPOT.XDS'):
        return {'step': 'indexing', 'success': False, 'reason': "Required files not found"}
    try:

        xdsio.write_xds_input(jobs, run_info)
        programs.xds_par(step_descr)
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
                _logger.warning('... {}'.format(PROBLEMS[prob]))

            if options.get('backup', False):
                misc.backup_files('SPOT.XDS', 'IDXREF.LP')

            if diagnosis['problems'] & {PROBLEMS.index_origin}:
                if not _all_images:
                    step_descr = '-> Expanding Spot Range'
                    run_info['spot_range'] = [run_info['data_range']]
                else:
                    step_descr = '-> Adjusting detector origin'
                    run_info['beam_center'] = diagnosis['options'].get('beam_center', run_info['beam_center'])
                xdsio.write_xds_input('COLSPOT IDXREF', run_info)
                programs.xds_par(step_descr)
                info = xds.parse_idxref()
                diagnosis = diagnose_index(info)
            elif (diagnosis['problems'] & {PROBLEMS.few_spots, PROBLEMS.dimension_2d}) and not _all_images:
                run_info.update(spot_range=[run_info['data_range']])
                xdsio.write_xds_input('IDXREF', run_info)
                programs.xds_par('-> Expanding Spot Range')
                info = xds.parse_idxref()
                diagnosis = diagnose_index(info)
            elif (diagnosis['problems'] & {PROBLEMS.poor_solution, PROBLEMS.spot_accuracy,
                                           PROBLEMS.non_integral}) and not _spot_adjusted:
                spot_size *= 1.5
                sigma = 6
                new_params = {'sigma': sigma, 'min_spot_size': spot_size, 'refine_index': "CELL BEAM ORIENTATION AXIS"}
                if not _all_images:
                    new_params['spot_range'] = [run_info['data_range']]
                run_info.update(new_params)
                xdsio.write_xds_input('COLSPOT IDXREF', run_info)
                programs.xds_par('-> Adjusting spot size and refinement parameters')
                info = xds.parse_idxref()
                diagnosis = diagnose_index(info)
                _spot_adjusted = spot_size > 12
            elif (diagnosis['problems'] & {PROBLEMS.unindexed_spots}) and not _weak_removed:
                sigma += 3
                _filter_spots(sigma=sigma)
                run_info.update(sigma=sigma)
                xdsio.write_xds_input('IDXREF', run_info)
                programs.xds_par('-> Removing weak spots (Sigma < {:2.0f})'.format(sigma))
                info = xds.parse_idxref()
                diagnosis = diagnose_index(info)
                _weak_removed = sigma >= 12
            elif (diagnosis['problems'] & {PROBLEMS.unindexed_spots,
                                           PROBLEMS.multiple_subtrees}) and not _aliens_removed:
                _filter_spots(unindexed=True)
                xdsio.write_xds_input(jobs, run_info)
                programs.xds_par('-> Removing all alien spots')
                info = xds.parse_idxref()
                diagnosis = diagnose_index(info)
                _aliens_removed = True
            else:
                _logger.critical('.. Unable to proceed.')
                _retries = 999

    except autoprocess.errors.ProcessError as e:
        return {'step': 'indexing', 'success': False, 'reason': str(e)}

    if info.get('failure_code') == 0:
        return {'step': 'indexing', 'success': True, 'data': info}
    else:
        return {'step': 'indexing', 'success': False, 'reason': info['failure']}
