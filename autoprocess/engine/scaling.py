import copy
import os
import time
from itertools import chain

import cluster

import autoprocess.errors
from autoprocess.engine import symmetry
from autoprocess.parsers import xds, pointless, phenix
from autoprocess.utils import log, misc, programs, xdsio, xtal

logger = log.get_module_logger(__name__)


def check_chisq(result):
    # check correction factors
    if result.get('correction_factors') is not None:
        for f in result['correction_factors'].get('factors', []):
            if (f['chi_sq_fit'] - 1.0) > 0.25:
                return False
    return True


def scale_datasets(dsets, options=None, message="Scaling"):
    options = options or {}
    os.chdir(options.get('directory', '.'))

    # indicate overwritten parameters
    suffix = []
    suffix_txt = ""
    if options.get('resolution'):
        suffix.append(f"res={options['resolution']:0.2f}")
    if len(suffix) > 0:
        suffix_txt = f"with [{','.join(suffix)}]"
    sg_name = xtal.SG_SYMBOLS[list(dsets.values())[0].results['correction']['summary']['spacegroup']]

    # Check Requirements
    for dset in list(dsets.values()):
        if dset.results.get('correction') is None:
            return {'step': 'scaling', 'success': False, 'reason': 'Can only scale after successful integration'}

    mode = options.get('mode', 'simple')
    if mode == 'mad':
        step_descr = ("Scaling {:d} MAD datasets in space-group {} {}".format(len(dsets), sg_name, suffix_txt))
        sections = []
        for dset in list(dsets.values()):
            dres = dset.results
            resol = options.get('resolution', dres['correction']['summary']['resolution'][0])
            in_file = dres['correction']['output_file']
            out_file = os.path.join(os.path.dirname(in_file), "XSCALE.HKL")
            sections.append(
                {'anomalous': options.get('anomalous', False),
                 'strict_absorption': check_chisq(dres['correction']),
                 'output_file': out_file,
                 'crystal': 'cryst1',
                 'inputs': [{'input_file': in_file, 'resolution': resol}],
                 'shells': xtal.resolution_shells(resol),
                 })
            if options.get('backup', False):
                misc.backup_files(out_file, 'XSCALE.LP')
            dset.results['scaling'] = {'output_file': out_file}
    else:
        if options.get('mode') == 'merge':
            step_descr = ("Merging {:d} datasets in '{}' {}".format(len(dsets), sg_name, suffix_txt))
        else:
            step_descr = ("Scaling dataset in '{}' {}".format(sg_name, suffix_txt))
        inputs = []
        resols = []
        strict = False
        for dset in list(dsets.values()):
            dres = dset.results
            resol = options.get('resolution', dres['correction']['summary']['resolution'][0])
            resols.append(resol)
            in_file = dres['correction']['output_file']
            inputs.append({'input_file': in_file, 'resolution': resol})
            strict = check_chisq(dres['correction']),
        sections = [{
            'anomalous': options.get('anomalous', False),
            'strict_absorption': strict,
            'shells': xtal.resolution_shells(min(resols)),
            'output_file': "XSCALE.HKL",
            'inputs': inputs, }]
        if options.get('backup', False):
            misc.backup_files('XSCALE.HKL', 'XSCALE.LP')

    xscale_options = {
        'sections': sections
    }

    xdsio.write_xscale_input(xscale_options)
    try:
        programs.xscale_par(step_descr)
        raw_info = xds.parse_xscale('XSCALE.LP')
    except autoprocess.errors.ProcessError as e:
        for dset in list(dsets.values()):
            dset.log.append((time.time(), 'scaling', False, str(e)))
        return {'step': 'scaling', 'success': False, 'reason': str(e)}

    if len(raw_info) == 1:
        info = list(raw_info.values())[0]
        # Set resolution
        if options.get('resolution'):
            resol = (options.get('resolution'), 4)
        else:
            resol = xtal.select_resolution(info['statistics'])
        info['summary']['resolution'] = resol

        if options.get('mode') == 'merge':
            dset = copy.deepcopy(list(dsets.values())[0])
            dset.parameters['name'] = 'combined'
            dset.name = dset.parameters['name']
            dsets[dset.name] = dset
        else:
            dset = list(dsets.values())[0]

        dset.results['scaling'] = info
        dset.log.append((time.time(), 'scaling', True, None))
    else:
        for name, info in list(raw_info.items()):
            # Set resolution
            if options.get('resolution'):
                resol = (options.get('resolution'), 4)
            else:
                resol = xtal.select_resolution(info['statistics'])
            info['summary']['resolution'] = resol

            dsets[name].results['scaling'].update(info)
            dsets[name].log.append((time.time(), 'scaling', True, None))

    return {'step': 'scaling', 'success': True}


def prepare_reference(dsets, options=None):
    options = options or {}
    os.chdir(options.get('directory', '.'))

    # use most complete dataset if fewer than 4 are being scaled
    best = max([(dset.results['correction']['summary']['completeness'], dset.name) for dset in list(dsets.values())])
    reference_name = best[1]  # the most complete dataset of the lot
    minimum_correlation = 0.0
    if len(dsets) < 4 or best[0] >= 30.0:
        logger.info('Using the most complete dataset "{}" ({:0.1f}%) as reference.'.format(best[1], best[0]))
        reference_file = dsets[reference_name].results['correction']['output_file']
    else:
        dset_names = [dset.name for dset in list(dsets.values())]
        dset_options = []
        for name in dset_names:
            dset_options.append(
                {'name': name,
                 'input_file': dsets[name].results['correction']['output_file'],
                 'resolution': 0,
                 'reference': name == reference_name})

        xscale_options = {'sections': [{
            'anomalous': options.get('anomalous', False),
            'strict_absorption': False,
            'output_file': "REF1.HKL",
            'inputs': dset_options,
        }]}

        xdsio.write_xscale_input(xscale_options)
        programs.xscale_par()
        misc.backup_special_file('XSCALE.LP', 'first')
        out = xds.parse_correlations('XSCALE.LP.first')
        correlations = out['correlations']
        corr_table = misc.Table(correlations)
        minimum_correlation = min(corr_table['corr'])
        if minimum_correlation >= 0.95:
            logger.info(f'All datasets correlate to better than {min(corr_table["corr"]):0.3f}.')
            reference_file = 'REF1.HKL'
        else:
            logger.info(f'Some correlations are low {min(corr_table["corr"]):0.3f}. Reference dataset needed ...')
            # cluster datasets by correlation
            distance_dict = dict([(tuple(sorted((v['i'], v['j']))), (v['corr'], v['num'])) for v in correlations])

            def _get_dist(x, y):
                xn = x['name']
                yn = y['name']
                i = 1 + dset_names.index(xn)
                j = 1 + dset_names.index(yn)
                key = tuple(sorted((i, j)))
                c, d = distance_dict[key]
                return (1 - c)  # + 0.1/numpy.sqrt(d)

            cl = cluster.HierarchicalClustering(dset_options, _get_dist, linkage='complete')
            cl.cluster()
            best_subtree = max(cl.getlevel(0.05), key=len)

            # set new reference name if old one not present withint the best subtree
            if reference_name not in [v['name'] for v in best_subtree]:
                reference_name = best_subtree[0]['name']
                best_subtree[0]['reference'] = True

            if len(best_subtree) > 1:
                # Merge the datasets and return
                logger.info(f'Creating reference from {len(best_subtree):d} datasets ... ')
                xscale_options = {'sections': [{
                    'anomalous': options.get('anomalous', False),
                    'strict_absorption': False,
                    'output_file': "REF1.HKL",
                    'inputs': best_subtree,
                }]}

                xdsio.write_xscale_input(xscale_options)
                programs.xscale_par()
                opt_info = list(xds.parse_xscale('XSCALE.LP').values())[0]
                opt_info['output_file'] = 'REF1.HKL'
                misc.backup_special_file('XSCALE.LP', 'ref1')
                reference_file = 'REF1.HKL'
            else:
                _good_corrs = [(v['i'], v['j']) for v in correlations if v['corr'] > 0.95 and v['num'] >= 10]
                _good_corrs = list(chain.from_iterable(_good_corrs))
                _best_num = max(set(_good_corrs), key=_good_corrs.count)
                _best_name = dset_names[_best_num - 1]
                reference_file = dsets[_best_name].results['correction']['output_file']
                logger.info(f'Using single {reference_file} as reference ... ')

    # Verify Spacegroup of reference
    programs.pointless(filename=reference_file, chiral=options.get('chiral', True))
    sg_info = pointless.parse_pointless()

    info = symmetry.get_symmetry_params(sg_info['sg_number'], dsets[reference_name])
    sg_info.update(info)
    sg_info['reference_data'] = reference_file
    cell_str = "{:0.2f} {:0.2f} {:0.2f} {:0.1f} {:0.1f} {:0.1f}".format(*sg_info['unit_cell'])
    logger.info(log.log_value(
        f'Reference {sg_info["type"]}:',
        '{} (#{})'.format(xtal.SG_SYMBOLS[sg_info['sg_number']], sg_info['sg_number'])
    ))
    logger.info(log.log_value('Reference Unit Cell:', cell_str))

    # now rescale reference data and transform to above spacegroup
    xscale_options = {'sections': [{
        'anomalous': False,
        'unit_cell': sg_info['unit_cell'],
        'space_group': sg_info['sg_number'],
        'reindex_matrix': sg_info['reindex_matrix'],
        'strict_absorption': False,
        'output_file': "REFERENCE.HKL",
        'inputs': [{'input_file': reference_file}],
    }]}

    xdsio.write_xscale_input(xscale_options)
    programs.xscale_par()
    opt_info = list(xds.parse_xscale('XSCALE.LP').values())[0]
    opt_info['output_file'] = 'REFERENCE.HKL'
    misc.backup_special_file('XSCALE.LP', 'reference')
    sg_info['reference_data'] = 'REFERENCE.HKL'
    sg_info['minimum_correlation'] = minimum_correlation

    return sg_info


def data_quality(dset, options=None):
    filename = dset.results['scaling']['output_file']
    options = options or {}
    os.chdir(options.get('directory', '.'))

    law_type = {'PM': 'Pseudo-merohedral', 'M': 'Merohedral'}
    # Check Requirements
    if not misc.file_requirements(filename):
        return {'step': 'data_quality', 'success': False, 'reason': 'Required files missing'}

    try:
        programs.xtriage(filename, label=f'Checking quality of dataset "{dset.name}"')
        info = phenix.parse_xtriage()
    except autoprocess.errors.ProcessError as e:
        return {'step': 'data_quality', 'success': False, 'reason': str(e)}

    statistics_deviate = False
    if info.get('twinning_l_zscore', 0) > 3.5:
        statistics_deviate = True
        logger.warning('Intensity statistics deviate significantly from expected.')

    if len(info.get('twin_laws',[])) > 0:
        if statistics_deviate:
            logger.warning('Possible twin laws which may explain the deviation:')
        else:
            logger.info('Possible twin laws:')
        max_fraction = 0.0
        for law in info['twin_laws']:
            fraction = 100.0 * max([law['britton_alpha'], law['ML_alpha'], law['H_alpha']])
            txt = ".. {} operator: [{}], Max twin-fraction: {:0.1f}%".format(
                law_type[law['type'].strip()],
                law['operator'].strip(),
                fraction,
            )
            max_fraction = max(max_fraction, fraction)
            if statistics_deviate:
                logger.warning(txt)
            else:
                logger.info(txt)
        if not statistics_deviate and max_fraction > 10.0:
            logger.warning('Despite reasonable intensity statistics, high twin-fraction suggests wrong symmetry.')
    if statistics_deviate and len(info.get('twin_laws', [])) == 0:
        logger.warning('No pseudo/merohedral twin laws possible in this lattice.')

    return {'step': 'data_quality', 'success': True, 'data': info}
