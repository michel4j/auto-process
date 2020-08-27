import inspect
import os
import shutil

import numpy
from prettytable import PrettyTable

from autoprocess.utils import gnuplot
from autoprocess.utils import xtal, misc, log
from autoprocess.utils.misc import json

_logger = log.get_module_logger(__name__)

SHARE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'share')


def save_report(datasets, options):
    directory = options['directory']
    report = {
        'id': None,
        'directory': directory,
        'filename': 'report.json',
        'score': None,
        'data_id': None,
        'details': {},
    }

    report_file = os.path.join(directory, report['filename'])
    text_file = os.path.join(directory, 'report.txt')

    # read previous json_file and obtain id from it if one exists:
    if os.path.exists(report_file):
        old_report = misc.load_json(report_file)
        report['id'] = old_report.get('id')

    if options.get('mode') == 'screen':
        results = datasets[0]['results']
        report['kind'] = 'MX Screening'
        report['title'] = '{}Screening of "{}"'.format(
            options.get('anomalous') and 'Anomalous ' or '', datasets[0]['parameters']['name']
        )
        report['details'] = screening_report(datasets[0], options)
        report['score'] = results['crystal_score']
        report['strategy'] = get_strategy(results)
    elif options.get('mode') == 'mad':
        report['kind'] = 'MX MAD Analysis'
        results = datasets[0]['results']
        names = []
        for dataset in datasets:
            names.append(dataset['parameters']['name'])
        report['details'] = mad_report(datasets, options)
        report['title'] = 'MAD Data Processing of "{}"'.format(", ".join(names))
        report['score'] = results['crystal_score']
    elif options.get('mode') == 'merge':
        results = datasets[0]['results']
        names = []
        for dataset in datasets:
            if dataset['parameters']['name'] == 'combined':
                results = dataset['results']
            else:
                names.append(dataset['parameters']['name'])
        report['title'] = '{}Merging of "{}"'.format(options.get('anomalous') and 'Anomalous ' or '', ', '.join(names))
        report['kind'] = 'MX Merging'
        report['details'] = merge_report(datasets, options)
        report['score'] = results['crystal_score']
    else:
        results = datasets[0]['results']
        name = datasets[0]['parameters']['name']
        report['title'] = '{}Analysis of "{}"'.format(options.get('anomalous') and 'Anomalous ' or '', name)
        report['kind'] = 'MX Native Analysis' if not options.get('anomalous') else 'MX Anomalous Analysis'
        report['details'] = single_report(datasets[0], options)
        report['score'] = results['crystal_score']

    # save
    with open(report_file, 'w') as handle:
        json.dump(report, handle)

    with open(text_file, 'w') as handle:
        handle.write(text_report(report['details']))

    shutil.copy(os.path.join(SHARE_DIR, 'report.html'), directory)
    shutil.copy(os.path.join(SHARE_DIR, 'report.min.js'), directory)
    shutil.copy(os.path.join(SHARE_DIR, 'report.min.css'), directory)


def get_strategy(results):
    strategy = results['strategy']
    run = strategy['runs'][0]
    info = {
        'attenuation': strategy['attenuation'],
        'start_angle': run['phi_start'],
        'total_angle': run['phi_width'] * run['number_of_images'],
        'resolution': strategy['resolution'],
        'max_delta': run['phi_width'],
        'overlaps': run['overlaps'],
        'exposure_rate': -1,
    }
    if run.get('exposure_time', 0) > 0:
        info['exposure_rate'] = float(round(run['phi_width'], 1)) / round(run['exposure_time'], 1)
    return info


def resolution_method(key):
    return {
        0: 'based on detector edge',
        1: 'based on I/sigma(I) > 0.5',
        2: 'based on CC½ significant at 0.1% level',
        3: 'by DISTL (see Zang et al, J. Appl. Cryst. (2006). 39, 112-119',
        4: 'manual',
    }.get(key, 'N/A')


def summary_table(datasets, options):
    """
    Generate the summary table for the provided list of datasets
    :param datasets: list of dataset dictionaries
    :param options: dictionary of options
    :return: dictionary of table specification
    """

    report = {
        'title': 'Data Quality Statistics',
        'kind': 'table',
        'data': [
            [''],
            ['Score¹'],
            ['Wavelength (A)'],
            ['Space Group²'],
            ['Unit Cell (A)'],
            ['Resolution⁵'],
            ['All Reflections'],
            ['Unique Reflections'],
            ['Multiplicity'],
            ['Completeness'],
            ['Mosaicity'],
            ['I/Sigma(I)'],
            ['R-meas'],
            ['CC½³'],
            ['ISa⁴'],
        ],
        'header': 'column',
        'notes': ("""
            1. Data Quality Score for comparing similar data sets. Typically, values >
               0.8 are excellent, > 0.6 are good, > 0.5 are acceptable, > 0.4
               marginal, and &lt; 0.4 are Barely usable
            2. This space group was automatically assigned using POINTLESS (see P.R.Evans,
               Acta Cryst. D62, 72-82, 2005). This procedure is unreliable for incomplete datasets
               such as those used for screening. Please Inspect the detailed results below.
            3. Percentage correlation between intensities from random half-datasets. 
               (see Karplus & Diederichs (2012), Science. 336 (6084): 1030-1033)
            4. The highest I/Sigma(I) that the experimental setup can produce (Diederichs (2010) 
               Acta Cryst D66, 733-740).
        """)
    }
    res_method = -1
    for dataset in reversed(datasets):
        results = dataset['results']
        params = dataset['parameters']
        analysis = results['correction'] if not 'scaling' in results else results['scaling']
        multiplicity = float(analysis['summary']['observed']) / analysis['summary']['unique']
        res_method = analysis['summary']['resolution'][1]

        report['data'][0].append(params['name'])
        report['data'][1].append('{:0.2f}'.format(results['crystal_score']))
        report['data'][2].append('{:0.5g}'.format(params['wavelength']))
        report['data'][3].append(xtal.SG_NAMES[results['correction']['symmetry']['space_group']['sg_number']])
        report['data'][4].append(
            "{:0.2f} {:0.2f} {:0.2f} {:0.1f} {:0.1f} {:0.1f}".format(*results['correction']['summary']['unit_cell'])
        )
        report['data'][5].append('{:0.2f}'.format(analysis['summary']['resolution'][0]))
        report['data'][6].append(analysis['summary']['observed'])
        report['data'][7].append(analysis['summary']['unique'])
        report['data'][8].append('{:0.1f}'.format(multiplicity))
        report['data'][9].append('{:0.1f} %'.format(analysis['summary']['completeness']))
        report['data'][10].append(
            'N/A' if dataset['parameters']['name'] == 'combined' else '{:0.2f}'.format(
                results['correction']['summary']['mosaicity']
            )
        )
        report['data'][11].append('{:0.1f}'.format(analysis['summary']['i_sigma']))
        report['data'][12].append('{:0.1f}'.format(analysis['summary']['r_meas']))
        report['data'][13].append('{:0.1f} %'.format(analysis['summary']['cc_half']))
        report['data'][14].append(
            'N/A' if dataset['parameters']['name'] == 'combined' else '{:0.1f}'.format(
                results['integration']['statistics']['summary']['ISa']
            )
        )

    report['notes'] += """    5. Resolution selection: {}""".format(resolution_method(res_method))
    report['notes'] = inspect.cleandoc(report['notes'])

    return report


def screening_summary_table(dataset, options):
    """
    Generate the summary table for the provided list of datasets
    :param datasets: list of dataset dictionaries
    :param options: dictionary of options
    :return: dictionary of table specification
    """
    results = dataset['results']
    params = dataset['parameters']
    analysis = results['correction'] if not 'scaling' in results else results['scaling']

    return {
        'title': 'Data Quality Statistics',
        'kind': 'table',
        'data': [
            ['Observed Parameters', ''],
            ['Score¹', '{:0.2f}'.format(results['crystal_score'])],
            ['Wavelength (A)', '{:0.5g}'.format(params['wavelength'])],
            ['Space Group²', xtal.SG_NAMES[results['correction']['symmetry']['space_group']['sg_number']]],
            [
                'Unit Cell (A)',
                "{:0.2f} {:0.2f} {:0.2f} {:0.4g} {:0.4g} {:0.4g}".format(*results['correction']['summary']['unit_cell'])
            ],
            ['Mosaicity', '{:0.2f}'.format(results['correction']['summary']['mosaicity'])],
            ['ISa', results['correction']['correction_factors']['parameters'].get('ISa', -1)],
            ['Expected Quality³', ''],
            ['Resolution (Å)⁴', '{:0.1f} '.format(results['strategy']['resolution'])],
            ['Multiplicity', '{:0.1f}'.format(results['strategy']['redundancy'])],
            ['Completeness', '{:0.1f} %'.format(results['strategy']['completeness'])],
            [
                'I/Sigma(I)',
                '{:0.1f} ({:0.1f})'.format(
                    results['strategy']['i_sigma'],
                    results['strategy']['prediction_hi']['average_i_over_sigma']
                )
            ],
            [
                'R-factor',
                '{:0.1f} ({:0.1f})'.format(
                    results['strategy']['prediction_all']['R_factor'],
                    results['strategy']['prediction_hi']['R_factor']
                )
            ],
        ],
        'header': 'column',
        'notes': inspect.cleandoc("""
            1. Data Quality Score for comparing similar data sets. Typically, values >
               0.8 are excellent, > 0.6 are good, > 0.5 are acceptable, > 0.4
               marginal, and &lt; 0.4 are Barely usable
            2. This space group was automatically assigned using POINTLESS (see P.R.Evans,
               Acta Cryst. D62, 72-82, 2005). This procedure is unreliable for incomplete datasets
               such as those used for screening. Please Inspect the detailed results below.
            3. Data collection strategy and predicted quality was calculated using BEST. See
               A.N. Popov and G.P. Bourenkov Acta Cryst. (2003). D59, 1145-1153, G.P. Bourenkov 
                 and A.N. Popov Acta Cryst. (2006). D62, 58-64.
            4. {} """.format(results['strategy']['resolution_reasoning'])
                                  )
    }


def lattice_table(dataset, options):
    results = dataset['results']
    return {
        'title': "Lattice Character",
        'kind': 'table',
        'data': [
                    ['No.', 'Lattice type', 'Cell Parameters', 'Quality', 'Cell Volume']
                ] + [
                    [
                        lattice['id'][0], lattice['id'][1],
                        '{:0.1f} {:0.1f} {:0.1f} {:0.1f} {:0.1f} {:0.1f}'.format(*lattice['unit_cell']),
                        '{:0.1f}'.format(lattice['quality']),
                        '{:0.1f}'.format(xtal.cell_volume(lattice['unit_cell']))
                    ] for lattice in
                    sorted(results['correction']['symmetry']['lattices'], key=lambda d: d['id'][0])
                ],
        'header': 'row',
        'notes': (
            "The Lattice Character is defined by the metrical parameters of its reduced cell as described "
            "in the International Tables for Crystallography Volume A, p. 746 (Kluwer Academic Publishers, "
            "Dordrecht/Boston/London, 1989). Note that more than one lattice character may have the "
            "same Bravais Lattice."
        ),
    }


def spacegroup_table(dataset, options):
    results = dataset['results']
    return {
        'title': "Likely Space-Groups and their Probabilities",
        'kind': 'table',
        'data': [
                    ['Selected', 'Candidates', 'Space Group Number', 'Probability']
                ] + [
                    [
                        '*' if sol['number'] == results['correction']['symmetry']['space_group'][
                            'sg_number'] else '',
                        xtal.SG_NAMES[sol['number']], sol['number'], sol['probability']
                    ] for sol in results['symmetry']['candidates']
                ],
        'header': 'row',
        'notes': (
            "The above table contains results from POINTLESS (see Evans, Acta Cryst. D62, 72-82, 2005). "
            "Indistinguishable space groups will have similar probabilities. If two or more of the top candidates "
            "have the same probability, the one with the fewest symmetry assumptions is chosen. "
            "This usually corresponds to the point group,  trying out higher symmetry space groups within the "
            "top tier does not require re-indexing the data as they are already in the same setting. "
            "For more detailed results, please inspect the output file 'pointless.log'."
        )
    }


def standard_error_report(dataset, options):
    results = dataset['results']
    return {
        'title': 'Standard Errors of Reflection Intensities by Resolution',
        'content': [
            {
                'kind': 'lineplot',
                'style': 'half-height',
                'data': {
                    'x': ['Resolution Shell'] + [
                        round(numpy.mean(row['resol_range']), 2) for row in
                        results['correction']['standard_errors'][:-1]
                    ],
                    'y1': [
                        ['Chi²'] + [row['chi_sq'] for row in results['correction']['standard_errors'][:-1]]
                    ],
                    'y2': [
                        ['I/Sigma'] + [row['i_sigma'] for row in results['correction']['standard_errors'][:-1]]
                    ],
                    'x-scale': 'inv-square'
                },

            },
            {
                'kind': 'lineplot',
                'style': 'half-height',
                'data':
                    {
                        'x': ['Resolution Shell'] + [
                            round(numpy.mean(row['resol_range']), 2) for row in
                            results['correction']['standard_errors'][:-1]
                        ],
                        'y1': [
                            ['R-observed'] + [row['r_obs'] for row in results['correction']['standard_errors'][:-1]],
                            ['R-expected'] + [row['r_exp'] for row in results['correction']['standard_errors'][:-1]],
                        ],
                        'y1-label': 'R-factors (%)',
                        'x-scale': 'inv-square'
                    }
            },
        ],
        'notes': inspect.cleandoc("""
            "* I/Sigma:  Mean intensity/Sigma of a reflection in shell"
            "* χ²: Goodness of fit between sample variances of symmetry-related intensities and their errors "
            "  (χ² = 1 for perfect agreement)."
            "* R-observed: Σ|I(h,i)-I(h)| / Σ[I(h,i)]"
            "* R-expected: Expected R-FACTOR derived from Sigma(I) """
                                  )
    }


def shell_statistics_report(dataset, options, ):
    results = dataset['results']
    analysis = results['correction'] if not 'scaling' in results else results['scaling']
    return {
        'title': 'Statistics of Final Reflections by Shell',
        'content': [
            {
                'kind': 'lineplot',
                'data': {
                    'x': ['Resolution Shell'] + [float(row['shell']) for row in analysis['statistics'][:-1]],
                    'y1': [
                        ['Completeness (%)'] + [row['completeness'] for row in analysis['statistics'][:-1]],
                        ['CC½'] + [row['cc_half'] for row in analysis['statistics'][:-1]],
                    ],
                    'y2': [
                        ['R-meas'] + [row['r_meas'] for row in analysis['statistics'][:-1]],
                    ],
                    'y2-label': 'R-factors (%)',
                    'x-scale': 'inv-square'
                }
            },
            {
                'kind': 'lineplot',
                'data': {
                    'x': ['Resolution Shell'] + [float(row['shell']) for row in analysis['statistics'][:-1]],
                    'y1': [
                        ['I/Sigma(I)'] + [row['i_sigma'] for row in analysis['statistics'][:-1]],
                    ],
                    'y2': [
                        ['SigAno'] + [row['sig_ano'] for row in analysis['statistics'][:-1]],
                    ],
                    'x-scale': 'inv-square'
                }

            },
            {
                'kind': 'table',
                'data': [
                            ['Shell', 'Completeness', 'R_meas', 'CC½', 'I/Sigma(I)¹', 'SigAno²', 'CCₐₙₒ³']
                        ] + [
                            [
                                row['shell'],
                                '{:0.2f}'.format(row['completeness']),
                                '{:0.2f}'.format(row['r_meas']),
                                '{:0.2f}'.format(row['cc_half']),
                                '{:0.2f}'.format(row['i_sigma']),
                                '{:0.2f}'.format(row['sig_ano']),
                                '{:0.2f}'.format(row['cor_ano']),
                            ] for row in analysis['statistics']
                        ],
                'header': 'row',
                'notes': inspect.cleandoc("""
                    1. Mean of intensity/Sigma(I) of unique reflections (after merging symmetry-related 
                       observations). Where Sigma(I) is the standard deviation of reflection intensity I 
                       estimated from sample statistics.
                    2. Mean anomalous difference in units of its estimated standard deviation 
                       (|F(+)-F(-)|/Sigma). F(+), F(-) are structure factor estimates obtained from the merged 
                       intensity observations in each parity class.
                    3. Percentage of correlation between random half-sets of anomalous intensity differences. """
                                          )
            }
        ]
    }


def frame_statistics_report(dataset, options):
    results = dataset['results']
    return {
        'title': 'Statistics of Intensities by Frame Number',
        'content': [
            {
                'kind': 'scatterplot',
                'style': 'half-height',
                'data': {
                    'x': ['Frame Number'] + [row['frame'] for row in results['integration']['scale_factors']],
                    'y1': [
                        ['Scale Factor'] + [row['scale'] for row in results['integration']['scale_factors']],
                    ],
                    'y2': [
                        ['Mosaicity'] + [row['mosaicity'] for row in results['integration']['scale_factors']],
                        # ['Divergence'] + [row['divergence'] for row in results['integration']['scale_factors']],
                    ],
                }
            },
            {
                'kind': 'scatterplot',
                'style': 'half-height',
                'data': {
                    'x': ['Frame Number'] + [row['frame'] for row in results['correction']['frame_statistics']],
                    'y1': [
                        ['R-meas'] + [row['r_meas'] for row in results['correction']['frame_statistics']]
                    ],
                    'y2': [
                        ['I/Sigma(I)'] + [row['i_sigma'] for row in results['correction']['frame_statistics']],
                    ]
                }
            },
            {
                'kind': 'scatterplot',
                'style': 'half-height',
                'data': {
                    'x': ['Frame Number'] + [row['frame'] for row in results['integration']['scale_factors']],
                    'y1': [
                        ['Reflections'] + [row['ewald'] for row in results['integration']['scale_factors']]
                    ],
                    'y2': [
                        ['Unique'] + [row['unique'] for row in results['correction']['frame_statistics']]
                    ],
                }
            },
            {
                'kind': 'lineplot',
                'data': {
                    'x': ['Frame Number Difference'] + [row['frame_diff'] for row in
                                                        results['correction']['diff_statistics']],
                    'y1': [
                        ['All'] + [row['rd'] for row in results['correction']['diff_statistics']],
                        ['Friedel'] + [row['rd_friedel'] for row in results['correction']['diff_statistics']],
                        ['Non-Friedel'] + [row['rd_non_friedel'] for row in
                                           results['correction']['diff_statistics']],
                    ],
                    'y1-label': 'Rd'
                },
                'notes': inspect.cleandoc("""
                    *  The above plots use data generated by XDSSTAT. See Diederichs K. (2006) Acta Cryst D62, 96-101. 
                    *  Divergence: Estimated Standard Deviation of Beam divergence 
                    *  Rd: R-factors as a function of frame difference. An increase in R-d with frame difference is
                       suggestive of radiation damage."""
                                          )
            }
        ]
    }


def wilson_report(dataset, options):
    results = dataset['results']
    analysis = results['correction']
    if results.get('data_quality') and results['data_quality'].get('intensity_plots'):
        plot = {
            'kind': 'lineplot',
            'data': {
                'x': ['Resolution'] + [
                    (row['inv_res_sq']) ** -0.5 for row in results['data_quality']['intensity_plots']
                ],
                'y1': [
                    ['<I> Expected'] + [row['expected_i'] for row in results['data_quality']['intensity_plots']],
                ],
                'y2': [
                    ['<I> Observed'] + [row['mean_i'] for row in results['data_quality']['intensity_plots']],
                    ['<I> Binned'] + [row['mean_i_binned'] for row in results['data_quality']['intensity_plots']],
                ],

                'y1-label': '<I>',
                'x-scale': 'inv-square',
            }
        }
    else:
        plot = {
            'kind': 'lineplot',
            'data': {
                'x': ['Resolution'] + [
                    row['resolution'] for row in analysis['wilson_plot']
                ],
                'y1': [
                    ['<I> Observed'] + [row['mean_i'] for row in analysis['wilson_plot']],
                ],
                'x-scale': 'inv-square',
            },
            'notes': "Wilson fit: A={:0.3f}, B={:0.3f}, Correlation={:0.2f}".format(*analysis['wilson_line'])

        }
    return {
        'title': 'Wilson Statistics',
        'content': [
            plot
        ],
    }


def twinning_report(dataset, options):
    results = dataset['results']
    quality = results['data_quality']
    if quality.get('twinning_l_zscore'):
        l_test = {
            'title': 'L Test for twinning',
            'kind': 'lineplot',
            'data': {
                'x': ['|L|'] + [row['abs_l'] for row in quality['twinning_l_test']],
                'y1': [
                    ['Observed'] + [row['observed'] for row in quality['twinning_l_test']],
                    ['Twinned'] + [row['twinned'] for row in quality['twinning_l_test']],
                    ['Untwinned'] + [row['untwinned'] for row in quality['twinning_l_test']],
                ],
                'y1-label': 'P(L>=1)',
            },
            'notes': inspect.cleandoc("""
                *  <|L|>: {1:0.3f}  [untwinned: {2:0.3f}, perfect twin: {3:0.3f}]
                *  Multivariate Z-Score: {0:0.3f}.  The multivariate Z score is a quality measure of the 
                   given spread in intensities. Good to reasonable data are expected to have a Z score 
                   lower than 3.5.  Large values can indicate twinning, but small values 
                   do not necessarily exclude it""".format(quality['twinning_l_zscore'], *quality['twinning_l_statistic'])
                                      )
        }
    else:
        return {
            'title': 'Twinning Analysis',
            'description': 'Twinning analysis could not be performed.'
        }

    if results['data_quality'].get('twin_laws'):
        laws = results['data_quality']['twin_laws']
        twin_laws = {
            'title': 'Twin Laws',
            'kind': 'table',
            'header': 'row',
            'data': [
                        ['Operator', 'Type', 'R', 'Britton alpha', 'H alpha', 'ML alpha'],
                    ] + [
                        [law['operator'], law['type'], law['r_obs'], law['britton_alpha'], law['H_alpha'],
                         law['ML_alpha']]
                        for law in laws
                    ],
            'notes': (
                "Please note that the possibility of twin laws only means that the lattice symmetry "
                "permits twinning; it does not mean that the data are actually twinned.  "
                "You should only treat the data as twinned if the intensity statistics are abnormal."
            )
        }
    else:
        twin_laws = {
            'title': 'Twin Laws',
            'description': 'No twin laws are possible for this crystal lattice.'
        }

    return {
        'title': 'Twinning Analysis',
        'content': [
            l_test,
            twin_laws
        ]
    }


def strategy_table(dataset, options):
    strategy = get_strategy(dataset['results'])

    return {
        'title': 'Suggested Data Acquisition Strategy',
        'kind': 'table',
        'header': 'column',
        'data': [
            ['Resolution', '{:0.2f}'.format(strategy['resolution'])],
            ['Attenuation', '{:0.1f}'.format(strategy['attenuation'])],
            ['Start Angle', '{:0.0f}'.format(strategy['start_angle'])],
            ['Maximum Delta Angle¹', '{:0.2f}'.format(strategy['max_delta'])],
            ['Minimum Angle Range²', '{:0.1f}'.format(strategy['total_angle'])],
            ['Exposure Rate (deg/sec)³', '{:0.2f}'.format(strategy['exposure_rate'])],
            ['Overlaps?', strategy['overlaps']],
        ],
        'notes': inspect.cleandoc("""
            1. This is the maximum delta-angle to be collected in order to avoid overlaps. Note that
               it may be desirable to use a smaller delta angle than this value to obtain better quality data, if the
               beamline allows.
            2. Minimum angle range for complete data. This is the bare minimum and it is strongly recommended to 
               to collect a full 180 degrees of data and often even more.
            3. The exposure rate specifies the ratio between the delta angle and the exposure time and determines
               the total does of x-rays for the full dataset.  To obtain an exposure time corresponding to any delta 
               angle, divide the selected delta angle by this number. When adjusting the delta angle, the exposure time 
               should be adjusted accordingly to keep the total does the same.
             """
                                  )
    }


def kappa_analysis_table(dataset, options):
    strategy = dataset['results']['strategy']
    return {
        'title': 'Suggested Kappa and Phi angles for Re-orienting Sample',
        'kind': 'table',
        'header': 'row',
        'data': [
                    ['Kappa', 'Phi', 'Vectors (v1, v2)'],
                ] + [
                    ['{:0.1f}'.format(kappa), '{:0.1f}'.format(phi), vectors]
                    for kappa, phi, vectors in strategy['details']['crystal_alignment']['solutions']
                ],
        'notes': 'Alignment is performed such that {}. Calculations apply to the {} goniometer'.format(
            strategy['details']['crystal_alignment']['method'],
            strategy['details']['crystal_alignment']['goniometer'],
        )
    }


def predicted_quality_report(dataset, options):
    strategy = dataset['results']['strategy']
    statistics = strategy['details']['shell_statistics']
    resolution = list(map(numpy.mean, list(zip(statistics['max_resolution'], statistics['min_resolution']))))
    return {
        'title': 'Predicted Statistics for Suggested Strategy by Resolution',
        'content': [
            {
                'kind': 'lineplot',
                'data': {
                    'x': ['Resolution Shell'] + resolution,
                    'y1': [['Completeness (%)'] + statistics['completeness']],
                    'y2': [['R-factor'] + statistics['R_factor']],
                    'y2-label': 'R-factor (%)',
                    'x-scale': 'inv-square'
                }
            },
            {
                'kind': 'lineplot',
                'data': {
                    'x': ['Resolution Shell'] + resolution,
                    'y1': [['I/Sigma(I)'] + statistics['average_i_over_sigma']],
                    'y2': [['Multipliticy'] + statistics['redundancy']],
                    'x-scale': 'inv-square'
                }

            },
            {
                'kind': 'table',
                'data': [
                            ['Shell', 'Completeness', 'R-factor', 'I/Sigma(I)', 'Multipliticy', 'Overload Fraction']
                        ] + [
                            [
                                '{:0.2f}'.format(resolution[i]),
                                '{:0.2f}'.format(statistics['completeness'][i]),
                                '{:0.2f}'.format(statistics['R_factor'][i]),
                                '{:0.2f}'.format(statistics['average_i_over_sigma'][i]),
                                '{:0.2f}'.format(statistics['redundancy'][i]),
                                '{:0.2f}'.format(statistics['fract_overload'][i]),
                            ] for i in range(len(resolution))
                        ],
                'header': 'row',
                'notes': inspect.cleandoc("""
                    * The above plot was calculated by BEST. See A.N. Popov and G.P. Bourenkov Acta Cryst. (2003). D59, 1145-1153, G.P. Bourenkov and A.N. Popov Acta Cryst. (2006). D62, 58-64
                    * I/Sigma: Mean intensity/Sigma of a reflection in shell
                    * R-factor: Σ|I(h,i)-I(h)| / Σ[I(h,i)]"""
                                          )
            }
        ]
    }


def screening_analysis_report(dataset, options):
    strategy = dataset['results']['strategy']
    delta_resolutions = sorted(strategy['details']['delta_statistics'].keys())
    total_angles = sorted(strategy['details']['completeness_statistics'].keys())
    delta_resolutions.remove('angle')
    total_angles.remove('start_angle')
    return {
        'title': 'Detailed Screening Analysis',
        'content': [
            {
                'title': 'Maximum Delta Angle to avoid overlaps',
                'kind': 'lineplot',
                'data': {
                    'x': ['Angle (deg)'] + strategy['details']['delta_statistics']['angle'],
                    'y1': [
                        [resolution] + strategy['details']['delta_statistics'][resolution]
                        for resolution in delta_resolutions
                    ],
                    'y1-label': 'Maximum Delta (deg)'
                },
                'notes': "The above plot was calculated by BEST. See A.N. Popov and G.P. Bourenkov Acta Cryst. "
                         "(2003). D59, 1145-1153, G.P. Bourenkov and A.N. Popov Acta Cryst. (2006). D62, 58-64"
            },
            {
                'title': 'Minimal Range for Complete Data Acquisition',
                'kind': 'lineplot',
                'data': {
                    'x': ['Start Angle (deg)'] + strategy['details']['completeness_statistics']['start_angle'],
                    'y1': [
                        [total] + strategy['details']['completeness_statistics'][total]
                        for total in total_angles
                    ],
                    'y1-label': 'Completeness (%)'
                },
                'notes': "The above plot was calculated by BEST. See A.N. Popov and G.P. Bourenkov Acta Cryst. "
                         "(2003). D59, 1145-1153, G.P. Bourenkov and A.N. Popov Acta Cryst. (2006). D62, 58-64"
            },
        ]
    }


def alt_screening_analysis_report(dataset, options):
    strategy = dataset['results']['strategy']
    total_angles = list(strategy['details']['completeness_statistics'].keys())[:]
    total_angles.remove('start_angle')
    total_angles = sorted(total_angles, key=lambda x: float(x))
    return {
        'title': 'Detailed Screening Analysis',
        'content': [
            {
                'title': 'Minimal Range for Complete Data Acquisition',
                'kind': 'lineplot',
                'data': {
                    'x': ['Start Angle (deg)'] + strategy['details']['completeness_statistics']['start_angle'],
                    'y1': [
                        [total] + strategy['details']['completeness_statistics'][total]
                        for total in total_angles
                    ],
                    'y1-label': 'Completeness (%)'
                },
                'notes': "The above plot was calculated by BEST. See A.N. Popov and G.P. Bourenkov Acta Cryst. "
                         "(2003). D59, 1145-1153, G.P. Bourenkov and A.N. Popov Acta Cryst. (2006). D62, 58-64"
            },
        ]
    }


def single_report(dataset, options):
    if options.get('anomalous'):
        title = 'Anomalous Data Quality Summary'
    else:
        title = 'Data Quality Summary'
    return [
        {
            'title': title,
            'content': [
                summary_table([dataset], options),
                lattice_table(dataset, options),
                spacegroup_table(dataset, options)
            ],
        },
        standard_error_report(dataset, options),
        frame_statistics_report(dataset, options),
        shell_statistics_report(dataset, options),
        wilson_report(dataset, options),
        twinning_report(dataset, options),
    ]


def merge_report(datasets, options):
    if options.get('anomalous'):
        title = 'Anomalous Data Quality Summary'
    else:
        title = 'Data Quality Summary'
    report = [
        {
            'title': title,
            'content': [
                summary_table(datasets, options),
            ],
        }
    ]
    combined = None
    for dataset in datasets:
        if dataset['parameters']['name'] == 'combined':
            combined = dataset
            continue
        report.extend([
            {
                'title': 'Analysis Report: Dataset "{}"'.format(dataset['parameters']['name']),
                'content': [
                    lattice_table(dataset, options),
                    spacegroup_table(dataset, options),
                ]
            },
            standard_error_report(dataset, options),
            frame_statistics_report(dataset, options),
            shell_statistics_report(dataset, options),
        ])
    if combined:
        report.extend([
            {
                'title': 'Analysis Report: "Combined"',
                'content': [
                    lattice_table(combined, options),
                    spacegroup_table(combined, options),
                ]
            },
            shell_statistics_report(combined, options),
            wilson_report(combined, options),
            twinning_report(combined, options),
        ])
    return report


def mad_report(datasets, options):
    report = [
        {
            'title': 'MAD Data Quality Summary',
            'content': [
                summary_table(datasets, options),
            ],
        }
    ]
    for dataset in datasets:
        report.extend([
            {
                'title': 'Analysis Report: Dataset "{}"'.format(dataset['parameters']['name']),
                'content': [
                    lattice_table(dataset, options),
                    spacegroup_table(dataset, options),
                ]
            },
            standard_error_report(dataset, options),
            frame_statistics_report(dataset, options),
            shell_statistics_report(dataset, options),
            wilson_report(dataset, options),
            twinning_report(dataset, options),
        ])
    return report


def screening_report(dataset, options):
    report = [
        {
            'title': 'Data Quality Summary',
            'content': [
                screening_summary_table(dataset, options),
                strategy_table(dataset, options),
                # kappa_analysis_table(dataset, options),
                lattice_table(dataset, options),
                spacegroup_table(dataset, options),
            ]
        }
    ]

    if dataset['results']['strategy']['details'].get('shell_statistics'):
        report.extend([
            predicted_quality_report(dataset, options),
            screening_analysis_report(dataset, options)
        ])
    else:
        report.extend([
            standard_error_report(dataset, options),
            alt_screening_analysis_report(dataset, options)
        ])

    return report


def heading(text, level):
    if level in [1, 2]:
        underline = {1: '=', 2: '-'}[level]
        return '\n{}\n{}'.format(text.title(), underline * len(text))
    else:
        return '\n{} {}'.format('#' * level, text)


def text_report(report):
    output = []
    for i, section in enumerate(report):
        if i != 0:
            output.append('\n\n{}\n\n'.format('-' * 79))
        output.append(heading(section['title'], 1))
        if 'description' in section:
            output.append(section['description'])
        if 'content' in section:
            for content in section['content']:
                if 'title' in content:
                    output.append(heading(content['title'], 2))
                output.append(content.get('description', ''))
                if content.get('kind') == 'table':
                    table = PrettyTable()
                    if content.get('header') == 'row':
                        table.field_names = content['data'][0]
                        for row in content['data'][1:]:
                            table.add_row(row)
                        table.align = 'r'
                    else:
                        table.header = False
                        table.field_names = ['{}'.format(j) for j in range(len(content['data'][0]))]
                        for j, row in enumerate(content['data']):
                            table.add_row(row)
                            table.align['{}'.format(j)] = 'l' if j == 0 else 'r'

                    output.append(table.get_string())
                elif content.get('kind') in ['lineplot', 'scatterplot']:
                    plot_type = {'lineplot': 'linespoints', 'scatterplot': 'points'}[content['kind']]
                    plot_text = gnuplot.plot(content['data'], plot_type=plot_type, style=content.get('style', 'full-height'))
                    output.append(plot_text.decode('utf8'))
                if 'notes' in content:
                    output.append(heading('NOTES', 4))
                    output.append(content['notes'] + '\n')
        if 'notes' in section:
            output.append(heading('NOTES', 3))
            output.append(section['notes'] + '\n')

    return '\n'.join(output)
